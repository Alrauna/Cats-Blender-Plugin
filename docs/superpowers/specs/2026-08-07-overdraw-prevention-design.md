# Design: Overdraw Prevention panel

Approved 2026-08-07. Branch `feature/overdraw-prevention`. Delete from `main`
once the milestone is complete and committed.

## Goal

Add an **Overdraw Prevention** sub-panel to the CATS Optimization panel that
drives the Blender Alpha Material Separator (AMS) extension, so a user can run
the alpha-separation workflow without leaving the CATS tab.

AMS finds mesh faces whose image pixels use alpha, leaves opaque faces on the
source material, and moves affected faces to a local `__AMS_ALPHA` copy. The
point is to cut overdraw: a real-time renderer cannot skip hidden pixels on a
transparent surface, so a single transparent material covering a whole mesh makes
every face pay that cost.

## Upstream facts this design relies on

`Alrauna/blender-alpha-material-separator`, extension id
`alpha_material_separator`, version 1.1.0, `blender_version_min = "5.2.0"`,
licensed GPL-3.0-or-later. CATS is GPL-3.0-or-later, so the licenses agree.

AMS ships `addon/api_contract.py`, a versioned public integration contract with
`API_VERSION = (1, 2)`. Its own comment states that operator IDs are reserved
there "so future callers can feature-detect instead of importing private
modules". The contract publishes five operator IDs:

- `alpha_material_separator.query_capabilities`
- `alpha_material_separator.analyze`
- `alpha_material_separator.select_faces`
- `alpha_material_separator.assign_materials`
- `alpha_material_separator.clear_results`

AMS registers these public properties in `addon/registration.py`:

- `WindowManager.alpha_material_separator_api` — `last_status_code`,
  `last_status_json`, `validation_state`
- `WindowManager.alpha_material_separator_settings`
- `WindowManager.alpha_material_separator_ui`
- `Material.alpha_material_separator_source`

`alpha_material_separator.analyze` declares `api_major: IntProperty(default=1)`,
an explicit version handshake for external callers.

AMS's own panels live under `bl_category = "AMS"` and call the public contract
operators directly. `addon/operators/ui_actions.py` holds only cancel, override,
and reset helpers, not the workflow buttons. There is no public function for
drawing AMS's interface: `addon/__init__.py` exposes only `register` and
`unregister`, and `addon/panel.py`'s drawing helpers are underscore-prefixed.

## Decisions

**AMS stays an external extension.** The user installs it separately. CATS
detects it and offers a download link when it is absent. AMS keeps its own
versioning, release cadence, and `AMS` sidebar tab. CATS's package size and
licensing surface do not change.

**The CATS panel is a thin driver, not a mirror.** It carries AMS's documented
three-step workflow — analyze, preview, apply — plus clear. Expert analysis
settings, manual alpha sources, inspection, exception policies, and technical
details stay in the AMS tab, because AMS exposes no supported way to render them
elsewhere.

**The integration uses the contract, not internals.** This deliberately does not
copy the Material Combiner mechanism in `ui/optimization.py`, which imports
`smc.operators.ui.include`, `smc.globs`, and `smc.ui.main_panel`, then probes
`hasattr(MaterialCombinerPanel, 'draw_pillow_installer')` to guess the version.
That approach is why four separate out-of-date and interface-error fallback paths
exist in that file. AMS provides an alternative and this design takes it.

Name-string detection is also wrong for AMS specifically. AMS is an extension, so
its module path varies with the repository it was installed from
(`bl_ext.user_default.alpha_material_separator`,
`bl_ext.blender_org.alpha_material_separator`). Operator IDs do not vary.

## Architecture

| Concern | Mechanism |
| --- | --- |
| Presence | `hasattr(bpy.ops, "alpha_material_separator")` and the `WindowManager.alpha_material_separator_api` property exists |
| Version gate | pass `api_major=1` to `analyze`; AMS refuses a mismatch and reports it |
| Actions | `layout.operator()` on the four workflow operator IDs |
| Status | parse `window_manager.alpha_material_separator_api.last_status_json` |
| Settings | mirror from `window_manager.alpha_material_separator_settings` |

`query_capabilities` is the fifth contract operator and this design does not call
it. Blender forbids invoking operators from a panel's `draw()`, so a capability
query would need either its own button or a deferred timer, and neither earns its
place: presence is answered by the `hasattr` check and version by `api_major`.
The ID stays available if a later feature needs richer feature detection.

No `addon_utils` scan, no `import_module`, no cached global detection state, and
no CATS wrapper operators around AMS's operators. `layout.operator()` returns the
operator's property group, so properties are set declaratively in `draw()`, which
is how AMS's own panel does it.

## Components

### `tools/overdraw.py` (new)

- `is_available()` — the presence check above. Returns a bool, raises nothing.
- `read_status()` — parse `last_status_json` and return a `dict`, or `None` when
  the property is missing, empty, or not valid JSON. Raises nothing.

  The panel renders the payload's `message` field and nothing else.
  `api_contract.status_payload()` guarantees `api_version`, `code`, and `message`
  on every payload; all other keys are per-operator details that CATS must not
  depend on. When `code` is the initial `NOT_QUERIED`, or `message` is absent or
  empty, the panel omits the status line rather than inventing text.
- `DownloadSeparatorButton` — operator `cats_overdraw.download_separator`, opens
  the AMS releases page. Mirrors `Atlas.ShotariyaButton`, including the
  `invoke_props_dialog` confirmation that names the URL before opening a browser.
- `OverdrawHelpButton` — operator `cats_overdraw.help`, opens the AMS README.

### `ui/optimization.py` (edit)

Add `OverdrawSubPanel(ToolPanel, bpy.types.Panel)`:

- `bl_idname = 'VIEW3D_PT_optimize_overdraw_v3'`
- `bl_parent_id = 'VIEW3D_PT_optimize_v3'`
- `bl_options = set()`, matching `AtlasSubPanel` and `MaterialSubPanel`

Defined after `AtlasSubPanel` in the file so it draws between Atlas and Material.
Blender orders sibling sub-panels by registration order, and `register_wrap`
collects classes in definition order, so file position controls it. Verify the
rendered order manually rather than assuming.

When AMS is absent: description, `draw_error_box`, and the download button. This
is the only state that hides the action buttons.

When AMS is present: description, the status line when one is available under the
rule above, the four action buttons, and a note that expert options are in the AMS
tab. The status text is AMS's own `message`; CATS does not compose it.

The whole `draw()` body sits inside `try`/`except` falling back to an error box,
matching `draw_atlas_section`.

### `resources/translations/*.json` (edit, four files)

New `OptimizePanel.overdraw.*` keys for the label, description, absent-state
message, expert-options note, and the four button labels, plus label, URL, and
success keys for the two new operators. English is authoritative. The `ja_JP`,
`ko_KR`, and `zh_CN` strings are flagged for native review in the same way the
maintainer credit strings were; new URLs are identical across languages.

## Data flow

```
CATS panel draw()
  |-- is_available()? --no--> error box + [Download Alpha Material Separator]
  \-- yes
        |-- read_status() --> status line, or omitted when None
        \-- layout.operator("alpha_material_separator.analyze",
                            api_major=1, + settings)
            layout.operator(".select_faces" / ".assign_materials"
                            / ".clear_results")
                        |
                        v
        AMS writes WindowManager.alpha_material_separator_api.last_status_json
                        |
                        v
              the next redraw shows the new status
```

## Error handling

- **AMS absent** — install prompt; action buttons hidden.
- **Status JSON missing, empty, or malformed** — `read_status()` returns `None`
  and the panel omits the status line. `draw()` never raises because of it.
- **API mismatch** — `api_major=1` makes AMS refuse and report. CATS does not
  duplicate the check or interpret the result.
- **Operator failure**, such as unsupported materials or an empty selection —
  AMS reports through its own status codes and operator reports. CATS surfaces
  the message and does not reinterpret it.
- **Any unexpected exception in `draw()`** — caught, replaced by an error box.

## Testing

- Unit tests for `read_status()` against valid, empty, malformed, and absent
  payloads, and for `is_available()` when AMS is absent.
- `tests/extension_smoke.py` gains `VIEW3D_PT_optimize_overdraw_v3` and the two
  `cats_overdraw` operators in its expected registration surface.
- `tests/import_sweep.py` and `tests/lifecycle_stress.py` must stay green with
  AMS **not** installed, which is CI's default state and the common user state.
- The AMS-present path cannot be covered in CI, because CI installs only CATS.
  Exercising the four buttons and the status line against a real AMS install is
  manual maintainer testing. Do not claim it as automated coverage.

## Open risk to settle first

It is not determinable from AMS's source whether `analyze` reads
`WindowManager.alpha_material_separator_settings` itself when its own properties
are left at their declared defaults. The first implementation step is a spike
that answers this:

- If `analyze` reads the settings itself, CATS sets only `api_major` and the
  eleven-property mirroring is deleted before it is written.
- If it does not, CATS mirrors `image_name`, `uv_map_name`, `image_channel`,
  `material_overrides_json`, `address_mode`, `alpha_threshold`,
  `min_affected_texels`, `min_affected_fraction`, `margin_texels`,
  `max_scanlines`, and `max_run_emissions`, so a CATS run behaves the same as
  clicking Analyze in the AMS tab.

Those eleven property names are the only coupling beyond `api_contract.py`, and
they are not themselves listed in the contract. `api_major` is the guard that
makes depending on them acceptable.

## Out of scope

- Bundling or vendoring AMS into `extern_tools/`.
- Surfacing AMS's expert settings, override list, or inspection UI inside CATS.
- Any change to the existing Material Combiner integration.
- Adding AMS to `.gitmodules` or to the extension package.
- A wiki page for the new panel.
