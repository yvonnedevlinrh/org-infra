## Context

org-infra maintains 12 reusable workflows (`reusable_*.yml`) consumed by 7 consumer
workflows (`ci_*.yml`). The `pin-workflows-to-release` change (completed) replaced all
`@main` references with SHA-pinned refs (`@<sha> # v0.2.1`), aligning with the org's
supply-chain security convention.

This created a self-testing gap: when a reusable workflow is modified on a PR, org-infra's
own CI still runs the previous release's version of that workflow. Breakage is not detected
until after a release is cut and SHA refs are bumped — at which point the broken workflow
has already been tagged and is ready to sync to all downstream repos.

The sync script (`sync-org-repositories.py`) currently copies `ci_*` workflow files as-is
to downstream repos. It already supports content-level transformations via
`apply_file_vars()` for per-repo variable substitution (e.g., `enable_trivy_source`).

Five `ci_*` files are synced to downstream repos. Two workflow files with reusable
workflow refs are not synced (`ci_compliance.yml`, `reusable_scheduled.yml`).

## Goals / Non-Goals

**Goals:**

- Enable org-infra to test its own reusable workflow changes during CI, including on PRs.
- Ensure downstream repos continue to receive SHA-pinned workflow refs via the sync
  process.
- Auto-detect the latest release for sync transformation with no manual configuration.
- Provide a CLI override when auto-detection fails or a specific version is needed.

**Non-Goals:**

- Adding CI consumers for reusable workflows not currently tested by org-infra.
- Changing the release process or release-drafter configuration.
- Modifying how downstream repos consume reusable workflows (they remain SHA-pinned).

## Decisions

### 1. Use local path refs in org-infra (`./.github/workflows/reusable_*.yml`)

Replace SHA-pinned cross-repo refs with local path syntax. GitHub Actions resolves
local refs to the current commit, meaning PRs that modify a reusable workflow will
test the modified version immediately.

**Alternatives considered:**

- **`@main` refs**: Would test whatever is on `main`, not the PR's changes. A PR
  modifying `reusable_ci.yml` would still run the old main-branch version. Rejected
  because it only catches breakage after merge, not during review.
- **Keep SHA-pinned refs (status quo)**: Does not catch breakage until after release.
  Rejected as this is the problem being solved.

### 2. Dedicated `transform_workflow_refs()` function

Add a new function alongside `apply_file_vars()` that replaces local workflow refs
with SHA-pinned cross-repo refs during sync. Both functions are content-level string
transforms that compose: vars are applied first, then workflow ref transformation.

**Alternatives considered:**

- **Extend the `vars` mechanism**: Would require adding synthetic variables to
  `sync-config.yml` for each workflow ref. The vars system uses
  `<var_name>: <value>` regex matching, which does not fit the `uses:` line format.
  Rejected as an awkward fit that would complicate the config.
- **Config-driven replacement map**: Add a mapping in `sync-config.yml` listing each
  local ref and its replacement. Rejected as redundant — the transformation is
  deterministic (local ref pattern + release SHA/tag) and does not need per-file config.

### 3. Auto-detect latest release via GitHub API

The sync script queries `GET /repos/{org}/{repo}/releases/latest` to obtain the
release tag name, then resolves the tag to a commit SHA via
`GET /repos/{org}/{repo}/git/ref/tags/{tag}`. This endpoint is added to the API
allowlist.

The org name comes from the existing `--org` CLI argument. The source repo name is a
module-level constant (`SOURCE_REPO = "org-infra"`) — easy to change, sensible default.

**Alternatives considered:**

- **Git tags on local checkout**: Would require `fetch-depth: 0` and `fetch-tags: true`
  in the CI checkout step. Rejected because it adds a CI configuration dependency and
  may not work when the script is run outside of CI.
- **Manual config in `sync-config.yml`**: Would require updating the config file on
  every release. Rejected as unnecessary manual toil when the API provides the
  information.
- **CLI argument only (no auto-detect)**: Would require passing `--release-ref` on
  every invocation. Rejected because the common case should be zero-friction.

### 4. Apply transformation only to `ci_*` workflow files

The transformation function checks whether the source path matches
`.github/workflows/ci_*.yml` before applying. Non-workflow files and reusable workflow
files pass through unchanged.

**Alternatives considered:**

- **Content-based detection (apply to all files)**: Would transform any file containing
  the `uses: ./.github/workflows/reusable_*.yml` pattern. Low risk of false positives
  but violates the explicit scoping requirement. Rejected for clarity and to avoid
  unintended transformation of documentation or config files that might contain example
  refs.
- **All workflow files**: Reusable workflows are not synced to downstream repos, so
  transforming them would be wasted work. Rejected as unnecessary.

### 5. `--release-ref` CLI argument as override

When provided, `--release-ref <tag>` (e.g., `--release-ref v0.3.0`) skips
auto-detection and uses the specified tag. The script resolves the tag to a commit SHA
via the same API path. This serves two purposes: recovery when no release exists yet,
and explicit version pinning for testing or rollback.

**Alternatives considered:**

- **Separate `--release-sha` argument**: Would allow passing both tag and SHA
  independently for fully offline use. Rejected as over-engineering — the API call
  to resolve a tag is trivial, and offline sync is not a supported use case.

### 6. Sync flow integration point

Files that need workflow ref transformation are routed through the content-transform
path (read → transform → compare → write) regardless of whether they also have `vars`.
This requires a small refactor to the existing branching logic in `sync_repository()`,
which currently sends var-less files through the direct-copy `sync_file()` path.

The composition order is: `apply_file_vars()` first (if vars exist), then
`transform_workflow_refs()`. Both are idempotent regex substitutions.

**Alternatives considered:**

- **Separate pre-processing pass**: Run transformation on all source files before the
  sync loop. Rejected because it would require modifying source files on disk (or
  maintaining a parallel transformed copy), adding complexity for no benefit.

## Risks / Trade-offs

- **[Risk] API rate limiting during sync.** The release detection adds 1-2 API calls
  per sync invocation (not per repo). The sync script already makes multiple API calls
  per repo (PR check, PR creation). The incremental cost is negligible.
  -> Mitigation: Release detection runs once at startup, not per-repo.

- **[Risk] Tag-to-SHA resolution for annotated tags.** If a release tag is annotated
  (not lightweight), the git ref API returns a tag object SHA, not a commit SHA. The
  tag object must be dereferenced to get the commit SHA.
  -> Mitigation: Check the `object.type` field in the API response. If `"tag"`,
  follow up with `GET /repos/{org}/{repo}/git/tags/{sha}` to get the commit SHA.

- **[Risk] GitHub API unavailability.** Release detection and tag-to-SHA resolution
  both require GitHub API access. If the API is unreachable, the sync script will fail.
  The `--release-ref` override does not help because it also requires an API call to
  resolve the tag. This is consistent with the script's existing behavior — it already
  requires API access for PR creation and repo discovery.
  -> Mitigation: No additional mitigation needed. The existing sync script's error
  handling covers HTTP failures. A `--release-sha` option was explicitly rejected
  (Decision 5) as over-engineering for an unsupported offline use case.

- **[Trade-off] Scorecard for org-infra only.** Local path refs are not flagged by
  OpenSSF Scorecard (it checks third-party action pinning, not same-repo workflow
  calls). No Scorecard regression expected.

- **[Trade-off] Supersedes `pin-workflows-to-release` for org-infra.** The prior
  change established universal SHA-pinning. This change narrows the scope: SHA-pinning
  remains mandatory for downstream repos (enforced by the sync transformation) but is
  replaced by local refs within org-infra. The prior change's spec
  (`workflow-sha-pinning`) is historical documentation of the original decision.
