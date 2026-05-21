## ADDED Requirements

### Requirement: org-infra workflows use local path refs for reusable workflows

All consumer workflow files (`ci_*.yml`) and reusable-to-reusable references within
org-infra SHALL use local path syntax (`./.github/workflows/reusable_*.yml`) instead
of cross-repo SHA-pinned references.

#### Scenario: Consumer workflow references a reusable workflow

- **WHEN** a consumer workflow (`ci_*`) in org-infra calls a reusable workflow
- **THEN** the `uses:` value SHALL be a local path (`./.github/workflows/reusable_*.yml`)
- **AND** no cross-repo reference (`complytime/org-infra/...@<ref>`) SHALL appear

#### Scenario: Reusable workflow references another reusable workflow

- **WHEN** a reusable workflow in org-infra calls another reusable workflow from the
  same repository
- **THEN** the `uses:` value SHALL be a local path

#### Scenario: PR modifying a reusable workflow tests the modified version

- **WHEN** a pull request modifies a reusable workflow file
- **AND** a consumer workflow that calls it runs as part of PR CI
- **THEN** the CI run executes the PR's version of the reusable workflow, not the
  main branch version

---

### Requirement: Sync script transforms local refs to SHA-pinned refs

The sync script SHALL transform local workflow path references in consumer workflow
files into SHA-pinned cross-repo references when syncing to downstream repositories.

#### Scenario: Local ref transformed during sync

- **WHEN** the sync script processes a consumer workflow file for a downstream repo
- **AND** the file contains a local reusable workflow reference
- **THEN** the reference SHALL be replaced with a cross-repo reference pinned to the
  latest release commit SHA with an inline version comment

#### Scenario: Transformation format matches existing convention

- **WHEN** a local ref is transformed during sync
- **THEN** the result SHALL use the format
  `<org>/<repo>/.github/workflows/<name>@<full-sha> # <tag>`
- **AND** the SHA SHALL be a full 40-character commit SHA
- **AND** the tag SHALL match the release version (e.g., `v0.3.0`)

#### Scenario: Non-workflow files are not transformed

- **WHEN** the sync script processes a file that is not a consumer workflow
- **THEN** no workflow ref transformation SHALL be applied

#### Scenario: Files without local refs pass through unchanged

- **WHEN** the sync script processes a consumer workflow file that contains no local
  reusable workflow references
- **THEN** the file content SHALL not be modified by the transformation step

#### Scenario: Transformation composes with variable substitution

- **WHEN** a consumer workflow file has both per-repo variable overrides and local
  reusable workflow references
- **THEN** both variable substitution and workflow ref transformation SHALL be applied
- **AND** the final content SHALL reflect both transformations

---

### Requirement: Sync script auto-detects the latest release

The sync script SHALL automatically determine the latest release tag and its commit
SHA from the source repository when no explicit override is provided.

#### Scenario: Latest release detected automatically

- **WHEN** the sync script runs without a release override argument
- **AND** the source repository has at least one published release
- **THEN** the script SHALL use the latest release tag and commit SHA for workflow
  ref transformation

#### Scenario: No release found and no override provided

- **WHEN** the sync script runs without a release override argument
- **AND** the source repository has no published releases
- **THEN** the script SHALL exit with a non-zero status code
- **AND** the error message SHALL inform the user that no release was found
- **AND** the error message SHALL instruct the user to retry with the release
  override argument

#### Scenario: Annotated tag is resolved to commit SHA

- **WHEN** the latest release tag is an annotated tag (not lightweight)
- **THEN** the script SHALL dereference the tag object to obtain the underlying
  commit SHA
- **AND** the commit SHA (not the tag object SHA) SHALL be used in workflow ref
  transformation

---

### Requirement: Release override via CLI argument

The sync script SHALL accept an optional CLI argument to override release
auto-detection with a specific release tag.

#### Scenario: Override with explicit tag

- **WHEN** the sync script is invoked with the release override argument and a tag
- **THEN** the script SHALL use the specified tag instead of auto-detecting
- **AND** the script SHALL resolve the tag to its commit SHA

#### Scenario: Override tag does not exist

- **WHEN** the sync script is invoked with a release override tag that does not exist
- **THEN** the script SHALL exit with a non-zero status code
- **AND** the error message SHALL indicate the tag was not found

---

## MODIFIED Requirements

> The following requirements amend `workflow-sha-pinning` from the completed
> `pin-workflows-to-release` change. That spec established universal SHA-pinning
> for all reusable workflow references. This change narrows its scope: SHA-pinning
> remains mandatory for downstream repositories (now enforced by the sync script
> transformation) but is replaced by local path refs within org-infra to enable
> self-testing of reusable workflow changes before release.
>
> The original `workflow-sha-pinning` spec is preserved as-is — it documents the
> initial decision and remains the authoritative reference for downstream behavior.
> This section records the scope narrowing for org-infra.

### Requirement: Reusable workflow references use immutable SHA pins

All `uses:` references to org-infra reusable workflows SHALL be pinned to a full
40-character commit SHA corresponding to a tagged release. This applies to ~~both
consumer workflows and reusable-to-reusable calls within org-infra~~ **downstream
repositories only**. Within org-infra, consumer workflows and reusable-to-reusable
calls SHALL use local path syntax (`./.github/workflows/reusable_*.yml`) as defined
in the ADDED requirement "org-infra workflows use local path refs for reusable
workflows" above.

The sync script SHALL ensure downstream repositories receive SHA-pinned references
by transforming local path refs during the sync process.

#### Scenario: Consumer workflow references a reusable workflow

- **WHEN** a consumer workflow (`ci_*`) in a **downstream repository** calls a
  reusable workflow from org-infra
- **THEN** the `uses:` value SHALL contain a full 40-character commit SHA (not a
  branch name, short SHA, or mutable tag)

#### Scenario: Consumer workflow references a reusable workflow within org-infra

- **WHEN** a consumer workflow (`ci_*`) in **org-infra** calls a reusable workflow
  from the same repository
- **THEN** the `uses:` value SHALL be a local path (`./.github/workflows/reusable_*.yml`)
- **AND** the sync script SHALL transform this to a SHA-pinned cross-repo reference
  before syncing to downstream repositories

#### Scenario: Reusable workflow references another reusable workflow

- **WHEN** a reusable workflow in **org-infra** calls another reusable workflow from
  the same repository
- **THEN** the `uses:` value SHALL be a local path
- **AND** since reusable workflows are not synced to downstream repositories, no
  transformation is required

---

### Requirement: SHA pins are updated as part of the release process

Updating reusable workflow SHA pins SHALL ~~be a required step in the org-infra release
process. The pins SHALL always reference the most recent tagged release~~ **be handled
automatically by the sync script**. The sync script SHALL resolve the latest release
tag and commit SHA and apply them during the sync process. Manual SHA pin updates
within org-infra are no longer required.

#### Scenario: Release checklist includes pin update

- **WHEN** a maintainer cuts a new org-infra release
- **THEN** the sync script SHALL automatically use the new release's commit SHA and
  version tag when transforming local refs for downstream repositories
- **AND** no manual update to org-infra's own workflow files is required
