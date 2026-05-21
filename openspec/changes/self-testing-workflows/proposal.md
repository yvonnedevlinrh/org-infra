## Why

org-infra's consumer workflows (`ci_*`) reference their own reusable workflows via
SHA-pinned refs (e.g., `@cfd981e...  # v0.2.1`). This means changes to reusable
workflows are not tested by org-infra's own CI until after a release is cut and the
SHA refs are bumped. Broken reusable workflows can be released and synced to all
downstream repositories before the breakage is caught.

## What Changes

- Replace all SHA-pinned reusable workflow references in org-infra's `ci_*` and
  `reusable_scheduled.yml` files with local path syntax
  (`./.github/workflows/reusable_*.yml`) so org-infra tests the current version of
  its own reusable workflows, including on PRs.
- Add a transformation step in the sync script that converts local workflow refs to
  SHA-pinned cross-repo refs (using the latest release tag and commit SHA) when syncing
  `ci_*` files to downstream repositories.
- Add auto-detection of the latest org-infra release in the sync script, with a
  `--release-ref` override for cases where no release exists or a specific version is
  desired.

## Non-goals

- Adding `ci_*` consumers for reusable workflows that org-infra does not currently
  consume (`reusable_publish_ghcr.yml`, `reusable_publish_oras.yml`,
  `reusable_sign_and_verify.yml`, `reusable_sonarqube.yml`). That is a separate concern.
- Changing how downstream repositories reference reusable workflows. They continue to
  receive SHA-pinned refs via the sync process.
- Modifying the release process itself.

## Capabilities

### New Capabilities

- `workflow-self-testing`: Use local path refs for reusable workflows in org-infra and
  transform them to SHA-pinned cross-repo refs during sync to downstream repositories.

### Modified Capabilities

(none)

## Impact

- **Workflows**: 7 consumer workflow files and 1 reusable workflow file in
  `.github/workflows/` are modified (9 total refs changed from SHA-pinned to local).
- **Sync script**: `scripts/sync-org-repositories.py` gains a new transformation
  function, release auto-detection, a `--release-ref` CLI argument, and an additional
  GitHub API endpoint in the allowlist.
- **Tests**: New unit tests for the transformation function and release detection.
- **Downstream repos**: No change in behavior. They continue to receive SHA-pinned
  refs, now produced by the sync script transformation instead of being copied as-is.
- **Scorecard**: Local path refs are not penalized by OpenSSF Scorecard (it checks
  third-party action refs, not same-repo workflow calls). No Scorecard regression.

## Supersedes

Narrows the policy established by `pin-workflows-to-release` — SHA pinning remains
mandatory for downstream repos but is replaced by local refs within org-infra for
self-testing. The `workflow-sha-pinning` capability's scope is reduced from "all
org-infra workflow references" to "downstream-facing workflow references only."
