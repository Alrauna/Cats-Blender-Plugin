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


def status_severity(api_state):
    """Return the separator's own severity for its last status.

    The separator publishes OK, INFO, or ERROR per status code and classifies
    unknown codes as ERROR itself, so CATS keeps no code list of its own. A
    separator older than 1.3.0 publishes no severity; treat that as OK, which
    leaves its status in the plain info box exactly as before.
    """
    payload = read_status(api_state)
    if payload is None:
        return "OK"
    severity = payload.get("severity")
    return severity if isinstance(severity, str) and severity else "OK"


def workflow_state(api_state):
    """Return the separator's published workflow gating, or None.

    This is the same snapshot the separator's own panel draws from, so gating
    CATS on it cannot drift from what the separator will actually accept. It is
    a computed property, always current, and absent before separator 1.3.0.
    """
    raw = getattr(api_state, "workflow_json", None)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


# The separator publishes this in every payload. 1.3 is the first API that
# publishes workflow state, which is what the panel's gating is built on.
SEPARATOR_MINIMUM_API = (1, 3)


def api_version(api_state):
    """Return the separator's published API major and minor, or None.

    Every published payload carries it, so the workflow channel is read first
    and the status channel second. A patch component is ignored: the separator
    versions its contract by major and minor only.
    """
    for payload in (workflow_state(api_state), read_status(api_state)):
        raw = payload.get("api_version") if payload else None
        if not isinstance(raw, str) or not raw:
            continue
        try:
            return tuple(int(part) for part in raw.split(".")[:2])
        except ValueError:
            return None
    return None


def meets_minimum_api(api_state):
    """Return True when the installed separator is new enough to drive.

    An unreadable version is treated as too old. Only a separator older than
    1.3.0 reaches that state: 1.3.0 and newer publish workflow_json from a
    computed property that is always current.
    """
    version = api_version(api_state)
    return version is not None and version >= SEPARATOR_MINIMUM_API


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
