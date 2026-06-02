# GitHub Branch Protection Scan Quickstart

This guide covers implementing GitHub branch protection scanning for repository maintainers adopting the reusable workflow.

## Prerequisites

Before setting up the workflow, ensure you have:

1. **GitHub Token**: A token with permission to read branch protection rules for the target repository (typically `secrets.GITHUB_TOKEN` for the same repository, or a PAT for cross-repository scanning)
2. **complytime.yaml**: A workspace configuration file defining the policy and target repository

## Setup Steps

### Step 1: Create the complytime.yaml Configuration

Add a `complytime.yaml` file to your repository that points to the `ampel-branch-protection` policy and defines the target repository to scan:

```yaml
policies:
  - url: http://localhost:8765/policies/ampel-branch-protection
    id: ampel-bp
targets:
  - id: my-target
    policies:
      - ampel-bp
    variables:
      url: https://github.com/<org>/<repo>
      branches: main
      specs: builtin:github/branch-rules.yaml
```

Replace `<org>/<repo>` with the GitHub organization and repository name to scan. The `branches` variable defaults to `main` if omitted.

> **Note:** The policy URL `http://localhost:8765/policies/ampel-branch-protection` always points to the mock-oci-registry started by the reusable workflow. Do not change this URL.

### Step 2: Add Consumer Workflow

Create `.github/workflows/github-bp-scan.yml` in your repository:

```yaml
name: GitHub Branch Protection Scan

on:
  push:
    branches:
      - main
  pull_request:

permissions:
  contents: none

jobs:
  branch-protection-scan:
    name: Branch Protection Scan
    permissions:
      contents: read
    uses: complytime/org-infra/.github/workflows/reusable_compliance.yml@main
    with:
      complytime_config_path: complytime.yaml
      # policy_id: ampel-bp  # optional, defaults to 'ampel-bp'
    secrets:
      source_token: ${{ secrets.GITHUB_TOKEN }}
```

Adjust `complytime_config_path` to the path of your `complytime.yaml` relative to the repository root.

## Configuration Options

### Required Inputs

| Input | Description |
|-------|-------------|
| `complytime_config_path` | Relative path to your `complytime.yaml` file in the repository (e.g., `complytime.yaml` or `config/complytime.yaml`) |

### Optional Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `policy_id` | `ampel-bp` | Policy ID passed to `complyctl generate` and `complyctl scan`; must match the `id` field in your `complytime.yaml` |

### Required Secrets

| Secret | Description |
|--------|-------------|
| `source_token` | GitHub token for snappy to read branch protection rules via the GitHub API |

### complytime.yaml Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `url` | Yes | Full GitHub repository URL to scan (e.g., `https://github.com/myorg/myrepo`) |
| `branches` | No | Comma-separated list of branch names to scan (default: `main`) |
| `specs` | Yes | Spec file to use — use `builtin:github/branch-rules.yaml` for standard GitHub branch rules |

## Scanning Multiple Repositories

To scan multiple repositories or branches, add additional targets to your `complytime.yaml`. The `branches` variable accepts a comma-separated list:

```yaml
policies:
  - url: http://localhost:8765/policies/ampel-branch-protection
    id: ampel-bp
targets:
  - id: repo-a
    policies:
      - ampel-bp
    variables:
      url: https://github.com/myorg/repo-a
      branches: main
      specs: builtin:github/branch-rules.yaml
  - id: repo-b
    policies:
      - ampel-bp
    variables:
      url: https://github.com/myorg/repo-b
      branches: main,release
      specs: builtin:github/branch-rules.yaml
```

## Viewing Results

After the workflow runs:

1. **Job Summary**: Open the workflow run in the GitHub Actions UI. The compliance report is published directly to the job summary — no artifact download required.
2. **Artifacts**: Download the following artifacts from the workflow run:
   - `report-policies-ampel-branch-protection.md` — Full Markdown compliance report
   - `ampel.intoto.json` — ampel in-toto attestation with policy evaluation results
   - `snappy.intoto.json` — snappy in-toto attestation with raw branch protection data

## Branch Protection Requirements

The `ampel-branch-protection` policy checks the following requirements:

| ID | Tenet | Description | Pass Condition | Guidance on Failure |
|----|-------|-------------|----------------|---------------------|
| require-pull-request | 01 | Require pull/merge requests — direct pushes are disabled | A `update` ruleset rule exists (GitHub) or `push_access_levels` is empty (GitLab) | GitHub: create a branch ruleset and enable **Restrict updates**. GitLab: remove all `push_access_levels`. |
| minimum-approvals | 01 | Minimum one approval required before merge | `required_approving_review_count >= 1` (GitHub) or `approvals_before_merge >= 1` (GitLab) | GitHub: set `required_approving_review_count >= 1`. GitLab: set `approvals_before_merge >= 1`. |
| minimum-approvals | 02 | Stale approvals dismissed on new commits | `dismiss_stale_reviews_on_push == true` (GitHub) or `reset_approvals_on_push == true` (GitLab) | GitHub: enable **Dismiss stale pull request approvals when new commits are pushed**. GitLab: enable **Remove all approvals when commits are added to the source branch**. |
| minimum-approvals | 03 | Author/committer cannot approve their own changes | `require_last_push_approval == true` (GitHub) or `merge_requests_disable_committers_approval == true` (GitLab) | GitHub: enable **Require approval of the most recent reviewable push**. GitLab: enable **Prevent approval by author and committers**. |
| block-force-push | 01 | Force pushes are blocked on protected branches | A `non_fast_forward` ruleset rule exists (GitHub) or `allow_force_push == false` (GitLab) | GitHub: create a branch ruleset and enable **Block force pushes**. GitLab: set `allow_force_push` to `false`. |
| prevent-admin-bypass | 01 | Admins cannot bypass branch protection | A `non_fast_forward` ruleset rule exists (GitHub) or `push_access_levels` is empty / set to access level 0 (GitLab) | GitHub: enable **Block force pushes** in branch ruleset. GitLab: set `push_access_levels` to empty or access level 0 (No one). |
| require-code-owner-review | 01 | Code owner review required when CODEOWNERS file exists | `require_code_owner_review == true` (GitHub) or `code_owner_approval_required == true` (GitLab) | GitHub: enable **Require review from Code Owners** in branch ruleset. GitLab: set `code_owner_approval_required` to `true`. |

## Troubleshooting

### `cp: cannot stat '_caller/...' : No such file or directory`

Ensure your `complytime.yaml` file is committed to the branch that triggered the workflow. The reusable workflow checks out the caller repository at the exact triggering commit SHA.

### All requirements show "required attestations missing to verify subject"

This indicates snappy could not collect branch protection data. Verify:
- The `source_token` secret has permission to read the target repository's branch protection rules
- The `url` in `complytime.yaml` points to a valid GitHub repository
- The repository has branch protection rules configured on the default branch

### Workflow fails at "Fetch ampel-branch-protection policy from mock registry"

The mock-oci-registry failed to start in time. This is a transient runner issue — re-run the workflow.

## Infrastructure Notes

The reusable workflow resides in the org-infra repository at `.github/workflows/reusable_compliance.yml`. It builds `complyctl` from source at `complytime/complyctl` on every run to ensure it always uses the latest version. Changes to the workflow should follow the repository's contribution guidelines and be tested before merging.
