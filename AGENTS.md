# CATS Blender Plugin — Agent Instructions

## Project purpose and branch model

This repository is a maintained personal fork of the archived unofficial CATS
Blender Plugin. It targets Blender 5.2 LTS while preserving existing CATS
workflows and behavior.

`main` is the protected integration base. Create focused topic branches from
the latest locally available `main`. Fetching remote updates requires explicit
network authorization. `blender-52`, the Blender 5.0 branches, and baseline tags
preserve migration history; do not modify, rewrite, or retag them unless the
user explicitly requests that exact operation.

## Repository layout

The flat root-level layout is intentional and is also the Blender extension
package root:

- `__init__.py`: extension entry point and registration lifecycle.
- `blender_manifest.toml`: extension metadata, permissions, version,
  compatibility, and package exclusions.
- `tools/`: operators and core feature implementation.
- `ui/`: Blender panels and UI integration.
- `resources/`: translations, icons, dictionaries, and runtime resources.
- `extern_tools/`: bundled third-party code and required third-party assets.
- `tests/`: static, package, Blender-background, lifecycle, armature, and
  shape-key tests.
- `scripts/`: repository tooling; excluded from the extension package.
- `docs/`: handoff notes and temporary or durable design documentation;
  excluded from the extension package.
- `.github/`: continuous-integration configuration.
- `README.md`: installation, build, and updater overview.
- `.local-references/`: ignored external references retained for local
  investigation only.
- `.packaged-releases/`: ignored local build output and retained packages.
- `.test-runtime/`: ignored isolated Blender profiles and generated test
  output; this is not source.

Do not introduce an `addon/`, `src/`, or duplicate repository-name wrapper
without a demonstrated Blender, packaging, or test requirement. Do not move
source folders merely for cosmetic organization. Keep `docs/` and `scripts/`
excluded by `blender_manifest.toml`, and verify the current tree before relying
on a documented path.

## Repository safeguards

### Local-only and generated material

`.local-references/`, `.packaged-releases/`, and `.test-runtime/` must remain
ignored. Do not stage or commit generated Blender profiles, installed test
copies, packages, caches, bytecode, logs, crash files, or temporary downloads.
Never use the user's normal Blender profile for automated validation.

Do not publish, quote, link to, or copy material from `.local-references/` into
source unless the user makes an explicit, task-specific provenance and
redistribution decision. External archives, extracted upstream copies,
downloaded fixtures, notes, and comparison artifacts are not source of truth.

The sole standing behavioral-reference exception is
`.local-references/Cats-Blender-Plugin-Unofficial5.0.3.1.zip`. For Blender 5.0
runtime comparisons, validate that exact ignored archive and install it only
into a separate isolated Blender 5.0 profile. Prefer it over rebuilding
`blender-50`. Never modify, replace, repackage, commit, publish, or copy the
archive into source.

Do not treat packages in `.packaged-releases/` as newer than the checked-out
commit. Git ignore rules do not control Blender extension packaging, so package
exclusions must be verified independently.

### Protected files and contracts

Do not touch the following without a task-specific reason:

- `.git/`, branches, tags, reflogs, and commit history;
- user-owned or unrelated working-tree changes;
- `LICENSE` and third-party license, notice, or attribution files;
- bundled code under `extern_tools/`;
- compatibility, permissions, version, maintainer, and website metadata in
  `blender_manifest.toml`;
- updater repository URLs and update-enabling constants;
- operator identifiers, RNA property names, panel identifiers, registration
  order, public module paths, and import/export contracts; and
- binary fixtures and bundled assets without verified licensing or provenance.

`extern_tools/mmd_tools_local` is compatibility-sensitive bundled code.
Preserve its structure and attribution. Change it only for a demonstrated
Blender 5.2 compatibility or functional requirement, then test affected MMD
workflows. The optional Immersive Scaler integration may be absent; verify its
current behavior before changing `.gitmodules` or dependency handling.

When repository behavior and external reference material disagree, the
checked-out source, manifest, tests, and current Git history take precedence.

## Authority and scope

A user request to implement a change authorizes relevant read-only inspection,
focused file edits, proportionate validation, and creation or switching of a
local topic branch when the work belongs there. It does not authorize staging,
committing, network access, dependency installation, system configuration,
pushing, opening or merging a pull request, tagging, publishing, releasing,
destructive Git actions, or history rewriting. Obtain explicit authorization
before any of those operations.

An explicit user instruction may authorize a normally gated operation, but it
does not silently waive unrelated safeguards. Confirm the exact target and
scope before destructive, publication, provenance-sensitive, or history
operations.

Treat each topic branch as one coherent objective. Do not add materially
different work because it is convenient, related, newly discovered, or part of
the same conversation. Preserve unrelated user changes and never discard,
rewrite, stage, or commit them merely to obtain a clean tree.

## Development workflow

### Investigate and decide

Before non-trivial edits, confirm the Git root, branch, HEAD, and
`git status --short`; inspect the relevant code, tests, callers, integrations,
configuration, and history. Expand the investigation when the possible blast
radius is unclear.

Begin defects and unexpected results with systematic debugging. Establish a
reproduction and root cause before production edits when reasonably practical.
If reliable reproduction is impossible, document the evidence, working
hypothesis, and remaining uncertainty instead of presenting the hypothesis as
fact.

A precise user request may serve as the approved design when it resolves the
material behavior and trade-offs. Use brainstorming and obtain approval when a
meaningful unresolved choice affects behavior, UX, compatibility,
architecture, performance, safety, scope, or publication. Stop for renewed
approval when investigation materially changes an approved choice.

Use a written implementation plan for risky or genuinely multi-step work. A
narrow change may use a concise inline plan. Temporary design and plan files do
not need to be committed; retain them only when they provide durable project
value, and do not promise preservation under an unspecified merge strategy.

### Implement, review, and verify

Use Superpowers for applicable investigation, design, planning, debugging,
execution, review, and verification phases. Use `executing-plans` by default
for an approved written plan. Subagent-driven development and parallel dispatch
require an explicit user request and safely independent work.

Ponytail governs scope inside those phases: prefer existing code,
Blender/Python-native behavior, standard-library features, minimal
dependencies, minimal abstractions, and the smallest correct diff. It may
recommend deferring unrelated work, but it may not remove necessary debugging,
testing, review, safety, or verification.

For production behavior changes, use test-driven development by default:
demonstrate the regression or new contract, make the smallest production edit,
and run the applicable change gate. When an automated regression is genuinely
impractical, document why and use the best available characterization or manual
validation. Do not claim background-mode tests validate interactive workflows.

Review material production changes for correctness before completion. Use
`requesting-code-review` for major or risky milestones and
`receiving-code-review` before acting on review feedback. Always use
`verification-before-completion` before success claims. Use
`finishing-a-development-branch` only when the user requests integration or a
publication step.

After edits, run validation proportionate to the risk, then inspect
`git diff`, `git diff --check`, and `git status --short`. Update tests,
documentation, imports, configuration, and packaging rules only when directly
affected.

For read-only inspection, status reporting, and mechanical documentation
corrections that do not change product or process policy, skip design and plan
artifacts. Factual claims still need evidence; changed files still require
`git diff --check`.

## Testing and CI

Validation must be proportional to risk and expected blast radius. Start with
the smallest relevant check, then run directly affected tests, smoke coverage,
integration tests, and the broader suite as warranted. Do not claim success
from inspection alone, and report the commands and results used.

For non-trivial changes, apply the relevant validation layers:

- syntax, compilation, imports, manifests, packaging, configuration, and
  dependency resolution;
- targeted tests for changed behavior, edge cases, and failure paths;
- regression tests for reproducible in-scope defects when practical;
- integration tests when behavior crosses components, applications,
  dependencies, plugins, file formats, or external tools; and
- smoke tests for installation or initialization, import/loading,
  registration/unregistration, important public identifiers, a representative
  happy path, minimally valid output, clean shutdown, and critical integration
  contracts.

Tests should protect meaningful observable behavior and stable contracts. Keep
them deterministic, repeatable, isolated from user-specific state,
non-destructive, reasonably fast, explicit about prerequisites, and runnable
unattended. Never weaken, delete, skip, or rewrite a valid failing test merely
to make a change pass; determine whether the implementation, expectation, or
environment is wrong.

Convert in-scope failure modes and compatibility requirements into durable
automated tests when useful and practical. Record unrelated discoveries as
future work rather than expanding the current branch; ask the user only when a
finding blocks the objective or requires a material decision. Evaluate stable
new unattended checks for CI inclusion without automatically expanding scope.

CI should catch syntax/import failures, installation or packaging failures,
smoke failures, public-contract breakage, targeted regressions, and supported
runtime failures where feasible. Expensive checks may use scheduled or manual
jobs while normal changes retain a fast must-never-fail gate.

When adequate automation is impractical, state what remains untested, why, and
what manual validation was performed.

## Compatibility requirements

- Target Blender 5.2 LTS as declared by `blender_manifest.toml`.
- Treat the manifest `version` as the source of truth. Whenever it changes,
  update `CATS_VERSION` in `__init__.py` to the exact same string and verify
  that `updater.py` imports and handles it, including prerelease suffixes. Do
  not introduce a second independent definition in `updater.py`.
- Prefer current Blender 5.2 Python APIs over obsolete compatibility hacks.
- Preserve existing CATS behavior wherever Blender 5.2 permits it. Do not
  remove a feature merely because it is difficult to test or migrate.
- Preserve the root package layout, relative imports, bundled dependencies, and
  required runtime resources.
- Automatic updater behavior remains disabled until fork-owned release URLs
  are configured. Do not enable it or restore upstream URLs without explicit
  approval.

## Validation and packaging

Use Blender 5.2 with an isolated test profile. Useful checks include:

```text
python -W ignore::SyntaxWarning -m compileall -q -f __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
python scripts/build.py --blend <blender> --allow-dirty
```

Do not pass `.` to `compileall`; it descends into local reference and runtime
trees and writes bytecode there. Name source paths explicitly.

Use `scripts/build.py`, not a hand-built ZIP. For development validation,
`--allow-dirty` permits a tracked dirty tree and warns that the commit hash in
the filename is approximate. For publication or release validation, omit that
flag: build from the exact clean intended commit, validate that ZIP, and report
its final path.

All extension builds belong in `.packaged-releases/`. Do not write ZIPs to the
repository root, `.test-runtime/`, or source directories. Confirm that
repository-only and local-only material is excluded by
`blender_manifest.toml` and absent from the ZIP.

`tests/verify_package.py` enforces top-level exclusions. When a new
repository-only directory is introduced, update its `FORBIDDEN_TOP_LEVEL` set
and the manifest `paths_exclude_pattern` in the same authorized change. If
precise exclusions are missing, report the issue and obtain approval before
changing packaging policy.

Use these runtime tests as applicable:

- `tests/extension_smoke.py`
- `tests/blender_52_api_smoke.py`
- `tests/import_sweep.py`
- `tests/lifecycle_stress.py`
- `tests/run.py` for armature and shape-key suites

When registration changes, exercise enable, disable, reload, restart, and
removal. Confirm unregistering cleans up classes, handlers, timers, properties,
menus, and keymaps. UI, interactive operator, viewport, file-browser,
material-preview, and model-specific workflows may require manual Blender
testing.

## Git and publication policy

Before a non-trivial implementation, determine whether the objective belongs
on the current branch and whether a suitable local branch already exists. If
not, create a focused `codex/` topic branch from the latest locally available
`main`. If unfinished work prevents a safe switch, preserve it and report the
situation instead of mixing objectives. A distinct objective requires a
distinct branch even when it touches the same files.

Base pull requests on `main`; do not create stacked pull requests unless the
user explicitly approves that workflow. `main` accepts no direct push. Local
implementation may stop with uncommitted changes when commits are not
authorized. When commits are authorized, stage explicit paths, inspect the
staged diff, and use coherent commit boundaries and messages.

Do not initialize another repository, change remotes, push, force-push, delete
branches, merge pull requests, publish, release, or rewrite history without the
specific authorization required in the Authority and scope section.

Before authorized GitHub publication:

- review staged and untracked files and the commits being published;
- scan the staged tree and new commits for secrets, PII, and machine-local
  paths without dumping unrelated historical metadata;
- confirm the intended commit author identity, remote, base, and target;
- verify maintainer, website, version, permissions, updater URLs, licensing,
  and asset provenance;
- build and validate the exact intended commit and inspect the ZIP member list;
  and
- record the source commit and SHA-256 of a release candidate.

Do not publish ignored/private material, credentials, generated output,
external archives without an explicit redistribution decision, or
machine-specific data.

## Branch completion and handoff

A branch is complete when its objective and acceptance criteria are satisfied,
proportionate validation passes, required documentation is current, and no
known in-scope blocker remains. Stop rather than starting the next distinct
objective. Review the complete diff, status, and authorized commit history for
scope drift, and separate follow-up ideas from the current work.

Update `docs/HANDOFF.md` when pausing unfinished work, transferring
responsibility, materially changing the next action, or completing a branch
with meaningful follow-up state. Record the branch purpose, important
decisions, completed work, validation, limitations, and next authorized action.
Do not edit it merely because a turn changed files.

Recommend a new chat only at a genuine boundary where isolating a distinct next
objective would reduce context or scope risk. If the user requests a different
objective after branch completion, keep the completed branch reviewable and
move the new work to an appropriate branch from the correct base.
