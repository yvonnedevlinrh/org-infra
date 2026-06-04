# Build Production Workflow — Tasks

## 1. Collect Workflow (fork-safe, no secrets)

- [ ] 1.1 Create `.github/workflows/ci_council_review_collect.yml` with `pull_request` trigger (opened, synchronize, reopened) targeting `main`
- [ ] 1.2 Add gate check job: skip drafts (`github.event.pull_request.draft`), skip dependabot (`github.event.pull_request.user.login == 'dependabot[bot]'`), output `should_collect` and `skip_reason`
- [ ] 1.3 Add collect job: run `gh pr diff ${{ github.event.pull_request.number }}` and write to `pr-diff.patch`; include PR metadata (number, head SHA, base branch) in a `pr-meta.json` file
- [ ] 1.4 Upload `pr-diff.patch` and `pr-meta.json` as a GitHub Actions artifact named `council-review-diff` with `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (v7.0.1)
- [ ] 1.5 Set workflow-level `permissions: {}` (none) and job-level `permissions: { contents: read, pull-requests: read }`
- [ ] 1.6 Pin all actions to full 40-character SHA with inline version comment

## 2. Reusable Review Workflow (WIF auth + artifact download + model invocation)

- [ ] 2.1 Create `.github/workflows/reusable_council_review.yml` with `workflow_call` trigger accepting:
  - **Secrets**: `GCP_WORKLOAD_IDENTITY_PROVIDER` (required: false), `GCP_PROJECT_ID` (required: false)
  - **Inputs**: `model` (string, default `claude-sonnet-4-6`), `region` (string, default `global`), `max_diff_lines` (number, default `1000`), `triggering_run_id` (number, required)
- [ ] 2.2 Set workflow-level `permissions: {}` (none) and job-level `permissions: { contents: read, id-token: write, pull-requests: write, actions: read }`
- [ ] 2.3 Add gate check step: detect WIF secret presence (`secrets.GCP_WORKLOAD_IDENTITY_PROVIDER != ''`), skip with reason when absent
- [ ] 2.4 Add artifact download step: `actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` (v8.0.1) with `name: council-review-diff`, `run-id: ${{ inputs.triggering_run_id }}`, `github-token: ${{ github.token }}`
- [ ] 2.5 Add step to extract PR number and metadata from `pr-meta.json`
- [ ] 2.6 Add step to read diff from `pr-diff.patch` and truncate to `max_diff_lines` if exceeded
- [ ] 2.7 Add WIF auth step using `google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093` (v3.0.0) with `project_id` and `workload_identity_provider` from secrets (direct WIF, no `service_account`)
- [ ] 2.8 Add `google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db` (v3.0.1) step
- [ ] 2.9 Add Claude Code CLI install step: `curl -fsSL https://claude.ai/install.sh | bash` and append `${HOME}/.claude/bin` to `$GITHUB_PATH`
- [ ] 2.10 Set job-level `env`: `CLAUDE_CODE_USE_VERTEX: "1"`, `CLOUD_ML_REGION: ${{ inputs.region }}`, `ANTHROPIC_VERTEX_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}`
- [ ] 2.11 Add review step: invoke `claude -p` with the diff content and `--model ${{ inputs.model }}`, capture output
- [ ] 2.12 Add comment step: post review output as PR comment using `peter-evans/create-or-update-comment@e8674b075228eee787fea43ef493e45ece1004c9` (v5.0.0) with `edit-mode: replace` to update existing comments, using PR number extracted from `pr-meta.json`

## 3. Consumer Review Workflow (workflow_run trigger)

- [ ] 3.1 Create `.github/workflows/ci_council_review.yml` with `workflow_run` trigger on `ci_council_review_collect.yml` completion
- [ ] 3.2 Add condition: only run when triggering workflow concluded with `success`
- [ ] 3.3 Call `reusable_council_review.yml` with `secrets: { GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_PROJECT_ID }` and `inputs: { triggering_run_id: ${{ github.event.workflow_run.id }} }`
- [ ] 3.4 Add `concurrency` block: group `council-review-${{ github.event.workflow_run.id }}`, `cancel-in-progress: true`
- [ ] 3.5 Set workflow-level `permissions: {}` (none); job-level permissions inherited by reusable workflow

## 4. Sync Configuration

- [ ] 4.1 Add `ci_council_review_collect.yml` and `ci_council_review.yml` to `sync-config.yml` in the GitHub Workflows section
- [ ] 4.2 Verify `reusable_council_review.yml` does NOT need syncing (reusable workflows are called cross-repo via `uses: complytime/org-infra/.github/workflows/reusable_council_review.yml@main`)

## 5. Validation and Cleanup

- [ ] 5.1 Run `yamllint` on all three new workflow files
- [ ] 5.2 Verify all action `uses:` references are pinned to full 40-character SHAs with inline version comments
- [ ] 5.3 Open a test PR on `complytime/org-infra` and verify: collect workflow runs, review workflow triggers, WIF auth succeeds, Claude responds, PR comment is posted
- [ ] 5.4 Test with a fork PR: verify collect runs (no secrets needed), review triggers and authenticates via WIF, comment is posted
- [ ] 5.5 Test with a draft PR: verify collect workflow skips with logged reason
- [ ] 5.6 Delete `.github/workflows/ci_council_review_test.yml` after production validation succeeds
- [ ] 5.7 Squash commits on the branch and open PR for review
