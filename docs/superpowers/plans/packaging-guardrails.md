# Plan: packaging guardrails

Approved 2026-08-06. Delete when the milestone is committed.

## Problem

Three sources of truth drift: `.gitignore`, the manifest `paths_exclude_pattern`,
and the validation commands documented in `AGENTS.md`. Nothing asserts they
agree. Two defects reached a built package during this session — `CLAUDE.md`,
then `docs/HANDOFF.md` — and both were caught by manual inspection of the member
list rather than by any check.

`verify_package.py` already blocks `.git`, `.github`, `__pycache__`, mutable
user state, and `tests/`. It does not block `docs/`, `AGENTS.md`, `CLAUDE.md`,
or the three ignored local-only trees.

`CATS_VERSION` drift is already covered (`verify_package.py:171-184`); no work
needed there.

## Changes

1. `tests/verify_package.py`: replace the single-purpose `tests/` check with a
   `FORBIDDEN_TOP_LEVEL` set covering repository-only files and directories.
   Generalizes and deletes the narrower check.
2. `scripts/build.py`: derive id, version, and short hash from
   `blender_manifest.toml` and `git rev-parse`, then build, validate, and verify
   in one command. Removes hand-typed paths and stale hashes as a failure mode.
3. `blender_manifest.toml`: exclude `/scripts/`.
4. `AGENTS.md`: correct the layout section, which states no tracked `docs/` or
   `scripts/` exists, and point the validation section at the build script.

## Tests

RED: tamper a built package by inserting `docs/HANDOFF.md` and `CLAUDE.md`, and
confirm `verify_package.py` currently accepts it.

GREEN: same tampered package must fail on each forbidden entry; the real package
must still pass.

## Validation

Full CI-equivalent run: source and package validate, `verify_package.py`, the
five background smokes, armature and shape-key suites, install, and removal.

## Commit boundaries

One commit for the verifier, one for the build script plus its manifest and
`AGENTS.md` updates.
