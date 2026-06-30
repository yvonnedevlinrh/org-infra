## Why

The reusable SonarCloud workflow (`reusable_sonarqube.yml`) does not expose inputs for
project-specific SonarCloud properties like `sonar.sources` and `sonar.tests`. Repos migrating
from inline workflows to the reusable workflow lose these settings, causing SonarCloud to treat
the entire repository as source code (including test files, scripts, and configs), which skews
quality metrics.

This was identified during the complyscribe migration (complytime/complyscribe#815) and filed
as complytime/org-infra#146.

Additionally, the existing `args` block has a quoting defect on the conditional coverage line:
when `coverage_file_path` is empty, the outer double quotes produce an empty-string argument
(`""`) that `string-argv` (used by sonarqube-scan-action v8.2.0) parses as a positional argument
to sonar-scanner, which may cause warnings or failures.

## What Changes

- Add two optional inputs to `reusable_sonarqube.yml`: `sonar_sources` and `sonar_tests`,
  with empty-string defaults (preserving backward compatibility)
- Append conditional `-D` flags for the new inputs to the scanner `args` block
- Fix the empty-string quoting defect on the existing conditional coverage line (line 87)
- Update spec documentation (`specs/002-sonarqube-workflow/quickstart.md` and `spec.md`)

## Non-goals

- Adding a generic `extra_args` free-form input. The org follows a strict explicit inputs
  pattern across all 15 reusable workflows (60 total inputs, zero catch-all string inputs).
  A free-form input would be an anti-pattern.
- Adding a `sonar_language_version` input (e.g., `sonar.python.version`). This property is
  language-specific and does not generalize well -- Go repos would not use it. Repos that need
  it should set it via `sonar-project.properties` in the repo root.

## Capabilities

### New Capabilities

- `sonar-source-path-config`: Callers can specify `sonar_sources` and `sonar_tests` inputs to
  control which directories SonarCloud treats as source code vs. test code, preventing metric
  skew from scanning non-source files.

### Modified Capabilities

- `sonarcloud-coverage-args`: The conditional coverage `-D` flag no longer produces an
  empty-string argument when coverage is not configured (quoting fix).

### Removed Capabilities

_None._

## Impact

- **`reusable_sonarqube.yml`**: 2 new inputs, 2 new conditional `-D` flags, 1 quoting fix.
  All changes are additive with empty defaults -- existing callers are unaffected.
- **`specs/002-sonarqube-workflow/quickstart.md`**: New usage example showing the inputs.
- **`specs/002-sonarqube-workflow/spec.md`**: Updated functional requirements.
- **Downstream repos**: No impact unless they opt in to the new inputs. Existing callers
  continue to work identically.
- **Sync config**: No changes. This workflow is not in `sync-config.yml`.

## Constitution Alignment

Assessed against the Unbound Force org constitution.

### I. Autonomous Collaboration

**Assessment**: N/A -- No change to artifact-based communication or self-describing outputs.

### II. Composability First

**Assessment**: PASS -- New inputs are optional with empty defaults. No new mandatory
dependencies introduced. Existing callers are unaffected.

### III. Observable Quality

**Assessment**: PASS -- The quoting fix eliminates a potential empty-string argument that could
cause scanner warnings. New inputs improve scan accuracy by scoping analysis to actual source
and test directories.

### IV. Testability

**Assessment**: N/A -- YAML workflow files have no unit test framework. Validation relies on
`yamllint` (syntax) and code review. No behavioral changes to testable components.
