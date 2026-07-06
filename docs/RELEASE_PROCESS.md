# Release Process

The release process values simplicity, automation, and predictability in order to provide low cost for maintainers. A release is a single workflow dispatch with a tag input. The automation handles validation, tagging, building, signing, and publishing. Maintainers should not need to run manual commands, manage signing keys, or coordinate multi-step procedures to ship a release.

This document describes the standard release flow that all repositories in the ComplyTime and Unbound Force organizations follow. Repository-specific procedures (Fedora packaging, container promotion, Homebrew tap publishing) are documented in each repository's own `docs/RELEASE_PROCESS.md` and reference this document as the base authority.

## Standard Release Flow

A release progresses through four phases: trigger, preflight validation, build and artifact generation, and GitHub Release publication. The entire pipeline runs in GitHub Actions with no local tooling required.

```text
Maintainer
    │
    │  workflow_dispatch (tag: "v1.2.3")
    ▼
┌─────────────────────────────────────────────────────┐
│  Preflight Validation                               │
│  (reusable_release_preflight.yml)                   │
│                                                     │
│  1. Tag format ─── vX.Y.Z strict semver             │
│  2. Tag uniqueness ─── re-run safe (tag at HEAD)    │
│  3. Semver ordering ─── new > latest existing tag   │
│  4. CI gates ─── auto-discovered from workflow files │
│  5. Security scan ─── at least one scan passed      │
│  6. Unreleased commits ─── prevent empty releases   │
│  7. Tag creation ─── annotated, pushed to remote    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Build & Artifact Generation                        │
│  (reusable_release_goreleaser.yml or container      │
│   pipeline, depending on repo type)                 │
│                                                     │
│  • Go version read from go.mod                      │
│  • cosign + syft always installed                   │
│  • GoReleaser builds binaries, checksums, SBOMs     │
│  • Sigstore keyless signing (no keys to manage)     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  GitHub Release Published                           │
│                                                     │
│  • Release page with changelog                      │
│  • Binary archives per OS/arch                      │
│  • checksums.txt + .sigstore.json bundles           │
│  • SBOMs (archive + source)                         │
└─────────────────────────────────────────────────────┘
```

### How to Trigger a Release

**Via the GitHub Actions UI:**

1. Navigate to the repository's **Actions** tab.
2. Select the release workflow (e.g., `Release`).
3. Click **Run workflow**.
4. Enter the tag (e.g., `v1.2.3`) and click **Run workflow**.

**Via the `gh` CLI:**

```bash
gh workflow run release.yml \
  --repo <org>/<repo> \
  -f tag=v1.2.3
```

The preflight validates the tag and creates it automatically. There is no need to create or push the tag manually.

### Preflight Validation

The preflight runs automatically as the first phase and performs these checks:

| Check | What it does | On failure |
|-------|-------------|------------|
| Tag format | Validates strict semver (`vX.Y.Z`) | Rejects with expected pattern |
| Tag uniqueness | Re-run safe (tag at HEAD) vs. conflict | Fails if tag at different commit |
| Semver ordering | New version > latest existing tag | Fails if version goes backwards |
| CI gates | Auto-discovers from workflow files | Fails if checks not passed on HEAD |
| Security scan | At least one scan passed on HEAD | Fails if no scan passed |
| Unreleased commits | Counts commits since last tag | Fails if nothing to release |
| Tag creation | Annotated tag on HEAD, pushed to remote | Skipped on re-runs |

CI check discovery reads workflow files from the repository checkout. Repos that use non-standard test workflow names can provide an explicit `ci_checks` input override (JSON array of check names) instead of relying on auto-discovery. See the [adoption guide](https://github.com/complytime/org-infra/blob/main/docs/RELEASE_WORKFLOWS.md) for details on the three-file discovery convention.

## Supply Chain Expectations

Every release produces supply chain artifacts that allow consumers to verify the integrity and provenance of downloaded binaries.

| Artifact | Format | Description |
|----------|--------|-------------|
| `checksums.txt` | SHA-256 digests | Covers all binary archives in the release |
| `checksums.txt.sigstore.json` | Sigstore bundle | Cosign keyless signature over checksums |
| `<archive>.sbom.json` | SPDX JSON | SBOM for each binary archive (via syft) |
| `<repo>-<version>-source.sbom.json` | SPDX JSON | SBOM for the source tree |

Cosign signatures use Sigstore keyless signing backed by GitHub Actions OIDC. No private keys are managed or rotated. The signing identity is the GitHub Actions workflow that produced the release.

### Verifying Signatures

After downloading release artifacts, verify the cosign signature over the checksums file:

```bash
cosign verify-blob \
  --signature checksums.txt.sig \
  --certificate checksums.txt.pem \
  checksums.txt \
  --certificate-identity-regexp="https://github.com/<org>/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

Replace `<org>` with the GitHub organization (e.g., `complytime` or `unbound-force`). The `--signature` and `--certificate` flags match the separate `.sig`/`.pem` files produced by the GoReleaser `signs:` configuration (see [GoReleaser Configuration Standards](RELEASE_WORKFLOWS.md#goreleaser-configuration-standards)). A successful verification confirms the checksums file was produced by a GitHub Actions workflow in the expected organization.

### Verifying Checksums

After verifying the signature, validate downloaded binaries against the checksums:

```bash
sha256sum --check checksums.txt
```

### Inspecting SBOMs

SBOMs list the dependencies included in each binary archive:

```bash
cat <artifact>.sbom.json | jq '.artifacts | length'
```

For a detailed view of included packages:

```bash
cat <artifact>.sbom.json | jq '.artifacts[] | .name + "@" + .version'
```

## Release Verification

After a release completes, verify the following:

- [ ] **GitHub Release page exists** with the correct tag and changelog.
- [ ] **All expected artifacts are attached**: binary archives, checksums, `.sigstore.json` bundle, and SBOMs.
- [ ] **Checksums match**: download at least one archive and verify with `sha256sum --check checksums.txt`.
- [ ] **Cosign signature is valid**: run `cosign verify-blob` as described above.
- [ ] **SBOMs are complete**: inspect at least one SBOM and confirm it lists the expected dependency count.
- [ ] **Binary runs**: download the binary for your platform and run `<binary> --version` to confirm the version string matches the tag.

## Failure Recovery

### GoReleaser Fails After Tag Creation

The preflight creates the tag before GoReleaser runs. If GoReleaser fails (compilation error, network timeout, runner issue), the tag already exists on the remote.

**Recovery:** Re-trigger the workflow with the same tag. The preflight detects the existing tag at HEAD and skips validation steps that are unnecessary on re-run (semver ordering, unreleased commits, tag creation). The build phase runs again from scratch.

```bash
# Re-trigger with the same tag
gh workflow run release.yml \
  --repo <org>/<repo> \
  -f tag=v1.2.3
```

### Preflight Validation Fails

Common preflight failures and their fixes:

| Failure | Cause | Fix |
|---------|-------|-----|
| Tag format invalid | Missing `v` prefix or incomplete version | Use correct format: `v1.2.3` |
| CI checks not passed | Tests or linters failed on HEAD | Fix checks, wait for CI, re-trigger |
| Security scan not passed | Scan failed or did not run | Address findings, re-trigger |
| Semver ordering violation | Version lower than latest tag | Use a higher version number |
| No unreleased commits | HEAD same as latest tag | Merge new commits, then release |

After fixing the issue, re-trigger the workflow with the same tag input.

### Partial Release Cleanup

In rare cases, a partial release may need manual cleanup:

1. **Delete the draft GitHub Release** (if one was created):

   ```bash
   gh release delete v1.2.3 \
     --repo <org>/<repo> \
     --yes
   ```

2. **Delete the tag** (only if the release must be abandoned entirely):

   ```bash
   git push --delete origin v1.2.3
   ```

   > **Warning:** Deleting a tag that consumers may have already fetched can cause confusion. Prefer re-running the workflow over deleting tags.

3. **Re-trigger** the workflow with the same tag to produce a clean release.

## Release Cadence

Release cadence is repository-dependent and agreed upon by project maintainers. There is no organization-wide fixed schedule.

When deciding on a cadence, consider:

- **User-facing projects** (e.g., CLI tools) benefit from predictable release intervals (e.g., every 2-4 weeks) so users can plan upgrades.
- **Library projects** (e.g., SDKs) may release on-demand when breaking changes or significant features are merged.
- **Infrastructure projects** (e.g., reusable workflows) release when the change set is stable and ready for consumption.

Maintainers should discuss and agree on the cadence for their project. The automation supports any cadence — from daily snapshots to quarterly releases. The cost of cutting a release is a single workflow dispatch.

## Pre-Release and Release Candidates

The standard release flow supports pre-release versions when the consumer workflow enables the `allow_prerelease` input on the preflight.

### Enabling Pre-Release Tags

In the consumer release workflow, pass `allow_prerelease: true` to the preflight:

```yaml
jobs:
  preflight:
    uses: complytime/org-infra/.github/workflows/reusable_release_preflight.yml@v1
    with:
      tag: ${{ inputs.tag }}
      allow_prerelease: true
```

With `allow_prerelease: true`, the preflight accepts tags with pre-release suffixes (e.g., `v1.0.0-alpha.1`, `v1.0.0-beta.0`, `v1.0.0-rc.1`) in addition to strict semver tags.

### Expected Version Progression

Pre-release versions follow the semver 2.0.0 specification for precedence. A typical progression:

```text
v1.0.0-alpha.0      earliest pre-release
v1.0.0-alpha.1      ↓
v1.0.0-alpha.beta   ↓  (alphanumeric > numeric identifiers)
v1.0.0-beta.0       ↓
v1.0.0-beta.2       ↓
v1.0.0-beta.11      ↓  (numeric identifiers compared as integers)
v1.0.0-rc.1         ↓
v1.0.0              GA release (higher precedence than any pre-release)
```

The preflight verifies semver ordering automatically. Pre-release versions have lower precedence than the associated GA release (e.g., `v1.0.0-rc.1 < v1.0.0`). Attempting to release `v1.0.0-rc.1` after `v1.0.0` has been released will fail the ordering check.

### Pre-Release in GoReleaser

GoReleaser automatically detects pre-release tags and marks the GitHub Release as a pre-release. No additional GoReleaser configuration is needed. The release page will show the pre-release badge, and the `latest` GitHub Release pointer will remain on the most recent GA release.

## Roles and Responsibilities

| Role | Responsibility | Permissions |
|------|---------------|-------------|
| Project maintainer | Triggers releases | `contents: write`, `checks: read` |
| Project maintainer | Verifies release artifacts | Repository read access |
| Org-infra maintainer | Maintains reusable workflows | Write access to org-infra |

Release triggering is restricted to project maintainers who have write access to the repository. The workflows require the following GitHub Actions permissions, declared at the job level:

- **Preflight**: `contents: write` (tag creation), `checks: read` (verify CI)
- **GoReleaser**: `contents: write` (GitHub Release), `id-token: write` (Sigstore OIDC for keyless signing)

## Extension Points

This document covers the standard release flow common to all repositories. Individual repositories extend it with repo-specific procedures documented in their own `docs/RELEASE_PROCESS.md`.

### Common Extensions

| Extension | Applicable repos | Description |
|-----------|-----------------|-------------|
| Fedora packaging | Go CLI tools | Packit automation for RPM builds, Koji, and Bodhi updates |
| Container promotion | Container services | Promote images from GHCR to Quay.io after release |
| Homebrew tap | CLI tools | Update the Homebrew formula in the tap repository |
| RPM packaging | Go CLI tools | Build and publish RPM packages to Copr or Fedora |
| Registry mirroring | OCI artifacts | Mirror artifacts to secondary registries |

### Structuring a Repo-Level Release Process

Each repository that has repo-specific release procedures should create a `docs/RELEASE_PROCESS.md` that references this org-wide document and adds its own sections. Use the following template:

```markdown
# Release Process for <repo-name>

This document extends the [org-wide release process](https://github.com/complytime/org-infra/blob/main/docs/RELEASE_PROCESS.md).

## Standard Release

Follow the [standard release flow](https://github.com/complytime/org-infra/blob/main/docs/RELEASE_PROCESS.md#standard-release-flow)
to trigger a release via `workflow_dispatch`.

## Repo-Specific Procedures

### <procedure name>

<steps specific to this repository>
```

The org-wide document is the canonical reference for the standard flow. Repo-level documents should not duplicate the standard content — link to it and add only what is specific to that repository.

## Related

- [Release Workflows Adoption Guide](https://github.com/complytime/org-infra/blob/main/docs/RELEASE_WORKFLOWS.md) — How to set up the reusable release workflows in your repository (one-time migration).
- [reusable_release_preflight.yml](https://github.com/complytime/org-infra/blob/main/.github/workflows/reusable_release_preflight.yml) — Reusable preflight validation workflow.
- [reusable_release_goreleaser.yml](https://github.com/complytime/org-infra/blob/main/.github/workflows/reusable_release_goreleaser.yml) — Reusable GoReleaser execution workflow.
