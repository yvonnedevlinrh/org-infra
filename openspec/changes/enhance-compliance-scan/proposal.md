## Why

The `reusable_compliance.yml` workflow has structural gaps and a config bug:

1. **Missing Gemara evaluation log artifact**: complyctl produces a provider-agnostic
   evaluation log in Gemara format (`.complytime/scan/evaluation-log-*.yaml`), but the
   workflow does not upload it. This artifact is the canonical scan result record.

2. **Scan failure blocks all subsequent steps**: When `complyctl scan` exits non-zero,
   GitHub Actions skips the publish-to-step-summary and all artifact upload steps.
   The job fails with no artifacts and no summary -- exactly the scenario where that
   evidence is most needed.

3. **Step summary and verdict are coupled to provider-specific formats**: The step
   summary is built from ampel intoto JSON and the verdict relies on the scan exit
   code. Following complyctl's exit code clarification (complytime/complyctl#618),
   the exit code indicates operational success/failure only -- it does not signal
   whether compliance checks passed or failed. The Gemara evaluation log is the
   canonical, provider-agnostic source of truth for compliance outcomes.

4. **Wrong OCI tag separator in `complytime.yaml`**: The config uses `@latest` (digest
   separator) instead of `:latest` (tag separator) for policy and complypack URLs.

## What Changes

- **Deferred scan failure**: The scan step captures its exit code and emits
  `::warning::` annotations on non-zero (operational issues). All publish and upload
  steps run unconditionally (`if: always()`). The scan exit code is used for
  operational warnings only, not for the compliance verdict.
- **Gemara-based step summary**: The step summary is rebuilt from the Gemara
  evaluation log (provider-agnostic YAML) instead of ampel intoto JSON. Uses
  `python3` with `pyyaml` to parse the YAML and generate the markdown report.
- **Gemara-based compliance verdict**: A new step parses all Gemara evaluation logs
  to determine the compliance outcome. The job fails if any log reports `Failed`,
  passes if all report `Passed`, and fails if no results are found.
- **Gemara evaluation log upload**: A new `actions/upload-artifact` step uploads
  `.complytime/scan/evaluation-log-*.yaml` with `if-no-files-found: warn`.
- **Fix OCI tag separator**: Change `@latest` to `:latest` on both `policies` and
  `complypacks` entries in `.complytime/complytime.yaml`.

## Non-goals

- Changing complyctl or ampel-provider behavior (upstream).
- Making scan failure mode configurable per caller.
- Removing ampel/snappy artifact uploads (kept for backward compatibility and
  detailed attestation evidence, even though the verdict uses Gemara).

## Capabilities

### New Capabilities

- `compliance-scan-resilience`: Gemara-based compliance verdict, provider-agnostic
  step summary, deferred failure pattern, and Gemara artifact upload.

### Modified Capabilities

(none -- no existing spec-level requirements change)

### Removed Capabilities

None.

## Impact

- **`reusable_compliance.yml`**: Structural change to scan step (exit code capture),
  step summary rewritten from intoto/jq to Gemara/python3, new compliance evaluation
  step, new verdict step based on Gemara results, `if: always()` on all post-scan
  steps, one new upload step.
- **Documentation**: No updates needed. The README description of
  `reusable_compliance.yml` remains accurate. External org repos that call this
  workflow cross-repo will also benefit from the improved evaluation.
- **`.complytime/complytime.yaml`**: Two-line fix (`@latest` to `:latest`).
  Not synced to other repos (not in `sync-config.yml`).
- **Downstream callers**: No input/output contract changes. The step summary format
  changes from ampel-specific to Gemara-based, but the information content is
  equivalent.
