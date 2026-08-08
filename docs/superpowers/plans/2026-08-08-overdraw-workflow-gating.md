# Overdraw Prevention Workflow Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw the Overdraw Prevention panel's Preview, Apply, and Clear buttons only
when the Alpha Material Separator says they will work, and surface the separator's
staleness warning, by reading its published `workflow_json` instead of inferring state
from status codes.

**Architecture:** Separator 1.3.0 publishes
`WindowManager.alpha_material_separator_api.workflow_json`, a computed `get=` property
carrying the same workflow snapshot its own panel draws from — `can_analyze`,
`can_preview`, `can_apply`, `stale`, `analysis_id` and nine more fields. CATS reads that
one property and mirrors the separator's gating exactly, replacing the current
hardcoded status-code heuristic. The separator also now publishes a `severity` field in
every status payload, so CATS stops carrying its own list of which codes are serious.

**Tech Stack:** Blender 5.2 LTS Python API, `bpy`, `unittest` in Blender background mode.

## Global Constraints

- Separator minimum is **1.3.0**, whose `API_VERSION` is `(1, 3)`. `README.md` states it.
- No fallback nudge when `workflow_json` is absent: an older separator gets today's
  behavior — every button drawn — and no new user-facing string.
- **No new translation strings.** No `resources/translations.json` change in this plan.
- Never import separator code. Read only published operator IDs and RNA property names.
- `SEPARATOR_API_MAJOR` stays `1`. The separator's `analyze` still checks `api_major`
  against `API_VERSION[0]`, which is unchanged at 1, so the handshake keeps working.
- CATS never composes status text. Status wording comes from the separator's `message`.
- Branch: this work stays on `feature/overdraw-prevention`. It repairs behavior that
  branch shipped in `3a1379b` and completes the same panel's workflow.
- Test runs must sync the working tree into the installed extension first, or
  `tests/overdraw_smoke.py` imports a stale copy and reports a false pass.

---

### Task 1: Read the published workflow state and status severity

**Files:**
- Modify: `tools/overdraw.py:77-88` (delete `ACTIONABLE_STATUS_CODES` and
  `status_is_actionable`, add `workflow_state` and `status_severity`)
- Test: `tests/overdraw_smoke.py:28-31, 99-117`

**Interfaces:**
- Consumes: `read_status(api_state)`, already in `tools/overdraw.py:48`.
- Produces:
  - `workflow_state(api_state) -> dict | None` — the parsed `workflow_json`, or `None`
    when the property is absent or unusable.
  - `status_severity(api_state) -> str` — the published `severity`, defaulting to
    `"OK"` when there is no payload or no severity field.
  - Deletes `status_is_actionable` and `ACTIONABLE_STATUS_CODES`. Task 2 is the only
    caller.

- [ ] **Step 1: Extend the test stub to carry the new properties**

In `tests/overdraw_smoke.py`, replace `StubApiState` (lines 28-31):

```python
class StubApiState:
    def __init__(self, last_status_json="", workflow_json=None):
        self.last_status_json = last_status_json
        if workflow_json is not None:
            self.workflow_json = workflow_json
```

`workflow_json` is set only when supplied, so the default stub reproduces a separator
that does not publish it.

- [ ] **Step 2: Write the failing tests**

In `tests/overdraw_smoke.py`, replace the three `status_is_actionable` tests
(lines 99-117) with:

```python
    def test_workflow_state_returns_the_published_payload(self):
        payload = {
            "api_version": "1.3",
            "state": "READY_TO_REVIEW",
            "can_preview": True,
            "can_apply": True,
            "stale": False,
            "analysis_id": "abc123",
        }
        self.assertEqual(
            payload,
            self.overdraw.workflow_state(StubApiState(workflow_json=json.dumps(payload))),
        )

    def test_workflow_state_returns_none_for_unusable_input(self):
        for raw in ("", "not json", "[]", "null", '"text"'):
            with self.subTest(raw=raw):
                self.assertIsNone(
                    self.overdraw.workflow_state(StubApiState(workflow_json=raw))
                )

    def test_workflow_state_returns_none_when_the_property_is_absent(self):
        self.assertIsNone(self.overdraw.workflow_state(StubApiState()))
        self.assertIsNone(self.overdraw.workflow_state(None))

    def test_status_severity_returns_the_published_severity(self):
        for severity in ("OK", "INFO", "ERROR"):
            with self.subTest(severity=severity):
                raw = json.dumps({"code": "ANY", "message": "m", "severity": severity})
                self.assertEqual(
                    severity, self.overdraw.status_severity(StubApiState(raw))
                )

    def test_status_severity_defaults_to_ok(self):
        self.assertEqual("OK", self.overdraw.status_severity(StubApiState("")))
        self.assertEqual("OK", self.overdraw.status_severity(None))
        raw = json.dumps({"code": "ANALYSIS_COMPLETE", "message": "m"})
        self.assertEqual("OK", self.overdraw.status_severity(StubApiState(raw)))
```

The last assertion matters: a separator older than 1.3.0 publishes no `severity`, and
defaulting to `"OK"` keeps its status in the plain info box rather than reddening every
line.

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cp -r tools ui tests .test-runtime/claude-ams-130/extensions/user_default/cats_blender_plugin/
BLENDER_USER_RESOURCES="$(pwd)/.test-runtime/claude-ams-130" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tests/overdraw_smoke.py
```

Expected: FAIL, `AttributeError: module ... has no attribute 'workflow_state'`.

- [ ] **Step 4: Write the implementation**

In `tools/overdraw.py`, delete lines 77-88 — the `ACTIONABLE_STATUS_CODES` comment
block, the constant, and all of `status_is_actionable` — and put this in their place:

```python
def status_severity(api_state):
    """Return the separator's own severity for its last status.

    The separator publishes OK, INFO, or ERROR per status code and classifies
    unknown codes as ERROR itself, so CATS does not keep a code list. A
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
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cp -r tools ui tests .test-runtime/claude-ams-130/extensions/user_default/cats_blender_plugin/
BLENDER_USER_RESOURCES="$(pwd)/.test-runtime/claude-ams-130" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tests/overdraw_smoke.py
```

Expected: PASS, 19 tests. The count moves from 17 to 19: three deleted, five added.

- [ ] **Step 6: Commit**

```bash
git add tools/overdraw.py tests/overdraw_smoke.py
git commit -m "feat: read the separator's published workflow state and status severity"
```

---

### Task 2: Gate the panel's buttons on the published state

**Files:**
- Modify: `ui/optimization.py:324-366`

**Interfaces:**
- Consumes: `Overdraw.workflow_state`, `Overdraw.status_severity` from Task 1;
  `Overdraw.status_message`, `Overdraw.configure_analysis`,
  `Overdraw.SEPARATOR_API_PROPERTY`, `Overdraw.SEPARATOR_SETTINGS_PROPERTY`, all
  already present; `draw_error_box` from `ui/main.py`, already imported at the top of
  this file.
- Produces: nothing other tasks consume.

Gating rules, mirroring `presentation.py:369-370` and the separator panel's
`if current_report:` block:

| Element | Drawn when |
| --- | --- |
| Analyze | always |
| Preview | `can_preview` |
| Apply | `can_apply` |
| Clear | `analysis_id` is non-empty |
| Stale error box | `stale` |

When `workflow_state()` returns `None` — a separator older than 1.3.0 — every element
draws, which is exactly the current behavior.

- [ ] **Step 1: Replace the status block and the action block**

In `ui/optimization.py`, replace lines 324-366 (from `window_manager = context.window_manager`
through the closing paren of the `clear.operator(...)` call) with:

```python
            window_manager = context.window_manager
            api_state = getattr(window_manager, Overdraw.SEPARATOR_API_PROPERTY, None)
            workflow = Overdraw.workflow_state(api_state)
            # No published workflow means a separator older than 1.3.0. Draw every
            # button, which is what CATS did before the separator published gating.
            stale = bool(workflow.get('stale')) if workflow else False
            show_preview = workflow.get('can_preview', True) if workflow else True
            show_apply = workflow.get('can_apply', True) if workflow else True
            show_clear = bool(workflow.get('analysis_id')) if workflow else True

            message = Overdraw.status_message(api_state)
            if message:
                # The separator files RESULT_STALE as INFO because its own panel
                # signals staleness in the step it blocks, not in the status line.
                # CATS has no such step, so a stale result is raised to an error box.
                if stale or Overdraw.status_severity(api_state) == 'ERROR':
                    draw_error_box(col, [message])
                else:
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
            if show_preview:
                actions.operator(
                    'alpha_material_separator.select_faces',
                    text=t('OptimizePanel.overdrawPreview'),
                    icon='RESTRICT_SELECT_OFF',
                )
            if show_apply:
                actions.operator(
                    'alpha_material_separator.assign_materials',
                    text=t('OptimizePanel.overdrawApply'),
                    icon='MATERIAL',
                )

            if show_clear:
                col.separator()
                clear = col.column(align=True)
                clear.operator(
                    'alpha_material_separator.clear_results',
                    text=t('OptimizePanel.overdrawClear'),
                    icon='X',
                )
```

Leave lines 368-375 — the `col.separator()`, the expert note, and the `except Exception`
handler — untouched.

- [ ] **Step 2: Verify the module still compiles**

```bash
python -W ignore::SyntaxWarning -m compileall -q -f ui/optimization.py tools/overdraw.py
```

Expected: no output.

- [ ] **Step 3: Verify the panel still registers and draws without the separator**

```bash
cp -r tools ui tests .test-runtime/claude-ams-130/extensions/user_default/cats_blender_plugin/
BLENDER_USER_RESOURCES="$(pwd)/.test-runtime/claude-ams-130" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tests/overdraw_smoke.py
```

Expected: PASS, 19 tests, including
`test_separator_is_absent_in_this_profile` — the separator-absent branch returns before
any of the new code.

- [ ] **Step 4: Commit**

```bash
git add ui/optimization.py
git commit -m "feat: draw Preview and Apply only when the separator accepts them"
```

---

### Task 3: Prove the gating against the real separator 1.3.0

**Files:**
- Create: `tests/overdraw_workflow_probe.py`

This is a repository test, not a scratchpad probe, because it converts the defect into
permanent institutional knowledge. It is skipped rather than failed when the separator
is absent, so it is safe for CI to run in the CATS-only profile.

**Interfaces:**
- Consumes: `tools/overdraw.py`'s `workflow_state`, `status_severity`, `status_message`,
  `configure_analysis`, `is_available`.
- Produces: nothing other tasks consume.

- [ ] **Step 1: Write the test**

Create `tests/overdraw_workflow_probe.py`:

```python
# GPL License

"""Prove CATS mirrors the separator's own Preview and Apply gating.

Skipped when the separator is absent, so the CATS-only CI profile stays green.
Run it in a profile with Alpha Material Separator 1.3.0 or newer installed to
exercise the integration for real.

Regression cover for the defect where CATS read only last_status_code: the
separator's depsgraph path publishes no status, so a stale-looking success text
stayed on screen while Preview silently returned CANCELLED.
"""

from __future__ import annotations

import importlib
import sys
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


class ShimOperatorProperties:
    """Stands in for the property group layout.operator() returns."""

    def __init__(self):
        self._values = {}

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._values[name] = value

    def kwargs(self):
        return dict(self._values)


def build_alpha_scene():
    """One grid with a half-transparent image driving Principled Alpha."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)

    image = bpy.data.images.new("overdraw_probe", 64, 64, alpha=True)
    pixels = []
    for _row in range(64):
        for column in range(64):
            pixels.extend((1.0, 1.0, 1.0, 0.0 if column < 32 else 1.0))
    image.pixels[:] = pixels

    material = bpy.data.materials.new("overdraw_probe_mat")
    material.use_nodes = True
    material.blend_method = "BLEND"
    nodes = material.node_tree.nodes
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    material.node_tree.links.new(
        texture.outputs["Alpha"], nodes["Principled BSDF"].inputs["Alpha"]
    )

    bpy.ops.mesh.primitive_grid_add(x_subdivisions=2, y_subdivisions=2)
    obj = bpy.context.active_object
    obj.data.materials.append(material)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


class OverdrawWorkflowGatingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overdraw = importlib.import_module(cats_module_name() + ".tools.overdraw")
        if not cls.overdraw.is_available():
            raise unittest.SkipTest("Alpha Material Separator is not installed")
        cls.window_manager = bpy.context.window_manager
        cls.api_state = getattr(
            cls.window_manager, cls.overdraw.SEPARATOR_API_PROPERTY
        )
        cls.settings = getattr(
            cls.window_manager, cls.overdraw.SEPARATOR_SETTINGS_PROPERTY
        )

    def setUp(self):
        self.obj = build_alpha_scene()

    def analyze(self):
        props = ShimOperatorProperties()
        self.overdraw.configure_analysis(props, self.settings)
        self.assertEqual(
            {"FINISHED"}, bpy.ops.alpha_material_separator.analyze(**props.kwargs())
        )

    def view(self):
        state = self.overdraw.workflow_state(self.api_state)
        self.assertIsNotNone(
            state, "separator 1.3.0 or newer must publish workflow_json"
        )
        return state

    def test_preview_and_apply_are_gated_off_before_any_analysis(self):
        bpy.ops.alpha_material_separator.clear_results()
        view = self.view()
        self.assertFalse(view["can_preview"])
        self.assertFalse(view["can_apply"])
        self.assertEqual("", view["analysis_id"])

    def test_preview_and_apply_open_after_analysis(self):
        self.analyze()
        view = self.view()
        self.assertTrue(view["can_preview"])
        self.assertTrue(view["can_apply"])
        self.assertFalse(view["stale"])
        self.assertNotEqual("", view["analysis_id"])

    def test_a_settings_change_closes_preview_and_reports_stale(self):
        self.analyze()
        original = self.settings.alpha_threshold
        try:
            self.settings.alpha_threshold = 0.5
            view = self.view()
            self.assertTrue(view["stale"])
            self.assertFalse(view["can_preview"])
            self.assertFalse(view["can_apply"])
            self.assertTrue(self.overdraw.status_message(self.api_state))
        finally:
            self.settings.alpha_threshold = original

    def test_a_mesh_edit_does_not_falsely_close_preview(self):
        """The depsgraph path publishes no status and is not proof of staleness.

        The separator resolves RECHECK_PENDING on the next action, so CATS must
        not hide Preview here or a mode switch would blank the panel.
        """
        self.analyze()
        self.obj.data.vertices[0].co.x += 0.25
        self.obj.data.update()
        bpy.context.view_layer.update()
        view = self.view()
        self.assertEqual("RECHECK_PENDING", view["validation_state"])
        self.assertTrue(view["can_preview"])


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(
        unittest.defaultTestLoader.loadTestsFromTestCase(
            OverdrawWorkflowGatingTests
        )
    )
    sys.exit(0 if result.wasSuccessful() else 1)
```

- [ ] **Step 2: Run it in the separator profile and verify it passes**

```bash
cp -r tools ui tests .test-runtime/claude-ams-130/extensions/user_default/cats_blender_plugin/
BLENDER_USER_RESOURCES="$(pwd)/.test-runtime/claude-ams-130" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tests/overdraw_workflow_probe.py
```

Expected: PASS, 4 tests. If `test_a_mesh_edit_does_not_falsely_close_preview` reports
`CLEAN` rather than `RECHECK_PENDING`, the separator coalesced the depsgraph update
differently — check the separator's handler before changing the assertion.

- [ ] **Step 3: Verify it skips cleanly with no separator installed**

```bash
BLENDER_USER_RESOURCES="$(pwd)/.test-runtime/claude-final3" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python tests/overdraw_workflow_probe.py
```

Expected: exit 0, reported as skipped. If that profile no longer has CATS enabled,
build a fresh CATS-only profile with
`blender -b --factory-startup --command extension install-file -r user_default -e <cats zip>`.

- [ ] **Step 4: Commit**

```bash
git add tests/overdraw_workflow_probe.py
git commit -m "test: cover the separator workflow gating CATS now mirrors"
```

---

### Task 4: Documentation, full change gate, close out the milestone

**Files:**
- Modify: `README.md:44-50`
- Modify: `docs/HANDOFF.md:96-112, 118-132`
- Delete: `docs/superpowers/plans/2026-08-08-overdraw-workflow-gating.md`

- [ ] **Step 1: Raise the documented separator minimum to 1.3.0**

In `README.md`, replace lines 44-50 with:

```markdown
- **Alpha Material Separator** 1.3.0 or newer, for Overdraw Prevention:
  [Alrauna/blender-alpha-material-separator](https://github.com/Alrauna/blender-alpha-material-separator)

  Overdraw Prevention reads the separator's published workflow state to decide when
  Preview and Apply are available. Separator 1.2.0 and earlier do not publish it, so
  the panel offers both buttons at all times and the separator refuses them itself.
```

- [ ] **Step 2: Correct the handoff**

In `docs/HANDOFF.md`, replace the `### Requires Alpha Material Separator 1.2.0 or newer`
subsection (lines 96-112) with:

```markdown
### Requires Alpha Material Separator 1.3.0 or newer

Separator 1.3.0 publishes `workflow_json` on
`WindowManager.alpha_material_separator_api` — a computed `get=` property carrying the
same workflow snapshot the separator's own panel draws from. `Overdraw.workflow_state()`
reads it, and the panel draws Preview when `can_preview`, Apply when `can_apply`, and
Clear when `analysis_id` is set. Because the separator computes that snapshot once for
both surfaces, CATS's gating cannot drift from what the separator will accept.

1.3.0 also publishes `severity` in every status payload, so CATS no longer keeps its own
list of which status codes are serious. `Overdraw.status_severity()` reads it and
defaults to `OK` when absent.

A stale result is raised to an error box even though the separator files `RESULT_STALE`
as `INFO`. The separator can afford `INFO` because its own panel reddens the step it
blocks; CATS has no equivalent step, so the status line carries the severity instead.

`RECHECK_PENDING` is deliberately not treated as stale. The separator raises it from
depsgraph notifications, which Blender also emits for harmless selection and mode
changes, and resolves it on the next action. Treating it as staleness would blank the
panel on a mode switch.

When `workflow_json` is absent — separator 1.2.0 or earlier — every button draws, which
is what CATS did before this work. There is no upgrade prompt; `README.md` records the
minimum. CATS cannot enforce it: the separator's published extension version derives
from its manifest, and its `api_version` is the only field that distinguishes the
releases.
```

Then replace the AMS-present Outstanding bullet (lines 118-126) with:

```markdown
- Overdraw Prevention is verified in background mode against separator 1.3.0 by
  `tests/overdraw_workflow_probe.py`: gating is off before analysis, open after it,
  closed by a settings change, and correctly left open by a mesh edit. That file skips
  itself when the separator is absent, so CI can run it in the CATS-only profile
  without installing the separator. Still unverified and GUI-only: panel repaint on a
  separator state change, and the download confirmation dialog.
```

- [ ] **Step 3: Run the full change gate**

```bash
python -W ignore::SyntaxWarning -m compileall -q -f __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
```

```bash
cp -r tools ui tests .test-runtime/claude-ams-130/extensions/user_default/cats_blender_plugin/
```

Then, with `BLENDER_USER_RESOURCES` pointed at `.test-runtime/claude-ams-130` and
`blender -b --factory-startup --python <file>`, run in order:
`tests/extension_smoke.py -- --expect-enabled`, `tests/blender_52_api_smoke.py`,
`tests/pose_mode_smoke.py`, `tests/overdraw_smoke.py`,
`tests/overdraw_workflow_probe.py`, `tests/import_sweep.py`,
`tests/lifecycle_stress.py`.

Expected: all PASS, 138 registered classes, `overdraw_smoke` at 19 tests and
`overdraw_workflow_probe` at 4.

Then the armature and shape-key suites. `tests/run.py` is a host-side subprocess
runner, not a `blender --python` script, and it needs both globs — these are the exact
invocations `.github/workflows/Cats Tests.yml:131-143` uses:

```bash
python tests/run.py --blend "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --test "./tests/armatures/*" --bfile "./tests/armatures/armature.*" --ci
```

```bash
python tests/run.py --blend "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --test "./tests/shapekeys/shape_key_to_basis" --bfile "./tests/shapekeys/shapekey.shape_key_to_basis" --ci
```

Expected: 13 armature invocations and 1 shape-key invocation, 0 failures.

- [ ] **Step 4: Review the diff and commit the documentation**

```bash
git diff --check
git status --short
```

`AGENTS.md` stays modified — that is the maintainer's uncommitted work. Do not stage it.

```bash
git add README.md docs/HANDOFF.md
git commit -m "docs: require separator 1.3.0 for Overdraw Prevention gating"
```

- [ ] **Step 5: Retire this plan**

```bash
git rm docs/superpowers/plans/2026-08-08-overdraw-workflow-gating.md
git commit -m "docs: retire the Overdraw workflow gating plan"
```

- [ ] **Step 6: Build the package**

```bash
python scripts/build.py --blend "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --allow-dirty
```

`--allow-dirty` is required only because `AGENTS.md` is modified; it is excluded by
`paths_exclude_pattern`, so the ZIP still matches the commit. Report the final path and
its SHA-256. Leave every existing build in `.packaged-releases/` alone.
