# org-infra

CI/CD infrastructure hub for ComplyTime. Syncs reusable workflows, lint configs, templates, and AI tooling to all org repositories via `sync-config.yml`.

## Structure

```text
.github/workflows/      # Reusable (reusable_*) and consumer (ci_*) workflows
scripts/                 # sync-org-repositories.py (Python, GitPython + PyYAML + requests)
tests/                   # pytest unit tests for sync script
compliance/              # Ampel policy definitions (branch protection rules)
specs/                   # SpecKit feature specifications
openspec/                # OpenSpec feature specifications
docs/                    # Project documentation (includes AI_TOOLING.md)
.agents/skills/          # Agent-agnostic AI skills (auto-discovered by OpenCode)
.opencode/commands/      # Project-specific AI commands (review-pr.md)
sync-config.yml          # Defines which files sync to org repos — check before modifying any config
.specify/memory/constitution.md  # All coding standards and governance (single source of truth)
Makefile                 # Build/test/lint automation
```

## Commands

```bash
make lint            # yamllint + ruff (all linters)
make test            # pytest -v
make sync-dry-run    # Preview file sync to org repos
make clean           # Remove __pycache__ and .pyc
```

## Constraints

- **Sync impact**: Config files (`.golangci.yml`, `.yamllint.yml`, `ruff.toml`, `.mega-linter.yml`, `commitlint.config.js`) and workflows (`ci_*`, `reusable_*`) sync to all org repos. Check `sync-config.yml` before modifying to understand downstream impact.
- **Workflow naming**: Reusable workflows MUST use `reusable_` prefix, consumer workflows `ci_` prefix.
- **Python**: Lint with `ruff` (`ruff.toml`). No `go.mod` — this repo is Python + YAML, not Go (Go configs are sync templates for other repos).
- **YAML**: Lint with `yamllint` (`.yamllint.yml`). Line length follows yamllint config, not the 99-char code rule.
- **Standards**: All coding standards are in `.specify/memory/constitution.md`. Do not duplicate them.
- **AI tooling**: Setup, commands, and skill creation documented in `docs/AI_TOOLING.md`.

## Commits

All commits MUST use Conventional Commits, the `-s` flag (Signed-off-by), and include an `Assisted-by` trailer:

```bash
git commit -s -m "feat: add feature X

Description of changes.

Assisted-by: OpenCode (model-name)"
```

Replace `model-name` with the actual model identifier (e.g., `claude-opus-4-6`).

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

## Active Technologies
- YAML (GitHub Actions syntax), Markdown, Python 3.x (sync scripts only) + OpenCode (agent), OpenSpec/SpecKit (spec frameworks — plugin-managed), `gh` CLI (PR review command), GitPython + PyYAML + requests (sync script — existing) (004-standardize-ai-tooling)
- N/A (filesystem-only; no database or persistent storage) (004-standardize-ai-tooling)
- Bash (shell scripts in GitHub Actions `run:` blocks), YAML (GitHub Actions workflow syntax) + GitHub Actions platform, `gh` CLI (pre-installed on runners), `jq` (pre-installed on runners), `curl` (pre-installed on runners), `actions/dependency-review-action@v4.9.0`, `peter-evans/create-or-update-comment@v5.0.0`, `actions/github-script@v8.0.0`, `actions/checkout@v6.0.2`, `tj-actions/changed-files@v47.0.5` (006-robust-dependabot-approval)
- N/A (no persistent storage; data flows via GitHub Actions outputs and environment variables) (006-robust-dependabot-approval)
- `renovatebot/github-action@v46.1.16` (self-hosted Renovate runner), `actions/create-github-app-token@v3.2.0` (GitHub App authentication) + JavaScript config (`renovate-config.js`), JSON preset (`go-toolchain-patches.json`) (go-toolchain-patch-automation)

## Recent Changes
- 004-standardize-ai-tooling: Added YAML (GitHub Actions syntax), Markdown, Python 3.x (sync scripts only) + OpenCode (agent), OpenSpec/SpecKit (spec frameworks — plugin-managed), `gh` CLI (PR review command), GitPython + PyYAML + requests (sync script — existing)
- 006-robust-dependabot-approval: Added Bash (shell scripts in GitHub Actions `run:` blocks), YAML (GitHub Actions workflow syntax) + GitHub Actions platform, `gh` CLI (pre-installed on runners), `jq` (pre-installed on runners), `curl` (pre-installed on runners), `actions/dependency-review-action@v4.9.0`, `peter-evans/create-or-update-comment@v5.0.0`, `actions/github-script@v8.0.0`, `actions/checkout@v6.0.2`, `tj-actions/changed-files@v47.0.5`
- 284-org-member-image-push: Extended `reusable_publish_ghcr.yml` with unprotected ref publishing (org membership verification, dev-prefixed tag isolation, configurable attestation policy). Added `docker/login-action@v4.2.0`, `docker/setup-qemu-action@v4.0.0`, `docker/setup-buildx-action@v4.1.0`, `docker/build-push-action@v7.2.0`, `docker/metadata-action@v6.1.0`, `actions/attest-build-provenance@v4.1.0`, `anchore/sbom-action@v0.24.0`, `actions/attest@v4.1.0`, `sigstore/cosign-installer@v4.1.2`
- 306-publish-complypack-ampel-bp: Added `reusable_publish_complypack.yml` (pack and push complypack OCI artifacts to GHCR with SLSA provenance and SBOM attestation) and `ci_publish_complypack.yml` (dual-registry: GHCR on push, Quay on release). Renamed `resuable_publish_quay.yml` to `reusable_publish_quay.yml` (typo fix). Uses `complypack` CLI via `go install`, `oras-project/setup-oras`, `imjasonh/setup-crane`.
- go-toolchain-patch-automation: Added `ci_renovate.yml` (centralized self-hosted Renovate runner for Go version patch updates). Uses `renovatebot/github-action@v46.1.16` with a dedicated GitHub App (`complytime-renovate[bot]`, `contents:write` + `pull-requests:write`). Shared preset (`go-toolchain-patches.json`) restricts to Go version patch updates only (matches `go` and `toolchain` directives via `matchDepNames`). Global config (`renovate-config.js`) autodiscovers org repos via `globalExtends`.

## Convention Packs

This repository uses convention packs scaffolded by
unbound-force. Agents MUST read the applicable pack(s)
before writing or reviewing code.

- `.opencode/uf/packs/default.md`
- `.opencode/uf/packs/default-custom.md`
- `.opencode/uf/packs/severity.md`
- `.opencode/uf/packs/content.md`
- `.opencode/uf/packs/content-custom.md`
