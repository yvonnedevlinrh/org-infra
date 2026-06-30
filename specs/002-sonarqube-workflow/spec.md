# Feature Specification: Reusable SonarCloud Analysis Workflow

## Document Overview

This specification details a centralized, reusable workflow for SonarCloud static code analysis that can be consumed by repositories across the organization. The workflow analyzes code on merges to main branch, enforces quality gates, and integrates with test coverage reporting.

**Key Metadata:**
- Workflow File: `.github/workflows/reusable_sonarqube.yml`
- Date: 2026-03-23
- Current Status: Active

## Core User Scenarios

### Priority 1: Main Branch Analysis

Repository maintainers can enable SonarCloud analysis on main branch by creating a consumer workflow that references the org-infra reusable workflow. The system automatically analyzes code on every merge to main, enforces quality gates, and provides continuous visibility into code quality metrics.

**Test Coverage:** Verifies analysis executes on pushes to main, quality gate results are surfaced, and the workflow properly authenticates with SonarCloud using provided tokens.

### Priority 2: Coverage Report Integration

Repositories with test coverage can provide coverage file paths that the SonarCloud analysis will consume. The workflow supports configurable coverage file paths and language-specific scanner properties for multiple language ecosystems.

**Test Coverage:** Validates coverage files are correctly passed to SonarCloud scanner, and the workflow gracefully handles missing coverage files.

### Priority 2: Multi-Language Support

The workflow supports multiple language ecosystems with language-specific coverage configuration. Currently configured for Go and Python repositories with appropriate scanner properties for each language's coverage format.

**Test Coverage:** Ensures language-specific scanner properties (Go and Python) can be configured, and the workflow correctly passes these to the SonarCloud scanner action.

### Priority 2: Source and Test Path Scoping

Callers can specify which directories SonarCloud treats as source code vs. test code via `sonar_sources` and `sonar_tests` inputs. Without these, SonarCloud scans the entire repository as source code, inflating code smell counts, duplication metrics, and skewing coverage percentages.

**Test Coverage:** Validates that source and test path inputs are correctly passed as `-Dsonar.sources` and `-Dsonar.tests` scanner arguments, and that omitting them does not change default behavior.

## Edge Cases Addressed

- **Missing coverage files**: Workflow proceeds with analysis when coverage files are not provided
- **Quality gate failures**: Workflow fails when SonarCloud quality gates are not met, maintaining code quality standards
- **Invalid coverage paths**: Gracefully handles misconfigured coverage file paths without failing the entire analysis

## Functional Requirements Summary

The specification mandates that the sonarqube workflow must:

1. **Analyze main branch**: Execute SonarCloud analysis on pushes to main branch
2. **Enforce quality gates**: Configure SonarCloud scanner to wait for and enforce quality gate results
3. **Handle coverage reports**: Optionally process test coverage files with language-specific scanner properties
4. **Maintain security**: Follow least-privilege principles with minimal required permissions
5. **Provide flexible configuration**: Accept inputs for organization, project key, coverage paths, scanner properties, and source/test directory scoping
6. **Use pinned actions**: Reference all GitHub actions by commit SHA for supply chain security

## Success Metrics

Adoption success requires:
- Any repository can enable SonarCloud analysis via a single consumer workflow file
- Quality gate violations are detected and reported within standard CI execution time
- Coverage reports from various languages integrate seamlessly
- Consumer workflows maintain simplicity (minimal configuration required)
- Analysis runs automatically on every merge to main branch

## Scope Boundaries

**Included:**
- Centralized reusable workflow for SonarCloud analysis
- Main branch analysis on push events
- Coverage file integration with language-specific scanner properties
- Quality gate enforcement
- Multi-language support via configurable scanner properties
- Source and test directory scoping via `sonar_sources` and `sonar_tests` inputs

**Excluded:**
- SonarCloud project creation and configuration (handled in SonarCloud UI)
- Coverage report generation (handled by consumer repositories or CI processes)
- Language-specific build steps (handled by consumer workflows or separate processes)
- Organization-level SonarCloud administration
- Custom quality gate definitions (managed in SonarCloud)
- Language-version properties (e.g., `sonar.python.version`) -- repos can set these via `sonar-project.properties`
