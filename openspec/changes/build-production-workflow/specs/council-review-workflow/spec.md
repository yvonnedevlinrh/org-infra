# Council Review Workflow Specification

## ADDED Requirements

### Requirement: Collect workflow gathers PR diff without secrets

The collect workflow SHALL run on every `pull_request` event (opened,
synchronize, reopened) without requiring any secrets or OIDC tokens. It
SHALL collect the PR diff and upload it as a GitHub Actions artifact for
the review workflow to consume.

#### Scenario: Fork PR triggers collect

- **WHEN** a contributor opens a PR from a fork
- **THEN** the collect workflow runs successfully, uploads the diff
  artifact, and completes without errors

#### Scenario: Upstream branch PR triggers collect

- **WHEN** an org member opens a PR from an upstream branch
- **THEN** the collect workflow runs successfully and uploads the diff
  artifact identically to a fork PR

#### Scenario: Draft PR is skipped

- **WHEN** a PR is marked as draft
- **THEN** the collect workflow skips diff collection and exits with a
  skip reason logged

#### Scenario: Dependabot PR is skipped

- **WHEN** the PR author is `dependabot[bot]`
- **THEN** the collect workflow skips diff collection and exits with a
  skip reason logged

### Requirement: Review workflow authenticates via WIF and invokes model

The review workflow SHALL trigger on `workflow_run` completion of the
collect workflow. It SHALL authenticate to GCP via the ITPC WIF pool,
download the diff artifact, invoke Claude via the Claude Code CLI, and
post review results as a PR comment.

#### Scenario: Successful end-to-end review

- **WHEN** the collect workflow completes for a non-draft, non-dependabot PR
  and WIF secrets are configured
- **THEN** the review workflow authenticates to GCP, calls Claude with the
  diff, and posts a structured review comment on the PR

#### Scenario: WIF secrets not configured

- **WHEN** the review workflow runs but `GCP_WORKLOAD_IDENTITY_PROVIDER`
  is empty (e.g., new repo not yet scoped for secrets)
- **THEN** the workflow logs a skip reason and exits without error

#### Scenario: Collect workflow failed or was cancelled

- **WHEN** the collect workflow did not complete successfully
- **THEN** the review workflow does not run

### Requirement: Review workflow posts results as PR comment

The review workflow SHALL post structured review findings as a comment
on the originating pull request. If a previous review comment exists
for the same PR, it SHALL be updated rather than creating a duplicate.

#### Scenario: First review on a PR

- **WHEN** no prior council review comment exists on the PR
- **THEN** a new comment is created with the review findings

#### Scenario: Updated review after new push

- **WHEN** a contributor pushes new commits and the review runs again
- **THEN** the existing review comment is updated with the latest findings

### Requirement: Concurrency control limits parallel reviews

The workflow chain SHALL prevent multiple concurrent reviews for the
same PR. Rapid pushes SHALL cancel the in-progress review and start
a new one with the latest diff.

#### Scenario: Rapid consecutive pushes

- **WHEN** a contributor pushes twice in quick succession
- **THEN** the first review run is cancelled and only the second runs
  to completion

### Requirement: Model invocation uses explicit model identifiers

The workflow SHALL invoke Claude using explicit Vertex AI model IDs
(not CLI aliases) to prevent silent model version drift.

#### Scenario: Model called with explicit ID

- **WHEN** the review workflow invokes Claude
- **THEN** the CLI receives an explicit model ID that matches an enabled
  model on the GCP project

### Requirement: Reusable workflow encapsulates auth and invocation

The reusable workflow SHALL accept secrets and inputs from the consumer
workflow and encapsulate all WIF authentication, CLI installation, and
model invocation logic. Consumer workflows SHALL not contain auth or
invocation details.

#### Scenario: Consumer calls reusable with secrets

- **WHEN** a consumer workflow calls the reusable workflow with WIF
  secrets and a diff artifact
- **THEN** the reusable workflow handles authentication, CLI setup,
  model invocation, and returns the review output

#### Scenario: Different repo uses same reusable workflow

- **WHEN** a downstream repo calls the same reusable workflow with its
  own org-scoped secrets
- **THEN** the review runs identically to org-infra

### Requirement: Workflow files follow org conventions

All workflow files SHALL follow the org's naming conventions, permission
model, and action pinning requirements.

#### Scenario: Naming convention

- **WHEN** the workflows are created
- **THEN** the reusable workflow is named `reusable_council_review.yml`
  and consumer workflows use the `ci_` prefix

#### Scenario: Action pinning

- **WHEN** external actions are referenced in the workflows
- **THEN** each reference uses a full 40-character SHA with an inline
  version comment

#### Scenario: Minimal permissions

- **WHEN** workflow-level and job-level permissions are declared
- **THEN** workflow-level permissions are `none` and job-level
  permissions include only the minimum required for each job

### Requirement: Consumer workflows sync to downstream repos

The consumer workflows SHALL be added to the sync configuration so
downstream repos receive them automatically.

#### Scenario: Sync config updated

- **WHEN** the workflows are merged to main
- **THEN** `sync-config.yml` includes the consumer workflow files in
  the sync list

#### Scenario: Repo without secrets skips gracefully

- **WHEN** a downstream repo receives the synced workflows but does
  not have WIF secrets scoped
- **THEN** the review workflow detects the missing secrets and skips
  without error
