# org-infra Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-05

## Active Technologies

- YAML (GitHub Actions workflow syntax), Markdown, Python 3.x (sync scripts only)
- OpenCode (agent), OpenSpec/SpecKit (spec frameworks — plugin-managed)
- `gh` CLI (PR review command), GitPython + PyYAML + requests (sync script)
- Bash (shell scripts in GitHub Actions `run:` blocks)

## Project Structure

```text
scripts/
tests/
```

## Commands

```bash
make lint            # yamllint + ruff (all linters)
make test            # pytest -v
make sync-dry-run    # Preview file sync to org repos
make clean           # Remove __pycache__ and .pyc
```

## Code Style

YAML (GitHub Actions workflow syntax): Follow `.yamllint.yml` configuration
Python: Follow `ruff.toml` configuration

## Recent Changes

- 001-crapload-workflow: Added YAML (GitHub Actions workflow syntax) + Gaze, Go toolchain, `jq`, `bc`
- 004-standardize-ai-tooling: Added OpenCode agent, OpenSpec/SpecKit, `gh` CLI, AI tooling docs
- 006-robust-dependabot-approval: Added dependabot approval workflow with dependency review
- go-toolchain-patch-automation: Added `ci_renovate.yml` (centralized self-hosted Renovate runner for Go version patch updates). Uses `renovatebot/github-action@v46.1.16` with a dedicated GitHub App (`complytime-renovate[bot]`, `contents:write` + `pull-requests:write`). Shared preset (`go-toolchain-patches.json`) restricts to Go version patch updates only (matches `go` and `toolchain` directives via `matchDepNames`). Global config (`renovate-config.js`) autodiscovers org repos via `globalExtends`.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

# Unbound Force — managed by uf init

@AGENTS.md
@.opencode/agents/cobalt-crush-dev.md

## Convention Packs

@.opencode/uf/packs/default.md
@.opencode/uf/packs/default-custom.md
@.opencode/uf/packs/severity.md
@.opencode/uf/packs/content.md
@.opencode/uf/packs/content-custom.md

## Review Agents (read on-demand)

When performing code review, read the applicable
Divisor agent from .opencode/agents/:
- divisor-guard.md — intent drift, constitution
- divisor-architect.md — structure, patterns, DRY
- divisor-adversary.md — security, error handling
- divisor-testing.md — test quality, assertions
- divisor-sre.md — operations, performance
