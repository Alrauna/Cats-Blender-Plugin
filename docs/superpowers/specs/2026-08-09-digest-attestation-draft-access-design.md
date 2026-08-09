# Digest-Based Attestation for Draft Release Access

## Problem

Release workflow run `31304178838` created and verified the 5.2.2 draft release,
then failed in `attest_release` with `HTTP 403: Resource not accessible by
integration`. The failing command was the first request for numeric draft
release ID `367427437`; the asset download was never reached.

GitHub exposes draft releases only to identities with push access. The isolated
attestation job intentionally has `contents: read`, so its `GITHUB_TOKEN`
cannot inspect or download the draft. Granting write access or another
push-capable token would violate the security requirement that the attestation
action never execute in a job holding release-write credentials.

The failure was safely contained: `draft_release` succeeded, the attestation
action did not run, `publish_release` was skipped, and the release remains a
draft.

## Security requirements

- Keep `draft_release` and `publish_release` action-free with only
  `contents: write`.
- Keep `attest_release` limited to `contents: read`, `id-token: write`, and
  `attestations: write`.
- Keep the exact reviewed pin
  `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Attest only `cats_blender_plugin-<version>.zip`, never the checksum, source
  archives, caches, or routine CI artifacts.
- Preserve fail-closed ordering: draft verification, then attestation, then
  publication.
- Preserve numeric release/asset identity and byte verification in both
  write-capable jobs.
- Do not introduce a PAT, GitHub App credential, workflow-artifact transfer,
  new action, dependency, recovery mode, or automatic publication.

Full-SHA pinning mitigates action substitution but does not prevent an action
from accessing its job's `github.token`. Job-level credential isolation remains
the controlling security boundary.

## Considered approaches

### 1. Attest the verified name and digest — recommended

The pinned action supports `subject-name` and `subject-digest`. Remove the
inaccessible REST lookup and download from `attest_release`, and provide:

```yaml
with:
  subject-name: ${{ needs.draft_release.outputs.archive_name }}
  subject-digest: sha256:${{ needs.draft_release.outputs.sha256 }}
```

`draft_release` already obtains the SHA-256 from the built ZIP, confirms the
release API's stored digest, downloads the numeric draft asset, and verifies its
bytes before emitting the digest. `publish_release` downloads that same numeric
asset again and verifies the digest immediately before publication. Therefore:

1. Stored draft asset bytes equal digest D.
2. The isolated action attests archive name N at digest D.
3. Publication proceeds only if the stored asset still equals D.

This removes the unsupported access assumption while preserving the exact
artifact's cryptographic binding and the action/write-token boundary. It also
keeps `gh attestation verify <downloaded ZIP>` usable because verification
resolves the local file's digest.

The trade-off is that the attestation job no longer performs its own byte
download. That check is impossible with its safe token. It is not a meaningful
control against a compromised attestation action, because an action holding
OIDC and `attestations: write` could ignore any downloaded file. The full-SHA
pin and lack of release-write credentials address that threat.

### 2. Transfer a workflow artifact — not recommended

A separate read-only build job could upload the ZIP as a workflow artifact;
the action-free write job could download it through the Actions API, and the
attestation job could download it again. This retains an independent byte check
but adds upload/download actions or manual artifact-protocol code, extra
permissions, retention state, and another artifact identity. It still proves
equality to the release asset only transitively through the digest. The added
mechanism does not improve the compromised-action threat model enough to
justify the complexity.

### 3. Give the attestation job push access — rejected

Adding `contents: write`, a PAT, or a push-capable GitHub App token would make
the draft API accessible, but the pinned action could access that credential.
This directly violates the primary security requirement. Publishing before
attestation is also rejected because an attestation failure would leave a
public unattested release.

## Workflow changes

Only `.github/workflows/Cats Tests.yml` changes in production:

- Delete `Download and verify exact draft asset` from `attest_release`.
- Keep the job dependency, condition, runner, timeout, and exact permissions.
- Change the attestation step to use `subject-name` and `subject-digest` from
  the validated `draft_release` outputs.
- Keep `draft_release` and `publish_release` unchanged.

No version bump is required. Version 5.2.2 has not been published.

## Contract tests

Update `tests/test_ci.py` test-first so it requires:

- The attestation job contains no `gh api`, release URL, asset URL,
  `GH_TOKEN`, or download/hash shell step.
- The pinned action receives exactly one `subject-name` and one
  `subject-digest` tied to `draft_release` outputs.
- `subject-path` and `subject-checksums` are absent.
- `attest_release` retains its exact read/OIDC/attestation permissions.
- `draft_release` and `publish_release` retain their numeric-ID and byte
  verification, action-free write permissions, dependency ordering, and
  fail-closed publication contract.
- No workflow-artifact transfer action is introduced.

The RED failure must demonstrate that the current workflow still downloads the
draft and uses `subject-path`. The smallest YAML deletion/input replacement then
makes the focused contract and full CI policy suite GREEN.

## Hosted verification and recovery

Local tests cannot prove GitHub's OIDC issuance or attestation API behavior.
After the fix is reviewed and merged, the failed draft must not be reused
implicitly. Preserve it for diagnosis until separate authorization is given to
delete release ID `367427437`. Then rerun the manual 5.2.2 release from the new
public `main` commit and verify:

- attestation succeeds for the emitted name/digest;
- `publish_release` re-verifies and publishes the exact stored asset;
- `gh attestation verify cats_blender_plugin-5.2.2.zip -R
  Alrauna/Cats-Blender-Plugin` succeeds;
- the release target and attestation identify the new fixed commit.

Deleting the failed draft, rerunning the workflow, publishing, tagging, or
editing release assets is outside this implementation branch and requires
explicit authorization.
