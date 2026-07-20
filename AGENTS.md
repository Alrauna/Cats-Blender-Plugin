# CATS Blender Plugin — Agent Instructions

## Project purpose

This repository is a maintained personal fork of the archived unofficial CATS
Blender Plugin. It targets Blender 5.2 LTS while preserving existing CATS
workflows and behavior.

The current Git development branch is `blender-52`. Historical Blender 5.0
branches and baseline tags preserve the upstream migration baseline. Do not
modify, rewrite, or retag historical baselines unless the user explicitly
requests it.

## Intended repository layout

The flat root-level layout is intentional and is also the Blender extension
package root:

- `__init__.py`: extension entry point and registration lifecycle.
- `blender_manifest.toml`: Blender extension metadata, permissions, version,
  compatibility, and package exclusions.
- `tools/`: operators and core feature implementation.
- `ui/`: Blender panels and UI integration.
- `resources/`: translations, icons, dictionaries, and runtime resources.
- `extern_tools/`: bundled third-party code and required third-party assets.
- `tests/`: static, package, Blender-background, lifecycle, armature, and
  shape-key tests.
- `.github/`: continuous-integration configuration.
- `README.md`: installation, build, and updater overview.
- `.local-references/`: ignored external references retained only for local
  investigation.
- `.packaged-releases/`: ignored locally built or retained release packages.
- `.test-runtime/`: ignored generated isolated Blender profiles and test
  output; this is not source.

Do not introduce an `addon/`, `src/`, or duplicate repository-name wrapper
without a demonstrated Blender, packaging, or test requirement. Do not move
source folders merely for cosmetic organization.

There is currently no separate tracked `docs/` or `scripts/` directory. Verify
the current tree before documenting or relying on one.

## Local-only and generated material

`.local-references/`, `.packaged-releases/`, and `.test-runtime/` are
intentionally ignored and must remain ignored.

Unless explicitly instructed:

- Do not publish, commit, quote, copy into source, or link to files from
  `.local-references/`.
- Do not treat external archives, extracted upstream copies, downloaded
  fixtures, notes, or comparison artifacts as source of truth.
- The sole standing exception is
  `.local-references/Cats-Blender-Plugin-Unofficial5.0.3.1.zip`. Treat that
  exact, ignored archive as the read-only Blender 5.0.3.1 behavioral reference
  for old-version runtime comparisons. Prefer it over rebuilding `blender-50`
  for Blender 5.0 tests. Validate the ZIP before use, install it only into a
  separate isolated Blender 5.0 profile, and never modify, replace, repackage,
  commit, publish, or copy it into the source tree.
- Do not treat ZIPs in `.packaged-releases/` as newer than the checked-out Git
  commit.
- Do not modify or replace a retained reference archive.
- Do not stage `.test-runtime/`, logs, caches, generated Blender profiles, or
  installed test copies of the extension.
- Do not use the user's normal Blender profile for automated validation.

Git ignore rules do not necessarily control Blender extension packaging.
Before building or releasing, verify that local-only directories and
repository-only files are excluded by `blender_manifest.toml` and absent from
the resulting ZIP. If precise manifest exclusions are missing, report the
problem and request approval before changing packaging policy.

## Files and areas requiring extra care

Do not touch these without a task-specific reason:

- `.git/`, branches, tags, reflogs, or commit history.
- `.local-references/`, `.packaged-releases/`, and `.test-runtime/`.
- User-owned uncommitted changes.
- `LICENSE` and third-party license, notice, or attribution files.
- Bundled code under `extern_tools/`.
- `blender_manifest.toml` compatibility, permissions, version, maintainer, or
  website metadata.
- Updater repository URLs or update-enabling constants.
- Operator identifiers, RNA property names, panel identifiers, registration
  order, public module paths, and import/export integration contracts.
- Binary fixtures and bundled assets whose licensing or provenance has not
  been verified.

`extern_tools/mmd_tools_local` is bundled compatibility-sensitive code.
Preserve its structure and attribution. Change it only for a demonstrated
Blender 5.2 compatibility or functional requirement, and test affected MMD
workflows afterward.

The optional Immersive Scaler integration may be absent. Verify its current
runtime behavior before changing `.gitmodules` or dependency handling.

## Compatibility requirements

- Target Blender 5.2 LTS, as declared by `blender_manifest.toml`.
- Treat the `version` field in `blender_manifest.toml` as the version source of
  truth. Whenever it changes, update `CATS_VERSION` in `__init__.py` to the
  exact same string and verify that `updater.py` imports and handles that value,
  including prerelease suffixes. Do not introduce a second independent
  `CATS_VERSION` definition in `updater.py`.
- Prefer current Blender 5.2 Python APIs over obsolete compatibility hacks.
- Preserve existing CATS behavior wherever Blender 5.2 permits it.
- Do not remove a feature merely because it is difficult to test or migrate.
- Keep the root package layout compatible with Blender extension validation,
  installation, and relative imports.
- Preserve bundled dependencies and required runtime resources in packages.
- Automatic updater behavior is intentionally disabled until fork-owned
  release URLs are configured. Do not enable it or restore upstream update
  URLs without explicit approval.
- Do not use network access, install packages, or change system configuration
  unless explicitly authorized.

If repository behavior and external reference material disagree, the
checked-out source, manifest, tests, and current Git history take precedence.

## Safe change workflow

1. Confirm the Git root, current branch, HEAD, and `git status --short`.
2. Inspect existing code, tests, and history before deciding that a change is
   necessary.
3. Preserve unrelated and user-authored changes in a dirty worktree.
4. Make the smallest focused change that satisfies the request.
5. Avoid broad formatting, mechanical rewrites, dependency upgrades, and
   unrelated refactors.
6. Update tests, documentation, imports, and packaging rules only when directly
   affected.
7. Run validation proportional to the risk.
8. Review `git diff`, `git diff --check`, and `git status --short` afterward.
9. Do not commit, tag, push, publish, upload, or create a release unless the
   user explicitly requests it.

Use logically scoped commits only when commits are authorized. Never amend or
rewrite migration checkpoints merely to tidy history.

## Validation

Use Blender 5.2 and an isolated test profile. Keep generated state out of the
normal Blender configuration.

Useful checks include:

```text
python -W ignore::SyntaxWarning -m compileall -q -f .
blender --command extension validate .
blender --command extension build --source-dir . --output-filepath .packaged-releases/<id>-<version>-<short-hash>.zip
blender --command extension validate .packaged-releases/<id>-<version>-<short-hash>.zip
python tests/verify_package.py .packaged-releases/<id>-<version>-<short-hash>.zip --source-dir .
```

All Blender extension builds, including release candidates, validation builds,
and test builds, must be placed in `.packaged-releases/`. Do not write build
ZIPs to the repository root, `.test-runtime/`, or another source directory.
Name every build exactly `<id>-<version>-<short-hash>.zip`. Read `id` and
`version` from the current `blender_manifest.toml`; obtain `short-hash` from
`git rev-parse --short HEAD`. Do not substitute the display name, manually
normalize the manifest values, reuse a stale hash, or infer metadata from an
older ZIP. Report all three source values and the final path after building.

Before using `extension build`, first ensure local-only directories cannot be
included in the package. Inspect the exact ZIP afterward.

For runtime changes, use the existing tests as applicable:

- `tests/extension_smoke.py`
- `tests/blender_52_api_smoke.py`
- `tests/import_sweep.py`
- `tests/lifecycle_stress.py`
- `tests/run.py` for armature and shape-key suites

Exercise enable, disable, reload, restart, and removal when registration code
changes. Confirm unregistering cleans up classes, handlers, timers, properties,
menus, and keymaps.

Some UI, interactive operator, viewport, file-browser, material-preview, and
model-specific workflows require manual Blender testing. Do not claim them as
validated solely from background-mode tests.

## Commit and publication policy

Commit only intentional source, tests, workflow configuration, documentation,
metadata, required assets, and applicable license files.

Never commit:

- `.local-references/`
- `.packaged-releases/`
- `.test-runtime/`
- Blender user profiles or preferences
- caches, bytecode, logs, crash files, temporary downloads, or build output
- external archives or fixtures without an explicit redistribution decision
- credentials, tokens, private keys, personal paths, or machine-specific data

Before GitHub publication:

- Review staged and untracked files.
- Scan tracked content and Git metadata for PII, secrets, and local paths.
- Confirm the intended commit author identity and remote URL.
- Verify maintainer, website, version, permissions, updater URLs, and licensing.
- Build from the intended commit and validate that exact ZIP.
- Inspect the ZIP member list for local-only, test, Git, cache, and reference
  material.
- Record the source commit and SHA-256 of any release candidate.

When uncertain about provenance, licensing, publication safety, compatibility,
or a change to public behavior, stop and ask the user before modifying it.
