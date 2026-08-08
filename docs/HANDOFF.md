# Handoff

## Repository state

- Default/base branch: `main` at `b4e36f7` (PR #1 merged).
- Active topic branch: `codex/ci-hardening-release`, based on `main` commit
  `b4e36f7` and published as draft PR #2.
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
- `65a8b4f` — repository-backed publication checkpoint replacing stale handoff
  branch claims.
- `1a82e5d` — use hosted runner Python only for the two fixture runners so
  Linux/macOS use the runner CA store; checksum-verified Blender remains the
  executable under test and every fixture security check remains active.

The workflow keeps global `contents: read`; only the release job receives
`contents: write` and the `release` environment. Every action reference is a
full commit SHA and checkout persistence is disabled. Release publication is
manual, public-`main` only, requires a separate full validation matrix, rejects
prereleases, and leaves failed drafts available for inspection. There is no
weekly schedule, automatic release, prerelease, dry-run job, cache, linter,
reusable workflow, or split-platform package.

## Local verification on 2026-08-08

All local Blender commands used isolated profiles under `.test-runtime/`.

- `python -m unittest tests.test_ci -v`: 21 passed after the CI regression fix.
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

## GitHub verification

Draft PR: <https://github.com/Alrauna/Cats-Blender-Plugin/pull/2>

The first matrix run `31265264642` proved workflow parsing and passed Windows,
but Linux and macOS failed when Blender's bundled Python rejected Dropbox's TLS
chain while fetching retained fixtures. The focused fix restored the prior
host-Python boundary for only `tests/run.py`; this uses the hosted runner CA
store without weakening TLS or changing fixture authentication.

The complete second run `31265564097` passed:

- Windows (`windows-2025`): passed in 1m49s.
- Linux (`ubuntu-24.04`): passed in 1m32s.
- macOS Apple Silicon (`macos-15`): passed in 1m59s.
- CodeQL Actions and Python analysis: passed.
- Release gate and publication jobs: correctly skipped for the pull request.

## Pending and limitations

- The real release path can only be exercised by a future manual final-version
  dispatch from public `main` after merge. Do not dispatch a release from this
  topic branch.
- The release job's fresh public-source build, draft upload, stored-ZIP
  verification, and publish transition remain intentionally unexecuted until a
  future final release is being cut from public `main`.

## Next action

Review and merge draft PR #2 into `main` when ready. After merge, use a manual
workflow dispatch with an exact manifest-matching final `X.Y.Z` only when an
actual release is intentionally being cut. Do not publish a release as part of
branch completion.
