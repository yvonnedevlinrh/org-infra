# SonarCloud Analysis Quickstart

This guide covers implementing SonarCloud analysis for repository maintainers adopting the reusable workflow.

## Prerequisites

Before setting up the workflow, ensure you have:

1. **SonarCloud Project**: A project created in SonarCloud for your repository
2. **SonarCloud Token**: An analysis token with appropriate permissions
3. **GitHub Secret**: The SonarCloud token stored as a repository or organization secret named `SONAR_TOKEN`

## Setup Steps

### Step 1: Configure Repository Variables

Set up repository or organization variables for SonarCloud configuration:

1. Navigate to your repository **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. Add the following variables:
   - `SONAR_ORGANIZATION`: Your SonarCloud organization key
   - `SONAR_PROJECT_KEY`: Your SonarCloud project key (format: `org_repo`)

### Step 2: Add Consumer Workflow

Create `.github/workflows/sonarcloud.yml` to analyze code on every merge to main:

**Basic workflow (without coverage):**
```yaml
name: SonarCloud Analysis

on:
  push:
    branches:
      - main

permissions:
  contents: none
  issues: none
  pull-requests: none

jobs:
  sonarqube:
    name: SonarCloud Analysis
    permissions:
      contents: read
      pull-requests: read
    uses: complytime/org-infra/.github/workflows/reusable_sonarqube.yml@main
    with:
      sonar_organization: ${{ vars.SONAR_ORGANIZATION }}
      sonar_project_key: ${{ vars.SONAR_PROJECT_KEY }}
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      source_token: ${{ secrets.GITHUB_TOKEN }}
```

**With coverage (Go example):**
```yaml
name: SonarQube Analysis

on:
  push:
    branches:
      - main

permissions:
  contents: none
  issues: none
  pull-requests: none

jobs:
  generate-coverage:
    name: Generate Coverage Report
    runs-on: ubuntu-latest
    steps:
      - name: Check out
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Run test
        run: make test-unit
      - name: Upload artifact
        uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
        with:
          name: coverage
          path: coverage.out

  sonarqube:
    name: SonarCloud Analysis
    permissions:
      contents: read
      pull-requests: read
    needs: generate-coverage
    uses: complytime/org-infra/.github/workflows/reusable_sonarqube.yml@main
    with:
      sonar_organization: ${{ vars.SONAR_ORGANIZATION }}
      sonar_project_key: ${{ vars.SONAR_PROJECT_KEY }}
      coverage_artifact_name: coverage
      coverage_file_path: coverage.out
      language_scanner_property: sonar.go.coverage.reportPaths
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      source_token: ${{ secrets.GITHUB_TOKEN }}
```

**With coverage (Python example):**
```yaml
name: SonarQube Analysis

on:
  push:
    branches:
      - main

permissions:
  contents: none
  issues: none
  pull-requests: none

jobs:
  generate-coverage:
    name: Generate Coverage Report
    runs-on: ubuntu-latest
    steps:
      - name: Check out
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Run test
        run: pytest --cov --cov-report=xml
      - name: Upload artifact
        uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
        with:
          name: coverage
          path: coverage.xml

  sonarqube:
    name: SonarCloud Analysis
    permissions:
      contents: read
      pull-requests: read
    needs: generate-coverage
    uses: complytime/org-infra/.github/workflows/reusable_sonarqube.yml@main
    with:
      sonar_organization: ${{ vars.SONAR_ORGANIZATION }}
      sonar_project_key: ${{ vars.SONAR_PROJECT_KEY }}
      coverage_artifact_name: coverage
      coverage_file_path: coverage.xml
      language_scanner_property: sonar.python.coverage.reportPaths
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      source_token: ${{ secrets.GITHUB_TOKEN }}
```

**With source/test path scoping (Python example):**
```yaml
name: SonarQube Analysis

on:
  push:
    branches:
      - main

permissions:
  contents: none
  issues: none
  pull-requests: none

jobs:
  generate-coverage:
    name: Generate Coverage Report
    runs-on: ubuntu-latest
    steps:
      - name: Check out
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Run test
        run: pytest --cov --cov-report=xml
      - name: Upload artifact
        uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
        with:
          name: coverage
          path: coverage.xml

  sonarqube:
    name: SonarCloud Analysis
    permissions:
      contents: read
      pull-requests: read
    needs: generate-coverage
    uses: complytime/org-infra/.github/workflows/reusable_sonarqube.yml@main
    with:
      sonar_organization: ${{ vars.SONAR_ORGANIZATION }}
      sonar_project_key: ${{ vars.SONAR_PROJECT_KEY }}
      coverage_artifact_name: coverage
      coverage_file_path: coverage.xml
      language_scanner_property: sonar.python.coverage.reportPaths
      sonar_sources: complyscribe/
      sonar_tests: tests/
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      source_token: ${{ secrets.GITHUB_TOKEN }}
```

Without `sonar_sources` and `sonar_tests`, SonarCloud treats the entire repository as source
code (including test files, scripts, and configs), which skews quality metrics. These inputs
map directly to `sonar.sources` and `sonar.tests` scanner properties.

Alternatively, repos can configure these properties via a `sonar-project.properties` file in
the repository root. Workflow inputs take precedence (they are passed as `-D` CLI flags).

**Language scanner properties:**
- Go: `sonar.go.coverage.reportPaths`
- Python: `sonar.python.coverage.reportPaths`

## Configuration Options

### Required Inputs

- `sonar_organization`: Your SonarCloud organization key (typically from `vars.SONAR_ORGANIZATION`)
- `sonar_project_key`: Your SonarCloud project key (format: `org_repo`, typically from `vars.SONAR_PROJECT_KEY`)

### Optional Inputs (for coverage)

- `coverage_artifact_name`: Name of the coverage artifact uploaded by the previous job (default: `coverage`)
- `coverage_file_path`: Path to coverage file within the artifact (e.g., `coverage.out`, `coverage.xml`)
- `language_scanner_property`: SonarCloud scanner property for coverage (see language-specific properties above)

### Optional Inputs (for source/test scoping)

- `sonar_sources`: Comma-separated list of source directories (e.g., `complyscribe/`, `pkg/`). Maps to `sonar.sources`.
- `sonar_tests`: Comma-separated list of test directories (e.g., `tests/`). Maps to `sonar.tests`.

### Required Secrets

- `SONAR_TOKEN`: SonarCloud analysis token
- `source_token`: GitHub token for API access (usually `secrets.GITHUB_TOKEN`)

### Repository Variables

- `SONAR_ORGANIZATION`: SonarCloud organization key (configured in repository or organization settings)
- `SONAR_PROJECT_KEY`: SonarCloud project key (configured in repository or organization settings)

## Verification

After setup:

1. **Push a commit to main** to trigger the workflow (or merge a pull request)
2. **Check the Actions tab** to verify the workflow executes successfully
3. **View results in SonarCloud** at `https://sonarcloud.io/project/overview?id=your_project_key`
4. **Review quality gate status** in the workflow run results

## Troubleshooting

### Quality Gate Failing

The workflow fails when SonarCloud quality gates are not met. Review the analysis results in SonarCloud to identify issues:
- Code coverage below threshold
- Code smells exceeding limits
- Security vulnerabilities detected
- Code duplication too high

### Coverage Not Appearing

Ensure:
- Coverage generation job completed successfully and uploaded the artifact
- `coverage_artifact_name` matches the artifact name from the upload step
- `coverage_file_path` matches the file path within the uploaded artifact
- `language_scanner_property` is correct for your language (Go or Python)
- Coverage file format is compatible with SonarCloud (coverage.out for Go, coverage.xml for Python)

## Infrastructure Notes

The reusable workflow resides in the org-infra repository at `.github/workflows/reusable_sonarqube.yml`. Changes to the workflow should follow the repository's contribution guidelines and be tested before merging.
