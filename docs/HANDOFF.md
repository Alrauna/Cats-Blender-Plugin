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

Revised design pending user re-approval:
`docs/superpowers/specs/2026-08-08-release-attestation-5-2-2-design.md`.

Security review found that the original single-job design would expose the
`contents: write` token to the attestation action through `github.token`, even
without an explicit token input. The revised design splits release work into
`draft_release`, read-only `attest_release`, and `publish_release`; no job that
contains an action has `contents: write`.

The current `release` environment has no protection rules or deployment branch
policy. It produces no approval prompt today. Both write-capable jobs will
still reference it so future protection rules cover both; if required reviewers
are later enabled, two sequential approvals may be necessary.

The revised design also passes numeric release/asset IDs alongside the validated
name, tag, and digest. This avoids relying on undocumented read-only lookup of
an unpublished draft by tag and introduces no workflow-artifact transfer.

## Next action

Review and re-approve the revised written design specification. After approval,
write and review the test-first implementation plan before editing production
files.
