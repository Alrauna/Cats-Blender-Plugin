# Overdraw Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Overdraw Prevention sub-panel to the CATS Optimization panel that drives the external Blender Alpha Material Separator (AMS) extension through its published operator contract.

**Architecture:** A new `tools/overdraw.py` holds pure detection, status-parsing, and operator-configuration helpers plus two small CATS operators. A new `OverdrawSubPanel` in `ui/optimization.py` calls AMS's four workflow operators directly with `layout.operator()`. No AMS module is ever imported; detection is by operator-ID presence, status comes from a public `WindowManager` property.

**Tech Stack:** Blender 5.2 LTS Python API (`bpy`), stdlib `json` and `webbrowser`, `unittest` run inside `blender --background`.

## Global Constraints

- Target Blender 5.2 LTS. `blender_manifest.toml` declares `blender_version_min = "5.2.0"`.
- Implements `docs/superpowers/specs/2026-08-07-overdraw-prevention-design.md`. Work on branch `feature/overdraw-prevention`.
- AMS stays an **external** extension. Do not vendor it, do not add it to `.gitmodules`, do not add it to the extension package.
- Never import an AMS module. Detection is `hasattr` on `bpy.ops` and `bpy.types.WindowManager` only.
- AMS extension id `alpha_material_separator`, version 1.1.0, `API_VERSION = (1, 2)`, so `api_major = 1`.
- The four workflow operator IDs, used verbatim: `alpha_material_separator.analyze`, `alpha_material_separator.select_faces`, `alpha_material_separator.assign_materials`, `alpha_material_separator.clear_results`. `query_capabilities` is deliberately not called.
- New CATS operator IDs: `cats_overdraw.download_separator`, `cats_overdraw.help`. New panel id: `VIEW3D_PT_optimize_overdraw_v3`.
- All four files in `resources/translations/` must gain every new key. English is authoritative; `ja_JP`, `ko_KR`, `zh_CN` are flagged for native review in the commit message. URLs are identical across languages.
- Never let `draw()` raise. Every panel path is inside `try`/`except` falling back to `draw_error_box`.
- Run `git diff --check` before every commit. Never commit `.packaged-releases/`, `.test-runtime/`, or `.local-references/`.
- Build only with `python scripts/build.py --blend <blender>`. Do not delete builds from `.packaged-releases/` unless the maintainer asks.

## Findings that replace the spec's open risk

The spec listed a spike to determine whether `analyze` reads AMS's settings itself. **It does not.** `addon/operators/analyze.py` reads `self.address_mode`, `self.alpha_threshold`, and its other declared properties; it touches `context.window_manager` only for the API state, the UI state, the runtime lock, and progress reporting. It also enforces `if self.api_major != api_contract.API_VERSION[0]`.

So CATS must set the properties. Two refinements to the spec's eleven:

1. AMS's own panel sets `image_name = ""`, `uv_map_name = ""`, and `image_channel = "ALPHA"`, which are already the operator's declared defaults. CATS does not set them.
2. That leaves **seven** tuning properties copied from AMS's public settings, plus `material_overrides_json`, whose default is the string `"[]"`.

`analyze` is a **modal** operator; it adds a timer and a modal handler. Calling it from a button is correct and it reports progress itself. Do not wrap it or wait on it.

## File Structure

| File | Responsibility |
| --- | --- |
| `tools/overdraw.py` (create) | Detection, status parsing, override payload, operator configuration, and the two CATS operators. Pure Python except the two operator classes, so it is unit-testable. |
| `ui/optimization.py` (modify) | Adds `OverdrawSubPanel`. Drawing only; no logic. |
| `resources/translations/*.json` (modify, 4) | New user-facing strings and URLs. |
| `tests/overdraw_smoke.py` (create) | Unit tests for every helper in `tools/overdraw.py`, plus the AMS-absent path. |
| `tests/extension_smoke.py` (modify) | Adds the two new operators and the new panel to the expected registration surface. |
| `.github/workflows/Cats Tests.yml` (modify) | Runs `tests/overdraw_smoke.py`. |
| `README.md` (modify) | Lists AMS under optional dependencies. |

## Running tests

Every task uses this. `$B` is the Blender 5.2 executable; on this machine
`C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`. The extension must
be installed into an isolated profile first, exactly as earlier sessions did:

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
P="$(pwd)/.test-runtime/overdraw"
rm -rf "$P" && mkdir -p "$P"/{resources,config,scripts,extensions,datafiles,repo}
export BLENDER_USER_RESOURCES="$P/resources" BLENDER_USER_CONFIG="$P/config" \
       BLENDER_USER_SCRIPTS="$P/scripts" BLENDER_USER_EXTENSIONS="$P/extensions" \
       BLENDER_USER_DATAFILES="$P/datafiles"
python scripts/build.py --blend "$B" --allow-dirty
Z=$(ls -t .packaged-releases/*.zip | head -1)
"$B" --command extension repo-add --name "Overdraw" --directory "$P/repo" --clear-all cats_ci
"$B" --command extension install-file --repo cats_ci --enable "$Z"
```

Then run a single suite with:

```bash
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/overdraw_smoke.py
```

AMS is **not** installed in this profile. That is deliberate: it is CI's state and
the common user state, and it is what the AMS-absent assertions require.

---

### Task 1: Detection, status parsing, and operator configuration

**Files:**
- Create: `tools/overdraw.py`
- Create: `tests/overdraw_smoke.py`
- Modify: `.github/workflows/Cats Tests.yml` (add a step after the Pose Mode step, around line 115)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, all used by Tasks 2 and 3:
  - `SEPARATOR_API_PROPERTY: str = "alpha_material_separator_api"`
  - `SEPARATOR_SETTINGS_PROPERTY: str = "alpha_material_separator_settings"`
  - `SEPARATOR_API_MAJOR: int = 1`
  - `is_available() -> bool`
  - `read_status(api_state) -> dict | None`
  - `status_message(api_state) -> str | None`
  - `overrides_json(settings) -> str`
  - `configure_analysis(operator_props, settings) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/overdraw_smoke.py`:

```python
# GPL License

"""Verify the CATS Overdraw Prevention integration helpers in Blender 5.2."""

from __future__ import annotations

import importlib
import json
import unittest

import bpy


PACKAGE_ID = "cats_blender_plugin"


def cats_module_name() -> str:
    modules = [
        addon.module
        for addon in bpy.context.preferences.addons
        if addon.module.rsplit(".", 1)[-1] == PACKAGE_ID
    ]
    if len(modules) != 1:
        raise AssertionError(f"Expected one enabled CATS extension, found {modules!r}")
    return modules[0]


class StubApiState:
    def __init__(self, last_status_json):
        self.last_status_json = last_status_json


class StubNamed:
    def __init__(self, name_full):
        self.name_full = name_full


class StubOverride:
    def __init__(self, material, image=None, image_channel="RED",
                 uv_map_name="UVMap", address_mode="CLIP"):
        self.material = material
        self.image = image
        self.image_channel = image_channel
        self.uv_map_name = uv_map_name
        self.address_mode = address_mode


class StubSettings:
    def __init__(self, overrides=(), **tuning):
        self.material_overrides = list(overrides)
        for key, value in tuning.items():
            setattr(self, key, value)


class StubOperatorProperties:
    pass


class OverdrawHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overdraw = importlib.import_module(cats_module_name() + ".tools.overdraw")

    def test_separator_is_absent_in_this_profile(self):
        self.assertFalse(self.overdraw.is_available())

    def test_read_status_returns_payload_dict(self):
        payload = {"api_version": "1.2", "code": "ANALYSIS_COMPLETE", "message": "Done"}
        self.assertEqual(
            payload, self.overdraw.read_status(StubApiState(json.dumps(payload)))
        )

    def test_read_status_returns_none_for_unusable_input(self):
        for raw in ("", "{", "not json", "[]", "null", '"text"', None):
            with self.subTest(raw=raw):
                self.assertIsNone(self.overdraw.read_status(StubApiState(raw)))

    def test_read_status_returns_none_when_property_absent(self):
        self.assertIsNone(self.overdraw.read_status(object()))
        self.assertIsNone(self.overdraw.read_status(None))

    def test_status_message_returns_message(self):
        raw = json.dumps({"code": "ANALYSIS_COMPLETE", "message": "3 materials"})
        self.assertEqual("3 materials", self.overdraw.status_message(StubApiState(raw)))

    def test_status_message_suppresses_unqueried_and_blank(self):
        cases = (
            {"code": "NOT_QUERIED", "message": "nothing yet"},
            {"code": "ANALYSIS_COMPLETE", "message": "   "},
            {"code": "ANALYSIS_COMPLETE"},
            {"message": "no code"},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    self.overdraw.status_message(StubApiState(json.dumps(payload)))
                )

    def test_overrides_json_defaults_to_empty_list(self):
        self.assertEqual("[]", self.overdraw.overrides_json(None))
        self.assertEqual("[]", self.overdraw.overrides_json(StubSettings()))

    def test_overrides_json_mirrors_the_separator_payload(self):
        settings = StubSettings(overrides=[
            StubOverride(StubNamed("Hair"), StubNamed("hair.png")),
            StubOverride(None),
        ])
        self.assertEqual(
            [{
                "address_mode": "CLIP",
                "image_channel": "RED",
                "image_name": "hair.png",
                "material_name": "Hair",
                "uv_map_name": "UVMap",
            }],
            json.loads(self.overdraw.overrides_json(settings)),
        )

    def test_overrides_json_forces_alpha_channel_without_an_image(self):
        settings = StubSettings(overrides=[StubOverride(StubNamed("Lace"))])
        entry = json.loads(self.overdraw.overrides_json(settings))[0]
        self.assertEqual("ALPHA", entry["image_channel"])
        self.assertEqual("", entry["image_name"])

    def test_configure_analysis_sets_api_major_and_overrides(self):
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, None)
        self.assertEqual(1, props.api_major)
        self.assertEqual("[]", props.material_overrides_json)

    def test_configure_analysis_copies_tuning_settings(self):
        settings = StubSettings(
            address_mode="MIRROR", alpha_threshold=0.5, min_affected_texels=4,
            min_affected_fraction=0.25, margin_texels=2, max_scanlines=1234,
            max_run_emissions=99,
        )
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, settings)
        self.assertEqual("MIRROR", props.address_mode)
        self.assertEqual(0.5, props.alpha_threshold)
        self.assertEqual(4, props.min_affected_texels)
        self.assertEqual(0.25, props.min_affected_fraction)
        self.assertEqual(2, props.margin_texels)
        self.assertEqual(1234, props.max_scanlines)
        self.assertEqual(99, props.max_run_emissions)

    def test_configure_analysis_skips_settings_it_cannot_read(self):
        props = StubOperatorProperties()
        self.overdraw.configure_analysis(props, StubSettings(alpha_threshold=0.75))
        self.assertEqual(0.75, props.alpha_threshold)
        self.assertFalse(hasattr(props, "address_mode"))


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OverdrawHelperTests)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the test to verify it fails**

Build and install per "Running tests", then:

```bash
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/overdraw_smoke.py
```

Expected: FAIL. `ModuleNotFoundError: No module named 'bl_ext...cats_blender_plugin.tools.overdraw'`.

- [ ] **Step 3: Write the minimal implementation**

Create `tools/overdraw.py`:

```python
# MIT License

import json

import bpy


SEPARATOR_OPERATOR_NAMESPACE = "alpha_material_separator"
SEPARATOR_API_PROPERTY = "alpha_material_separator_api"
SEPARATOR_SETTINGS_PROPERTY = "alpha_material_separator_settings"

# analyze() checks this against its own API_VERSION[0] and refuses a mismatch.
SEPARATOR_API_MAJOR = 1

# analyze() reads these from its own operator properties, never from the
# separator's settings, so CATS has to copy them across. image_name, uv_map_name,
# and image_channel are omitted on purpose: the separator's own panel leaves them
# at the operator defaults ("", "", "ALPHA").
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
```

- [ ] **Step 4: Run the test to verify it passes**

Rebuild, reinstall, and rerun the command from Step 2.
Expected: PASS, 12 tests.

- [ ] **Step 5: Add the CI step**

In `.github/workflows/Cats Tests.yml`, immediately after the "Exercise Pose Mode reset controls" step:

```yaml
      - name: Exercise Overdraw Prevention helpers
        run: >-
          $BLENDER_BIN --background --offline-mode -noaudio
          --python-exit-code 1 --python tests/overdraw_smoke.py
```

- [ ] **Step 6: Commit**

```bash
git add tools/overdraw.py tests/overdraw_smoke.py ".github/workflows/Cats Tests.yml"
git diff --check
git commit -m "feat: add Alpha Material Separator detection and status helpers"
```

---

### Task 2: The download and help operators

**Files:**
- Modify: `tools/overdraw.py` (append)
- Modify: `tests/overdraw_smoke.py` (add a second test case class)
- Modify: `resources/translations/en_US.json`, `ja_JP.json`, `ko_KR.json`, `zh_CN.json`

**Interfaces:**
- Consumes: nothing from Task 1's helpers.
- Produces, used by Task 3: `DownloadSeparatorButton` and `OverdrawHelpButton`, both with a `bl_idname` attribute.

- [ ] **Step 1: Write the failing test**

Append to `tests/overdraw_smoke.py`, and add the class to `main()`:

```python
class OverdrawOperatorTests(unittest.TestCase):
    def test_cats_overdraw_operators_are_registered(self):
        for name in ("download_separator", "help"):
            with self.subTest(operator=name):
                self.assertTrue(hasattr(bpy.ops.cats_overdraw, name))
                self.assertIsNotNone(
                    getattr(bpy.ops.cats_overdraw, name).get_rna_type()
                )

    def test_operator_urls_point_at_the_separator_repository(self):
        translations = importlib.import_module(
            cats_module_name() + ".tools.translations"
        )
        for key in ("DownloadSeparatorButton.URL", "OverdrawHelpButton.URL"):
            with self.subTest(key=key):
                self.assertIn(
                    "github.com/Alrauna/blender-alpha-material-separator",
                    translations.t(key),
                )
```

Update `main()` to run both classes:

```python
def main() -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([
        loader.loadTestsFromTestCase(OverdrawHelperTests),
        loader.loadTestsFromTestCase(OverdrawOperatorTests),
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1
```

- [ ] **Step 2: Run the test to verify it fails**

Rebuild, reinstall, rerun.
Expected: FAIL with `AttributeError` on `bpy.ops.cats_overdraw`.

- [ ] **Step 3: Write the minimal implementation**

Add to the imports at the top of `tools/overdraw.py`:

```python
import webbrowser

from .register import register_wrap
from .translations import t
```

Append to `tools/overdraw.py`:

```python
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
```

- [ ] **Step 4: Add the translation keys**

Insert into the `messages` object of all four translation files. English:

```json
"DownloadSeparatorButton.label": "Download Alpha Material Separator",
"DownloadSeparatorButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator/releases/latest",
"DownloadSeparatorButton.success": "Alpha Material Separator releases opened",
"DownloadSeparatorButton.dialog": "This will open Alpha Material Separator releases:",
"DownloadSeparatorButton.confirm": "Click OK to open, or Cancel to visit manually.",
"OverdrawHelpButton.label": "About Overdraw Prevention",
"OverdrawHelpButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator",
"OverdrawHelpButton.success": "Alpha Material Separator page opened",
```

`ja_JP.json`:

```json
"DownloadSeparatorButton.label": "Alpha Material Separator をダウンロード",
"DownloadSeparatorButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator/releases/latest",
"DownloadSeparatorButton.success": "Alpha Material Separator のリリースを開きました",
"DownloadSeparatorButton.dialog": "Alpha Material Separator のリリースを開きます:",
"DownloadSeparatorButton.confirm": "OK で開き、キャンセルで手動アクセスします。",
"OverdrawHelpButton.label": "オーバードロー対策について",
"OverdrawHelpButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator",
"OverdrawHelpButton.success": "Alpha Material Separator のページを開きました",
```

`ko_KR.json`:

```json
"DownloadSeparatorButton.label": "Alpha Material Separator 다운로드",
"DownloadSeparatorButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator/releases/latest",
"DownloadSeparatorButton.success": "Alpha Material Separator 릴리스를 열었습니다",
"DownloadSeparatorButton.dialog": "Alpha Material Separator 릴리스를 엽니다:",
"DownloadSeparatorButton.confirm": "확인을 누르면 열리고, 취소하면 직접 방문합니다.",
"OverdrawHelpButton.label": "오버드로 방지 정보",
"OverdrawHelpButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator",
"OverdrawHelpButton.success": "Alpha Material Separator 페이지를 열었습니다",
```

`zh_CN.json`:

```json
"DownloadSeparatorButton.label": "下载 Alpha Material Separator",
"DownloadSeparatorButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator/releases/latest",
"DownloadSeparatorButton.success": "已打开 Alpha Material Separator 发布页",
"DownloadSeparatorButton.dialog": "将打开 Alpha Material Separator 发布页：",
"DownloadSeparatorButton.confirm": "点击确定打开，或取消后手动访问。",
"OverdrawHelpButton.label": "关于过度绘制优化",
"OverdrawHelpButton.URL": "https://github.com/Alrauna/blender-alpha-material-separator",
"OverdrawHelpButton.success": "已打开 Alpha Material Separator 页面",
```

Then confirm every file is still valid JSON and has the keys:

```bash
PYTHONIOENCODING=utf-8 python -c "
import json,glob,os
for f in sorted(glob.glob('resources/translations/*.json')):
    m=json.load(open(f,encoding='utf-8'))['messages']
    missing=[k for k in ('DownloadSeparatorButton.label','DownloadSeparatorButton.URL','DownloadSeparatorButton.success','DownloadSeparatorButton.dialog','DownloadSeparatorButton.confirm','OverdrawHelpButton.label','OverdrawHelpButton.URL','OverdrawHelpButton.success') if k not in m]
    print(os.path.basename(f), 'OK' if not missing else 'MISSING '+repr(missing))"
```

Expected: four `OK` lines.

- [ ] **Step 5: Run the test to verify it passes**

Rebuild, reinstall, rerun. Expected: PASS, 14 tests. Registered CATS classes rises from 135 to 137.

- [ ] **Step 6: Commit**

```bash
git add tools/overdraw.py tests/overdraw_smoke.py resources/translations
git diff --check
git commit -m "feat: add Alpha Material Separator download and help buttons"
```

---

### Task 3: The Overdraw Prevention sub-panel

**Files:**
- Modify: `ui/optimization.py` — add an import near line 11 and a class after `AtlasSubPanel` (which ends around line 281)
- Modify: `tests/extension_smoke.py:16-31`
- Modify: `resources/translations/*.json` (4 files)

**Interfaces:**
- Consumes: from Task 1, `is_available()`, `status_message()`, `configure_analysis()`, `SEPARATOR_API_PROPERTY`, `SEPARATOR_SETTINGS_PROPERTY`; from Task 2, `DownloadSeparatorButton.bl_idname`, `OverdrawHelpButton.bl_idname`.
- Produces: panel `VIEW3D_PT_optimize_overdraw_v3`.

**One addition to the spec.** The spec's Components list names
`OverdrawHelpButton` but never places it. This plan puts it in a credit box above
the status line, mirroring how `AtlasSubPanel` pairs
`t('OptimizePanel.atlasAuthor')` with `Atlas.AtlasHelpButton` at
`ui/optimization.py:202-208`. The box shows in both the AMS-present and
AMS-absent states, so the help link is reachable before installing.

- [ ] **Step 1: Write the failing test**

In `tests/extension_smoke.py`, add to `EXPECTED_OPERATORS`:

```python
    ("cats_overdraw", "download_separator"),
    ("cats_overdraw", "help"),
```

Replace the single `EXPECTED_PANEL` constant with a tuple, then update its test:

```python
EXPECTED_PANELS = (
    "VIEW3D_PT_quickaccess_v3",
    "VIEW3D_PT_optimize_overdraw_v3",
)
```

```python
    def test_expected_panel_and_scene_property_are_registered(self):
        for panel in EXPECTED_PANELS:
            with self.subTest(panel=panel):
                self.assertIsNotNone(getattr(bpy.types, panel, None))
        self.assertIsNotNone(bpy.types.Scene.bl_rna.properties.get(EXPECTED_SCENE_PROPERTY))
```

In `ExtensionAbsentTests.test_registration_surface_was_removed`, replace the
`EXPECTED_PANEL` assertion with:

```python
        for panel in EXPECTED_PANELS:
            with self.subTest(panel=panel):
                self.assertIsNone(getattr(bpy.types, panel, None))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/extension_smoke.py -- --expect-enabled
```

Expected: FAIL on subTest `panel='VIEW3D_PT_optimize_overdraw_v3'`, `assertIsNotNone(None)`.

- [ ] **Step 3: Write the minimal implementation**

Add to the imports in `ui/optimization.py`, after the `atlas` import on line 11:

```python
from ..tools import overdraw as Overdraw
```

Add after `AtlasSubPanel` and before `MaterialSubPanel`:

```python
@register_wrap
class OverdrawSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_overdraw_v3'
    bl_label = t('OptimizePanel.overdraw.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            desc_col = col.column(align=True)
            desc_col.scale_y = 0.75
            desc_col.label(text=t('OptimizePanel.overdrawDesc1'))
            desc_col.label(text=t('OptimizePanel.overdrawDesc2'))

            col.separator()

            box = col.box()
            row = box.row(align=True)
            row.scale_y = 0.75
            split = row.split(factor=0.7)
            split.label(text=t('OptimizePanel.overdrawAuthor'), icon='SHADERFX')
            split.operator(Overdraw.OverdrawHelpButton.bl_idname, text="", icon='QUESTION')

            col.separator()

            if not Overdraw.is_available():
                draw_error_box(col, [
                    t('OptimizePanel.overdrawNotInstalled1'),
                    t('OptimizePanel.overdrawNotInstalled2'),
                ])
                col.separator()
                row = col.row(align=True)
                row.scale_y = 1.3
                row.operator(Overdraw.DownloadSeparatorButton.bl_idname, icon=globs.ICON_URL)
                return

            window_manager = context.window_manager
            message = Overdraw.status_message(
                getattr(window_manager, Overdraw.SEPARATOR_API_PROPERTY, None)
            )
            if message:
                status_col = col.box().column(align=True)
                status_col.scale_y = 0.75
                status_col.label(text=message, icon='INFO')
                col.separator()

            settings = getattr(window_manager, Overdraw.SEPARATOR_SETTINGS_PROPERTY, None)

            actions = col.column(align=True)
            actions.scale_y = 1.3
            Overdraw.configure_analysis(
                actions.operator(
                    'alpha_material_separator.analyze',
                    text=t('OptimizePanel.overdrawAnalyze'),
                    icon='VIEWZOOM',
                ),
                settings,
            )
            actions.operator(
                'alpha_material_separator.select_faces',
                text=t('OptimizePanel.overdrawPreview'),
                icon='RESTRICT_SELECT_OFF',
            )
            actions.operator(
                'alpha_material_separator.assign_materials',
                text=t('OptimizePanel.overdrawApply'),
                icon='MATERIAL',
            )

            col.separator()

            clear = col.column(align=True)
            clear.operator(
                'alpha_material_separator.clear_results',
                text=t('OptimizePanel.overdrawClear'),
                icon='X',
            )

            col.separator()

            note_col = col.column(align=True)
            note_col.scale_y = 0.75
            note_col.label(text=t('OptimizePanel.overdrawExpertNote'))

        except Exception:
            draw_error_box(col, [t('OptimizePanel.overdrawInterfaceError')])
```

- [ ] **Step 4: Add the translation keys**

Insert into all four files. English:

```json
"OptimizePanel.overdraw.label": "Overdraw Prevention",
"OptimizePanel.overdrawDesc1": "Moves alpha-covered faces onto their own material",
"OptimizePanel.overdrawDesc2": "so solid faces stop paying the transparency cost.",
"OptimizePanel.overdrawAuthor": "Uses Alpha Material Separator",
"OptimizePanel.overdrawNotInstalled1": "Alpha Material Separator is not installed.",
"OptimizePanel.overdrawNotInstalled2": "Install it to use Overdraw Prevention.",
"OptimizePanel.overdrawAnalyze": "Analyze Selected Meshes",
"OptimizePanel.overdrawPreview": "Preview Faces to Move",
"OptimizePanel.overdrawApply": "Apply Material Separation",
"OptimizePanel.overdrawClear": "Clear Results",
"OptimizePanel.overdrawExpertNote": "Expert options are in the AMS tab.",
"OptimizePanel.overdrawInterfaceError": "Could not draw Overdraw Prevention. Use the AMS tab.",
```

`ja_JP.json`:

```json
"OptimizePanel.overdraw.label": "オーバードロー対策",
"OptimizePanel.overdrawDesc1": "アルファのある面を専用マテリアルへ移動し、",
"OptimizePanel.overdrawDesc2": "不透明な面の透過コストを削減します。",
"OptimizePanel.overdrawAuthor": "Alpha Material Separator を使用",
"OptimizePanel.overdrawNotInstalled1": "Alpha Material Separator がインストールされていません。",
"OptimizePanel.overdrawNotInstalled2": "使用するにはインストールしてください。",
"OptimizePanel.overdrawAnalyze": "選択メッシュを解析",
"OptimizePanel.overdrawPreview": "移動する面をプレビュー",
"OptimizePanel.overdrawApply": "マテリアル分離を適用",
"OptimizePanel.overdrawClear": "結果をクリア",
"OptimizePanel.overdrawExpertNote": "詳細設定は AMS タブにあります。",
"OptimizePanel.overdrawInterfaceError": "オーバードロー対策を描画できません。AMS タブを使用してください。",
```

`ko_KR.json`:

```json
"OptimizePanel.overdraw.label": "오버드로 방지",
"OptimizePanel.overdrawDesc1": "알파가 있는 면만 별도 머티리얼로 옮겨",
"OptimizePanel.overdrawDesc2": "불투명한 면의 투명 처리 비용을 줄입니다.",
"OptimizePanel.overdrawAuthor": "Alpha Material Separator 사용",
"OptimizePanel.overdrawNotInstalled1": "Alpha Material Separator가 설치되지 않았습니다.",
"OptimizePanel.overdrawNotInstalled2": "사용하려면 설치하세요.",
"OptimizePanel.overdrawAnalyze": "선택한 메시 분석",
"OptimizePanel.overdrawPreview": "이동할 면 미리보기",
"OptimizePanel.overdrawApply": "머티리얼 분리 적용",
"OptimizePanel.overdrawClear": "결과 지우기",
"OptimizePanel.overdrawExpertNote": "고급 옵션은 AMS 탭에 있습니다.",
"OptimizePanel.overdrawInterfaceError": "오버드로 방지를 그릴 수 없습니다. AMS 탭을 사용하세요.",
```

`zh_CN.json`:

```json
"OptimizePanel.overdraw.label": "过度绘制优化",
"OptimizePanel.overdrawDesc1": "将带 Alpha 的面移到单独材质，",
"OptimizePanel.overdrawDesc2": "使不透明面不再承担透明开销。",
"OptimizePanel.overdrawAuthor": "使用 Alpha Material Separator",
"OptimizePanel.overdrawNotInstalled1": "未安装 Alpha Material Separator。",
"OptimizePanel.overdrawNotInstalled2": "请安装后再使用过度绘制优化。",
"OptimizePanel.overdrawAnalyze": "分析所选网格",
"OptimizePanel.overdrawPreview": "预览待移动的面",
"OptimizePanel.overdrawApply": "应用材质分离",
"OptimizePanel.overdrawClear": "清除结果",
"OptimizePanel.overdrawExpertNote": "高级选项位于 AMS 选项卡。",
"OptimizePanel.overdrawInterfaceError": "无法绘制过度绘制优化，请使用 AMS 选项卡。",
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/extension_smoke.py -- --expect-enabled
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/overdraw_smoke.py
"$B" --command extension remove cats_blender_plugin
"$B" --background --offline-mode -noaudio --python-exit-code 1 --python tests/extension_smoke.py -- --expect-absent
```

Expected: all PASS. Registered CATS classes is 138. Reinstall before continuing.

- [ ] **Step 6: Commit**

```bash
git add ui/optimization.py tests/extension_smoke.py resources/translations
git diff --check
git commit -m "feat: add the Overdraw Prevention panel to Optimization"
```

---

### Task 4: Documentation, full validation, and milestone close-out

**Files:**
- Modify: `README.md` — the "Optional dependencies" list
- Modify: `docs/HANDOFF.md`
- Delete: `docs/superpowers/specs/2026-08-07-overdraw-prevention-design.md`, `docs/superpowers/plans/2026-08-07-overdraw-prevention.md`

- [ ] **Step 1: Add AMS to the README's optional dependencies**

This is an addition beyond the spec's Components table. It is required for
correctness: the README lists optional dependencies and would be wrong without
AMS. Insert after the Immersive Scaler bullet:

```markdown
- **Alpha Material Separator**, for Overdraw Prevention:
  [Alrauna/blender-alpha-material-separator](https://github.com/Alrauna/blender-alpha-material-separator)
```

- [ ] **Step 2: Verify every new URL resolves**

```bash
python - <<'EOF'
import urllib.request
for u in ("https://github.com/Alrauna/blender-alpha-material-separator",
          "https://github.com/Alrauna/blender-alpha-material-separator/releases/latest"):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "link-check"}), timeout=30) as r:
            print(r.status, u)
    except Exception as e:
        print("FAIL", u, type(e).__name__, e)
EOF
```

Expected: two `200` lines. If `releases/latest` 404s because AMS has published no
release, stop and ask the maintainer whether the download button should point at
the repository root instead.

- [ ] **Step 3: Run the whole gate**

```bash
python -W ignore::SyntaxWarning -m compileall -q -f __init__.py globs.py extentions.py updater.py tools ui extern_tools tests scripts
python scripts/build.py --blend "$B"
```

Then install the fresh build into the isolated profile and run, expecting all
green: `extension_smoke.py --expect-enabled`, `blender_52_api_smoke.py`,
`pose_mode_smoke.py`, `overdraw_smoke.py`, `import_sweep.py`,
`lifecycle_stress.py`, the 13 armature invocations, the shape-key suite, then
`extension remove` and `extension_smoke.py --expect-absent`.

- [ ] **Step 4: Update the handoff**

In `docs/HANDOFF.md`, record the new panel, that AMS is an external optional
dependency detected by operator ID, and under Outstanding:

- The AMS-present path is manual-only. CI installs CATS alone, so the four
  buttons and the status line are never exercised automatically.
- `ja_JP`, `ko_KR`, and `zh_CN` Overdraw Prevention strings need native review.
- CATS mirrors seven `analyze` operator properties plus the override payload.
  These are not part of `api_contract.py`, so an AMS release that renames one
  needs a matching CATS change. `api_major` is the guard.

- [ ] **Step 5: Retire the spec and plan**

```bash
git rm docs/superpowers/specs/2026-08-07-overdraw-prevention-design.md \
       docs/superpowers/plans/2026-08-07-overdraw-prevention.md
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/HANDOFF.md
git diff --check
git commit -m "docs: document Overdraw Prevention and retire its planning docs"
```

- [ ] **Step 7: Report, do not merge**

Report the built package path and SHA-256, and state plainly that the AMS-present
workflow is unverified pending maintainer testing. Do not merge into `main` or
push unless the maintainer asks.

---

## Manual test script for the maintainer

CI cannot cover these. With AMS installed:

1. Open the CATS tab, expand **Optimization**. **Overdraw Prevention** sits
   between Atlas and Material.
2. Disable AMS. The panel shows the install prompt and the download button, and
   the four action buttons disappear.
3. Re-enable AMS. The action buttons return.
4. Select a mesh with a partly transparent texture, click **Analyze Selected
   Meshes**. A status line appears with AMS's own message.
5. Click **Preview Faces to Move**, confirm Edit Mode opens with faces selected.
6. Click **Apply Material Separation**, confirm the `__AMS_ALPHA` material appears
   and the confirmation dialog was shown.
7. Change a threshold in the **AMS** tab's expert settings, rerun Analyze from the
   CATS panel, and confirm the result reflects the changed setting. This is the
   check that the seven mirrored properties actually work.
8. Add a manual alpha source in the AMS tab, rerun Analyze from CATS, and confirm
   the override is honoured. This checks the override payload.
9. Click **Clear Results**, confirm the status line disappears.
