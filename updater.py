# MIT License

import os
import ssl
import bpy
import time
import json
import re
import fnmatch
import tomllib
import urllib.error
import urllib.request
import shutil
import pathlib
import zipfile
from threading import Thread
from queue import Empty, Queue
from collections import OrderedDict
from bpy.app.handlers import persistent
from .tools.translations import t
from .tools.common import wrap_dynamic_enum_items
from .extern_tools.mmd_tools_local.preferences import MMDToolsAddonPreferences
from . import CATS_VERSION, dev_branch

no_ver_check = False
fake_update = False

is_checking_for_update = False
checked_on_startup = False
version_list = None
current_version = []
current_version_str = ''
update_needed = False
latest_version = None
latest_version_str = ''
used_updater_panel = False
update_finished = False
remind_me_later = False
is_ignored_version = False

confirm_update_to = ''

show_error = ''

# The full package name includes Blender's ``bl_ext.<repo>`` prefix for
# extensions. AddonPreferences must use that exact identity.
package_name = __package__ or __name__.rpartition('.')[0]


def _user_storage_dir(path):
    try:
        return bpy.utils.extension_path_user(package_name, path=path, create=True)
    except (AttributeError, ValueError):
        return bpy.utils.user_resource(
            'CONFIG', path=os.path.join("cats_blender_plugin", path), create=True
        )


updater_state_dir = _user_storage_dir("updater")
downloads_dir = _user_storage_dir(os.path.join("updater", "downloads"))
ignore_ver_file = os.path.join(updater_state_dir, "ignore_version.txt")
no_auto_ver_check_file = os.path.join(updater_state_dir, "no_auto_ver_check.txt")

# Keep release endpoints in one place so a maintained fork only needs to change
# this repository slug. Do not fall back to the archived Disroot updater.
UPDATE_REPOSITORY = "teamneoneko/Cats-Blender-Plugin-Unofficial-"
UPDATE_API_URL = f"https://api.github.com/repos/{UPDATE_REPOSITORY}/releases"
UPDATE_DEV_BRANCH = "blender-5x-dev"
NETWORK_TIMEOUT_SECONDS = 30
_update_result_queue = Queue()
_update_check_generation = 0
EXTENSION_PACKAGE_ID = "cats_blender_plugin"


def _online_access_allowed():
    return bool(getattr(bpy.app, 'online_access', True))


def _version_tuple(version):
    return tuple(int(part) for part in re.findall(r'\d+', version or ''))


def _extension_repository_id():
    package_parts = package_name.split('.')
    if len(package_parts) >= 3 and package_parts[0] == 'bl_ext':
        return package_parts[1]
    return None


def _release_package_url(release):
    candidates = []
    for asset in release.get('assets') or []:
        if not isinstance(asset, dict):
            continue
        name = asset.get('name') or ''
        url = asset.get('browser_download_url') or ''
        if name.lower().endswith('.zip') and url.lower().startswith('https://'):
            candidates.append((name, url))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            'cats-blender-plugin' not in item[0].lower(),
            'cats' not in item[0].lower(),
            item[0].lower(),
        )
    )
    return candidates[0][1]


def _matches_build_exclusion(relative_path, patterns):
    path = pathlib.PurePosixPath(relative_path)
    path_text = path.as_posix()
    for pattern in patterns:
        normalized = str(pattern).replace('\\', '/').lstrip('/')
        if not normalized:
            continue
        if normalized.endswith('/'):
            directory = normalized.rstrip('/')
            if '/' in directory:
                if path_text == directory or path_text.startswith(directory + '/'):
                    return True
            elif directory in path.parts:
                return True
            continue
        if fnmatch.fnmatch(path_text, normalized) or fnmatch.fnmatch(path.name, normalized):
            return True
    return False


def _normalize_source_archive(source_path, destination_path):
    with zipfile.ZipFile(source_path, 'r') as source:
        manifest_entries = [
            info for info in source.infolist()
            if not info.is_dir() and pathlib.PurePosixPath(info.filename).name == 'blender_manifest.toml'
        ]
        if len(manifest_entries) != 1:
            raise ValueError('The development archive does not contain exactly one Blender manifest')

        manifest_entry = manifest_entries[0]
        manifest_path = pathlib.PurePosixPath(manifest_entry.filename)
        prefix = manifest_path.parts[:-1]
        if not prefix:
            shutil.copyfile(source_path, destination_path)
            return

        manifest = tomllib.loads(source.read(manifest_entry).decode('utf-8'))
        exclusions = manifest.get('build', {}).get('paths_exclude_pattern', [])

        with zipfile.ZipFile(destination_path, 'w', compression=zipfile.ZIP_DEFLATED) as destination:
            for info in source.infolist():
                source_name = pathlib.PurePosixPath(info.filename)
                if info.is_dir() or source_name.parts[:len(prefix)] != prefix:
                    continue
                relative_parts = source_name.parts[len(prefix):]
                if not relative_parts or '..' in relative_parts:
                    continue
                relative_name = pathlib.PurePosixPath(*relative_parts).as_posix()
                if _matches_build_exclusion(relative_name, exclusions):
                    continue
                with source.open(info, 'r') as source_file:
                    destination.writestr(relative_name, source_file.read())


def _validate_update_archive(archive_path):
    try:
        with zipfile.ZipFile(archive_path, 'r') as archive:
            for info in archive.infolist():
                path = pathlib.PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts:
                    return 'The update ZIP contains an unsafe path'

            manifest_entries = [
                info for info in archive.infolist()
                if not info.is_dir() and info.filename.replace('\\', '/') == 'blender_manifest.toml'
            ]
            if len(manifest_entries) != 1:
                return 'The update ZIP is not a built Blender extension package'

            manifest = tomllib.loads(archive.read(manifest_entries[0]).decode('utf-8'))
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, tomllib.TOMLDecodeError) as error:
        return 'The update ZIP could not be validated: ' + str(error)

    if manifest.get('id') != EXTENSION_PACKAGE_ID:
        return 'The update ZIP belongs to a different Blender extension'
    if not manifest.get('version'):
        return 'The update ZIP does not declare a version'
    minimum_version = _version_tuple(manifest.get('blender_version_min'))
    if minimum_version and minimum_version > tuple(bpy.app.version):
        return 'The update ZIP requires a newer Blender version'
    return ''

# Icons for UI
ICON_URL = 'URL'

class CheckForUpdateButton(bpy.types.Operator):
    bl_idname = 'cats_updater.check_for_update'
    bl_label = t('CheckForUpdateButton.label')
    bl_description = t('CheckForUpdateButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return not is_checking_for_update

    def execute(self, context):
        global used_updater_panel, show_error
        used_updater_panel = True
        if not _online_access_allowed():
            show_error = "Online access is disabled in Blender's preferences"
            self.report({'ERROR'}, show_error)
            ui_refresh()
            return {'CANCELLED'}
        check_for_update_background()
        return {'FINISHED'}


class UpdateToLatestButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_latest'
    bl_label = t('UpdateToLatestButton.label')
    bl_description = t('UpdateToLatestButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return update_needed

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = 'latest'
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class UpdateToSelectedButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_selected'
    bl_label = t('UpdateToSelectedButton.label')
    bl_description = t('UpdateToSelectedButton.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if is_checking_for_update or not version_list:
            return False
        return True

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = context.scene.cats_updater_version_list
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class UpdateToDevButton(bpy.types.Operator):
    bl_idname = 'cats_updater.update_dev'
    bl_label = t('UpdateToDevButton.label')
    bl_description = t('UpdateToDevButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global confirm_update_to, used_updater_panel
        confirm_update_to = 'dev'
        used_updater_panel = True

        bpy.ops.cats_updater.confirm_update_panel('INVOKE_DEFAULT')
        return {'FINISHED'}


class RemindMeLaterButton(bpy.types.Operator):
    bl_idname = 'cats_updater.remind_me_later'
    bl_label = t('RemindMeLaterButton.label')
    bl_description = t('RemindMeLaterButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global remind_me_later
        remind_me_later = True
        self.report({'INFO'}, t('RemindMeLaterButton.success'))
        return {'FINISHED'}


class IgnoreThisVersionButton(bpy.types.Operator):
    bl_idname = 'cats_updater.ignore_this_version'
    bl_label = t('IgnoreThisVersionButton.label')
    bl_description = t('IgnoreThisVersionButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        set_ignored_version()
        self.report({'INFO'}, t('IgnoreThisVersionButton.success', name=latest_version_str))
        return {'FINISHED'}


class ShowPatchnotesPanel(bpy.types.Operator):
    bl_idname = 'cats_updater.show_patchnotes'
    bl_label = t('ShowPatchnotesPanel.label')
    bl_description = t('ShowPatchnotesPanel.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if is_checking_for_update or not version_list:
            return False
        return True

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        global used_updater_panel
        used_updater_panel = True
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 8.2))

    def check(self, context):
        # Important for changing options
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = col.row(align=True)
        row.prop(context.scene, 'cats_updater_version_list')

        if context.scene.cats_updater_version_list:
            version = version_list.get(context.scene.cats_updater_version_list)

            col.separator()
            row = col.row(align=True)
            row.label(text=t('ShowPatchnotesPanel.releaseDate', date=version[2]))

            col.separator()
            for line in version[1].replace('**', '').split('\r\n'):
                row = col.row(align=True)
                row.scale_y = 0.75
                row.label(text=line)

        col.separator()


class ConfirmUpdatePanel(bpy.types.Operator):
    bl_idname = 'cats_updater.confirm_update_panel'
    bl_label = t('ConfirmUpdatePanel.label')
    bl_description = t('ConfirmUpdatePanel.desc')
    bl_options = {'INTERNAL'}

    show_patchnotes = False

    def execute(self, context):
        if not _online_access_allowed():
            self.report({'ERROR'}, "Online access is disabled in Blender's preferences")
            return {'CANCELLED'}

        print('UPDATE TO ' + confirm_update_to)
        if confirm_update_to == 'dev':
            update_now(dev=True)
        elif confirm_update_to == 'latest':
            update_now(latest=True)
        else:
            update_now(version=confirm_update_to)
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.1))

    def check(self, context):
        # Important for changing options
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        version_str = confirm_update_to
        if confirm_update_to == 'latest':
            version_str = latest_version_str
        elif confirm_update_to == 'dev':
            version_str = 'Dev'

        col.separator()
        row = col.row(align=True)
        row.label(text='Version: ' + version_str)

        if confirm_update_to == 'dev':
            col.separator()
            col.separator()
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev1'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev2'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev3'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev4'))
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('ConfirmUpdatePanel.warn.dev5'))

        else:
            row.operator(ShowPatchnotesPanel.bl_idname, text=t('ConfirmUpdatePanel.ShowPatchnotesPanel.label'))

        col.separator()
        col.separator()
        # col.separator()
        row = col.row(align=True)
        row.scale_y = 0.65
        # row.label(text='Update now to ' + version_str + ':', icon=ICON_URL)
        row.label(text=t('ConfirmUpdatePanel.updateNow'), icon=ICON_URL)


class UpdateCompletePanel(bpy.types.Operator):
    bl_idname = 'cats_updater.update_complete_panel'
    bl_label = t('UpdateCompletePanel.label')
    bl_description = t('UpdateCompletePanel.desc')
    bl_options = {'INTERNAL'}

    show_patchnotes = False

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.1))

    def check(self, context):
        # Important for changing options
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        if update_finished:
            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.success1'), icon='FILE_TICK')

            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.success2'), icon='BLANK1')
        else:
            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.failure1'), icon='CANCEL')

            row = col.row(align=True)
            row.scale_y = 0.9
            row.label(text=t('UpdateCompletePanel.failure2'), icon='BLANK1')


class UpdateNotificationPopup(bpy.types.Operator):
    bl_idname = 'cats_updater.update_notification_popup'
    bl_label = t('UpdateNotificationPopup.label')
    bl_description = t('UpdateNotificationPopup.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        action = context.scene.cats_update_action
        if action == 'UPDATE':
            if not _online_access_allowed():
                self.report({'ERROR'}, "Online access is disabled in Blender's preferences")
                return {'CANCELLED'}
            update_now(latest=True)
        elif action == 'IGNORE':
            set_ignored_version()
        else:
            # Remind later aka defer
            global remind_me_later
            remind_me_later = True
        ui_refresh()
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = context.preferences.system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.6))

    # def invoke(self, context, event):
    #     return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        # Important for changing options
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        row = layout_split(col, factor=0.55, align=True)
        row.scale_y = 1.05
        row.label(text=t('UpdateNotificationPopup.newUpdate', name=latest_version_str), icon='SOLO_ON')
        row.operator(ShowPatchnotesPanel.bl_idname, text=t('UpdateNotificationPopup.ShowPatchnotesPanel.label'))

        col.separator()
        col.separator()
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'cats_update_action', expand=True)


def check_for_update_background(check_on_startup=False):
    global is_checking_for_update, checked_on_startup, show_error, _update_check_generation
    if check_on_startup and checked_on_startup:
        # print('ALREADY CHECKED ON STARTUP')
        return
    if is_checking_for_update:
        # print('ALREADY CHECKING')
        return

    if not _online_access_allowed():
        if check_on_startup:
            checked_on_startup = True
        else:
            show_error = "Online access is disabled in Blender's preferences"
            ui_refresh()
        return

    checked_on_startup = True

    if check_on_startup and os.path.isfile(no_auto_ver_check_file):
        print('AUTO CHECK DISABLED VIA FILE')
        return

    is_checking_for_update = True

    if not bpy.app.timers.is_registered(_consume_update_check_result):
        bpy.app.timers.register(_consume_update_check_result, first_interval=0.1)

    blender_series = tuple(bpy.app.version[:2])
    _update_check_generation += 1
    check_generation = _update_check_generation
    thread = Thread(
        target=check_for_update,
        args=[blender_series, check_generation],
        daemon=True,
    )
    thread.start()


def check_for_update(blender_series, check_generation):
    print('Checking for Cats update...')

    # Get all releases from Github
    if not get_github_releases(
        UPDATE_REPOSITORY,
        blender_series=blender_series,
        check_generation=check_generation,
    ):
        if check_generation == _update_check_generation:
            _update_result_queue.put(
                (check_generation, t('check_for_update.cantCheck'), False)
            )
        return

    if check_generation != _update_check_generation:
        return

    # Check if an update is needed
    global update_needed, is_ignored_version
    update_needed = check_for_update_available()
    is_ignored_version = check_ignored_version()

    # Update needed, show the notification popup if it wasn't checked through the UI
    if update_needed:
        print('Update found!')
    else:
        print('No update found.')

    if check_generation != _update_check_generation:
        return
    should_notify = update_needed and not used_updater_panel and not is_ignored_version
    _update_result_queue.put((check_generation, '', should_notify))


def _consume_update_check_result():
    while True:
        try:
            check_generation, error, should_notify = _update_result_queue.get_nowait()
        except Empty:
            return 0.1
        if check_generation == _update_check_generation:
            break

    if should_notify:
        prepare_to_show_update_notification()
    finish_update_checking(error=error)
    return None


def get_github_releases(repo, blender_series=None, check_generation=None):
    global version_list
    releases = OrderedDict()
    if check_generation is None or check_generation == _update_check_generation:
        version_list = releases

    if fake_update:
        print('FAKE INSTALL!')

        version = 'v-99-99-99'
        version_tag = version.replace('-', '.')
        if version_tag.startswith('v.'):
            version_tag = version_tag[2:]
        if version_tag.startswith('v'):
            version_tag = version_tag[1:]

        releases[version_tag] = ['', 'Put exiting new stuff here', 'Today']
        releases['12.34.56.78'] = ['', 'Nothing new to see', 'A week ago probably']
        version_list = releases
        return True

    if blender_series is None and not _online_access_allowed():
        return False

    repository = repo if '/' in repo else f"teamneoneko/{repo}"
    api_url = (
        UPDATE_API_URL
        if repository == UPDATE_REPOSITORY
        else f"https://api.github.com/repos/{repository}/releases"
    )
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Cats-Blender-Plugin",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as url:
            data = json.loads(url.read().decode('utf-8'))
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, json.JSONDecodeError) as error:
        print('UPDATE RELEASE CHECK FAILED:', error)
        return False
    if not isinstance(data, list) or not data:
        return False

    if blender_series is None:
        blender_series = tuple(bpy.app.version[:2])
    compatible_releases = []
    for release in data:
        if not isinstance(release, dict):
            continue
        if release.get('draft'):
            continue

        full_tag = release.get('tag_name') or ''
        tag_version = _version_tuple(full_tag)
        if len(tag_version) < 2 or tag_version[:2] != blender_series:
            continue

        update_url = _release_package_url(release)
        if not update_url:
            continue

        published_at = release.get('published_at') or ''
        compatible_releases.append((tag_version, full_tag, [
            update_url,
            release.get('body') or '',
            published_at.split('T')[0],
        ]))

    for _tag_version, full_tag, release_data in sorted(
        compatible_releases, key=lambda item: item[0], reverse=True
    ):
        releases[full_tag] = release_data

    if check_generation is not None and check_generation != _update_check_generation:
        return False
    version_list = releases

    return True


def check_for_update_available():
    if not version_list:
        return False

    global latest_version, latest_version_str
    latest_version_str = next(iter(version_list))
    latest_version = list(_version_tuple(latest_version_str))

    # print(latest_version, '>', current_version)
    if latest_version > current_version:
        return True

    return False


def finish_update_checking(error=''):
    global is_checking_for_update, show_error
    is_checking_for_update = False

    # Only show error if the update panel was used before
    if used_updater_panel:
        show_error = error

    ui_refresh()


def ui_refresh():
    # A way to refresh the ui
    refreshed = False
    while not refreshed:
        if hasattr(bpy.data, 'window_managers'):
            for windowManager in bpy.data.window_managers:
                for window in windowManager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()
            refreshed = True
            # print('Refreshed UI')
        else:
            time.sleep(0.5)


def get_update_post():
    return bpy.app.handlers.depsgraph_update_post


def prepare_to_show_update_notification():
    # This is necessary to show a popup directly after startup
    # You will get a nasty error otherwise
    # Run once from the dependency-graph post handler, then remove it immediately.
    # print('PREPARE TO SHOW UI')
    if show_update_notification not in get_update_post():
        get_update_post().append(show_update_notification)


@persistent
def show_update_notification(scene, depsgraph=None):
    # print('SHOWING UI NOW!!!!')

    # # Immediately remove this from handlers again
    if show_update_notification in get_update_post():
        get_update_post().remove(show_update_notification)

    # Show notification popup
    atr = UpdateNotificationPopup.bl_idname.split(".")
    getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


def update_now(version=None, latest=False, dev=False):
    if fake_update:
        finish_update()
        return

    if not _online_access_allowed():
        finish_update(error="Online access is disabled in Blender's preferences")
        return

    if dev:
        print('UPDATE TO DEVELOPMENT')
        update_link = (
            f"https://github.com/{UPDATE_REPOSITORY}/archive/refs/heads/"
            f"{UPDATE_DEV_BRANCH}.zip"
        )
    elif latest or not version:
        if not version_list or latest_version_str not in version_list:
            finish_update(error="No compatible Blender 5.2 update is available")
            return
        print('UPDATE TO ' + latest_version_str)
        update_link = version_list.get(latest_version_str)[0]
        bpy.context.scene.cats_updater_version_list = latest_version_str
    else:
        if not version_list or version not in version_list:
            finish_update(error="The selected update is no longer available")
            return
        print('UPDATE TO ' + version)
        update_link = version_list[version][0]

    download_file(update_link, normalize_source_archive=dev)


def download_file(update_url, normalize_source_archive=False):
    update_zip_file = os.path.join(downloads_dir, "cats-update.zip")
    downloaded_file = update_zip_file + ".download.tmp"
    prepared_file = update_zip_file + ".prepared.tmp"

    if not _online_access_allowed():
        finish_update(error="Online access is disabled in Blender's preferences")
        return
    if not update_url or not update_url.lower().startswith('https://'):
        finish_update(error="Cats refused an update URL that was not HTTPS")
        return

    pathlib.Path(downloads_dir).mkdir(parents=True, exist_ok=True)

    print('DOWNLOAD FILE')
    try:
        request = urllib.request.Request(
            update_url,
            headers={"User-Agent": "Cats-Blender-Plugin"},
        )
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            with open(downloaded_file, 'wb') as outfile:
                shutil.copyfileobj(response, outfile)

        if normalize_source_archive:
            _normalize_source_archive(downloaded_file, prepared_file)
            os.replace(prepared_file, update_zip_file)
            os.remove(downloaded_file)
        else:
            os.replace(downloaded_file, update_zip_file)
    except (OSError, ValueError, urllib.error.URLError, ssl.SSLError, TimeoutError, zipfile.BadZipFile, tomllib.TOMLDecodeError) as error:
        print("FILE COULD NOT BE DOWNLOADED:", error)
        for temporary_file in (downloaded_file, prepared_file):
            try:
                os.remove(temporary_file)
            except FileNotFoundError:
                pass
        finish_update(error=t('download_file.cantConnect'))
        return
    print('DOWNLOAD FINISHED')

    if not os.path.isfile(update_zip_file) or not zipfile.is_zipfile(update_zip_file):
        print("VALID UPDATE ZIP NOT FOUND!")
        finish_update(error=t('download_file.cantFindZip'))
        return

    validation_error = _validate_update_archive(update_zip_file)
    if validation_error:
        print("INVALID UPDATE PACKAGE:", validation_error)
        finish_update(error=validation_error + "; the ZIP was kept at " + update_zip_file)
        return

    # Let Blender replace the extension through its supported installer. The old
    # updater extracted archives over its own live package, which is unsafe for
    # extension repositories and could delete unrelated files on malformed ZIPs.
    repository_id = _extension_repository_id()
    if not repository_id:
        finish_update(
            error="Cats is not running from a Blender extension repository; the update ZIP was kept at "
            + update_zip_file
        )
        return

    try:
        result = bpy.ops.extensions.package_install_files(
            'EXEC_DEFAULT',
            filepath=update_zip_file,
            repo=repository_id,
            enable_on_install=True,
            overwrite=True,
        )
    except (AttributeError, RuntimeError) as error:
        print("BLENDER COULD NOT INSTALL THE UPDATE:", error)
        finish_update(
            error="Blender could not install the update automatically; the ZIP was kept at "
            + update_zip_file
        )
        return

    if 'FINISHED' not in result:
        finish_update(
            error="Blender did not install the update; the ZIP was kept at " + update_zip_file
        )
        return

    finish_update()


def finish_update(error=''):
    global update_finished, show_error
    show_error = error

    if not error:
        update_finished = True

    bpy.ops.cats_updater.update_complete_panel('INVOKE_DEFAULT')
    ui_refresh()
    print("UPDATE DONE!")


def clean_addon_dir():
    # Retained as a compatibility shim for third-party callers. Package cleanup
    # is deliberately delegated to Blender's extension installer.
    print("Package cleanup is managed by Blender's extension installer")


def set_ignored_version():
    pathlib.Path(updater_state_dir).mkdir(parents=True, exist_ok=True)

    # Create ignore file
    with open(ignore_ver_file, 'w', encoding="utf8") as outfile:
        outfile.write(latest_version_str)

    # Set ignored status
    global is_ignored_version
    is_ignored_version = True
    print('IGNORE VERSION ' + latest_version_str)


def check_ignored_version():
    if not os.path.isfile(ignore_ver_file):
        # print('IGNORE FILE NOT FOUND')
        return False

    # Read ignore file
    with open(ignore_ver_file, 'r', encoding="utf8") as outfile:
        version = outfile.read()

    # Check if the latest version matches the one in the ignore file
    if latest_version_str == version:
        print('Update ignored.')
        return True

    # Delete ignore version file if the latest version is not the version in the file
    try:
        os.remove(ignore_ver_file)
    except OSError:
        print("FAILED TO REMOVE IGNORE VERSION FILE")

    return False


def get_version_list(self, context):
    choices = []
    if version_list:
        for version in version_list.keys():
            choices.append((version, version, version))

    return choices


def get_user_preferences():
    return bpy.context.preferences


def layout_split(layout, factor=0.0, align=False):
    return layout.split(factor=factor, align=align)


def draw_update_notification_panel(layout):
    if not update_needed or remind_me_later or is_ignored_version:
        # pass
        return

    col = layout.column(align=True)

    if update_finished:
        col.separator()
        row = col.row(align=True)
        row.label(text=t('draw_update_notification_panel.success'), icon='ERROR')
        col.separator()
        return

    row = col.row(align=True)
    row.scale_y = 0.75
    row.label(text=t('draw_update_notification_panel.newUpdate', name=latest_version_str), icon='SOLO_ON')

    col.separator()
    row = col.row(align=True)
    row.scale_y = 1.3
    row.operator(UpdateToLatestButton.bl_idname, text=t('draw_update_notification_panel.UpdateToLatestButton.label'))

    row = col.row(align=True)
    row.scale_y = 1
    row.operator(RemindMeLaterButton.bl_idname, text=t('draw_update_notification_panel.RemindMeLaterButton.label'))
    row.operator(IgnoreThisVersionButton.bl_idname, text=t('draw_update_notification_panel.IgnoreThisVersionButton.label'))


def draw_updater_panel(context, layout, user_preferences=False):
    col = layout.column(align=True)

    scale_big = 2
    scale_small = 1.2

    row = col.row(align=True)
    row.scale_y = 0.8
    row.label(text=t('draw_updater_panel.updateLabel') if not user_preferences else t('draw_updater_panel.updateLabel_alt'), icon=ICON_URL)
    col.separator()

    if update_finished:
        col.separator()
        row = col.row(align=True)
        row.label(text=t('draw_updater_panel.success'), icon='ERROR')
        col.separator()
        return

    if show_error:
        row = col.row(align=True)
        row.label(text=show_error, icon='ERROR')
        col.separator()

    if is_checking_for_update:
        if not used_updater_panel:
            row = col.row(align=True)
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label'))
        else:
            split = col.row(align=True)
            row = split.row(align=True)
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label'))
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            row.scale_y = scale_big
            row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')

    elif update_needed:
        split = col.row(align=True)
        row = split.row(align=True)
        row.scale_y = scale_big
        row.operator(UpdateToLatestButton.bl_idname, text=t('draw_updater_panel.UpdateToLatestButton.label', name=latest_version_str))
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')

    elif not used_updater_panel or not version_list:
        row = col.row(align=True)
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text=t('draw_updater_panel.CheckForUpdateButton.label_alt'))

    else:
        split = col.row(align=True)
        row = split.row(align=True)
        row.scale_y = scale_big
        row.operator(UpdateToLatestButton.bl_idname, text=t('draw_updater_panel.UpdateToLatestButton.label_alt'))
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.scale_y = scale_big
        row.operator(CheckForUpdateButton.bl_idname, text="", icon='FILE_REFRESH')

    # col.separator()
    # col.separator()
    # col.separator()
    # row = layout_split(col, factor=0.6, align=True)
    # row.scale_y = 0.9
    # row.active = True if not is_checking_for_update and version_list else False
    # row.label(text="Select Version:")
    # row.prop(context.scene, 'cats_updater_version_list', text='')
    #
    # row = layout_split(col, factor=0.6, align=True)
    # row.scale_y = scale_small
    # row.operator(UpdateToSelectedButton.bl_idname, text='Install Selected Version')
    # row.operator(ShowPatchnotesPanel.bl_idname, text='Show Patchnotes')

    col.separator()
    col.separator()
    split = col.row(align=True)
    row = layout_split(split, factor=0.55, align=True)
    row.scale_y = scale_small
    row.active = True if not is_checking_for_update and version_list else False
    row.operator(UpdateToSelectedButton.bl_idname, text=t('draw_updater_panel.UpdateToSelectedButton.label'))
    row.prop(context.scene, 'cats_updater_version_list', text='')
    row = split.row(align=True)
    row.scale_y = scale_small
    row.operator(ShowPatchnotesPanel.bl_idname, text="", icon='WORDWRAP_ON')

    # topsplit = layout_split(col, factor=0.55, align=True)
    #
    # split = topsplit.row(align=True)
    # row = split.row(align=True)
    # row.scale_y = scale_small
    # row.active = True if not is_checking_for_update and version_list else False
    # row.operator(UpdateToSelectedButton.bl_idname, text='Install Version:')
    #
    # row = split.row(align=True)
    # row.alignment = 'RIGHT'
    # row.scale_y = scale_small
    # row.operator(ShowPatchnotesPanel.bl_idname, text="", icon='WORDWRAP_ON')
    #
    # row = topsplit.row(align=True)
    # row.scale_y = scale_small
    # row.prop(context.scene, 'cats_updater_version_list', text='')

    row = col.row(align=True)
    row.scale_y = scale_small
    row.operator(UpdateToDevButton.bl_idname, text=t('draw_updater_panel.UpdateToDevButton.label'))

    col.separator()
    row = col.row(align=True)
    row.scale_y = 0.65
    row.label(text=t('draw_updater_panel.currentVersion', name=current_version_str))


# demo bare-bones preferences
class DemoPreferences(MMDToolsAddonPreferences):
    bl_idname = package_name
    __annotations__ = dict(MMDToolsAddonPreferences.__annotations__)

    def draw(self, context):
        layout = self.layout
        layout.label(text="CATS Updates")
        draw_updater_panel(context, layout, user_preferences=True)
        layout.separator()
        layout.label(text="Bundled MMD Tools")
        MMDToolsAddonPreferences.draw(self, context)


to_register = [
    CheckForUpdateButton,
    UpdateToLatestButton,
    UpdateToSelectedButton,
    UpdateToDevButton,
    RemindMeLaterButton,
    IgnoreThisVersionButton,
    ShowPatchnotesPanel,
    ConfirmUpdatePanel,
    UpdateCompletePanel,
    UpdateNotificationPopup,
    DemoPreferences,
]


def register(dev_branch, version_str):
    # print('REGISTER CATS UPDATER')
    global current_version, fake_update, current_version_str, checked_on_startup

    # If not dev branch, always disable fake update!
    if not dev_branch:
        fake_update = False
    checked_on_startup = False
    current_version_str = version_str

    # Get current version
    current_version = []
    version_parts = CATS_VERSION.split(".")

    for part in version_parts:
        current_version.append(int(part))

    bpy.types.Scene.cats_updater_version_list = bpy.props.EnumProperty(
        name=t('bpy.types.Scene.cats_updater_version_list.label'),
        description=t('bpy.types.Scene.cats_updater_version_list.desc'),
        items=wrap_dynamic_enum_items(get_version_list, 'cats_updater_version_list', sort=False)
    )
    bpy.types.Scene.cats_update_action = bpy.props.EnumProperty(
        name=t('bpy.types.Scene.cats_update_action.label'),
        description=t('bpy.types.Scene.cats_update_action.desc'),
        items=[
            ("UPDATE", t('bpy.types.Scene.cats_update_action.update.label'), t('bpy.types.Scene.cats_update_action.update.desc')),
            ("IGNORE", t('bpy.types.Scene.cats_update_action.ignore.label'), t( 'bpy.types.Scene.cats_update_action.ignore.desc')),
            ("DEFER", t('bpy.types.Scene.cats_update_action.defer.label'), t( 'bpy.types.Scene.cats_update_action.defer.desc'))
        ]
    )

    # Register all Updater classes
    count = 0
    for cls in to_register:
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError:
            pass
    # print('Registered', count, 'CATS updater classes.')
    if count < len(to_register):
        print('Skipped', len(to_register) - count, 'CATS updater classes.')


def unregister():
    global is_checking_for_update, checked_on_startup, _update_check_generation

    # Invalidate an in-flight network result before removing its main-thread
    # consumer. A worker that finishes later will see the generation mismatch.
    _update_check_generation += 1
    is_checking_for_update = False
    checked_on_startup = False

    if bpy.app.timers.is_registered(_consume_update_check_result):
        bpy.app.timers.unregister(_consume_update_check_result)

    update_post = get_update_post()
    if show_update_notification in update_post:
        update_post.remove(show_update_notification)

    while True:
        try:
            _update_result_queue.get_nowait()
        except Empty:
            break

    # Unregister all Updater classes
    for cls in reversed(to_register):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    if hasattr(bpy.types.Scene, 'cats_updater_version_list'):
        del bpy.types.Scene.cats_updater_version_list
    if hasattr(bpy.types.Scene, 'cats_update_action'):
        del bpy.types.Scene.cats_update_action
