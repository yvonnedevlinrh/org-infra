# Build Production Workflow — Design

## Context

The council review test workflow (`ci_council_review_test.yml`) has validated
end-to-end connectivity: GitHub Actions → ITPC WIF pool → `unbound-force` GCP
project → Claude Sonnet 4.6 on Vertex AI. Both `complytime` and `unbound-force`
GitHub orgs are registered with ITPC and have `roles/aiplatform.user` IAM
bindings on the `unbound-force` project.

No production workflows exist yet. The org follows a reusable workflow pattern
where `reusable_*.yml` workflows contain shared logic and `ci_*.yml` consumer
workflows call them with repo-specific inputs and secrets. Consumer workflows
sync to downstream repos via `sync-config.yml`.

ComplyTime contributors use the fork-and-pull model. GitHub does not expose
secrets or OIDC tokens to fork PR workflows, so a single-workflow approach
would skip council review for all fork PRs. The `workflow_run` two-workflow
chain pattern (used by SonarCloud, Codecov) solves this.

**Stakeholders**: org-infra maintainers, downstream repos consuming the
synced workflows, contributors using fork-and-pull.

## Goals / Non-Goals

**Goals:**

- Two-workflow chain that supports fork PRs (collect → review)
- Keyless authentication via ITPC WIF (no stored credentials)
- Claude Code CLI invocation with explicit model IDs
- Graceful degradation when WIF secrets are absent
- Cost controls (skip drafts, dependabot, concurrency, diff size limits)
- Follows all org conventions (SHA-pinned actions, minimal permissions, naming)

**Non-Goals:**

- Multi-model dynamic selection (future enhancement, not in v1)
- Persona prompt engineering or review output formatting
- GCP resource automation (Terraform/Pulumi)
- Opus model support in v1 (Sonnet 4.6 default, Opus can be added later)

## Decisions

### D1: Two-workflow chain via `workflow_run`

**Decision**: Split council review into `ci_council_review_collect.yml`
(`pull_request` trigger) and `ci_council_review.yml` (`workflow_run` trigger).

**Alternative**: Single `pull_request_target` workflow with label gating.

**Why rejected**: `pull_request_target` requires careful checkout discipline —
any future change that adds `actions/checkout` with the PR ref creates a
security vulnerability. The two-workflow chain is structurally safe: the
privileged workflow never has access to fork code. This matches the pattern
used by SonarCloud and Codecov already in our pipeline.

### D2: Reusable workflow downloads artifact via `run-id`

**Decision**: The collect workflow uploads the diff as a GitHub Actions
artifact. The reusable review workflow receives `triggering_run_id` as an
input and downloads the artifact itself using `actions/download-artifact@v8`
with the `run-id` and `github-token` parameters.

**Alternative A**: Consumer workflow downloads artifact in a separate job,
then calls the reusable workflow. Rejected because reusable workflows run
on fresh runners and cannot access artifacts from a previous job in the
calling workflow.

**Alternative B**: Pass diff content as a `workflow_call` string input.
Rejected because GitHub limits workflow inputs to 65K characters — too
small for large diffs.

**Why chosen**: The reusable workflow downloads the artifact directly using
`run-id: ${{ inputs.triggering_run_id }}` and `github-token: ${{ github.token }}`.
The `GITHUB_TOKEN` in the `workflow_run` context has `actions:read` permission
on the same repo, which is sufficient for cross-run artifact downloads.

### D3: Reusable workflow encapsulates the full review lifecycle

**Decision**: Create `reusable_council_review.yml` that encapsulates artifact
download, WIF auth, CLI install, model invocation, and comment posting. The
`ci_council_review.yml` consumer is a thin wrapper that passes the triggering
run ID and secrets.

**Alternative**: Put all logic directly in `ci_council_review.yml` without a
reusable layer.

**Why rejected**: The reusable pattern allows other org repos to customize
inputs (model, region, diff size limit) while sharing the auth and invocation
logic. Consistent with all other workflows in the org (`reusable_security.yml`,
`reusable_compliance.yml`, etc.).

### D4: Explicit model IDs, not aliases

**Decision**: Use `claude-sonnet-4-6` as the model ID in workflow env vars,
not `sonnet`.

**Alternative**: Use the CLI alias `--model sonnet`.

**Why rejected**: The `sonnet` alias resolved to `claude-sonnet-4-5@20250929`
(an older version not enabled on the project), causing 403 errors. Explicit
model IDs prevent silent version drift and ensure the workflow calls an
enabled model.

### D5: `global` region for Vertex AI

**Decision**: Set `CLOUD_ML_REGION=global` for automatic capacity routing.

**Alternative**: Pin to `us-east5` (confirmed working region).

**Why rejected**: `global` routing was validated in the test workflow and
provides resilience against regional capacity issues. Pinning to a single
region creates a SPOF.

### D6: Actions pinned to SHA (Node 24)

**Decision**: Pin all actions to full 40-character SHAs. Use Node 24
versions (v3.x for Google actions, v5 for peter-evans/create-or-update-comment,
v7/v8 for artifact actions) since GitHub Actions deprecated Node 20 runners
as of June 2026.

**Pinned versions:**

| Action                                  | Version | SHA                                        |
| --------------------------------------- | ------- | ------------------------------------------ |
| `actions/checkout`                      | v6.0.3  | `df4cb1c069e1874edd31b4311f1884172cec0e10` |
| `actions/upload-artifact`               | v7.0.1  | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact`             | v8.0.1  | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` |
| `google-github-actions/auth`            | v3.0.0  | `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093` |
| `google-github-actions/setup-gcloud`    | v3.0.1  | `aa5489c8933f4cc7a4f7d45035b3b1440c9c10db` |
| `peter-evans/create-or-update-comment`  | v5.0.0  | `e8674b075228eee787fea43ef493e45ece1004c9` |

**Alternative**: Use mutable tags (`@v3`, `@v5`).

**Why rejected**: Constitution requires SHA pinning for supply-chain security.

### D7: Claude Code CLI installed via install script (bash)

**Decision**: Install Claude Code CLI with
`curl -fsSL https://claude.ai/install.sh | bash` on each run. Note: the
install script requires `bash`, not `sh` (dash), which is the default
shell on Ubuntu runners.

**Alternative**: Cache the CLI binary across runs.

**Why rejected**: The CLI install takes ~5s. Caching adds complexity
(cache invalidation, version management) for minimal gain on a workflow
that runs infrequently (PR events only, gated).

### D8: Model and diff limit are configurable inputs

**Decision**: The reusable workflow accepts `model` (default `claude-sonnet-4-6`)
and `max_diff_lines` (default `1000`) as `workflow_call` inputs. This allows
per-repo overrides when calling the reusable workflow.

**Alternative**: Hardcode both values.

**Why rejected**: Configurable inputs add minimal complexity and allow repos
to use different models (e.g., Opus for critical repos) or adjust the diff
limit without forking the reusable workflow.

## Risks / Trade-offs

**[R1] `workflow_run` delay** — There is a brief delay (typically seconds)
between the collect workflow completing and the review workflow starting.
→ Acceptable for a review workflow; users will see the review comment
shortly after CI completes.

**[R2] Artifact expiration** — GitHub Actions artifacts expire after 90
days by default. → Not a concern; the review workflow runs immediately
after the collect workflow, not days later.

**[R3] Cost from Opus usage** — If Opus 4.6 is added later, cost per
review increases from ~$1.26 to ~$2.10. → Mitigated by gate checks
(skip drafts, dependabot, forks without diff), concurrency control,
and GCP budget alerts documented in the research doc.

**[R4] Claude Code CLI breaking changes** — The CLI is installed from
`claude.ai/install.sh` on every run; a breaking change could fail the
workflow. → The CLI is Anthropic's official tool with stable interfaces.
If a break occurs, pin to a specific version via the install script's
version flag.

**[R5] Cross-run artifact download requires token** — Downloading
artifacts from the triggering `workflow_run` requires explicitly passing
`github-token` to `actions/download-artifact`. The default `GITHUB_TOKEN`
works for same-repo downloads. → No additional PATs needed.

## Migration Plan

1. **Create workflows**: Add `reusable_council_review.yml`,
   `ci_council_review_collect.yml`, and `ci_council_review.yml`
2. **Validate locally**: Run `yamllint` on all three files
3. **Test on org-infra**: Open a test PR, verify the collect → review
   chain works end-to-end (including a fork PR test)
4. **Remove test workflow**: Delete `ci_council_review_test.yml`
5. **Update sync config**: Add consumer workflows to `sync-config.yml`
6. **Sync to org repos**: Downstream repos receive the workflows; repos
   without WIF secrets configured will gracefully skip

**Rollback**: Remove the three workflow files. No GCP resources need
to be torn down — they are inert without the workflows invoking them.
