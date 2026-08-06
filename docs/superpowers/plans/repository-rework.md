# Plan: repository rework and maintainer transition

Implements `docs/superpowers/specs/repository-rework.md`. Delete from `main` when
the milestone is complete.

## Phase 1 — unblocked content work, on `blender-52`

1. Rewrite `README.md` in the Welcome structure with corrected 5.2 content, the
   maintainer change, acknowledgements, and upstream wikis labelled archival.
   Commit alone.
2. Repoint Material Combiner to `Alrauna/material-combiner-addon` in
   `tools/atlas.py:144,157`. Verify the release URL resolves before committing.
3. Update `CreditsPanel.maintainers1` and `maintainers2` in all four translation
   files. Keep the maintainer name untranslated inside the localized sentence.
   Flag the wording for review rather than asserting the translations are right.

Gate: `compileall`, `python scripts/build.py`, and the full CI-equivalent suite,
because translation JSON and operator modules are runtime content.

## Phase 2 — blocked on maintainer-created forks

4. Immersive Scaler: repoint `tools/scale.py:58`, the four
   `ImmersiveScalerHelpButton.URL` entries, and the two `README.md` references
   to `Alrauna/immersive_scaler`. Until that fork exists the README points at
   `triazo/immersive_scaler`, which is accurate but not the chosen target. Leave
   the attribution comment at `tools/armature_manual.py:16` pointing at the
   source the bone names actually came from. Decide `.gitmodules` separately; the
   submodule is uninitialized and absent.
5. Translation dictionary: repoint `tools/translations.py:38` and the
   `repo_owner` at line 305. Confirm the raw URL for branch `5x-translations`
   returns JSON over the network before committing, since a wrong branch name
   fails silently at runtime.

Gate: same as Phase 1, plus a live fetch of the dictionary URL.

## Phase 3 — topology, each step separately confirmed

6. Push `blender-52` to origin. Ten local commits are unpushed.
7. Create `main` from `blender-52` and push it.
8. Delete the spec and plan documents for completed milestones from `main`, per
   the handoff rule in `AGENTS.md`.
9. Set `main` as the default branch on GitHub. Maintainer action; cannot be done
   from the CLI without a token.
10. Tag the nine untagged tips as `archive/<branch>` and push the tags.
11. Delete the fifteen remote branches: `Blender-5x`, `Welcome`, `blender-36`,
    `blender-36-dev`, `blender-40`, `blender-40-dev`, `blender-41`,
    `blender-41-dev`, `blender-42`, `blender-42-dev`, `blender-43`,
    `blender-43-dev`, `blender-44`, `blender-44-dev`, `blender-5x-dev`.
12. Delete local `blender-50` and remove the `upstream` remote.

## Preservation checks

Confirm before step 11 that every deleted tip is reachable from a tag. Confirm
`blender-45`, `blender-45-dev`, `blender-52`, and `main` still exist afterward,
and that `git ls-remote --tags origin` still returns 117 tags plus the nine new
archive tags.

## Commit boundaries

One commit per numbered content step in Phases 1 and 2. Phase 3 is Git
operations, not commits, except step 8.
