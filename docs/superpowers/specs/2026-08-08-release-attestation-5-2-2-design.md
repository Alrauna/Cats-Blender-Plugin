# Release Attestation and Version 5.2.2 Design

## Goal

Prepare CATS 5.2.2 as the first release whose published extension ZIP has
GitHub-native, signed build-provenance attestation. Preserve the existing
manual release gates, checksum verification, draft-first failure behavior, and
three-platform validation matrix.

## Verified starting point

- Local and remote `main` are both `90c1f194dedda1d5657a7b50ceff1a7dce4471cd`.
- Pull request #2 is merged and its manual release workflow successfully
  published `v5.2.1` from that commit.
- The published `cats_blender_plugin-5.2.1.zip` has SHA-256
  `b362cd49ba95de46a9ce6be7949127c16bec55b3cb8dbba73d6ee51372e0a70b`.
- The current workflow verifies a freshly built ZIP, uploads it to a draft
  release, downloads the stored ZIP, verifies its digest, and only then
  publishes the release.
- The workflow does not currently request OIDC or attestation permissions and
  does not call an attestation action.
- `blender_manifest.toml` and `CATS_VERSION` in `__init__.py` both currently
  declare `5.2.1`; `tests/verify_package.py` enforces that they remain equal.

## Scope

The change will:

- Increment `blender_manifest.toml` and `CATS_VERSION` in `__init__.py` to the
  exact final version `5.2.2`.
- Keep the Blender compatibility floor at `5.2.0` and make no runtime behavior
  change.
- Grant `id-token: write` and `attestations: write` only to the existing
  protected manual `release` job. Global permissions remain `contents: read`;
  the release job retains `contents: write`.
- Use `actions/attest` pinned to the full verified commit SHA for immutable
  release `v4.2.2`:
  `1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Attest the ZIP downloaded back from the draft release, after its existing
  SHA-256 verification and before the draft is published.
- Add static regression coverage for permission scope, immutable action
  pinning, subject selection, and release-step ordering.
- Document how a consumer verifies the downloaded ZIP with GitHub CLI.
- Correct `docs/HANDOFF.md` so it reflects merged PR #2, published `v5.2.1`,
  and the active 5.2.2 attestation branch.

The change will not:

- Attest the three seven-day validation-matrix artifacts.
- Add OIDC or attestation permissions to pull-request or ordinary validation
  jobs.
- Add an SBOM, custom predicate, offline attestation bundle, new dependency,
  reusable workflow, dry-run release mode, or separate attestation job.
- Backfill `v5.2.1`. A later workflow would attest the later workflow, not the
  original release build, so it would not be honest provenance for that run.
- Tag, publish, or dispatch the `5.2.2` release as part of branch completion.

## Attestation design

The release job will keep its current build and draft-release sequence. After
`Download and verify stored ZIP` succeeds, it will run:

```yaml
- name: Attest stored release ZIP
  uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
  with:
    subject-path: '${{ runner.temp }}/stored-release/${{ steps.release_meta.outputs.archive_name }}'
```

The release job will have these exact permissions:

```yaml
permissions:
  contents: write
  id-token: write
  attestations: write
```

Using `subject-path` makes the action calculate provenance for the exact file
downloaded from GitHub rather than trusting a separately supplied digest. The
existing digest verification proves that file is byte-identical to the locally
verified build. Placing attestation before `Publish verified release` makes
attestation a publication gate: any failure leaves the draft available for
inspection and does not expose an unattested final release.

The broader permissions apply only to this job because GitHub Actions does not
support step-scoped token permissions. The job is already limited to a manual
dispatch with a non-empty release version, public `main`, successful validation
and release-gate jobs, and the protected `release` environment. The only new
third-party executable is the GitHub-owned action pinned by full commit SHA.

## Version design

`blender_manifest.toml` remains the version source of truth and will change
from `5.2.1` to `5.2.2`. `CATS_VERSION` in `__init__.py` will change to the exact
same string. No second version definition will be added to `updater.py`; it
will continue importing `CATS_VERSION`.

The version increment intentionally prepares a future final release but does
not authorize a tag, workflow dispatch, GitHub release, or publication.

## Testing and validation

Test-driven implementation will begin with a focused failing workflow-policy
test in `tests/test_ci.py`. It will require:

- Exactly one `id-token: write` and one `attestations: write` occurrence.
- Their presence inside the release-job portion of the workflow.
- The exact immutable `actions/attest` SHA.
- The stored-release ZIP as `subject-path`.
- Step order: stored ZIP verification, attestation, publication.

The existing immutable-action test will continue rejecting tag references.
The production workflow will then receive the smallest change that makes the
new policy test pass.

Version validation will rely on the existing package verifier contract plus
targeted assertions and release identity checks. Final validation will include:

- The targeted RED/GREEN workflow policy test.
- `python -m unittest tests.test_ci -v`.
- Explicit-path `compileall` over the repository source and tests.
- Blender 5.2 source validation and `scripts/build.py` from a clean commit.
- `tests/verify_package.py` and inspection of the resulting ignored ZIP.
- `git diff --check`, complete diff/status review, and the GitHub pull-request
  validation matrix when publication is authorized.

The attestation action cannot be truthfully exercised by a pull request or a
validation-only dispatch without broadening credentials or generating
meaningless provenance. Its first end-to-end execution will therefore be the
intentional future `5.2.2` release dispatch from public `main`. Workflow policy,
GitHub workflow parsing, action pinning, and all surrounding release gates will
be validated before merge; this remaining live-release limitation will be
recorded in the handoff.

## Documentation

`README.md` will add the minimal online verification command:

```text
gh attestation verify cats_blender_plugin-5.2.2.zip \
  -R Alrauna/Cats-Blender-Plugin
```

The checksum file remains published and documented by the release itself; the
attestation adds signed origin and build-workflow identity rather than
replacing SHA-256 verification.

## Acceptance criteria

- Manifest and runtime versions are exactly `5.2.2` and remain synchronized.
- Global and validation-job permissions are unchanged.
- Only the protected release job can mint an OIDC token and write attestations.
- The exact GitHub-stored ZIP is attested after digest verification and before
  publication.
- Any attestation failure prevents publication and leaves the draft intact.
- Every action reference remains a full 40-character commit SHA.
- Consumer verification is documented.
- Applicable local checks and the pull-request matrix pass.
- No release, tag, or workflow dispatch occurs during implementation.
