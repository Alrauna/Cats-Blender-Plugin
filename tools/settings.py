# GPL License

import os
import bpy
import json
import copy
import time
import pathlib
import collections
from datetime import datetime, timezone
from collections import OrderedDict
from contextlib import contextmanager

from .. import globs
from ..tools.register import register_wrap
from ..extern_tools.google_trans_new.google_trans_new import google_translator
from . import translate as Translate
from .translations import t

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
bundled_resources_dir = os.path.join(str(main_dir), "resources")
bundled_settings_file = os.path.join(bundled_resources_dir, "settings.json")

# Blender extensions can be installed into read-only repositories and are replaced
# wholesale during upgrades. Keep all mutable settings in Blender's per-extension
# user directory instead of beside the installed Python files.
addon_package = __package__.rpartition('.')[0]


def _user_storage_dir(path):
    try:
        return bpy.utils.extension_path_user(addon_package, path=path, create=True)
    except (AttributeError, ValueError):
        # Keep legacy add-on installs working without writing into their package.
        return bpy.utils.user_resource(
            'CONFIG', path=os.path.join("cats_blender_plugin", path), create=True
        )


resources_dir = _user_storage_dir("resources")
settings_file = os.path.join(resources_dir, "settings.json")

settings_data = None
settings_data_unchanged = None
settings_timer_started_at = None
settings_timer_stopped = True
SETTINGS_TIMER_INTERVAL = 0.3
SETTINGS_TIMER_TIMEOUT = 5.0

# Settings name = [Default Value, Require Blender Restart]
settings_default = OrderedDict()
settings_default['embed_textures'] = [False, False]
settings_default['ui_lang'] = ["auto", False]

lock_settings = False

@contextmanager
def settings_lock_context():
    global lock_settings
    lock_settings = True
    try:
        yield
    finally:
        lock_settings = False

@register_wrap
class RevertChangesButton(bpy.types.Operator):
    bl_idname = 'cats_settings.revert'
    bl_label = t('RevertChangesButton.label')
    bl_description = t('RevertChangesButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        for setting in settings_default.keys():
            setattr(bpy.context.scene, setting, settings_data_unchanged.get(setting))
        save_settings()
        self.report({'INFO'}, t('RevertChangesButton.success'))
        return {'FINISHED'}

@register_wrap
class ResetGoogleDictButton(bpy.types.Operator):
    bl_idname = 'cats_settings.reset_google_dict'
    bl_label = t('ResetGoogleDictButton.label')
    bl_description = t('ResetGoogleDictButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        Translate.reset_google_dict()
        Translate.load_translations()
        self.report({'INFO'}, t('ResetGoogleDictButton.resetInfo'))
        return {'FINISHED'}

@register_wrap
class DebugTranslations(bpy.types.Operator):
    bl_idname = 'cats_settings.debug_translations'
    bl_label = t('DebugTranslations.label')
    bl_description = t('DebugTranslations.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if not bpy.app.online_access:
            self.report({'ERROR'}, "Online access is disabled in Blender's preferences")
            return {'CANCELLED'}

        bpy.context.scene.debug_translations = True
        translator = google_translator()
        try:
            translator.translate('猫')
        except:
            self.report({'INFO'}, t('DebugTranslations.error'))

        bpy.context.scene.debug_translations = False
        self.report({'INFO'}, t('DebugTranslations.success'))
        return {'FINISHED'}

def load_settings():
    global settings_data, settings_data_unchanged

    source_file = settings_file
    migrate_legacy_settings = False
    if not os.path.isfile(source_file) and os.path.isfile(bundled_settings_file):
        source_file = bundled_settings_file
        migrate_legacy_settings = True

    try:
        with open(source_file, encoding="utf8") as file:
            settings_data = json.load(file, object_pairs_hook=collections.OrderedDict)
    except FileNotFoundError:
        print("SETTINGS FILE NOT FOUND!")
        reset_settings(full_reset=True)
        return
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN SETTINGS FILE")
        reset_settings(full_reset=True)
        return

    if not settings_data:
        print("NO DATA IN SETTINGS FILE")
        reset_settings(full_reset=True)
        return

    to_reset_settings = []

    for setting in ['last_supporter_update']:
        if setting not in settings_data and setting not in to_reset_settings:
            to_reset_settings.append(setting)
            print('RESET SETTING', setting)

    for setting in settings_default.keys():
        if setting not in settings_data and setting not in to_reset_settings:
            to_reset_settings.append(setting)
            print('RESET SETTING', setting)

    utc_now = datetime.strptime(datetime.now(timezone.utc).strftime(globs.time_format), globs.time_format)
    for setting in ['last_supporter_update']:
        if setting not in to_reset_settings and settings_data.get(setting):
            try:
                timestamp = datetime.strptime(settings_data.get(setting), globs.time_format)
            except ValueError:
                to_reset_settings.append(setting)
                print('RESET TIME', setting)
                continue

            time_delta = (utc_now - timestamp).total_seconds()
            if time_delta < 0:
                to_reset_settings.append(setting)
                print('TIME', setting, 'IN FUTURE!', time_delta)

    if to_reset_settings:
        reset_settings(to_reset_settings=to_reset_settings)
        return

    settings_data_unchanged = copy.deepcopy(settings_data)

    if migrate_legacy_settings:
        save_settings()

def save_settings():
    os.makedirs(resources_dir, exist_ok=True)
    temporary_file = settings_file + ".tmp"
    with open(temporary_file, 'w', encoding="utf8") as outfile:
        json.dump(settings_data, outfile, ensure_ascii=False, indent=4)
    os.replace(temporary_file, settings_file)

def reset_settings(full_reset=False, to_reset_settings=None):
    if not to_reset_settings:
        full_reset = True

    global settings_data, settings_data_unchanged

    if full_reset:
        settings_data = OrderedDict()
        settings_data['last_supporter_update'] = None

        for setting, value in settings_default.items():
            settings_data[setting] = value[0]

    else:
        for setting in to_reset_settings:
            if setting in settings_default.keys():
                settings_data[setting] = settings_default[setting][0]
            else:
                settings_data[setting] = None

    save_settings()

    settings_data_unchanged = copy.deepcopy(settings_data)
    print('SETTINGS RESET')

def start_apply_settings_timer():
    global settings_timer_started_at, settings_timer_stopped

    if bpy.app.timers.is_registered(apply_settings_with_timeout):
        bpy.app.timers.unregister(apply_settings_with_timeout)

    # An add-on can be disabled and enabled again in the same Blender session.
    settings_timer_stopped = False
    settings_timer_started_at = time.monotonic()
    bpy.app.timers.register(apply_settings_with_timeout, first_interval=0.0)

def apply_settings_with_timeout():
    global settings_timer_started_at

    if settings_timer_stopped:
        settings_timer_started_at = None
        return None

    if (
        settings_timer_started_at is not None
        and time.monotonic() - settings_timer_started_at >= SETTINGS_TIMER_TIMEOUT
    ):
        release_lock()
        settings_timer_started_at = None
        return None

    with settings_lock_context():
        if apply_settings():
            settings_timer_started_at = None
            return None

    return SETTINGS_TIMER_INTERVAL

def release_lock():
    global lock_settings
    print("Settings lock timed out, releasing lock")
    lock_settings = False

def apply_settings():
    if not hasattr(bpy.context, 'scene') or bpy.context.scene is None:
        return False

    try:
        settings_to_reset = []
        for setting in settings_default.keys():
            try:
                setattr(bpy.context.scene, setting, settings_data.get(setting))
            except TypeError:
                settings_to_reset.append(setting)
        if settings_to_reset:
            reset_settings(to_reset_settings=settings_to_reset)
            print("RESET SETTINGS ON TIMER:", settings_to_reset)
    except (AttributeError, ReferenceError):
        return False

    print('Settings applied successfully')
    return True

def stop_apply_settings_threads():
    global settings_timer_started_at, settings_timer_stopped, lock_settings

    print("Stopping settings timer...")
    settings_timer_stopped = True
    settings_timer_started_at = None
    if bpy.app.timers.is_registered(apply_settings_with_timeout):
        bpy.app.timers.unregister(apply_settings_with_timeout)
    lock_settings = False
    print("Settings timer stopped.")

def settings_changed():
    for setting, value in settings_default.items():
        if value[1] and settings_data.get(setting) != settings_data_unchanged.get(setting):
            return True
    return False

def update_settings(self, context):
    update_settings_core(self, context)

def update_settings_core(self, context):
    print("update_settings_core function called")
    settings_changed_tmp = False
    if lock_settings:
        print("Settings are locked, returning")
        return settings_changed_tmp

    with settings_lock_context():
        for setting in settings_default.keys():
            old = settings_data[setting]
            new = getattr(bpy.context.scene, setting)
            print(f"Checking setting: {setting}")
            print(f"Old value: {old}")
            print(f"New value: {new}")
            if old != new:
                print(f"Setting {setting} changed")
                settings_data[setting] = new
                settings_changed_tmp = True

        if settings_changed_tmp:
            print("Settings changed, saving settings")
            save_settings()
        else:
            print("No settings changed")

    return settings_changed_tmp

def get_embed_textures():
    return settings_data.get('embed_textures')

def get_ui_lang():
    return settings_data.get('ui_lang')
