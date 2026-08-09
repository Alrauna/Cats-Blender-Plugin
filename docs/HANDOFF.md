# Handoff

## Repository state

- Default branch: `origin/main` at merge commit
  `cfae36c0e3c1cc635186e2bc97e48964841f52c6`.
- Active branch: `codex/fix-release-draft-lookup`, created directly from that
  commit to fix the hosted release verification failure. Draft pull request
  #5 targets `main`:
  `https://github.com/Alrauna/Cats-Blender-Plugin/pull/5`.
- CATS version metadata remains synchronized at final version `5.2.2`.
- The latest published release remains `v5.2.1`.
- Failed draft release `367444039`, created by run `31307655995` for target
  `cfae36c0e3c1cc635186e2bc97e48964841f52c6`, was permanently deleted under
  the user's explicit instruction. Its ZIP asset ID was `507383000` with
  SHA-256 `2b0bee54d9718c7c14f8d772c9d3f3baab84ad50bfa1bfddb1316c6ff49e0ccd`;
  checksum asset ID was `507383002`. Follow-up queries found no `v5.2.2`
  release or Git tag.

## Hosted incident and root cause

Manual release run `31307655995` successfully passed all validation and the
release gate, created the draft, and uploaded both assets. The draft job then
failed before attestation while verifying the stored release:

```text
jq: error: draft release is missing or duplicated
```

Verification immediately searched the paginated releases collection for the
new draft and required exactly one match. The draft's successful creation and
asset uploads prove that the failure was the post-create collection lookup,
not release creation. The collection did not expose a unique match at that
instant, so the workflow failed closed. `attest_release` never ran and
`publish_release` was skipped.

## Approved correction

The draft job now creates the release with `POST /releases`, captures the
authoritative numeric `.id` from the successful response, validates it, and
emits it as `steps.created_release.outputs.release_id`. The existing successful
`gh release upload` command remains. Stored-release verification consumes the
captured ID and calls `GET /releases/{id}` directly; it no longer rediscovers
the new draft through the releases collection.

The following boundaries are unchanged:

- `draft_release`: `contents: write`, protected `release` environment, no
  actions, exact-commit build, draft creation, upload, stored-byte verification.
- `attest_release`: `contents: read`, `id-token: write`,
  `attestations: write`, no environment, and only
  `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6` with the verified
  subject name and digest.
- `publish_release`: `contents: write`, protected `release` environment, no
  actions, and re-verification of the exact release, asset, digest, and bytes
  before publication.

Full-SHA pinning mitigates action substitution but does not make it safe to
give an action `contents: write`; isolation remains enforced by job boundaries.
No retry, sleep, new action, dependency, token, permission, artifact transfer,
or alternate publication path was added.

## Test-first evidence

The new contract initially failed because the create step had no ID output and
verification used the paginated releases list. After the minimal workflow
change:

- `python -m unittest tests.test_ci.WorkflowPolicyTests -v` — 10 passed.
- `python -m unittest tests.test_ci -v` — 26 passed.
- The regression contract requires REST creation, numeric `.id` extraction,
  step-output propagation, direct numeric verification, and absence of the
  collection lookup from the verification step.

## Hosted-only checks

Local tests cannot prove GitHub's hosted REST read-after-write behavior, the
OIDC attestation exchange and persistence, or final publication. After review
and merge, an authorized maintainer must manually rerun `release=5.2.2` from
the new public `main` commit and confirm the draft verification, attestation,
publish re-verification, final release asset, and provenance.

## Next action

Implementation milestone `59bad47` is complete. Wait for draft pull request
#5's hosted workflow validation and review. Do not rerun or publish 5.2.2
before the fix is reviewed and merged.
