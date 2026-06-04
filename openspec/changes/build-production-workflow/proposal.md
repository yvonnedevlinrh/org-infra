## Why

The council review concept has been validated end-to-end: ITPC WIF
authentication works, Claude Sonnet 4.6 and Opus 4.6 respond via Vertex AI,
and the test workflow (`ci_council_review_test.yml`) confirms the full chain
from GitHub Actions OIDC token to model response. However, no production
workflows exist — there is no `reusable_council_review.yml` or
`ci_council_review.yml`. The test workflow must be replaced with production
artifacts that follow the org's reusable workflow pattern and handle fork PRs
via the `workflow_run` two-workflow chain.

Closes complytime/nunya#384

## Non-goals

- Multi-provider support (Bedrock, direct Anthropic API)
- Automating GCP resource provisioning (Terraform, Pulumi)
- Changing persona definitions or review output formatting
- Service account creation or key management
- Open-source model integration (DeepSeek, Qwen, Gemma)

## What Changes

- **New**: `reusable_council_review.yml` — reusable workflow with WIF auth,
  Claude Code CLI install, and model invocation steps
- **New**: `ci_council_review_collect.yml` — consumer workflow triggered on
  `pull_request` that collects the PR diff and uploads it as an artifact (works
  for fork PRs, no secrets needed)
- **New**: `ci_council_review.yml` — consumer workflow triggered on
  `workflow_run` that downloads the diff artifact, authenticates via WIF, runs
  council review, and posts results as a PR comment
- **Remove**: `ci_council_review_test.yml` — temporary test workflow, replaced
  by the production workflows above
- **Update**: `sync-config.yml` — add the new consumer workflows to the sync
  list for downstream repos

## Capabilities

### New Capabilities

- `council-review-workflow`: Production two-workflow chain for AI council
  review — collect phase (fork-safe), review phase (WIF-authenticated), and
  reusable orchestration layer with gate checks, model selection, and cost
  controls

### Modified Capabilities

(none)

## Impact

- **Workflows**: Three new workflow files, one removed
- **Sync**: New consumer workflows sync to all org repos via `sync-config.yml`
- **Secrets**: Requires `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_PROJECT_ID`
  org secrets (already configured)
- **GCP**: Uses existing `unbound-force` project with WIF IAM bindings
  (already granted for both `complytime` and `unbound-force` orgs)
- **Dependencies**: `google-github-actions/auth@v3` (SHA-pinned),
  `google-github-actions/setup-gcloud@v2` (SHA-pinned), Claude Code CLI
