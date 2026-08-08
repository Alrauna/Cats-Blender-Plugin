# Overdraw Prevention: the stale-result gap after Alpha Material Separator 1.2.0

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The defect this plan was originally written for is fixed upstream.
Alpha Material Separator 1.2.0 publishes a `RESULT_STALE` status on every stale
transition, so CATS's existing `status_message()` already surfaces it with no CATS
code change. What remains is to make the panel *look* like a warning when it is
one, correct one stale comment, and record that Overdraw Prevention now requires
the separator at 1.2.0 or newer.

**Tech Stack:** Blender 5.2 LTS extension Python, `bpy.types.Panel`, `unittest`
run inside Blender background mode.

## Why the original plan is retired

Reviewed at `E:/AI/ChatGPT/Codex/Blender Alpha Material Separator` commit
`51a012d`, which is byte-identical to
`.local-references/alpha_material_separator-1.2.0.zip` (verified by `diff -r`;
differences only in `__pycache__`).

`addon/runtime.py` `_sync_public_validation_state()` now ends with:

```python
        if _VALIDATION_STATE == VALIDATION_STALE and state.analysis_id:
            # Published here, not at each call site, so every current and future
            # stale transition carries a status. A consumer must never have to
            # read validation_state to discover that ANALYSIS_COMPLETE is false.
            api_contract.publish_status(
                state,
                "RESULT_STALE",
                "Analysis inputs changed; analyze again before preview or assignment",
                analysis_id=state.analysis_id,
                dirty_reason=_DIRTY_REASON,
            )
```

That is exactly the single-field contract the original Task 1 was written to work
around. `is_result_stale()`, the `validation_state`/`analysis_id` reads, its four
unit tests, and the two `overdrawStale*` translation keys are all retired.

Measured against AMS 1.2.0 + CATS `f8584f2` in `.test-runtime/claude-ams-120`,
with **no CATS change**:

```
analyze                      -> ANALYSIS_COMPLETE  validation_state CLEAN
                                panel: 'Analysis completed; review the report ...'
settings.alpha_threshold=0.5 -> RESULT_STALE       validation_state STALE
                                panel: 'Analysis inputs changed; analyze again
                                        before preview or assignment'
assign_materials             -> {'CANCELLED'}, STALE_ANALYSIS
                                panel: 'Analysis settings changed'
```

Original Task 2's reset-to-defaults half is also retired.
`addon/operators/analyze.py` now carries `options={"SKIP_SAVE"}` on `image_name`,
`uv_map_name`, and `image_channel`, and `addon/panel.py`
`_set_analysis_properties` dropped its three explicit resets because SKIP_SAVE
covers them. Scenario C re-measured: CATS omits all three and the separator no
longer persists them between invocations.

Original Task 2's `is_available()` hardening is dropped as YAGNI. The two
WindowManager properties are registered by one module in one call; there is no
reachable state where `alpha_material_separator_api` exists without
`alpha_material_separator_settings`, and `draw()` already sits inside a
`try`/`except Exception`.

Also fixed upstream, no CATS action needed:

- `api_contract.ANALYSIS_SETTING_NAMES` moved out of `properties.py` and is now
  guarded as public API. Its content is unchanged and still exactly CATS's seven
  `TUNING_PROPERTIES`.
- `api_contract.ADDRESS_MODES` is published unfiltered, so it no longer
  contradicts the `AUTO` default CATS passes through in `overrides_json()`.
- The ESC path publishes `ANALYSIS_CANCELLED` before `_finish_modal()`.
- `RESULT_STALE` is in the separator panel's `normal` set so it does not
  double-alert beside that panel's own stale box. CATS has no such box, which is
  why Task A below still matters on the CATS side.

`API_VERSION` is still `(1, 2)`, so `SEPARATOR_API_MAJOR = 1` is unchanged and
the handshake still passes. That also means the published `api_version` cannot
distinguish separator 1.1.1 from 1.2.0, so version gating from CATS is not
possible — Task B documents the requirement instead.

## Global Constraints

- Target Blender 5.2 LTS; version stays `5.2.0-alpha.1`.
- Never import separator code. Read only public operator IDs and `WindowManager`
  property names, because the separator's module path varies with the repository
  it was installed from.
- CATS never composes separator status text. Only CATS's own strings go through
  `t()`, and any new key must exist in all four catalogues (`en_US`, `ja_JP`,
  `ko_KR`, `zh_CN`) as line-based JSON edits — never re-serialise a catalogue.
  This plan adds no new keys.
- `tools/overdraw.py` is MIT-licensed like the rest of `tools/`; do not add a
  second licence header.
- Do not change operator identifiers, RNA property names, panel identifiers,
  registration order, or public module paths. Registered class count stays 138.
- Run the change gate in an isolated Blender profile under `.test-runtime/`.
  Never use the maintainer's normal Blender profile.
- Build only with `python scripts/build.py --blend <blender>`, which writes to
  `.packaged-releases/`. Leave existing builds in place; they are removed only
  when the maintainer asks.
- Do not merge into `main` or push. Report at the end.

## The test cycle, and why it needs a sync step

`tests/overdraw_smoke.py` resolves CATS through
`bpy.context.preferences.addons`, so it imports the **installed** extension, not
the working tree. Editing `tools/overdraw.py` and running the suite without
copying the file across first reports a false GREEN.

```bash
export BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
export PROFILE="$(pwd)/.test-runtime/claude-stale-fix"
export INSTALLED="$PROFILE/extensions/user_default/cats_blender_plugin"
```

Create the profile once:

```bash
BLENDER_USER_RESOURCES="$PROFILE" "$BL" -b --factory-startup --command extension \
  install-file -r user_default -e .packaged-releases/cats_blender_plugin-5.2.0-alpha.1-f8584f2.zip
```

Every RED/GREEN step is then sync-then-run:

```bash
cp tools/overdraw.py "$INSTALLED/tools/overdraw.py" && \
BLENDER_USER_RESOURCES="$PROFILE" "$BL" -b --python-exit-code 1 --python tests/overdraw_smoke.py
```

When a step touches `ui/optimization.py`, sync that path too.

## File Structure

- `tools/overdraw.py` — gains `ACTIONABLE_STATUS_CODES` and
  `status_is_actionable()`; its `TUNING_PROPERTIES` comment is corrected. Stays a
  single flat module.
- `ui/optimization.py` — `OverdrawSubPanel.draw()` status block only.
- `tests/overdraw_smoke.py` — three new tests in `OverdrawHelperTests`.
- `README.md` — the optional-dependency entry gains a minimum version.
- `docs/HANDOFF.md` — updated at close-out.

No new files, no new translation keys, no manifest change.

## Task A — render an actionable status as a warning, not as INFO

`ui/optimization.py:328-332` draws every separator status in a plain box with
`icon='INFO'`. `RESULT_STALE` and `STALE_ANALYSIS` mean the user must re-run
Analyze before Apply will do anything, yet they render identically to
`ANALYSIS_COMPLETE`. This is the surviving user-visible part of the approved
design; the rest of it moved upstream.

- [ ] **Step A1 — RED.** Add to `OverdrawHelperTests` in
      `tests/overdraw_smoke.py`:

```python
    def test_status_is_actionable_for_stale_codes(self):
        for code in ("RESULT_STALE", "STALE_ANALYSIS"):
            with self.subTest(code=code):
                raw = json.dumps({"code": code, "message": "changed"})
                self.assertTrue(
                    self.overdraw.status_is_actionable(StubApiState(raw))
                )

    def test_status_is_not_actionable_for_normal_codes(self):
        for code in ("ANALYSIS_COMPLETE", "ASSIGNMENT_COMPLETE", "CLEARED"):
            with self.subTest(code=code):
                raw = json.dumps({"code": code, "message": "fine"})
                self.assertFalse(
                    self.overdraw.status_is_actionable(StubApiState(raw))
                )

    def test_status_is_not_actionable_without_a_payload(self):
        self.assertFalse(self.overdraw.status_is_actionable(StubApiState("")))
        self.assertFalse(self.overdraw.status_is_actionable(None))
```

      Sync and run. Expect three failures on a missing `status_is_actionable`.

- [ ] **Step A2 — GREEN.** In `tools/overdraw.py`, after `status_message()`:

```python
# The separator publishes these when a completed report no longer matches the
# scene. Its own panel treats them as normal because it draws a dedicated stale
# box; CATS has no such box, so the status line carries the severity instead.
ACTIONABLE_STATUS_CODES = frozenset({"RESULT_STALE", "STALE_ANALYSIS"})


def status_is_actionable(api_state):
    payload = read_status(api_state)
    if payload is None:
        return False
    return payload.get("code") in ACTIONABLE_STATUS_CODES
```

      Sync and run. Expect all 17 tests green.

- [ ] **Step A3 — wire the panel.** Replace `ui/optimization.py:324-332` with a
      single `api_state` read:

```python
            window_manager = context.window_manager
            api_state = getattr(window_manager, Overdraw.SEPARATOR_API_PROPERTY, None)
            message = Overdraw.status_message(api_state)
            if message:
                if Overdraw.status_is_actionable(api_state):
                    draw_error_box(col, [message])
                else:
                    status_col = col.box().column(align=True)
                    status_col.scale_y = 0.75
                    status_col.label(text=message, icon='INFO')
                col.separator()
```

      `settings = getattr(window_manager, ...)` on the following line is
      unchanged. No new translation keys: the separator supplies the string, as it
      already does for every other status.

- [ ] **Step A4 — integration proof.** Sync `tools/overdraw.py` into
      `.test-runtime/claude-ams-120` (AMS 1.2.0 + CATS `f8584f2`), then run the
      stale probe and assert `status_is_actionable()` returns `True` at the point
      where `status_message()` returns the `RESULT_STALE` text, and `False`
      immediately after a fresh Analyze. Record the output.

## Task B — correct the stale comment and record the version requirement

- [ ] **Step B1.** In `tools/overdraw.py`, replace the `TUNING_PROPERTIES`
      comment. Its current wording claims the separator's panel "leaves them at
      the operator defaults", which was false at 1.1.1 (that panel reset them
      explicitly) and is true at 1.2.0 for a different reason:

```python
# analyze() reads these from its own operator properties, never from the
# separator's settings, so CATS has to copy them across. They mirror
# api_contract.ANALYSIS_SETTING_NAMES, which the separator guards as public API.
# image_name, uv_map_name, and image_channel are omitted on purpose: since 1.2.0
# they carry options={'SKIP_SAVE'} and reset to ("", "", "ALPHA") per invocation.
```

- [ ] **Step B2.** `README.md:44-45` lists the separator with no version. Add the
      minimum, because CATS relies on the separator to publish `RESULT_STALE` and
      has no fallback on older builds: state that Overdraw Prevention needs Alpha
      Material Separator 1.2.0 or newer, and that on 1.1.1 and earlier the panel
      can show `ANALYSIS_COMPLETE` for a result the separator has already marked
      stale.

- [ ] **Step B3 — change gate.**

```bash
python -W ignore::SyntaxWarning -m compileall -q -f __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
```

      Then in the isolated profile: `tests/extension_smoke.py`,
      `tests/blender_52_api_smoke.py`, `tests/import_sweep.py`,
      `tests/lifecycle_stress.py`, `tests/overdraw_smoke.py`, `tests/run.py`.
      Confirm 138 classes registered. Then
      `python scripts/build.py --blend <blender>` and report the path.

## Task C — close the milestone

- [ ] `git diff --check` and `git status --short`.
- [ ] Update `docs/HANDOFF.md`: mark the Overdraw Prevention AMS-present path
      verified against AMS 1.2.0, record the separator-version requirement, remove
      the seven-mirrored-property risk bullet now that
      `api_contract.ANALYSIS_SETTING_NAMES` guards those names upstream, and note
      that native review of the `ja_JP`/`ko_KR`/`zh_CN` Overdraw strings and the
      GUI-only checks (panel repaint, download dialog, Edit Mode preview) are
      still open.
- [ ] `git rm` this plan and the Overdraw Prevention spec under
      `docs/superpowers/specs/`.
- [ ] Two scoped commits: Task A, then Tasks B and C.
- [ ] Report. Do not merge or push.

## Known limitation

CATS cannot detect the separator's release version — the published `api_version`
is `1.2` on both 1.1.1 and 1.2.0. A user on 1.1.1 gets the original stale-result
defect with no CATS-side warning. Step B2 documents this rather than guessing at
a version probe.
