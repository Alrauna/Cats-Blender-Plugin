# Handoff

Branch `blender-52`, version `5.2.0-alpha.1`.

## State

The Blender 5.2 port is functionally complete. `tools/` and `ui/` carry the same
module set as the 5.0.3.1 reference archive, so no feature was dropped in the
migration. Version wiring is consistent: `blender_manifest.toml`, `CATS_VERSION`
in `__init__.py`, and the value `updater.py` imports all agree. The automatic
updater remains intentionally disabled — `UPDATE_REPOSITORY` is empty and gated
by `_update_source_configured`.

The shape-key-preserving Pose Mode controls
(`cats_manual.start/stop_pose_mode_no_shapekey_reset`) are complete, covered by
`tests/pose_mode_smoke.py`, and the maintainer has confirmed them by manual GUI
testing.

## Verified on 2026-08-06 (Blender 5.2.0 LTS, build 2026-07-14)

Full CI-equivalent run at commit `4e9e7b5`, in an isolated profile, all passing:
source and package validation, `verify_package.py`, install/enable, the five
background smoke suites, the 13 armature invocations, the shape-key suite, and
removal with `--expect-absent`. The package that run exercised was
`cats_blender_plugin-5.2.0-alpha.1-4e9e7b5.zip`, SHA-256
`a303b101878522c2b82a633a880a2e5410b8493b578014190a6bc295c37f2c21`.

`.packaged-releases/` is now kept empty. Packages are build output, not
artifacts to retain; rebuild with `scripts/build.py` when one is needed. The
SHA-256 above records what was validated and will not reproduce byte-for-byte,
since ZIP member timestamps vary between builds.

The three test-asset URLs in `tests/run.py` were confirmed live. Two of the
three assets are gzip-compressed blend files, which `read_blender_file_magic`
already handles.

## Repository rework

In flight. See `docs/superpowers/specs/repository-rework.md` and
`docs/superpowers/plans/repository-rework.md`.

Phase 1 is complete: the README was rebuilt as a landing page crediting the
previous maintainers, Material Combiner now points at
`Alrauna/material-combiner-addon`, the credits panel names Alrauna, and the
Support Us button was removed because `neoneko.xyz/support-us.html` returns 404
and this fork has no website. Registered classes dropped 137 to 136 as a result.

**Phase 2 is blocked on two forks the maintainer must create:**

- `Alrauna/immersive_scaler` — then repoint `tools/scale.py:58`, the four
  `ImmersiveScalerHelpButton.URL` entries, and the two README references.
- `Alrauna/Cats-Blender-Plugin-Unofficial-translations`, **keeping the
  `5x-translations` branch** — then repoint `tools/translations.py:38` and the
  `repo_owner` at line 305. Verify the raw URL returns JSON first; a wrong branch
  name fails silently at runtime.

Phase 3 is the topology change: push `blender-52`, create `main`, set it default
on GitHub, tag the nine untagged branch tips as `archive/<branch>`, delete
fifteen remote branches, delete local `blender-50`, and remove the `upstream`
remote. Keep `blender-45` and `blender-45-dev`; Blender 4.5 LTS is still
supported. Keep all 117 tags.

## Outstanding

- No interactive coverage exists for import/export, file browser, or material
  preview workflows. Background tests cannot substitute for these.
- The `ja_JP`, `ko_KR`, and `zh_CN` maintainer credit strings need a native
  review. The maintainer name was left untranslated inside each sentence.
- `HelpButton.URL` in all four translation files points at
  `catsblenderplugin.xyz/wiki.html`, a Team Neoneko site. It still returns 200,
  so it was left alone, but it is not this fork's to rely on.
- `ForumButton` in `tools/credits.py` is registered but drawn by no panel, and
  its URL points at a third-party forum thread. Dead code; removal not requested.
- `FixArmature.cantFix3` and `update_dictionary.error.apiChanged` tell users to
  find Discord links in the credits panel. No such link exists there. Stale
  before this work started.

## Packaging guardrails

Build with `python scripts/build.py --blend <blender>`. It names and places the
package itself and refuses a dirty tracked tree. `tests/verify_package.py` fails
the build if anything under `FORBIDDEN_TOP_LEVEL` reaches a package; a new
repository-only directory must be added there and to `paths_exclude_pattern` in
the same change.

The CI workflow still builds with the raw `extension build` commands rather than
`scripts/build.py`, because it packages into `RUNNER_TEMP`. It calls
`verify_package.py`, so the exclusion guardrail applies there too. This
divergence is deliberate.

## Local environment notes

Test blend files are gitignored by design and must stay that way. They are
downloaded on demand by `tests/run.py`; keep local copies under the canonical
names (`tests/armatures/armature.ryuko.blend`,
`tests/armatures/armature.bonetranslationerror.blend`,
`tests/shapekeys/shapekey.shape_key_to_basis.blend`) so offline runs match CI.

Do not run the documented `compileall -q -f .` from the repository root without
narrowing the paths. It descends into `.local-references/` and `.test-runtime/`
and writes bytecode into the read-only 5.0 reference tree. Pass the source
directories explicitly instead.
