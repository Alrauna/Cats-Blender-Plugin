# Handoff

## Repository state

- Default/base branch: `main` at `b4e36f7` (PR #1 merged).
- Active topic branch: `codex/ci-hardening-release` at `dc39c4d`, based on
  `main` commit `b4e36f7`.
- `blender-52` remains an older branch at `c1d020f`; it is not the default and
  is not expected to track `main`.
- Manifest version: final `5.2.1`; Blender target: `5.2.0 LTS`.
- The working tree was clean after the implementation commits. Generated test
  profiles and packages remain ignored under `.test-runtime/` and
  `.packaged-releases/`.

## CI hardening branch

Objective: secure CI inputs, retain the existing CATS validation gates on
Windows, Linux, and macOS Apple Silicon, remove unreachable CI-only files, and
add manual checksum-verified publication for final releases only.

Completed commits:

- `63d6e3e` — strict checksum, GitHub-output, and release-identity primitives.
- `d1f0da7` — verified Blender acquisition with committed archive hashes and
  byte-identical checksum manifests fetched through normal DNS, Cloudflare DoH,
  and Quad9 DoT.
- `2d6da12` — SHA-256-pinned, size-bounded Blender fixtures and
  `--disable-autoexec` for fixture execution.
- `2ebda43` — immutable three-platform validation workflow on `windows-2025`,
  `ubuntu-24.04`, and `macos-15`; no scheduled trigger or `setup-python`.
- `20a27a2` — optional manual release input, exact final `X.Y.Z` gate, fresh
  public-source build, draft upload, `SHA256SUMS.txt`, stored-ZIP download and
  digest verification, then publication.
- `dc39c4d` — removal of unreferenced `tests/termcolor.py` and three obsolete
  `tests/old/` probes.

The workflow keeps global `contents: read`; only the release job receives
`contents: write` and the `release` environment. Every action reference is a
full commit SHA and checkout persistence is disabled. Release publication is
manual, public-`main` only, requires a separate full validation matrix, rejects
prereleases, and leaves failed drafts available for inspection. There is no
weekly schedule, automatic release, prerelease, dry-run job, cache, linter,
reusable workflow, or split-platform package.

## Local verification on 2026-08-08

All local Blender commands used isolated profiles under `.test-runtime/`.

- `python -m unittest tests.test_ci -v`: 20 passed.
- Explicit-path `compileall` over `__init__.py`, `globs.py`, `extentions.py`,
  `updater.py`, `tools`, `ui`, `extern_tools`, and `tests`: passed.
- Blender 5.2.0 LTS source validation with `--factory-startup`: passed.
- `python scripts/build.py --blend <Blender 5.2>`: source validation, build,
  ZIP validation, and `tests/verify_package.py` passed from clean commit
  `dc39c4d`.
- Package:
  `.packaged-releases/cats_blender_plugin-5.2.1-dc39c4d.zip`.
- Package SHA-256:
  `8e10b90dd3465ee06087097597676b5844a1e126f63d3b83bb3f2e07af47fd09`.
- Package inspection: 183 members, 129 Python modules, and no repository-only,
  local-reference, runtime-profile, cache, Git, test, docs, or scripts content.
- The package verifier recorded 1,666 legacy invalid-escape `SyntaxWarning`s;
  these pre-existing warnings are not package-validation errors.
- Inline correctness/security review found no Critical or Important issue.

## Pending and limitations

- The workflow has not been parsed or run by GitHub yet. No local `actionlint`
  or YAML parser was installed, and no dependency was added solely for that
  check.
- The Windows, Linux, and macOS Apple Silicon matrix must pass on GitHub before
  this milestone is complete.
- The real release path can only be exercised by a future manual final-version
  dispatch from public `main` after merge. Do not dispatch a release from this
  topic branch.
- The approved design and implementation plan remain in
  `docs/superpowers/` until implementation review and the GitHub matrix pass;
  retire both in the final handoff commit afterward.

## Next action

Obtain explicit authorization to push `codex/ci-hardening-release` and open a
draft pull request targeting `main`. Then wait for all three matrix entries,
address any verified failure through a RED/GREEN fix, update this handoff with
the PR/check results, retire the in-flight design and plan, and commit the final
milestone handoff. Do not publish a release as part of branch completion.
