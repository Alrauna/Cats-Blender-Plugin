# Handoff

## Repository state

- Base/default branch: `origin/main` at merge commit
  `19d46f27100ae111eac73a29fd89df79edfaf398`.
- Completed topic branch: `codex/fix-release-attestation-draft-access`, based
  directly on that commit.
- The latest published release remains `v5.2.1`.
- Manual 5.2.2 workflow run `31304178838` created draft release ID
  `367427437` and failed before attestation. The draft and its verified ZIP and
  checksum assets remain unpublished and were not modified during this fix.
- CATS version metadata remains synchronized at final version `5.2.2`; no
  additional version bump was needed because 5.2.2 has not been published.

## Incident and root cause

The merged release design gave `attest_release` only `contents: read`,
`id-token: write`, and `attestations: write`, then attempted to retrieve the
numeric draft release before downloading its primary asset. GitHub returned
`HTTP 403: Resource not accessible by integration` on the first
`GET /releases/{release_id}`. GitHub exposes draft releases only to identities
with push access, so the asset download was never reached.

The security boundary behaved correctly:

- `draft_release` built, uploaded, downloaded, and verified the stored 5.2.2
  ZIP and emitted its validated name, SHA-256, release ID, and asset ID.
- `attest_release` failed before the pinned action ran.
- `publish_release` was skipped, leaving the release as a draft.

Granting the attestation job `contents: write`, a PAT, or a push-capable GitHub
App token was rejected. Any action can access its job's `github.token` even
when that token is not explicitly passed. Full-SHA pinning mitigates action
substitution but does not replace job-level credential isolation.

## Completed correction

- `acddd0c` — remove the inaccessible draft API/download step and attest the
  stored artifact's already-verified name and digest using the pinned action's
  native inputs.
- `9c6fae0` — restrict the action `with:` mapping to exactly `subject-name` and
  `subject-digest`, including across blank lines and YAML comments.

The release graph remains fail closed:

1. `draft_release` depends on `validate` and `release_gate`, references the
   `release` environment, has only `contents: write`, and contains no actions.
   It verifies the exact public source commit, builds and validates the ZIP,
   creates the draft, uploads both assets, downloads the stored primary asset
   by numeric ID, and verifies its GitHub digest metadata and bytes.
2. `attest_release` depends on `draft_release`, has exactly `contents: read`,
   `id-token: write`, and `attestations: write`, and has no environment. Its
   only step is
   `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`, with:
   - `subject-name: ${{ needs.draft_release.outputs.archive_name }}`
   - `subject-digest: sha256:${{ needs.draft_release.outputs.sha256 }}`
3. `publish_release` depends on both preceding jobs, references the `release`
   environment, has only `contents: write`, and contains no actions. It
   rechecks numeric release/asset identity, target commit, stored digest, and
   downloaded bytes immediately before publishing the exact draft.

This cryptographically binds the attestation to the stored ZIP without giving
the action release-write credentials: the draft job proves the stored bytes
equal digest D, the isolated action attests archive name N at D, and the
publication job proceeds only if the stored bytes still equal D. No workflow
artifact transfer, new action, dependency, credential, recovery mode, or
automatic publication was introduced.

## Test-first evidence and review

The focused RED contract failed because the merged workflow still contained
`gh api` draft access and `subject-path`. After the minimal YAML correction:

- three focused credential/data-flow contracts passed;
- all 25 `tests.test_ci` tests passed;
- the action-input allowlist was mutation-tested and rejected a temporary
  `github-token` placed after a blank line and comment;
- the secure workflow was restored before commits and the full suite passed;
- independent correctness/security review reported no remaining Critical,
  Important, or Minor findings.

## Local verification

The following passed on Windows with Blender 5.2 and isolated profiles:

- `python -m unittest tests.test_ci -v` — 25 tests.
- Explicit-path `compileall` over source and tests.
- `blender.exe --factory-startup --command extension validate .`.
- `python scripts/build.py --blend <Blender 5.2>`.
- Independent `tests/verify_package.py` verification.
- `git diff --check` and clean tracked status.

Verified package from implementation commit `acddd0c`:

- Path:
  `.packaged-releases/cats_blender_plugin-5.2.2-acddd0c.zip`.
- SHA-256:
  `52538592310b08628ccc72f79b7d6656a76fcdbf0f9d796a24b0822a84b0bfbb`.
- Contents: 183 files and 129 Python modules; Blender 5.2-compatible manifest
  at version 5.2.2.
- Generated packages and Blender profiles remain ignored and must not be
  staged.

## Hosted-only checks and recovery boundary

Local verification cannot prove:

- GitHub's hosted YAML execution of the two action inputs.
- OIDC issuance and GitHub/Sigstore attestation persistence.
- `gh attestation verify` resolving the downloaded ZIP's digest attestation.
- Successful publication after the write job re-verifies the stored draft.
- Environment approval UX if protection rules are later enabled.

Draft release ID `367427437` must remain preserved until separately authorized
recovery. After this fix is reviewed and merged, an authorized maintainer must
explicitly approve deleting that failed draft and rerunning `release=5.2.2`
from the new public `main` commit. The recovery run must verify the attestation,
release target, stored ZIP digest, and final publication. Do not reuse the old
draft implicitly.

## Next action

Request explicit authorization to push this branch and open a draft pull
request against `main`. Require the three-platform validation matrix, CodeQL,
and review of the hosted workflow diff. Do not delete draft `367427437`, rerun
the release workflow, create a tag, or publish 5.2.2 as part of branch
publication.
