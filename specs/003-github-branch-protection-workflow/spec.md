# Feature Specification: Reusable GitHub Branch Protection Scan Workflow

## Document Overview

This specification details a centralized, reusable workflow for scanning GitHub branch protection rules using [complyctl](https://github.com/complytime/complyctl) and the `ampel-branch-protection` policy. The workflow builds `complyctl` from source, runs it against a target repository's branch protection configuration, and publishes results as a GitHub Actions job summary and downloadable artifacts.

**Key Metadata:**
- Workflow File: `.github/workflows/reusable_compliance.yml`
- Date: 2026-03-26
- Current Status: Active

## Core User Scenarios

### Priority 1: Branch Protection Rule Scanning

Repository maintainers can enable branch protection scanning by creating a consumer workflow that references the org-infra reusable workflow. The system automatically scans branch protection rules using the `ampel-branch-protection` policy and surfaces a compliance report in the GitHub Actions job summary.

**Test Coverage:** Verifies that `complyctl get → generate → scan` executes successfully, the report is published to `$GITHUB_STEP_SUMMARY`, and result artifacts are uploaded.

### Priority 2: User-Supplied Workspace Configuration

The caller provides a `complytime.yaml` workspace configuration file checked into their repository. This file defines the policy URL, policy ID, and scan targets (repository URL, branch, spec). The reusable workflow checks out the caller's repository at the exact triggering commit SHA and copies the file before running `complyctl`.

**Test Coverage:** Validates that the workspace config is correctly copied from the caller's checkout, and that scans respect the targets defined by the caller.

### Priority 3: Attestation Artifact Collection

The workflow uploads three artifact types: the human-readable Markdown scan report, snappy in-toto attestations, and ampel in-toto attestations. These support downstream audit and compliance workflows.

**Test Coverage:** Ensures artifacts are uploaded with predictable names and the `if-no-files-found: warn` flag is set so missing artifacts produce warnings rather than failures.

## Edge Cases Addressed

- **PR branch not yet merged**: The caller checkout uses `ref: ${{ github.sha }}` to check out the exact triggering commit, ensuring files added on a PR branch are available even before merge.
- **mock-oci-registry startup latency**: The workflow polls `http://localhost:8765/v2/` for up to 15 seconds (30 × 0.5 s) before failing, preventing race conditions.
- **Policy evaluation failures**: Non-zero exit from `ampel verify` (policy checks failed) is treated as a compliance finding, not a tool error; the scan step does not exit non-zero on policy failures.
- **Unknown artifact filenames**: Artifact paths use glob patterns (`report-*.md`, `*-snappy.intoto.json`, `*-ampel.intoto.json`) because filenames are derived at runtime from the target URL, branch, and spec name.

## Functional Requirements Summary

The workflow must:

1. **Build complyctl from source**: Check out `complytime/complyctl` and run `make build` to produce all binaries (`complyctl`, `ampel-plugin`, `mock-oci-registry`).
2. **Register the ampel provider**: Copy `bin/ampel-plugin` to `~/.complytime/providers/complyctl-provider-ampel`.
3. **Serve the policy via mock-oci-registry**: Start `./bin/mock-oci-registry` in the background, wait for it to be ready, then proceed.
4. **Accept caller-supplied workspace config**: Accept a `complytime_config_path` input (relative path within the caller repo) and copy it to `complytime.yaml` at the complyctl workspace root.
5. **Copy granular policy files**: Copy `compliance/ampel/branch-protection/*` from the org-infra checkout to `.complytime/ampel/granular-policies/` before running `generate`.
6. **Run the complyctl pipeline**: Execute `complyctl get`, `complyctl generate --policy-id ampel-bp`, and `complyctl scan --policy-id ampel-bp --format pretty`.
7. **Pass GITHUB_TOKEN to snappy**: Expose the `source_token` secret as `GITHUB_TOKEN` in the scan step environment so snappy can call the GitHub API.
8. **Publish the report**: Append `report-*.md` contents to `$GITHUB_STEP_SUMMARY`.
9. **Upload artifacts**: Upload the scan report, snappy attestations, and ampel attestations as named artifacts.
10. **Maintain security**: Use least-privilege permissions; the job requires only `contents: read`.
11. **Use pinned actions**: Reference all GitHub Actions by commit SHA for supply chain security.

## Inputs and Secrets

### Required Inputs

| Name | Type | Description |
|------|------|-------------|
| `complytime_config_path` | `string` | Relative path of the `complytime.yaml` file in the calling repository (e.g., `config/complytime.yaml`) |

### Optional Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `policy_id` | `string` | `ampel-bp` | Policy ID passed to `complyctl generate` and `complyctl scan` via `--policy-id`; must match the `id` defined in `complytime.yaml` |

### Required Secrets

| Name | Description |
|------|-------------|
| `source_token` | GitHub token used by snappy to read branch protection rules via the GitHub API |

## Artifacts Produced

| Artifact Name | Content |
|---------------|---------|
| `report-policies-ampel-branch-protection.md` | Human-readable Markdown compliance report |
| `ampel.intoto.json` | ampel in-toto attestation(s) with policy evaluation results |
| `snappy.intoto.json` | snappy in-toto attestation(s) with raw branch protection data |

## Success Metrics

- Any repository can enable branch protection scanning with a single consumer workflow file and a `complytime.yaml` config.
- The compliance report is visible directly in the GitHub Actions job summary without downloading artifacts.
- Scan results clearly indicate which branch protection requirements pass or fail.
- The workflow runs without requiring any pre-installed tools beyond what GitHub-hosted runners provide.

## Scope Boundaries

**Included:**
- Building complyctl and all plugins from source
- Serving the `ampel-branch-protection` policy via the embedded mock-oci-registry
- Installing `snappy` and `ampel` CLI tools
- Scanning branch protection rules for targets defined in the caller's `complytime.yaml`
- Uploading scan reports and in-toto attestations as artifacts
- Publishing the report to the GitHub Actions job summary

**Excluded:**
- Pushing attestations to the GitHub attestation store (see `reusable_compliance.yml` for that pattern)
- Scanning GitLab repositories (GitHub only via this workflow)
- Generating the `complytime.yaml` workspace config (responsibility of the caller)
- Posting scan results as pull request comments (callers can add this step to their own workflow)
- Organization-level branch protection configuration management
