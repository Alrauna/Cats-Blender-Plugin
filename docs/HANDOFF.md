# Handoff

## Repository state

- Default/base branch: `main` at `90c1f194dedda1d5657a7b50ceff1a7dce4471cd`.
- Pull request #2 (`codex/ci-hardening-release`) was merged into `main` on
  2026-08-08; its remote topic branch has been deleted.
- Active topic branch: `codex/release-attestation-5-2-2`, based directly on
  current `origin/main`.
- `blender-52` remains an older historical development branch at `c1d020f`.
- Checked-in manifest/runtime version remains `5.2.1` until implementation of
  the approved 5.2.2 design begins.

## Verified release state

- Manual workflow run `31284826473` passed the Windows, Linux, and macOS
  validation matrix and published final release `v5.2.1` from `90c1f19`.
- Published ZIP: `cats_blender_plugin-5.2.1.zip`.
- Published ZIP SHA-256:
  `b362cd49ba95de46a9ce6be7949127c16bec55b3cb8dbba73d6ee51372e0a70b`.
- The workflow uploaded and verified `SHA256SUMS.txt`, downloaded and verified
  the stored ZIP, and then published the draft.
- `v5.2.1` has no build-provenance attestation and will not be backfilled.

## Active objective

Prepare version `5.2.2` as the first GitHub-attested release while preserving
the existing manual release and validation controls.

Approved design:
`docs/superpowers/specs/2026-08-08-release-attestation-5-2-2-design.md`.

The design limits OIDC and attestation write permissions to the existing
protected release job and attests the GitHub-stored ZIP after digest
verification but before publication. It does not authorize a release dispatch,
tag, push, or GitHub release.

## Next action

Review the written design specification. After approval, write and review the
test-first implementation plan before editing production files.
