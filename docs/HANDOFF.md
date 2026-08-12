# Handoff

## Repository state

- Integration base: locally available `origin/main` at
  `cfae36c0e3c1cc635186e2bc97e48964841f52c6`.
- Active branch: `codex/revise-agent-instructions`, created directly from that
  base for the approved repository-policy revision.
- The final intended working-tree diff contains only `AGENTS.md` and this
  handoff. It is not staged or committed.
- No source, tests, CI, manifest behavior, package, release state, remote, tag,
  or historical ref was changed.
- The completed release-lookup work remains separate on
  `codex/fix-release-draft-lookup` in draft pull request #5.

## Completed policy revision

`AGENTS.md` now:

- identifies protected `main` as the integration base and `blender-52` as a
  preserved migration branch;
- uses the latest locally available `main` without implying network
  authorization;
- defines one authority model for edits, local branches, staging, commits,
  network access, publication, destructive Git actions, and history rewriting;
- permits a precise request to serve as an approved design and reserves new
  approval gates for material unresolved choices;
- requires written plans only for risky or genuinely multi-step work;
- keeps TDD as the production-behavior default with a documented manual or
  characterization fallback when automation is impractical;
- scales investigation and validation with risk, uncertainty, and blast radius;
- defers unrelated discoveries instead of expanding the current branch;
- documents `scripts/build.py --allow-dirty` for development validation and
  clean exact-commit builds for release or publication work;
- updates handoff records only at meaningful work boundaries; and
- consolidates repeated Git, testing, generated-file, and publication rules
  while retaining the repository's Blender, packaging, updater, version,
  licensing, provenance, local-reference, user-data, and public-contract
  safeguards.

## Validation

- The obsolete-policy search found none of the conflicting branch, mandatory
  commit, per-turn handoff, or dirty-build language.
- The replacement-policy search found the required branch, authority,
  planning, manual-validation, regression, build, and handoff concepts.
- `python scripts/build.py --help` exited successfully and exposed
  `--allow-dirty`.
- The acceptance checklist confirmed every approved policy requirement.
- Git confirmed that `blender-52` is an ancestor of `main`.
- Manifest and package-verification checks confirmed exclusions for
  `.local-references`, `.packaged-releases`, `.test-runtime`, `docs`, and
  `scripts`.
- `git diff --check` passed.
- The policy shrank from 3,264 words to about 2,200 words while retaining the
  project-specific safeguards and executable validation guidance.

No runtime, CI, package, or Blender tests were run because this branch changes
repository instructions only. No external or subagent review was requested.

## Next authorized action

Review the uncommitted documentation diff. If it is accepted, the user may
separately authorize staging and committing it. Pushing or opening a pull
request remains a separate publication action.
