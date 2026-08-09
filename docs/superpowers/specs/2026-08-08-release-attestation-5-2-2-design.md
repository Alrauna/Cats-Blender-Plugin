# Release Attestation and Version 5.2.2 Design

## Goal

Prepare CATS 5.2.2 as the first release whose primary downloadable extension
ZIP has GitHub-native, signed build-provenance attestation. Keep every action,
including the pinned attestation action, out of jobs with `contents: write`.
Preserve the existing manual release gates, exact-source rebuild, checksum
verification, draft-first failure behavior, and three-platform validation
matrix.

## Verified repository and release state

- Local and remote `main` are both
  `90c1f194dedda1d5657a7b50ceff1a7dce4471cd`.
- The clean topic branch `codex/release-attestation-5-2-2` contains only the
  committed design/handoff checkpoint `b71b684` on top of `main`; it has not
  been pushed and has no pull request.
- Pull requests #1 and #2 are merged. There are no open pull requests.
- Pull request #2's release workflow successfully published final `v5.2.1`
  from `90c1f19` in workflow run `31284826473`.
- The release has two uploaded assets:
  `cats_blender_plugin-5.2.1.zip` and `SHA256SUMS.txt`. GitHub-generated source
  archives are not release assets produced by the workflow.
- The primary ZIP has SHA-256
  `b362cd49ba95de46a9ce6be7949127c16bec55b3cb8dbba73d6ee51372e0a70b`.
- The current release job fetches `github.sha` from the public repository into
  a new Git repository, verifies the checked-out SHA, builds and validates a
  fresh ZIP, creates a draft, uploads both assets, downloads and verifies the
  stored ZIP, and publishes the draft.
- Global workflow permissions are `contents: read`; the current monolithic
  release job has `contents: write` and references the `release` environment.
- The repository's default workflow-token setting is read-only.
- The `release` environment exists but currently has no protection rules and
  no deployment branch policy. Calling it "protected" would be inaccurate.
  It caused no approval prompt for the 5.2.1 release.
- `blender_manifest.toml` and `CATS_VERSION` in `__init__.py` both declare
  `5.2.1`; `tests/verify_package.py` enforces their equality.

`docs/HANDOFF.md` was stale on `main`: it described pull request #2 and the
5.2.1 release path as pending after both had completed. The topic-branch
handoff corrected those claims, but its single-job attestation design is
superseded by this revision.

## Threat model and security decision

An action can access `github.token` even when the workflow does not explicitly
pass the token. Full-SHA pinning prevents a moved tag from silently changing
the code and records the reviewed action revision, but it does not prevent a
bug or compromise in that pinned code from using every permission available to
its job. Therefore full-SHA pinning mitigates supply-chain substitution but
does not solve the problem of an action receiving `contents: write`.

CATS will enforce isolation through job boundaries. No job with
`contents: write` will contain a `uses:` step. The attestation action will run
only in a separate job whose repository permission is `contents: read`.

The design protects against these failure modes:

- Attestation action attempts repository mutation: its job token lacks
  `contents: write`.
- Attestation fails: publication never runs and the release remains a draft.
- A different file is downloaded between jobs: every consumer verifies the
  SHA-256 produced by the draft job.
- The named draft asset is deleted or replaced: jobs address the original
  numeric asset ID and verify its name and digest; deletion fails closed.
- A different draft is substituted under the tag: downstream jobs address the
  original numeric release ID and verify its tag/draft state.
- Routine matrix packages are mistaken for releases: only the primary ZIP
  attached to the exact draft release is attested.

GitHub does not provide an atomic "verify asset, attest, and publish" operation.
A repository writer could theoretically mutate a draft after the final check
and before publication. Re-downloading and verifying in `publish_release`
narrows that time-of-check/time-of-use window without adding an action. The
remaining non-atomic API boundary will be documented rather than hidden.

## Considered approaches

### 1. Add attestation to the existing release job

This is the smallest YAML diff and was the original design. The action would
run after stored-ZIP verification and before publication.

Rejected: the job has `contents: write`, and actions can access `github.token`
without an explicit input. Pinning the action by full SHA does not create a
credential boundary.

### 2. Split three jobs and identify the draft only by tag/name/digest

This follows the proposed AMS shape closely. It passes three short strings as
job outputs and uses `gh release download <tag> --pattern <name>` downstream.

Viable in principle, but not preferred: GitHub documents `contents: read` for
downloading a release asset, while the documented "get release by tag"
endpoint describes published releases. CATS has no disposable draft with which
to prove that `gh release download` can resolve a draft by tag under a
read-only job token. Depending on undocumented draft lookup behavior would
make the first real 5.2.2 release the experiment.

### 3. Split three jobs and pass immutable GitHub release/asset IDs

Recommended. In addition to the validated tag, archive name, and SHA-256, the
draft job passes the numeric draft release ID and primary asset ID. These are
small job outputs, not an artifact-transfer mechanism or secret. Downstream
jobs download the asset directly through GitHub's release-asset API, whose
documented token requirement is `contents: read`.

This adds two identifiers but removes draft-discovery ambiguity, detects
asset/release replacement, and keeps the release itself as the only byte
transfer mechanism.

## Recommended job architecture

The existing `validate` matrix and `release_gate` remain unchanged.

```text
validate + release_gate
          |
          v
    draft_release  (contents: write; no actions)
          |
          v
    attest_release (contents: read + OIDC + attestations; pinned action)
          |
          v
   publish_release (contents: write; no actions)
```

All three release jobs retain the current defense-in-depth condition: manual
`workflow_dispatch`, non-empty release input, `refs/heads/main`, and public
repository. Dependency ordering is also mandatory, so no downstream job can
run after a skipped or failed predecessor.

### `draft_release`

Exact permissions and environment:

```yaml
environment: release
permissions:
  contents: write
```

Responsibilities, in order:

1. Depend on successful `validate` and `release_gate` jobs.
2. Fetch only `github.sha` from the public repository into a new Git
   repository, check out detached, and compare `HEAD` to the expected SHA.
3. Acquire checksum-verified Blender 5.2.0.
4. Validate source; build, validate, and package-verify exactly
   `cats_blender_plugin-5.2.2.zip`.
5. Produce `SHA256SUMS.txt`, validated tag/archive outputs, and the ZIP digest
   with the existing `scripts/ci.py` primitives.
6. Refuse any existing tag or release.
7. Create the draft release targeting the exact workflow SHA.
8. Upload the primary ZIP and checksum file.
9. Query the exact draft, require one primary asset with the expected name,
   capture numeric `release_id` and `asset_id`, download that asset by ID, and
   verify its SHA-256.
10. Expose only `tag`, `archive_name`, `sha256`, `release_id`, and `asset_id` as
    job outputs. Validate IDs as decimal integers and retain the existing
    single-line output protection.

This job contains no `uses:` step. Hosted Git and GitHub CLI commands remain
the only operations with the write token.

### `attest_release`

Exact permissions:

```yaml
permissions:
  contents: read
  id-token: write
  attestations: write
```

This job does not reference an environment and runs on `ubuntu-24.04`. It:

1. Depends on `draft_release` and receives only its five validated outputs via
   `needs.draft_release.outputs` and step environment variables.
2. Uses the read-only token to query the numeric release ID; verifies it is
   still a draft with the expected tag and exact primary asset ID/name.
3. Downloads the primary ZIP directly by numeric asset ID.
4. Independently calculates SHA-256 and compares it with the draft output.
5. Runs only:

   ```yaml
   - name: Attest stored release ZIP
     uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
     with:
       subject-path: '${{ runner.temp }}/stored-release/${{ needs.draft_release.outputs.archive_name }}'
   ```

The action SHA is the reviewed, verified commit for immutable `v4.2.2`. The
primary extension ZIP is the only subject. `SHA256SUMS.txt`, source archives,
routine CI packages, caches, logs, and unrelated files are not attested.

### `publish_release`

Exact permissions and environment:

```yaml
environment: release
permissions:
  contents: write
```

This job runs on `ubuntu-24.04`, contains no `uses:` step, and:

1. Depends on both `draft_release` and successful `attest_release`.
2. Queries the exact numeric release ID and requires it to remain a draft with
   the expected tag and original primary asset ID/name.
3. Downloads that asset by ID again and independently verifies the expected
   SHA-256 immediately before publication.
4. Publishes that exact release ID through the GitHub API.

Any failure leaves the release as a draft. The job does not rebuild, re-upload,
or replace any asset.

## Environment approval behavior

The current `release` environment has no protection rules, so splitting the
write operations creates two deployment records but no approval prompts.

If required reviewers or other protection rules are configured later, both
`draft_release` and `publish_release` must reference the environment because
both hold `contents: write`. Since the jobs are sequential, this can require
two approvals. CATS should accept that operational cost rather than leave one
write-capable job outside the protection boundary. Avoiding a second prompt is
not a valid reason to combine the attestation action with a write token or to
make draft creation unprotected.

Calling the path "protected" requires a separate repository-setting decision.
Enabling required reviewers and a deployment branch policy is recommended but
is not authorized by this code change and cannot be implemented in workflow
YAML alone.

## Version design

`blender_manifest.toml` remains the version source of truth and changes from
`5.2.1` to the CATS-specific next patch version `5.2.2`. `CATS_VERSION` in
`__init__.py` changes to the exact same string. `updater.py` continues importing
that value; no independent version definition is added. Blender compatibility
remains `5.2.0`.

AMS's `1.3.1` version is unrelated and will not appear in CATS metadata.
Preparing 5.2.2 does not authorize a tag, workflow dispatch, release, or push.

## Existing and proposed contract tests

Current coverage in `tests/test_ci.py` enforces:

- Every `uses:` reference is a full 40-character SHA.
- Checkout drops persisted credentials.
- Global `contents: read`, runner/trigger policy, and explicit compile paths.
- The monolithic release is manual, public-main-only, environment-scoped,
  write-scoped, draft-first, checksum-bearing, and dependent on validation.
- Release version/name validation, strict GitHub outputs, and SHA-256 helpers.

It does not currently enforce an action allowlist by job, separation of write
permissions from actions, exact permission sets, multi-job release ordering,
job-output allowlists, or re-verification before publication.

Test-driven implementation will add a small test-only job-block extractor and
RED contract tests in `tests/test_ci.py` that require:

- Global permissions remain exactly read-only.
- `draft_release` and `publish_release` each have `contents: write`, reference
  `environment: release`, and contain no `uses:` step.
- `attest_release` has exactly `contents: read`, `id-token: write`, and
  `attestations: write`; it does not have `contents: write` or an environment.
- The only action in `attest_release` is
  `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`.
- No other job receives `id-token: write` or `attestations: write`.
- `draft_release` still rebuilds exact public `github.sha`, validates the ZIP,
  creates a draft, uploads ZIP/checksum, and verifies the stored primary asset.
- Its job-output allowlist is exactly tag, archive name, SHA-256, release ID,
  and asset ID.
- `attest_release` depends on `draft_release`, addresses the exact IDs,
  verifies draft identity/name/digest, and attests only the primary ZIP.
- `publish_release` depends on both prior jobs, repeats identity and digest
  checks, and publishes only after successful attestation.
- No workflow-artifact upload/download step is introduced into the release
  pipeline.
- No source archive, checksum file, matrix artifact, cache, or unrelated path
  appears as an attestation subject.
- All action references continue to satisfy the existing immutable-SHA test.

The version RED check is the existing release gate invoked with `5.2.2`; it
must fail against the 5.2.1 manifest before the version edit and pass after the
manifest and `CATS_VERSION` change. The package verifier continues enforcing
their equality.

## Target files

- Modify `.github/workflows/Cats Tests.yml`: split the release pipeline,
  isolate permissions, pass validated outputs, and attest the stored ZIP.
- Modify `tests/test_ci.py`: add RED/GREEN workflow security contracts.
- Modify `blender_manifest.toml`: set version `5.2.2`.
- Modify `__init__.py`: set `CATS_VERSION = "5.2.2"`.
- Modify `README.md`: document online `gh attestation verify` usage.
- Modify `docs/HANDOFF.md`: record branch state, validation, operational
  limitations, and the future release action.
- Retire this spec and its implementation plan after the verified milestone,
  as required by repository policy.

No new implementation module, dependency, workflow, or artifact-transfer
mechanism is planned. `scripts/ci.py` should be reused unchanged unless the
test-first plan demonstrates that safe ID/output validation cannot remain
small and clear in the workflow.

## Validation and hosted-only evidence

Local and pull-request validation will include:

- Targeted RED/GREEN workflow contract tests.
- `python -m unittest tests.test_ci -v`.
- `python scripts/ci.py check-release --version 5.2.2 --manifest
  blender_manifest.toml` before and after the version edit.
- Explicit-path `compileall`.
- Blender 5.2 source validation and `scripts/build.py` from a clean commit.
- Package verification, member inspection, and SHA-256 recording.
- Complete diff, status, commit-scope, and `git diff --check` review.
- GitHub pull-request parsing and the Windows/Linux/macOS validation matrix
  when push/PR publication is separately authorized.

These interactions cannot be proven locally or safely exercised on a pull
request:

- A read-only job token downloading an asset belonging to an unpublished draft
  by numeric asset ID. GitHub documents `contents: read` for the endpoint, but
  CATS has no disposable draft for a non-publishing integration test.
- OIDC issuance, Sigstore signing, attestation API persistence, and the
  resulting `gh attestation verify` experience.
- Fail-closed behavior after a real attestation failure.
- Environment approval prompts if protection rules are configured later.
- The final transition of the verified draft to a published release.

The first end-to-end exercise is therefore the intentional future 5.2.2
release dispatch from public `main`. A failure at any stage must leave the
draft unpublished for inspection. No implementation or branch-completion step
will dispatch that release.

## Documentation

`README.md` will add the minimal consumer command:

```text
gh attestation verify cats_blender_plugin-5.2.2.zip \
  -R Alrauna/Cats-Blender-Plugin
```

The published checksum remains useful for byte integrity. Attestation adds
signed origin and workflow identity; it does not replace SHA-256 verification.

## Acceptance criteria

- Manifest and runtime versions are exactly `5.2.2` and synchronized.
- Global and validation-job permissions are unchanged.
- No job containing an action has `contents: write`.
- Only `attest_release` can mint an OIDC token or write attestations, and its
  repository access is read-only.
- Both jobs with `contents: write` contain no actions and reference the
  `release` environment.
- The exact stored primary ZIP is addressed by asset ID, independently verified
  in every downstream job, and is the sole attestation subject.
- Attestation is a required dependency of publication; failure leaves a draft.
- Publication targets the exact draft release ID and re-verifies immediately
  before publishing.
- Every action reference remains a full 40-character commit SHA.
- No workflow-artifact transfer or new dependency is introduced.
- Consumer verification and hosted-only limitations are documented.
- Applicable local checks and the pull-request matrix pass.
- No release, tag, push, or workflow dispatch occurs during implementation.
