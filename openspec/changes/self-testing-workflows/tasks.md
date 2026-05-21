## 1. Convert Workflow Refs to Local Paths

- [x] 1.1 Update `.github/workflows/ci_checks.yml`: replace `complytime/org-infra/.github/workflows/reusable_ci.yml@cfd981e757253218aefb37c91969c32827e5c4b1 # v0.2.1` with `./.github/workflows/reusable_ci.yml`
- [x] 1.2 Update `.github/workflows/ci_compliance.yml`: replace `complytime/org-infra/.github/workflows/reusable_compliance.yml@cfd981e757253218aefb37c91969c32827e5c4b1 # v0.2.1` with `./.github/workflows/reusable_compliance.yml`
- [x] 1.3 Update `.github/workflows/ci_crapload.yml`: replace `complytime/org-infra/.github/workflows/reusable_crapload_analysis.yml@cfd981e757253218aefb37c91969c32827e5c4b1 # v0.2.1` with `./.github/workflows/reusable_crapload_analysis.yml`
- [x] 1.4 Update `.github/workflows/ci_dependencies.yml`: replace both reusable workflow refs (`reusable_deps_reviewer.yml` and `reusable_dependabot_reviewer.yml`) with local paths
- [x] 1.5 Update `.github/workflows/ci_scheduled.yml`: replace `complytime/org-infra/.github/workflows/reusable_scheduled.yml@cfd981e757253218aefb37c91969c32827e5c4b1 # v0.2.1` with `./.github/workflows/reusable_scheduled.yml`
- [x] 1.6 Update `.github/workflows/ci_security.yml`: replace both reusable workflow refs (`reusable_vuln_scan.yml` and `reusable_security.yml`) with local paths
- [x] 1.7 Update `.github/workflows/reusable_scheduled.yml`: replace the reusable-to-reusable ref to `reusable_security.yml` with a local path

## 2. Sync Script — Release Detection

- [x] 2.1 Add `SOURCE_REPO` module-level constant to `scripts/sync-org-repositories.py`
- [x] 2.2 Add the releases API endpoint (`GET /repos/{owner}/{repo}/releases/latest`) and git ref endpoint (`GET /repos/{owner}/{repo}/git/ref/tags/*`) to the API allowlist in `scripts/sync-org-repositories.py`
- [x] 2.3 Implement `get_latest_release(org, repo_name)` function in `scripts/sync-org-repositories.py` that fetches the latest release tag and resolves it to a commit SHA, handling both lightweight and annotated tags
- [x] 2.4 Add `--release-ref` optional CLI argument to the argument parser in `scripts/sync-org-repositories.py`
- [x] 2.5 Integrate release detection at script startup: auto-detect if `--release-ref` is not provided, fail with clear message and `--release-ref` usage hint if no release is found

## 3. Sync Script — Workflow Ref Transformation

- [x] 3.1 Implement `transform_workflow_refs(content, org, source_repo, sha, tag)` function in `scripts/sync-org-repositories.py` that replaces local path refs with SHA-pinned cross-repo refs
- [x] 3.2 Update the sync loop in `sync_repository()` in `scripts/sync-org-repositories.py` to apply `transform_workflow_refs()` for source files matching `.github/workflows/ci_*.yml`, ensuring it composes with the existing `apply_file_vars()` path

## 4. Tests

- [x] 4.1 Add unit tests for `transform_workflow_refs()` in `tests/`: single ref, multiple refs, no refs (passthrough), mixed content
- [x] 4.2 Add unit tests for `get_latest_release()` in `tests/`: successful detection, no release found, annotated tag dereferencing, `--release-ref` override
- [x] 4.3 Add integration test for composition: a workflow file with both per-repo vars and local workflow refs produces correct output after both transforms

New functions (`transform_workflow_refs`, `get_latest_release`) SHALL have 100% branch
coverage via unit tests.

## 5. Validation

- [x] 5.1 Run `yamllint` on all modified workflow files to verify YAML validity
- [x] 5.2 Verify zero cross-repo `@sha` or `@main` refs remain for `complytime/org-infra` reusable workflows in `.github/workflows/*.yml`
- [x] 5.3 Run `make test` to verify all existing and new tests pass
- [x] 5.4 Run `make lint` to verify all linting passes
- [ ] 5.5 Run `make sync-dry-run` and verify that dry-run output shows transformed refs for downstream repos (requires GITHUB_TOKEN — deferred to CI)
- [x] 5.6 Update sync script `--help` text to document the `--release-ref` argument usage and purpose

<!-- spec-review: passed -->
<!-- code-review: passed -->
