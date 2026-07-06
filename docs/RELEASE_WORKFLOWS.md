# Release Workflows Adoption Guide

How to adopt the reusable release workflows (`reusable_release_preflight.yml` and `reusable_release_goreleaser.yml`) in your repository. This is a one-time setup guide — for ongoing release operations, see [`docs/RELEASE_PROCESS.md`](#cross-reference-release-process).

## Overview

The release pipeline is split into two reusable workflows that compose with existing org-infra publishing workflows:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Consumer repo: release.yml (workflow_dispatch)                        │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  reusable_release_preflight.yml         (org-infra)             │  │
│  │  ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌───────────────┐  │  │
│  │  │ Tag format │→│ Tag      │→│ Semver     │→│ CI check      │  │  │
│  │  │ validation │ │ unique?  │ │ ordering   │ │ verification  │  │  │
│  │  └────────────┘ └──────────┘ └────────────┘ └───────┬───────┘  │  │
│  │                                                     │          │  │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │          │  │
│  │  │ Unreleased       │←─│ Security gate            │←┘          │  │
│  │  │ commits check    │  │ (OSV-Scanner)            │            │  │
│  │  └────────┬─────────┘  └──────────────────────────┘            │  │
│  │           │                                                    │  │
│  │  ┌────────▼─────────┐                                          │  │
│  │  │ Create + push    │ outputs: tag, tag_created                │  │
│  │  │ annotated tag    │                                          │  │
│  │  └──────────────────┘                                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                            │
│           ▼                                                            │
│  ┌─────────────────────┐   ┌─────────────────────┐                    │
│  │ Binary path:        │   │ Container path:     │                    │
│  │ reusable_release_   │   │ reusable_publish_   │                    │
│  │ goreleaser.yml      │   │ ghcr.yml            │                    │
│  │ (cosign + syft      │   │     │               │                    │
│  │  always installed)  │   │     ▼               │                    │
│  └─────────────────────┘   │ reusable_trivy_     │                    │
│                            │ image_scan.yml      │                    │
│                            │     │               │                    │
│                            │     ▼               │                    │
│                            │ reusable_sign_      │                    │
│                            │ and_verify.yml      │                    │
│                            │     │               │                    │
│                            │     ▼               │                    │
│                            │ reusable_publish_   │                    │
│                            │ quay.yml (optional) │                    │
│                            └─────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Composition Patterns

| Pattern | Repos | Pipeline |
|---------|-------|----------|
| **Binary** | complyctl, complytime-providers, c2p-go | preflight → goreleaser |
| **Container** | complybeacon, gemara-content-service, complypack | preflight → ghcr → trivy → sign (→ quay) |
| **Hybrid** | (future) | preflight → goreleaser + ghcr → trivy → sign |
| **Library** | oscal-sdk-go | preflight → GitHub Release (no build artifacts) |

The preflight workflow is universal — every release type uses it. Downstream jobs branch based on what the repo produces.

## Prerequisites

Before adopting the reusable workflows, verify:

1. **Synced CI workflows** — Your repo has the latest `ci_checks.yml` and `ci_security.yml` from org-infra (synced via `sync-config.yml`). These provide the CI gates that preflight verifies.

2. **`ci_local.yml` exists** (recommended) — A repo-specific `.github/workflows/ci_local.yml` containing your test and build jobs. Preflight auto-discovers check names from this file. If your tests live in differently named workflows, use the `ci_checks` input override instead.

3. **Branch protection** — The `main` branch should have required status checks configured. While preflight verifies checks independently, branch protection ensures the same gates apply to PRs.

4. **`workflow_dispatch` permissions** — Only users with write access to the repository can trigger `workflow_dispatch`. Verify the intended release operators have the correct role.

5. **GoReleaser config** (binary repos only) — A `.goreleaser.yaml` file with the required supply chain sections. See [GoReleaser Configuration Standards](#goreleaser-configuration-standards).

## Adoption Instructions

### CLI/Binary Tool (complyctl, complytime-providers pattern)

Pipeline: preflight → goreleaser

Create `.github/workflows/release.yml`:

```yaml
# SPDX-License-Identifier: Apache-2.0
#
# Release workflow for CLI/binary tool repos.
# Uses the org-infra reusable preflight and GoReleaser workflows.
#
# Usage:
#   gh workflow run release.yml --ref main -f tag=v1.2.3

name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Semver tag to release (e.g., v1.2.3)'
        required: true
        type: string

permissions: {}

jobs:
  preflight:
    # Validates tag, verifies CI checks passed, creates annotated tag
    uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@main
    with:
      tag: ${{ inputs.tag }}
      # ci_checks: '["Custom Check / job-name"]'  # Uncomment to override auto-discovery

  release:
    needs: preflight
    if: needs.preflight.outputs.tag != ''
    # Runs GoReleaser with cosign signing and syft SBOMs
    uses: complytime/org-infra/.github/workflows/reusable_release_goreleaser.yml@main
    with:
      tag: ${{ needs.preflight.outputs.tag }}
```

### Container Service (complybeacon, gemara-content-service pattern)

Pipeline: preflight → ghcr → trivy → sign

Create `.github/workflows/release.yml`:

```yaml
# SPDX-License-Identifier: Apache-2.0
#
# Release workflow for container service repos.
# Uses the org-infra reusable preflight and publishing workflows.
#
# Usage:
#   gh workflow run release.yml --ref main -f tag=v1.2.3

name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Semver tag to release (e.g., v1.2.3)'
        required: true
        type: string

permissions: {}

jobs:
  preflight:
    uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@main
    with:
      tag: ${{ inputs.tag }}

  publish-ghcr:
    needs: preflight
    if: needs.preflight.outputs.tag != ''
    uses: complytime/org-infra/.github/workflows/reusable_publish_ghcr.yml@main
    with:
      component_name: my-service        # adjust to your component
      containerfile_path: Containerfile  # path to your Containerfile
      context_path: .                    # build context
      image_name: complytime/my-service  # org/image without registry prefix
    permissions:
      contents: read
      packages: write
      id-token: write
      actions: read
      attestations: write

  scan:
    needs: publish-ghcr
    uses: complytime/org-infra/.github/workflows/reusable_trivy_image_scan.yml@main
    with:
      image_ref: ${{ needs.publish-ghcr.outputs.image_ref }}
    permissions:
      contents: read
      packages: write
      id-token: write

  sign:
    needs: [publish-ghcr, scan]
    uses: complytime/org-infra/.github/workflows/reusable_sign_and_verify.yml@main
    with:
      image_name: ${{ needs.publish-ghcr.outputs.image }}
      digest: ${{ needs.publish-ghcr.outputs.digest }}
      allowed_identity_regex: 'https://github.com/complytime/.*'
    permissions:
      contents: read
      packages: write
      id-token: write
```

**Note:** Adjust `component_name`, `image_name`, `containerfile_path`, and `allowed_identity_regex` to match your repository. Add `reusable_publish_quay.yml` as a final job if your repo promotes to Quay.

### Library (oscal-sdk-go pattern)

Pipeline: preflight → GitHub Release

Libraries have no build artifacts — the release is a tagged commit with release notes.

Create `.github/workflows/release.yml`:

```yaml
# SPDX-License-Identifier: Apache-2.0
#
# Release workflow for Go library repos.
# Uses the org-infra reusable preflight workflow, then creates a GitHub
# Release with auto-generated release notes.
#
# Usage:
#   gh workflow run release.yml --ref main -f tag=v1.2.3

name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Semver tag to release (e.g., v1.2.3)'
        required: true
        type: string

permissions: {}

jobs:
  preflight:
    uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@main
    with:
      tag: ${{ inputs.tag }}

  release:
    needs: preflight
    if: needs.preflight.outputs.tag != ''
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GH_REPO: ${{ github.repository }}
          RELEASE_TAG: ${{ needs.preflight.outputs.tag }}
        run: |
          gh release create "$RELEASE_TAG" \
            --repo "$GH_REPO" \
            --title "$RELEASE_TAG" \
            --generate-notes
```

### Hybrid (Binary + Container)

Pipeline: preflight → goreleaser + ghcr → trivy → sign

For repos that produce both CLI binaries and container images:

```yaml
# SPDX-License-Identifier: Apache-2.0
#
# Hybrid release workflow: binary artifacts via GoReleaser and container
# images via GHCR, both gated by a single preflight check.
#
# Usage:
#   gh workflow run release.yml --ref main -f tag=v1.2.3

name: Release

on:
  workflow_dispatch:
    inputs:
      tag:
        description: 'Semver tag to release (e.g., v1.2.3)'
        required: true
        type: string

permissions: {}

jobs:
  preflight:
    uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@main
    with:
      tag: ${{ inputs.tag }}

  # Binary artifacts via GoReleaser
  goreleaser:
    needs: preflight
    if: needs.preflight.outputs.tag != ''
    uses: complytime/org-infra/.github/workflows/reusable_release_goreleaser.yml@main
    with:
      tag: ${{ needs.preflight.outputs.tag }}

  # Container image via GHCR (runs in parallel with GoReleaser)
  publish-ghcr:
    needs: preflight
    if: needs.preflight.outputs.tag != ''
    uses: complytime/org-infra/.github/workflows/reusable_publish_ghcr.yml@main
    with:
      component_name: my-service
      containerfile_path: Containerfile
      context_path: .
      image_name: complytime/my-service
    permissions:
      contents: read
      packages: write
      id-token: write
      actions: read
      attestations: write

  scan:
    needs: publish-ghcr
    uses: complytime/org-infra/.github/workflows/reusable_trivy_image_scan.yml@main
    with:
      image_ref: ${{ needs.publish-ghcr.outputs.image_ref }}
    permissions:
      contents: read
      packages: write
      id-token: write

  sign:
    needs: [publish-ghcr, scan]
    uses: complytime/org-infra/.github/workflows/reusable_sign_and_verify.yml@main
    with:
      image_name: ${{ needs.publish-ghcr.outputs.image }}
      digest: ${{ needs.publish-ghcr.outputs.digest }}
      allowed_identity_regex: 'https://github.com/complytime/.*'
    permissions:
      contents: read
      packages: write
      id-token: write
```

## CI Check Auto-Discovery

The preflight workflow automatically discovers which CI checks must pass before a release. It reads three workflow files from the repo's checkout:

### The Three-File Convention

| File | Source | Check name construction |
|------|--------|------------------------|
| `ci_checks.yml` | Synced from org-infra | Known by convention: `CI / Standardized CI / Run linters` |
| `ci_security.yml` | Synced from org-infra | Pattern match: at least one `Security Checks / OSV-Scanner / *` must pass |
| `ci_local.yml` | Repo-specific | Parsed with `yq`: `<workflow name> / <job name>` for each job |

### How Check Names Are Constructed

GitHub Actions check names follow the pattern: `<workflow name> / <job name>` (or `<workflow name> / <job name> / <step name>` for reusable workflow calls).

For `ci_local.yml`, the preflight uses `yq` to extract:
1. The workflow `name:` field
2. Each job key and its optional `name:` field

Example: if your `ci_local.yml` contains:

```yaml
name: Local CI
jobs:
  unit-test:
    name: Unit Tests
    ...
  integration-test:
    name: Integration Tests
    ...
```

The preflight discovers two checks:
- `Local CI / Unit Tests`
- `Local CI / Integration Tests`

### When to Use the Override

Pass an explicit JSON array via the `ci_checks` input when:

- Your repo does not have `ci_local.yml` (tests live in custom-named workflows)
- Your check names do not follow the `<workflow name> / <job name>` pattern
- You need to verify checks from workflows other than the three convention files

Example override:

```yaml
preflight:
  uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@main
  with:
    tag: ${{ inputs.tag }}
    ci_checks: '["unit-test", "Build and test", "Unit + Integration Tests (Go 1.24)"]'
```

## GoReleaser Configuration Standards

Every `.goreleaser.yaml` in the organization should include these supply chain sections to meet the constitution's requirement that all release artifacts include SLSA provenance and SBOMs.

### Required: SBOM Generation

```yaml
sboms:
  - artifacts: archive
    cmd: syft
  - artifacts: source
    cmd: syft
```

This generates SBOMs for both the compiled archive and the source tarball. The `syft` binary is pre-installed by `reusable_release_goreleaser.yml`.

### Required: Cosign Signing

```yaml
signs:
  - cmd: cosign
    certificate: "${artifact}.pem"
    args:
      - "sign-blob"
      - "--yes"
      - "--output-certificate=${certificate}"
      - "--output-signature=${signature}"
      - "${artifact}"
    artifacts: checksum
    output: true
```

This signs the checksum file with Sigstore keyless signing. The `cosign` binary is pre-installed by `reusable_release_goreleaser.yml`. The `--yes` flag enables non-interactive mode required for CI.

### Complete Supply Chain Example

```yaml
# .goreleaser.yaml (relevant sections only)

sboms:
  - artifacts: archive
    cmd: syft
  - artifacts: source
    cmd: syft

signs:
  - cmd: cosign
    certificate: "${artifact}.pem"
    args:
      - "sign-blob"
      - "--yes"
      - "--output-certificate=${certificate}"
      - "--output-signature=${signature}"
      - "${artifact}"
    artifacts: checksum
    output: true

# ... builds, archives, changelog, etc.
```

## Workflow Inputs Reference

### `reusable_release_preflight.yml`

**Inputs:**

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tag` | `string` | yes | — | Semver tag to release (e.g., `v1.2.3`) |
| `allow_prerelease` | `boolean` | no | `false` | Accept pre-release suffixes (e.g., `v1.0.0-beta.0`) |
| `ci_checks` | `string` | no | `''` (empty) | JSON array of CI check names to verify. Empty = auto-discover from workflow files |


**Outputs:**

| Output | Description |
|--------|-------------|
| `tag` | The validated tag string (empty if validation failed) |
| `tag_created` | Whether a new tag was created (`true` / `false`). `false` on re-runs where the tag already exists at HEAD |

### `reusable_release_goreleaser.yml`

**Inputs:**

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tag` | `string` | yes | — | The release tag (e.g., `v1.2.3`). Must exist as a git tag |
| `goreleaser_version` | `string` | no | `'~> v2'` | GoReleaser version constraint |
| `goreleaser_args` | `string` | no | `'release --clean --verbose'` | GoReleaser command-line arguments |

**Permissions required:**

| Permission | Reason |
|------------|--------|
| `contents: write` | Create GitHub Release and upload artifacts |
| `id-token: write` | Sigstore OIDC for cosign keyless signing |

## Migration Checklist

Use this checklist when migrating your repository to the reusable release workflows:

### Prerequisites

- [ ] Repo has `ci_checks.yml` and `ci_security.yml` synced from org-infra
- [ ] Repo has `ci_local.yml` with test/build jobs (or plan to use `ci_checks` override)
- [ ] Branch protection is configured on `main`
- [ ] Release operators have write access to the repository

### GoReleaser Repos (Binary)

- [ ] `.goreleaser.yaml` includes `sboms:` section with syft
- [ ] `.goreleaser.yaml` includes `signs:` section with cosign
- [ ] Created `.github/workflows/release.yml` using the CLI/binary template
- [ ] Tested with a pre-release tag (e.g., `v0.0.1-rc.1`) with `allow_prerelease: true`
- [ ] Removed old inline release workflow (or renamed to `release.yml.bak`)
- [ ] Verified GoReleaser produces signed checksums and SBOMs

### Container Repos

- [ ] Created `.github/workflows/release.yml` using the container template
- [ ] Verified `reusable_publish_ghcr.yml` output names match your pipeline
- [ ] Tested with a pre-release tag
- [ ] Removed old inline release workflow

### Library Repos

- [ ] Created `.github/workflows/release.yml` using the library template
- [ ] Tested with a pre-release tag
- [ ] Verified GitHub Release is created with auto-generated notes

### Post-Migration

- [ ] Ran a full release to verify end-to-end pipeline
- [ ] Updated repo-level `docs/RELEASE_PROCESS.md` to reference org-infra workflows
- [ ] Communicated the change to other maintainers

## Troubleshooting

### No CI checks discovered

**Symptom:** Preflight logs `WARNING: No CI checks discovered from workflow files` and the release proceeds without verifying any checks.

**Cause:** The repo does not have `ci_local.yml`, `ci_checks.yml`, or `ci_security.yml` in `.github/workflows/`.

**Fix:** Either:
- Create a `ci_local.yml` with your test and build jobs (recommended)
- Pass explicit check names via the `ci_checks` input:
  ```yaml
  ci_checks: '["unit-test", "Build and test"]'
  ```

### Check name mismatch

**Symptom:** Preflight fails with `Check 'Local CI / unit-test' not found for commit <sha>`.

**Cause:** The check name constructed from `ci_local.yml` does not match the actual check name reported by GitHub. Common reasons:
- The job has a `name:` field that differs from the job key
- The workflow calls a reusable workflow, adding a third level to the check name (`Workflow / Job / Step`)
- The workflow `name:` field was recently changed

**Fix:**
1. Find the actual check names:
   ```bash
   gh api "repos/<owner>/<repo>/commits/<sha>/check-runs" \
     --jq '.check_runs[].name'
   ```
2. Either fix `ci_local.yml` to match or use the `ci_checks` override with the exact names from the API.

### Re-run after partial failure

**Symptom:** GoReleaser failed but the tag was already created. Re-running the workflow fails with `Tag already exists`.

**How it works:** The preflight has smart re-run detection. If the tag already exists and points at HEAD (the same commit), the preflight treats this as a re-run:
- Skips semver ordering verification (already validated)
- Skips unreleased commits check (already validated)
- Skips tag creation (already done)
- Outputs `tag_created=false` and the validated `tag`

The downstream GoReleaser job will re-run and complete the release. No manual tag deletion is needed.

**If the tag points at a different commit:** The preflight will fail with `Tag already exists at commit <sha> — refusing to move an existing tag`. This is intentional — tags are immutable. Use a new version number.

### `sort -V` pre-release ordering

**Symptom:** Preflight rejects a valid pre-release tag with `New tag is not greater than <latest>`.

**Context:** GNU `sort -V` does not follow semver 2.0.0 pre-release ordering rules. For example, `sort -V` incorrectly sorts `1.0.0` before `1.0.0-alpha` (semver says `1.0.0-alpha < 1.0.0`).

**How it works:** The preflight uses `sort -V` only for strict `vX.Y.Z` comparisons (the fast path). When either version contains a pre-release suffix, it switches to a Python-based semver 2.0.0 comparator that correctly handles all pre-release ordering rules:

```text
v1.0.0-alpha < v1.0.0-alpha.1 < v1.0.0-alpha.beta < v1.0.0-beta
  < v1.0.0-beta.2 < v1.0.0-beta.11 < v1.0.0-rc.1 < v1.0.0
```

**Fix:** Ensure `allow_prerelease: true` is set when releasing pre-release tags. If ordering still fails, verify your tag follows semver 2.0.0 format (no build metadata `+` suffix, valid pre-release identifiers).

### `yq` not found during auto-discovery

**Symptom:** Preflight logs `WARNING: yq not found — skipping ci_local.yml check discovery`.

**Cause:** The `yq` binary (mikefarah version) is not installed on the runner. GitHub-hosted `ubuntu-latest` runners include `yq` since late 2022, but self-hosted runners may not have it.

**Fix:** If using self-hosted runners, install `yq` in your runner image. Alternatively, use the `ci_checks` input override to bypass auto-discovery.

## Repo Adoption Status

| Repository | Release Type | ci_local.yml | Supply Chain | Adoption Status |
|---|---|---|---|---|
| complyctl | Binary | No (custom) | Full | Override needed |
| complytime-providers | Binary | Yes | Full | Ready |
| complypack | Container | No | Via GHCR | Ready |
| complybeacon | Container | No | Via GHCR | Needs ci_local |
| gemara-content-service | Container | No | Via GHCR | Needs ci_local |
| compliance-to-policy-go | Binary | No | Partial | Override needed |
| oscal-sdk-go | Library | No | N/A | TBD |

**Legend:**

- **Ready**: Can adopt immediately with zero or minimal configuration.
- **Override needed**: Requires the `ci_checks` input override because tests are in custom-named workflows (not `ci_local.yml`).
- **Needs ci_local**: Requires creating a `ci_local.yml` or using the override before adoption.
- **TBD**: Adoption plan not yet determined.

## Cross-Reference: Release Process

This document covers **one-time setup** — how to adopt the reusable release workflows in your repository.

For **ongoing release operations** (how to trigger a release, what to verify after it completes, failure recovery, pre-release workflows, and supply chain expectations), see [`docs/RELEASE_PROCESS.md`](RELEASE_PROCESS.md).

| Document | Audience | When to read |
|----------|----------|--------------|
| `docs/RELEASE_WORKFLOWS.md` (this doc) | Workflow maintainers | Once, during initial setup |
| `docs/RELEASE_PROCESS.md` | Release operators | Every release cycle |

## Related

- [reusable_release_preflight.yml](../.github/workflows/reusable_release_preflight.yml) — Preflight validation workflow source.
- [reusable_release_goreleaser.yml](../.github/workflows/reusable_release_goreleaser.yml) — GoReleaser release workflow source.
- [complytime/complyctl#655](https://github.com/complytime/complyctl/issues/655) — Original issue requesting centralized release workflows.
- [complytime/complyctl#654](https://github.com/complytime/complyctl/issues/654) — Re-run blocking and pre-release ordering bugs fixed in the reusable preflight.
