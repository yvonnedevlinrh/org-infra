## Context

The `reusable_compliance.yml` workflow builds complyctl from source, runs a branch
protection scan via the ampel provider, publishes results to the GitHub Step Summary,
and uploads attestation artifacts. It is consumed by `ci_compliance.yml` and called
by org repositories.

Current state:

- The scan step (`complyctl scan --format pretty`) exits non-zero on operational
  failures only (provider errors, zero assessed requirements). Per complyctl#618,
  the exit code does NOT indicate whether compliance checks passed or failed.
- The step summary is built from `*-ampel.intoto.json` (provider-specific format).
- complyctl produces a provider-agnostic evaluation log in Gemara format
  at `.complytime/scan/evaluation-log-*.yaml`, but the workflow does not use it.
- `.complytime/complytime.yaml` uses `@latest` (OCI digest syntax) instead of
  `:latest` (OCI tag syntax) for policy and complypack URLs.

## Goals / Non-Goals

**Goals:**

- Ensure all available scan artifacts are uploaded regardless of scan outcome.
- Use the Gemara evaluation log as the source of truth for the compliance verdict.
- Build the step summary from the Gemara evaluation log (provider-agnostic).
- Upload the Gemara evaluation log as a new workflow artifact.
- Fix the OCI tag separator in `complytime.yaml`.

**Non-Goals:**

- Modifying complyctl or ampel-provider behavior.
- Making the failure behavior configurable per caller.
- Removing ampel/snappy artifact uploads (kept for attestation evidence).

## Decisions

### D1: Scan exit code is operational only

The scan step uses `set +e` to capture the exit code and always exits 0. The exit
code is emitted as a `::warning::` annotation when non-zero, providing visibility
into operational issues (provider failures, nothing assessed). The exit code is
NOT used for the compliance verdict -- that comes from parsing the Gemara results.

This aligns with complyctl#618: the scan exit code indicates whether the scan
operation succeeded, not whether compliance checks passed or failed.

### D2: `if: always()` on all post-scan steps

All steps after the scan (step summary, compliance evaluation, five upload steps,
verdict) use `if: always()` so they execute regardless of any prior step's outcome.
This ensures artifacts from partially successful scans are captured even when some
providers fail.

### D3: Gemara-based compliance verdict

A dedicated step parses all Gemara evaluation logs (`.complytime/scan/evaluation-log-*.yaml`)
using `python3` with `pyyaml`. It reads the top-level `result` field from each log:

- If any log has `result: Failed` -> `compliance_result=fail`
- If all logs have `result: Passed` -> `compliance_result=pass`
- If no logs exist -> `compliance_result=none`

The final verdict step uses this output to determine the job exit code. This
decouples the compliance signal from the scan exit code and from any
provider-specific format.

**Alternative considered**: Parse the ampel intoto JSON for compliance results.
Rejected because it couples the verdict to a specific provider format. If providers
change, the Gemara log remains the stable interface.

**Alternative considered**: Use `grep '^result:'` to extract the YAML field.
Rejected because it is fragile (could match nested `result:` fields) and less
readable than proper YAML parsing.

### D4: Gemara-based step summary

The step summary is rewritten to parse the Gemara evaluation log with `python3`
instead of the ampel intoto JSON with `jq`. The output format is equivalent
(markdown table with overall status, per-control results, per-requirement details)
but sourced from the provider-agnostic Gemara structure.

**Alternative considered**: Keep the intoto-based summary alongside the Gemara
verdict. Rejected because it maintains unnecessary provider coupling and the
Gemara log contains all the same information in a standardized format.

### D5: Gemara upload uses `if-no-files-found: warn`

The Gemara evaluation log exists when at least one provider succeeds. If all
providers fail, the file is absent. Using `if-no-files-found: warn` (consistent
with the existing upload steps) handles this gracefully.

### D6: Static artifact name for Gemara evaluation log

The artifact name is `gemara-evaluation-log` (static). There is exactly one
evaluation log file per scan run, so a dynamic name is unnecessary.

## Risks / Trade-offs

- **[`if: always()` runs on cancellation]**: If a user cancels the workflow mid-scan,
  post-scan steps still attempt to run. Mitigation: uploads are no-ops when files
  are absent (`if-no-files-found: warn`), so this is harmless.

- **[`pyyaml` availability]**: The workflow installs `pyyaml` via pip. If pip or
  the PyPI registry is unavailable, the step summary and compliance evaluation steps
  would fail. Mitigation: `pyyaml` is one of the most widely-used Python packages
  and `pip install` on GitHub runners is highly reliable. The `--quiet` flag keeps
  output clean.

- **[Step summary format change]**: The step summary format changes from
  ampel-specific field names (Policy, Tenet) to Gemara-specific field names
  (Control, Requirement). This is a visible change for users who read the step
  summary. Mitigation: the information content is equivalent and the Gemara
  naming is more aligned with compliance terminology.
