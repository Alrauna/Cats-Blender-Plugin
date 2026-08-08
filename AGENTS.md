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
- `scripts/`: repository tooling; excluded from the extension package.
- `docs/`: handoff notes and in-flight Superpowers specs and plans; excluded
  from the extension package.
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

Keep `docs/` and `scripts/` excluded by `blender_manifest.toml`. Verify the
current tree before documenting or relying on any directory.

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

## Development approach

- Superpowers owns the development lifecycle. Use its phases in this order when
  they apply: investigate, design, obtain design approval, write a test-first
  plan, obtain plan approval, implement, review, verify, and commit.
- Begin every defect or unexpected result with systematic debugging. Establish
  a reproduction and root cause before proposing or editing production code.
- Treat new or changed behavior—including UX, API, architecture, cache,
  assignment, material resolution, and performance behavior—as design work.
  Use brainstorming, present the design, and obtain user approval before
  production edits.
- Convert an approved design or other multi-step production request into a
  written implementation plan with explicit files, RED/GREEN tests, validation,
  preservation checks, and commit boundaries. Obtain user approval before
  execution. A plan may be concise for a narrow change, but a small expected
  diff is not a reason to omit it.
- Design specs and implementation plans live in `docs/superpowers/specs/` and
  `docs/superpowers/plans/` while the work is in flight, and are committed so
  the approved wording is reviewable. Delete them from `main` once the milestone
  they describe is complete and committed. Git history retains them, so a
  completed milestone leaves its rationale recoverable without carrying
  superseded documents in the working tree. Do not treat that deletion as
  optional cleanup; it is the last step of the milestone.
- Execute approved plans with `executing-plans` by default.
  `subagent-driven-development` or parallel dispatch requires an explicit user
  request and independent work that can be safely isolated.
- Use test-driven development for every production behavior change: demonstrate
  the generated or synthetic regression before the production edit, implement
  the smallest fix, and run the applicable change gate. Track plan progress and
  record any material deviation; stop for approval when findings change the
  agreed behavior, scope, risk, or architecture.
- Review material production changes for correctness before completion. Use
  `requesting-code-review` for major or risky milestones and
  `receiving-code-review` before acting on review feedback. Use
  `verification-before-completion` before success claims or commits, and
  `finishing-a-development-branch` only when integration is actually requested.
- Ponytail governs scope inside every Superpowers phase. Use it during
  investigation, design, planning, implementation, and review to prefer reuse,
  Blender/Python-native behavior, minimal dependencies, minimal abstractions,
  and the smallest correct diff. Ponytail may recommend deleting or deferring
  work, but it may not skip investigation, design or plan approval, TDD,
  review, verification, preservation checks, or required acceptance gates.
- Read-only inspection, status reporting, and mechanical documentation
  corrections that do not create or change product/process policy may proceed
  without design, plan, or implementation artifacts. They still require
  evidence for factual claims and `git diff --check` when files change.
- Direct user instructions and repository safety invariants take precedence
  over both toolsets. Do not create ceremony merely to demonstrate a skill, but
  do not relabel required reasoning, approval, or verification as ceremony.

## Handoff maintenance

Update `docs/HANDOFF.md` at the end of a turn that changes repository state or
materially changes what the next turn must address. Pure read-only answers and
status checks that leave the next action unchanged do not require a handoff
edit. Remove or revise items that no longer require immediate attention.

## Testing and CI Requirements

- Testing is part of implementation, not a separate cleanup task: before making changes, inspect the existing test suite, CI configuration, build/package configuration, public interfaces, primary workflows, integration points, and relevant existing coverage, and assume that changes may affect behavior outside the files or functions directly edited.
- For every non-trivial change, apply all applicable validation layers: basic/static validation such as syntax, compilation, imports, manifests, packaging, configuration, and dependency resolution.
- Maintain fast smoke tests proving the project remains fundamentally usable, including installation or initialization in a clean environment, import/loading, registration and unregistration where applicable, construction of important objects, presence of expected public modules/classes/operators/commands/identifiers/properties, execution of at least one minimal representative happy-path workflow, production of minimally valid output, clean shutdown, and preservation of critical compatibility or integration contracts.
- Add targeted tests covering the changed behavior, relevant edge cases, and failure paths.
- Add regression tests for reproducible defects whenever reasonably practical.
- Add integration tests whenever behavior crosses components, dependencies, applications, plugins, file formats, or external tools.
- When the possible blast radius is unclear, do not assume existing tests are sufficient: inspect callers, consumers, public contracts, integrations, and important invariants, compare behavior before and after the change where practical, run broader smoke/integration coverage, and add characterization tests for important existing behavior that lacks reliable documentation or coverage.
- Tests should protect meaningful observable behavior and stable contracts rather than implementation details or arbitrary test-count targets, and must be deterministic, repeatable, isolated from user-specific machine state, non-destructive, reasonably fast, explicit about fixtures and prerequisites, and runnable unattended through documented commands.
- During development, run the smallest relevant tests frequently, then all directly affected tests, the smoke suite, and broader integration or full-suite testing whenever the blast radius warrants it; do not claim success from code inspection alone, and record the validation commands performed and their results.
- Any useful, stable, unattended test created locally must be evaluated for CI inclusion and normally integrated into CI rather than left as an undocumented local check.
- CI should at minimum catch syntax/compile/import failures, installation or packaging failures, smoke-test failures, public API or compatibility-contract breakage where applicable, targeted regressions, and failures on supported runtimes or platforms where feasible.
- Expensive tests may live in separate scheduled or manual jobs so that a small, fast “must never fail” smoke gate remains on normal changes.
- Never weaken, delete, skip, or rewrite a failing test merely to make CI pass: first determine whether the implementation is wrong, the test is wrong, or expected behavior intentionally changed, preserve tests representing valid contracts, and update expectations only for deliberate and justified behavior changes.
- Treat every discovered failure mode, invariant, compatibility requirement, regression, or newly learned way the project can break as reusable engineering knowledge: whenever such knowledge is discovered, explicitly ask whether it can be converted into a permanent automated test, and add that test when practical so the test suite and CI continuously accumulate institutional knowledge rather than requiring future agents or maintainers to rediscover the same risks.
- A change is not complete until relevant automated tests and smoke tests pass, new behavior has appropriate coverage, fixed defects have regression coverage where practical, affected integration contracts have been checked, useful repeatable tests have been considered for CI, and no known validation failure is hidden or ignored.
- When adequate automation is genuinely impractical, explicitly document what remains untested, why it could not be automated, and what manual validation was performed instead.

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
python -W ignore::SyntaxWarning -m compileall -q -f __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
python scripts/build.py --blend <blender>
```

Do not pass `.` to `compileall`. It descends into `.local-references/` and
`.test-runtime/` and writes bytecode into the read-only reference tree. Name the
source paths explicitly, as above.

Build with `scripts/build.py` rather than by hand. It names and places the
package itself, then validates the source, validates the package, and runs
`tests/verify_package.py`. It refuses to build a dirty tracked tree. Report the
final path after building.

All Blender extension builds, including release candidates, validation builds,
and test builds, must live in `.packaged-releases/`. Do not write build ZIPs to
the repository root, `.test-runtime/`, or another source directory.

`tests/verify_package.py` enforces the exclusions: its `FORBIDDEN_TOP_LEVEL` set
fails the build when repository-only material reaches a package. Add new
repository-only directories to that set and to `paths_exclude_pattern` in the
same change.

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

## Git policy

Treat each topic branch as a bounded unit of work with one coherent objective. Do not continue onto materially different work merely because it is related, convenient, discovered during implementation, or part of the same conversation.

Before beginning any non-trivial implementation task:

- Inspect the current branch, its relationship to `main`, its existing commits, and the working tree.
- Determine whether the requested work belongs to the current branch's established scope.
- Check whether an existing local branch already has an appropriate scope for the work.
- If the work belongs on an existing suitable branch, stop and switch to that branch before modifying files.
- If no suitable branch exists, stop and create a new topic branch from an up-to-date `main` before modifying files.
- If the current branch contains unfinished work that prevents a safe switch, preserve that work appropriately and explicitly report the situation rather than mixing the new task into the branch.
- Do not interpret user momentum, conversational continuity, or phrases such as "also," "while you're here," or "next" as permission to expand the current branch's scope.

A materially different objective requires a separate branch even when it touches the same files, component, feature area, or bug. Examples include moving from a bug fix to refactoring, adding an unrelated improvement discovered during testing, performing cleanup not necessary for the current acceptance criteria, beginning the next planned milestone, or addressing a separate review concern.

When uncertain whether work belongs on the current branch, prefer stopping and separating it. Branches and pull requests should be small enough that their purpose can be described accurately in one concise sentence and reviewed independently.

Start each new topic branch from an up-to-date `main` and land it through a pull request. `main` is protected and accepts no direct push.

Base pull requests on `main`, not on another unmerged topic branch. Do not create stacked pull requests unless the user explicitly approves a stacked workflow. When new work genuinely depends on an unmerged branch, finish and merge the prerequisite branch first, update `main`, then create or rebase the dependent topic branch onto the updated `main` before opening its pull request.

During implementation, commit each coherent, verified unit before beginning a materially different unit of work. Do not accumulate unrelated completed changes through a long coding session or conversation. Stage explicit paths, inspect the staged diff, and ensure every commit contains only the scope described by its commit message.

Preserve unrelated user changes. Never discard, rewrite, stage, or commit unrelated modifications merely to obtain a clean working tree. Never commit ignored, private, credential-bearing, machine-local, reference-only, or generated outputs unless the repository explicitly requires them.

Do not initialize another repository, change repository remotes, push branches, force-push, delete branches, merge pull requests, or otherwise publish or destructively alter Git state without the approval required by the surrounding instructions. Rewriting history is permitted only when rebasing or cleaning up a branch that has never been published; rewriting published history requires separate approval.

### Branch completion and handoff

Continuously distinguish between "more work could be done" and "the branch's intended work is complete." Do not use spare context, remaining ideas, newly discovered opportunities, or conversational momentum as reasons to extend a completed branch.

Consider the branch complete when its stated objective and acceptance criteria are satisfied, appropriate tests and validation pass, required documentation for that scope is updated, and no known blocker remains that must be fixed before review.

When the branch reaches that state:

- Stop implementation rather than beginning the next task.
- Review the complete branch diff and commit history for accidental scope expansion.
- Run the appropriate final validation.
- Update `docs/HANDOFF.md` with the branch's purpose, important decisions, completed work, validation performed, known limitations or follow-up work, and the recommended next action.
- Explicitly separate follow-up ideas into future work rather than implementing them on the completed branch.
- Present the branch as ready for review, commit/PR preparation, or whatever publication step the user has authorized.

After `docs/HANDOFF.md` accurately captures the completed state, recommend ending the current chat and starting a new chat before beginning the next branch or substantial objective. The new chat should begin by reviewing `docs/HANDOFF.md`, the relevant repository state, and the new branch's intended scope. This handoff boundary is preferred once a branch is genuinely complete because carrying a finished implementation's full conversational history into unrelated work wastes context and increases the risk of scope drift.

Do not recommend a new chat merely because the conversation is long. Recommend it when there is a natural work boundary: the current branch is complete, its state has been documented, and the next meaningful work should occur on another branch.

If the user asks for additional implementation after a branch has reached this completion point, first classify the request against the completed branch's scope. If it is a distinct objective, do not modify files on the completed branch. Stop, explain that the existing branch should remain reviewable, and switch to an existing suitable branch or create a new topic branch from the appropriate updated base before continuing.