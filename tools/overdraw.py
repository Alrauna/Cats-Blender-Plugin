# MIT License

import json
import webbrowser

import bpy

from .register import register_wrap
from .translations import t


SEPARATOR_OPERATOR_NAMESPACE = "alpha_material_separator"
SEPARATOR_API_PROPERTY = "alpha_material_separator_api"
SEPARATOR_SETTINGS_PROPERTY = "alpha_material_separator_settings"

# analyze() checks this against its own API_VERSION[0] and refuses a mismatch.
SEPARATOR_API_MAJOR = 1

# analyze() reads these from its own operator properties, never from the
# separator's settings, so CATS has to copy them across. They mirror
# api_contract.ANALYSIS_SETTING_NAMES, which the separator guards as public API.
# image_name, uv_map_name, and image_channel are omitted on purpose: since 1.2.0
# they carry options={'SKIP_SAVE'} and reset to ("", "", "ALPHA") per invocation.
TUNING_PROPERTIES = (
    "address_mode",
    "alpha_threshold",
    "min_affected_texels",
    "min_affected_fraction",
    "margin_texels",
    "max_scanlines",
    "max_run_emissions",
)


def is_available():
    """Return True when the Alpha Material Separator extension can be driven.

    Detection is by operator ID and property name, never by module import: the
    separator is an extension, so its module path depends on which repository it
    was installed from.
    """
    namespace = getattr(bpy.ops, SEPARATOR_OPERATOR_NAMESPACE, None)
    if namespace is None or not hasattr(namespace, "analyze"):
        return False
    return hasattr(bpy.types.WindowManager, SEPARATOR_API_PROPERTY)


def read_status(api_state):
    """Return the separator's published status payload, or None."""
    raw = getattr(api_state, "last_status_json", None)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def status_message(api_state):
    """Return the separator's own status text, or None when there is none.

    Only 'code' and 'message' are guaranteed by the separator's contract, so
    nothing else is read. CATS never composes this text itself.
    """
    payload = read_status(api_state)
    if payload is None:
        return None
    if payload.get("code") in (None, "NOT_QUERIED"):
        return None
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return None


# The separator publishes these when a completed report no longer matches the
# scene. Its own panel treats them as normal because it draws a dedicated stale
# box; CATS has no such box, so the status line carries the severity instead.
ACTIONABLE_STATUS_CODES = frozenset({"RESULT_STALE", "STALE_ANALYSIS"})


def status_is_actionable(api_state):
    """Return True when the published status means the user must act."""
    payload = read_status(api_state)
    if payload is None:
        return False
    return payload.get("code") in ACTIONABLE_STATUS_CODES


def overrides_json(settings):
    """Build the separator's per-material override payload."""
    payload = []
    for item in getattr(settings, "material_overrides", ()) or ():
        material = getattr(item, "material", None)
        if material is None:
            continue
        image = getattr(item, "image", None)
        payload.append({
            "address_mode": item.address_mode,
            "image_channel": item.image_channel if image else "ALPHA",
            "image_name": image.name_full if image else "",
            "material_name": material.name_full,
            "uv_map_name": item.uv_map_name,
        })
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def configure_analysis(operator_props, settings):
    """Point an analyze button at the separator's current settings."""
    operator_props.api_major = SEPARATOR_API_MAJOR
    operator_props.material_overrides_json = overrides_json(settings)
    for name in TUNING_PROPERTIES:
        value = getattr(settings, name, None)
        if value is not None:
            setattr(operator_props, name, value)


@register_wrap
class DownloadSeparatorButton(bpy.types.Operator):
    bl_idname = 'cats_overdraw.download_separator'
    bl_label = t('DownloadSeparatorButton.label')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('DownloadSeparatorButton.URL'))

        self.report({'INFO'}, t('DownloadSeparatorButton.success'))
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        col = self.layout.column()
        col.label(text=t('DownloadSeparatorButton.dialog'), icon='INFO')
        col.separator()
        col.label(text=t('DownloadSeparatorButton.URL'))
        col.separator()
        col.label(text=t('DownloadSeparatorButton.confirm'))


@register_wrap
class OverdrawHelpButton(bpy.types.Operator):
    bl_idname = 'cats_overdraw.help'
    bl_label = t('OverdrawHelpButton.label')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('OverdrawHelpButton.URL'))

        self.report({'INFO'}, t('OverdrawHelpButton.success'))
        return {'FINISHED'}
