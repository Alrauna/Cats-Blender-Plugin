# Handoff

Branches `main` and `blender-52`, version `5.2.0-alpha.1`.

## Action required from the maintainer

**Set `main` as the default branch** in the GitHub repository settings. This
cannot be done from the CLI without a token. `blender-52` is still the default,
so until it is switched, visitors land on `blender-52` rather than `main`. The two
branches are identical at the commit `main` was created from.

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

Leave builds in `.packaged-releases/` alone. They are the maintainer's to keep or
discard, and are removed only when the maintainer asks. Do not delete a build
after validating it.

A recorded SHA-256 will not reproduce byte-for-byte on a rebuild, since ZIP
member timestamps vary between builds.

The three test-asset URLs in `tests/run.py` were confirmed live. Two of the
three assets are gzip-compressed blend files, which `read_blender_file_magic`
already handles.

## Repository rework — complete

The fork now presents as Alrauna's, not as a continuation of Team Neoneko's
archived project.

The README is a landing page that credits the lineage: Absolute Quantum with
Hotox and GiveMeAllYourCats created Cats, Team Neoneko with Yusarina carried it
to 5.0, and this work starts from their release. 989onan is credited as a
contributor, not a Neoneko maintainer; only one upstream string claimed otherwise
and the commit record contradicts it. The archived upstream wiki is labelled
historical, and remains the only feature documentation that exists.

Companion projects point at maintained forks: `Alrauna/material-combiner-addon`,
`Alrauna/immersive_scaler`, and
`Alrauna/Cats-Blender-Plugin-Unofficial-translations` for both the dictionary and
the UI translation download. Patch notes point at this fork's releases rather
than the archived project's. The Support Us button was removed; its only target
returned 404 and this fork has no website. Registered classes are 136, down from
137, for that reason alone.

### Topology

`main` and `blender-52` are identical. `blender-45` and `blender-45-dev` are kept
because Blender 4.5 LTS is still supported. Fifteen branches for Blender 3.6
through 5.0 were deleted, along with the local `blender-50` and the `upstream`
remote that pointed at `git.disroot.org/Neoneko`.

All 117 original tags are kept, plus nine `archive/<branch>` tags created for the
branch tips no release tag reached: `Welcome`, `blender-36-dev`, `blender-40`,
`blender-40-dev`, `blender-41`, `blender-41-dev`, `blender-42-dev`,
`blender-43-dev`, and `blender-44-dev`. Every deleted tip was confirmed reachable
from a tag before deletion. To recover one, branch from its tag.

## Outstanding

- No interactive coverage exists for import/export, file browser, or material
  preview workflows. Background tests cannot substitute for these.
- The `ja_JP`, `ko_KR`, and `zh_CN` maintainer credit strings need a native
  review. The maintainer name was left untranslated inside each sentence.
- The credits panel's Help button and three in-app wiki links point at the
  archived upstream wiki, which is the only feature documentation that exists.
  They stay until this fork has a wiki of its own.
- `.gitmodules` points `extern_tools/imscale` at
  `https://github.com/Alrauna/immersive_scaler.git`, but no gitlink is registered
  for that path, so the submodule is still absent at runtime. Registering it is a
  separate decision.
- `FixArmature.cantFix3` and `update_dictionary.error.apiChanged` tell users to
  find forum and Discord links in the credits panel. Neither exists there. Both
  messages were already stale before this work started, and the credits panel now
  holds only Help and Patch notes. Rewording them needs a decision on where users
  should actually report problems; the issue tracker is the only channel this fork
  has.

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
