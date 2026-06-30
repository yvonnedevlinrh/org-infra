## Context

`reusable_sonarqube.yml` (87 lines) currently accepts 5 inputs focused on organization/project
identity and coverage reporting. The scanner `args` block hardcodes `sonar.organization`,
`sonar.projectKey`, and `sonar.qualitygate.wait=true`, with a conditional coverage flag.

Without `sonar.sources` and `sonar.tests`, SonarCloud scans the entire repo as source code,
including test files, scripts, and configs. This inflates code smell counts, duplication metrics,
and skews coverage percentages.

Key files:
- `.github/workflows/reusable_sonarqube.yml` -- reusable workflow (target of changes)
- `specs/002-sonarqube-workflow/quickstart.md` -- consumer setup documentation
- `specs/002-sonarqube-workflow/spec.md` -- feature specification

## Goals / Non-Goals

### Goals

- Allow callers to scope SonarCloud analysis to specific source and test directories
- Fix the empty-string argument defect in the coverage `args` line
- Maintain full backward compatibility (all new inputs optional with empty defaults)

### Non-Goals

- Adding a generic `extra_args` input
- Adding language-version inputs (e.g., `sonar.python.version`)
- Modifying sync-config or creating a consumer workflow

## Decisions

### Decision 1: Dedicated inputs, not a generic `extra_args`

**Decision**: Add `sonar_sources` and `sonar_tests` as explicit, typed string inputs.

**Rationale**: All 15 reusable workflows in the org use strictly explicit inputs (60 total
inputs, zero free-form catch-alls). The only exception is `scan-args` in
`reusable_scheduled.yml`, which is a deliberate pass-through to an upstream Google workflow.
A generic `extra_args` would violate the established org convention and Principle VII
(Convention Over Configuration).

**Alternative rejected**: `extra_args` free-form string -- flexible but inconsistent with org
patterns, harder to discover, and higher misconfiguration risk.

### Decision 2: Exclude `sonar_language_version`

**Decision**: Do not add a `sonar_language_version` (or `sonar_python_version`) input.

**Rationale**: `sonar.python.version` is the only language-version property currently relevant
in the org. Adding it as an input creates a Python-specific parameter on a language-agnostic
workflow. Go repos would see a meaningless input. Repos needing this property can set it via
`sonar-project.properties` in the repo root, which SonarCloud reads automatically.

**Alternative rejected**: Adding `sonar_python_version` -- too narrow. Adding a generic
`sonar_language_version` with a companion `sonar_language_version_property` -- too complex for
a single edge case.

### Decision 3: Fix the empty-string quoting on line 87

**Decision**: Remove the outer double quotes from the conditional coverage `-D` flag so that
an empty expression produces no token rather than an empty-string argument.

Current (problematic):
```yaml
"${{ env.COVERAGE_FILE_PATH && format('-D{0}={1}', ...) || '' }}"
```

Fixed:
```yaml
${{ env.COVERAGE_FILE_PATH && format('-D{0}={1}', ...) || '' }}
```

**Rationale**: sonarqube-scan-action v8.2.0 is a Node.js action that parses `args` via
`string-argv`. Quoted empty string `""` becomes an empty positional argument to sonar-scanner.
Without quotes, an empty expression produces whitespace that `string-argv` ignores.

**Same pattern applied to new inputs**: The new conditional `-D` flags for `sonar_sources`
and `sonar_tests` use the unquoted pattern to avoid the same issue.

### Decision 4: Use `env:` indirection for new inputs

**Decision**: Map new inputs to `env:` variables in the step's `env:` block, then reference
via `${{ env.* }}` in the `args` block. Do not use `${{ inputs.* }}` directly in `args`.

**Rationale**: This matches the existing pattern in the workflow (lines 74-80) and aligns
with the org's security convention of environment variable indirection to prevent script
injection.

## Risks / Trade-offs

**[Risk: None] Backward compatibility**: All new inputs have empty-string defaults. Existing
callers pass no value, so the conditional `-D` flags evaluate to empty and produce no scanner
arguments. Behavior is identical to current.

**[Risk: Low] Quoting fix changes behavior for edge cases**: If any caller currently relies
on the empty-string argument being passed (unlikely -- it would be a bug in the caller),
removing it changes behavior. Mitigation: this is a bug fix, not a behavior change.

**[Trade-off] sonar-project.properties vs. workflow inputs**: Repos can already configure
`sonar.sources` and `sonar.tests` via a `sonar-project.properties` file in the repo root.
Workflow inputs provide a centralized alternative but create two configuration paths. This
is acceptable because workflow inputs take precedence (they're CLI `-D` flags) and the
quickstart docs will clarify the precedence.
