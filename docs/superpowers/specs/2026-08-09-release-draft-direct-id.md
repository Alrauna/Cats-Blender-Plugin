# Release Draft Direct-ID Design

## Problem

Hosted release run `31307655995` successfully created a draft and uploaded its
assets, then failed because the verification step immediately searched the
paginated releases collection for that draft. The collection query did not
return exactly one match, so the workflow failed closed before attestation.

## Approved design

Create the draft through GitHub's release REST endpoint, capture the numeric
release ID from the successful create response, validate it, and expose it as a
step output. Keep the existing successful `gh release upload` operation. Pass
the captured ID into stored-release verification and retrieve the draft by its
numeric resource URL instead of rediscovering it through the releases list.

Preserve the existing preflight checks, draft metadata and target commit,
stored asset digest and byte verification, job outputs, attestation isolation,
and fail-closed publish ordering. Do not add retries, sleeps, new actions,
dependencies, artifact transfer, permissions, or tokens.

## Hosted limitation

Local contract tests cannot prove GitHub's release API consistency or hosted
token behavior. A protected manual release run after merge remains required.
