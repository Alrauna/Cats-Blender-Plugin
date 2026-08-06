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

Full CI-equivalent run at commit `7b2b93e`, in an isolated profile, all passing:
source and package validation, `verify_package.py`, install/enable, the five
background smoke suites, the 13 armature invocations, the shape-key suite, and
removal with `--expect-absent`. The package that run exercised was
`cats_blender_plugin-5.2.0-alpha.1-7b2b93e.zip`, SHA-256
`a8088696ba0c68fd4c30af713217afc56a897316a6ca9346296046e8f51e5fac`.

`.packaged-releases/` is now kept empty. Packages are build output, not
artifacts to retain; rebuild with `scripts/build.py` when one is needed. The
SHA-256 above records what was validated and will not reproduce byte-for-byte,
since ZIP member timestamps vary between builds.

The three test-asset URLs in `tests/run.py` were confirmed live. Two of the
three assets are gzip-compressed blend files, which `read_blender_file_magic`
already handles.

## Outstanding

- `README.md` needs a rewrite. Its build instructions still name a root-level
  `Cats-Blender-Plugin-5.2.0.zip`, which contradicts the `.packaged-releases/`
  naming rule in `AGENTS.md`. Deferred by maintainer decision, not blocked.
- No interactive coverage exists for import/export, file browser, or material
  preview workflows. Background tests cannot substitute for these.

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
