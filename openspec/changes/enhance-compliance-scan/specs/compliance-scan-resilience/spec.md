## ADDED Requirements

### Requirement: Scan artifacts are uploaded regardless of scan outcome

The compliance workflow SHALL upload all available scan artifacts even when the
scan has operational failures or compliance violations.

#### Scenario: Scan completes with compliance failures

- **GIVEN** the compliance workflow has reached the scan step successfully
- **WHEN** the Gemara evaluation log reports one or more failed controls
- **THEN** all available artifacts SHALL be uploaded before the job reports failure

#### Scenario: Scan completes with all checks passing

- **GIVEN** the compliance workflow has reached the scan step successfully
- **WHEN** the Gemara evaluation log reports all controls passed
- **THEN** all artifacts SHALL be uploaded and the job SHALL report success

#### Scenario: Scan has operational failure

- **GIVEN** the compliance workflow has reached the scan step successfully
- **WHEN** complyctl exits with a non-zero code (operational failure)
- **THEN** any artifacts that were generated SHALL still be uploaded
- **AND** missing artifacts SHALL be skipped with a warning

#### Scenario: Some providers fail during scan

- **GIVEN** the compliance workflow is configured with multiple providers
- **WHEN** some providers succeed and some fail during the scan
- **THEN** artifacts from successful providers SHALL be uploaded
- **AND** missing artifacts from failed providers SHALL produce a warning

#### Scenario: Workflow cancelled during scan

- **GIVEN** the compliance workflow is executing
- **WHEN** the workflow is cancelled while the scan is in progress
- **THEN** upload steps SHALL attempt to upload any artifacts generated
  before cancellation
- **AND** missing artifacts SHALL be skipped with a warning

### Requirement: Step summary is built from Gemara evaluation log

The compliance workflow SHALL publish the scan results to the GitHub Step Summary
using the provider-agnostic Gemara evaluation log as the data source.

#### Scenario: Gemara evaluation log exists after scan

- **GIVEN** the compliance workflow has completed the scan step
- **WHEN** one or more Gemara evaluation logs exist
- **THEN** the Step Summary SHALL display per-control results with overall status,
  a summary table, and per-requirement details sourced from the Gemara YAML

#### Scenario: No Gemara evaluation log exists

- **GIVEN** the compliance workflow has completed the scan step
- **WHEN** no Gemara evaluation logs were generated
- **THEN** the Step Summary step SHALL complete without error (empty summary)

### Requirement: Gemara evaluation log is uploaded as a workflow artifact

The compliance workflow SHALL upload the provider-agnostic Gemara evaluation log
produced by complyctl during a scan.

#### Scenario: Evaluation log exists after scan

- **GIVEN** the compliance workflow has completed the scan step
- **WHEN** at least one provider succeeds during the scan
- **THEN** the Gemara evaluation log SHALL be uploaded as an artifact named
  `gemara-evaluation-log`

#### Scenario: Evaluation log does not exist after scan

- **GIVEN** the compliance workflow has completed the scan step
- **WHEN** all providers fail and no evaluation log is generated
- **THEN** the upload step SHALL warn and continue (not fail the job)

### Requirement: Compliance verdict is based on Gemara evaluation results

The compliance workflow SHALL determine the job outcome by parsing the Gemara
evaluation log, not by using the scan exit code. The scan exit code indicates
operational success/failure only (per complyctl#618).

#### Scenario: Gemara reports compliance failure

- **GIVEN** the compliance workflow has completed all upload and publish steps
- **WHEN** any Gemara evaluation log has `result: Failed`
- **THEN** the job SHALL exit with a non-zero code

#### Scenario: Gemara reports compliance pass

- **GIVEN** the compliance workflow has completed all upload and publish steps
- **WHEN** all Gemara evaluation logs have `result: Passed`
- **THEN** the job SHALL report success
- **AND** if the scan had an operational failure (non-zero exit code), a warning
  annotation SHALL note the operational issue

#### Scenario: No Gemara evaluation logs found

- **GIVEN** the compliance workflow has completed all upload and publish steps
- **WHEN** no Gemara evaluation logs were generated
- **THEN** the job SHALL exit with a non-zero code

#### Scenario: Scan step was skipped

- **GIVEN** a step before the scan failed and the scan step was skipped
- **WHEN** no Gemara evaluation logs exist and no scan exit code was produced
- **THEN** the job SHALL exit with a non-zero code

### Requirement: OCI references use tag syntax for tags

Configuration files that reference OCI artifacts by tag SHALL use the colon
separator (`:tag`) and not the digest separator (`@tag`).

#### Scenario: Policy and complypack URLs reference latest tag

- **GIVEN** the complytime configuration file defines policy and complypack URLs
- **WHEN** the URLs reference a `latest` tag
- **THEN** the URL SHALL use `:latest` (not `@latest`)

#### Scenario: OCI URL incorrectly uses digest separator for tag

- **GIVEN** the complytime configuration file defines OCI artifact URLs
- **WHEN** a URL uses `@` syntax with a tag name (not a digest)
- **THEN** the configuration SHALL be considered invalid
