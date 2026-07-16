# MIT License

CATS_VERSION = "5.2.0"
MIN_BLENDER_VERSION = (5, 2, 0)
dev_branch = False

import pathlib
import importlib


def _import_bundled_immersive_scaler():
    """Load the optional submodule without exposing bundled code globally."""
    package_name = f"{__package__}.extern_tools.imscale"
    try:
        return importlib.import_module(".extern_tools.imscale.immersive_scaler", __package__)
    except ModuleNotFoundError as exc:
        if exc.name not in {package_name, f"{package_name}.immersive_scaler"}:
            raise
        return None

from . import globs

imscale = globals().get('imscale')

# Check if cats is reloading or started fresh
if "bpy" not in locals():
    import bpy
    is_reloading = False
else:
    is_reloading = True

# Load or reload all cats modules
if not is_reloading:
    # This order is important
    from .extern_tools import mmd_tools_local
    imscale = _import_bundled_immersive_scaler()
    from . import updater
    from . import tools
    from . import ui
    from . import extentions
else:
    importlib.reload(updater)
    importlib.reload(mmd_tools_local)
    if imscale is not None:
        importlib.reload(imscale)
    importlib.reload(tools)
    importlib.reload(ui)
    importlib.reload(extentions)

from .tools import translations
from .tools.translations import t

_updater_registered = False
_mmd_tools_registered = False
_immersive_scaler_registered = False
_scene_properties_registered = False
_icons_loaded = False
_shape_key_menu_registered = False
_settings_timer_started = False


# How to update mmd_tools_local:
# MMD Tools is no longer a drop in replacement, manually work is required please ask
# us to update it instead.

# How to set up PyCharm with Blender:
# https://b3d.interplanety.org/en/using-external-ide-pycharm-for-writing-blender-scripts/


def validate_install_location():
    """Reject a legacy loose-file install without modifying neighboring add-ons."""
    if (__package__ or '').startswith('bl_ext.'):
        return

    package_directory = pathlib.Path(__file__).resolve().parent
    if (
        package_directory.name.lower() == 'addons'
        or package_directory.parent.name.lower() == 'addons'
    ):
        raise ImportError(t('Main.error.installViaPreferences'))


def check_unsupported_blender_versions():
    if bpy.app.version < MIN_BLENDER_VERSION:
        required_version = '.'.join(str(part) for part in MIN_BLENDER_VERSION)
        raise ImportError(
            f"CATS {CATS_VERSION} requires Blender {required_version} or newer; "
            f"this is Blender {bpy.app.version_string}."
        )

def set_cats_version_string():
    version_parts = CATS_VERSION.split(".")

    # Convert version parts to integers
    version_parts = [int(part) for part in version_parts]

    # Increment the last version component if in dev branch
    if dev_branch:
        version_parts[-1] += 1

    # Convert version back to string
    version_str = ".".join(str(part) for part in version_parts)

    # Add -dev if in dev version
    if dev_branch:
        version_str += "-dev"

    return version_str

def register():
    global _updater_registered
    global _mmd_tools_registered
    global _immersive_scaler_registered
    global _scene_properties_registered
    global _icons_loaded
    global _shape_key_menu_registered
    global _settings_timer_started
    global imscale

    print("\n### Loading CATS...")

    # The manifest prevents unsupported installs; keep this runtime guard for
    # direct development loads and manually copied installations.
    check_unsupported_blender_versions()
    validate_install_location()

    version_str = set_cats_version_string()

    try:
        _updater_registered = True
        updater.register(dev_branch, version_str)

        # Set some global settings, first allowed use of globs.
        globs.dev_branch = dev_branch
        globs.version_str = version_str

        tools.settings.load_settings()

        _mmd_tools_registered = True
        mmd_tools_local.register()

        # Register Immersive Scaler only when the optional submodule exists.
        if imscale is not None:
            _immersive_scaler_registered = True
            imscale.register()

        count = tools.register.register_classes()
        print('Registered', count, 'CATS classes.')

        # Register Scene types. Mark the step first so a partial property
        # failure is removed by the rollback path.
        _scene_properties_registered = True
        extentions.register()

        _icons_loaded = True
        tools.iconloader.load_other_icons()

        # Load the dictionaries and check if they are found.
        globs.dict_found = tools.translate.load_translations()

        # Set preferred Blender options.
        preferences = tools.common.get_user_preferences()
        if hasattr(preferences, 'system') and hasattr(preferences.system, 'use_international_fonts'):
            preferences.system.use_international_fonts = True
        elif hasattr(preferences, 'view') and hasattr(preferences.view, 'use_international_fonts'):
            preferences.view.use_international_fonts = True
        preferences.filepaths.use_file_compression = True
        if hasattr(bpy.context.window_manager, 'addon_support'):
            bpy.context.window_manager.addon_support = {'OFFICIAL', 'COMMUNITY'}

        bpy.types.MESH_MT_shape_key_context_menu.append(tools.shapekey.addToShapekeyMenu)
        _shape_key_menu_registered = True

        # Apply settings after registration because Blender does not permit
        # changing every preference while add-on classes are being registered.
        _settings_timer_started = True
        tools.settings.start_apply_settings_timer()
    except Exception:
        try:
            unregister()
        except Exception as rollback_exc:
            print(f"CATS registration rollback encountered errors: {rollback_exc}")
        raise

    print("### Loaded CATS successfully!\n")


def _unregister_step(label, callback, errors):
    try:
        return callback()
    except Exception as exc:
        print(f"CATS: failed to unregister {label}: {exc}")
        errors.append((label, exc))
        return None


def unregister():
    global _updater_registered
    global _mmd_tools_registered
    global _immersive_scaler_registered
    global _scene_properties_registered
    global _icons_loaded
    global _shape_key_menu_registered
    global _settings_timer_started

    print("### Unloading CATS...")
    errors = []

    if _settings_timer_started:
        _unregister_step('settings timer', tools.settings.stop_apply_settings_threads, errors)
        _settings_timer_started = False

    if _shape_key_menu_registered:
        _unregister_step(
            'shape-key menu',
            lambda: bpy.types.MESH_MT_shape_key_context_menu.remove(tools.shapekey.addToShapekeyMenu),
            errors,
        )
        _shape_key_menu_registered = False

    count = _unregister_step('CATS classes', tools.register.unregister_classes, errors)
    if count is not None:
        print('Unregistered', count, 'CATS classes.')

    if _scene_properties_registered:
        _unregister_step('Scene properties', extentions.unregister, errors)
        _scene_properties_registered = False

    if _icons_loaded:
        _unregister_step('icons', tools.iconloader.unload_icons, errors)
        _icons_loaded = False

    if _immersive_scaler_registered:
        _unregister_step('Immersive Scaler', imscale.unregister, errors)
        _immersive_scaler_registered = False

    if _mmd_tools_registered:
        _unregister_step('bundled MMD Tools', mmd_tools_local.unregister, errors)
        _mmd_tools_registered = False

    if _updater_registered:
        _unregister_step('updater', updater.unregister, errors)
        _updater_registered = False

    if errors:
        failed_steps = ', '.join(label for label, _ in errors)
        raise RuntimeError(f"CATS could not fully unregister: {failed_steps}") from errors[0][1]

    print("### Unloaded CATS successfully!\n")


if __name__ == '__main__':
    register()
