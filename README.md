# ⚙️ CI/CD Reusable Workflows

This repository centrally manages configuration files, templates, and standardized CI/CD workflows for the organization.
Its purpose is to ensure **security, consistency, and reusability** across all repositories by defining common settings and automation processes once.

---

## 🎯 Purpose

The primary goal is to provide **pre-vetted, security-hardened pipeline steps** for common tasks, such as environment deployment, lint checks, dependency review, vulnerability scans, tests coverage, and more.

Specifically, this repository includes:

* [Reusable Workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) for common tasks
* Container image build, publish, sign, and promotion pipelines with supply chain security
* Compliance evaluation with attestation-based policy checks
* Templates to consume reusable workflows in org repositories
* Templates for PRs and Issues creation
* Configuration files for lint checks
* Synchronization script integrated with [peribolos](https://github.com/complytime/.github/blob/main/peribolos.yaml) to periodically check consistence among repositories

---

## 📁 Directory Structure

```bash
org-infra/
├── .github/
│  ├── ISSUE_TEMPLATE/
│  │  ├── bug_report.yml                    # Issue form to report a Bug.
│  │  ├── feature_request.yml               # Issue form to request a Feature.
│  │  ├── task.yml                          # Issue form for tracked work items.
│  │  └── user_story.yml                    # Issue form for user stories.
│  ├── workflows/
│  │  ├── ci_checks.yml                     # Workflow to consume `reusable_ci`.
│  │  ├── ci_compliance.yml                 # Workflow to consume `reusable_compliance`.
│  │  ├── ci_publish_complypack.yml         # Publish ampel complypack to GHCR (push) and Quay (release).
│  │  ├── ci_dependencies.yml               # Workflow to consume `reusable_dependabot_reviewer` and `reusable_deps_reviewer`
│  │  │                                     # plus local jobs to auto-approve and comment on dependabot PRs.
│  │  ├── ci_scheduled.yml                  # Scheduled OSV-Scanner and OpenSSF Scorecards via `reusable_scheduled`.
│  │  ├── ci_crapload.yml                   # Workflow to consume `reusable_crapload_analysis` for CRAP load analysis.
│  │  ├── ci_security.yml                   # Workflow to consume `reusable_vuln_scan` and `reusable_security`.
│  │  ├── reusable_ci.yml                   # Generic CI checks, such as linters, typos and PR titles.
│  │  ├── reusable_compliance.yml           # Compliance evaluation with attestation-based policy checks.
│  │  ├── reusable_crapload_analysis.yml    # CRAP (Change Risk Anti-Patterns) load analysis for Go code using Gaze.
│  │  ├── reusable_dependabot_reviewer.yml  # Specific for dependabot PRs. Classify risk and checks dependency adoption.
│  │  ├── reusable_deps_reviewer.yml        # Check for vulnerabilities, license issues, and OpenSSF Scorecard Level.
│  │  ├── reusable_gemini_review.yml        # AI-powered code review using Google Gemini to review pull requests.
│  │  ├── reusable_publish_complypack.yml   # Pack and push complypack OCI artifacts to GHCR with provenance and SBOM.
│  │  ├── reusable_publish_ghcr.yml         # Build and push container images to GHCR with supply chain security artifacts.
│  │  ├── reusable_publish_oras.yml         # Push arbitrary files as OCI artifacts to GHCR via ORAS CLI.
│  │  ├── reusable_publish_quay.yml         # Promote images between registries with signature verification.
│  │  ├── reusable_scheduled.yml            # Scheduled OSV-Scanner and OpenSSF Scorecards.
│  │  ├── reusable_security.yml             # OpenSSF Scorecards analysis and SARIF upload.
│  │  ├── reusable_sign_and_verify.yml      # Sigstore keyless signing and attestation verification for container images.
│  │  ├── reusable_sonarqube.yml            # SonarCloud static analysis for code quality and security.
│  │  ├── reusable_vuln_scan.yml            # Vulnerability scanning via OSV-Scanner and Trivy.
│  │  └── sync_org_repositories.yml         # Manual, scheduled, and event-based workflow to synchronize files.
│  ├── dependabot.yml                       # Dependabot settings for GitHub Actions and Go modules.
│  ├── dependabot_python.yml                # Dependabot settings for GitHub Actions (Python repos) and pip.
│  └── pull_request_template.md             # PR template applicable to all repositories.
├── compliance/
│  └── ampel/                               # Policy definitions for branch protection rule compliance checks.
├── docs/                                   # More detailed and specific documentation.
│  ├── LOCAL_TESTING.md                     # Documentation on how to test synchronization locally.
│  └── SYNC_REPOSITORIES_SETUP.md          # Documentation on how to setup the repository synchronization infrastructure.
├── scripts/
│  ├── sync-org-repositories.py             # Python script to check and ensure consistence among repositories.
│  └── resolve-go-packages.sh              # Bash: multi-module Go package auto-discovery
├── ...                                     # Multiple technology specific configuration files
├── sync-config.yml                         # Configuration file consumed by `sync-org-repositories.py`
└── README.md                               # This file.
```

---

## 🧪 Testing

### Quick Start

```bash
# Set up Python virtual environment (automatic dependency installation)
make venv

# Activate the virtual environment (optional for interactive use)
source .venv/bin/activate

# Run all tests (unit and integration)
make test

# Run linters
make lint             # Lint YAML and Python (auto-creates venv if needed)
```

The `make venv` target automatically creates a `.venv` directory and installs all Python dependencies from `requirements.txt` (including pytest, ruff, yamllint). All make targets that need Python (`make test`, `make lint`, `make sync-dry-run`) automatically use the virtual environment - you don't need to activate it manually for make commands.

### Test Suites

All tests use pytest and are located in the `tests/` directory:

1. **Python Unit Tests** - Test the sync script logic
2. **Integration Tests** - Test CRAP load package resolution and workflow input validation

Run all tests with:
```bash
make test
# or directly with pytest
pytest tests/ -v
```

See [`docs/LOCAL_TESTING.md`](docs/LOCAL_TESTING.md) for detailed setup and troubleshooting.

---

## Style Guides

* Reusable workflows are prefixed by `reusable_` and should have a clear, descriptive name reflecting its function.
* Reusable workflows are generic enough to be consumed by any repository within the organization.
* Regular workflows consuming reusable workflows are prefixed by `ci_`.
* Workflows must ensure the Principle of Least Privilege.
* Write permissions must be avoided. When necessary, they are defined in the minimal possible scope.
* Prefer defining explicit permissions per Job.
* PRs must pass all CI jobs.
