## 1. Deferred Scan Failure

- [x] 1.1 Modify the "Scan branch protection rules" step in `.github/workflows/reusable_compliance.yml` — add `id: scan`, use `set +e` to capture the exit code into a step output (`exit_code`), emit `::warning::` with the exit code when non-zero, and always exit 0.
- [x] 1.2 Add `if: always()` to all post-scan steps in `.github/workflows/reusable_compliance.yml`.

## 2. Gemara-Based Step Summary

- [x] 2.1 Add a "Install YAML parser" step after the scan — `pip install --quiet pyyaml`. Uses `if: always()`.
- [x] 2.2 Replace the jq/intoto-based "Publish report to GitHub Step Summary" step with a Python script that parses `.complytime/scan/evaluation-log-*.yaml` and generates the markdown report from Gemara data.

## 3. Gemara Compliance Evaluation

- [x] 3.1 Add an "Evaluate compliance results" step (`id: compliance`) — Python script that reads all Gemara evaluation logs, checks the top-level `result` field, and outputs `compliance_result=pass|fail|none` to `$GITHUB_OUTPUT`. Uses `if: always()`.

## 4. Gemara Evaluation Log Upload

- [x] 4.1 Add a new "Upload Gemara Evaluation Log" step — uses `actions/upload-artifact` (same pinned SHA as existing upload steps), artifact name `gemara-evaluation-log`, path `.complytime/scan/evaluation-log-*.yaml`, `if-no-files-found: warn`, `if: always()`.

## 5. Compliance Verdict

- [x] 5.1 Rewrite the "Compliance scan verdict" step — uses `compliance_result` from step 3.1 (not scan exit code). Fails on `fail` or `none`, passes on `pass`. Emits `::warning::` if scan had operational issues (non-zero exit) but compliance passed.

## 6. Fix OCI Tag Separator

- [x] 6.1 In `.complytime/complytime.yaml`, change `@latest` to `:latest` on both policy and complypack URLs.

## 7. Validation

> **Test strategy**: YAML workflow changes have no unit test framework.
> Validation relies on yamllint (syntax), structural checks (grep/yq),
> and end-to-end workflow execution in a branch.

- [x] 7.1 Run `yamllint` on `.github/workflows/reusable_compliance.yml` — zero lint errors.
- [x] 7.2 Run `yamllint` on `.complytime/complytime.yaml` — zero lint errors.
- [x] 7.3 Verify all `actions/upload-artifact` `uses:` references are pinned to the same SHA.
- [x] 7.4 Verify the scan step has `id: scan` and captures exit code.
- [x] 7.5 Verify all post-scan steps include `if: always()`.
- [x] 7.6 Verify the verdict step uses `steps.compliance.outputs.compliance_result`.
- [x] 7.7 Verify the step summary uses Python/Gemara (no jq, no intoto references).
- [x] 7.8 Verify `.complytime/complytime.yaml` contains no `@latest` patterns.

<!-- spec-review: passed -->
<!-- code-review: passed -->
