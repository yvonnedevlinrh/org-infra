# Complypack Publish Pipeline

This document describes how ampel branch-protection policies are published as
[complypack](https://github.com/complytime/complypack) OCI artifacts, the
dual-registry strategy, and how to cut a release.

## Overview

The ampel branch-protection granular policies (JSON files in
`compliance/ampel/branch-protection/`) are packaged as complypack OCI artifacts
and published to container registries. Downstream consumers (e.g., `complyctl`)
pull these artifacts via the `complypacks:` section in their `complytime.yaml`.

```text
┌──────────────────────────────┐
│  compliance/ampel/           │
│    branch-protection/        │
│      block-force-push.json   │
│      minimum-approvals.json  │     complypack pack
│      prevent-admin-bypass.json ──────────────────┐
│      require-code-owner-     │                   │
│        review.json           │                   ▼
│      require-pull-request.json  ┌─────────────────────────────┐
│                              │  │  OCI Artifact               │
└──────────────────────────────┘  │  artifactType:              │
                                  │    application/vnd.          │
                                  │    complypack.artifact.v1    │
                                  │  config: id, evaluator-id,  │
                                  │          version             │
                                  │  content: tar+gzip of       │
                                  │           policy JSON files  │
                                  └─────────────────────────────┘
```

## Dual-Registry Strategy

| Registry | Purpose | Tag format | Trigger |
|----------|---------|------------|---------|
| `ghcr.io/complytime/complypack-ampel-branch-protection` | Dev / test | `sha-<commit>` | Push to `main` (policy file changes) |
| `quay.io/complytime/complypack-ampel-branch-protection` | Production | `vX.Y.Z` (semver) | GitHub Release published |
| `quay.io/complytime/complypack-ampel-branch-protection` | Production | `vX.Y.Z` (semver) | `workflow_dispatch` (manual promotion) |

GHCR is the staging area. Every push to `main` that modifies files under
`compliance/ampel/branch-protection/` triggers a publish to GHCR with a
commit-based tag. The artifact is signed with Sigstore keyless signing and
includes SLSA provenance and SBOM attestations.

Quay is the production registry. The current procedure promotes from GHCR to Quay through
two paths: automatically when a GitHub Release is published, or manually via
`workflow_dispatch`. Manual promotion exists because GitHub Actions does not
trigger downstream workflows from release events created by `GITHUB_TOKEN`-based
workflows — see [Manual Quay Promotion](#manual-quay-promotion) for details.

> **Note:** this limitation will be addressed in a follow-up PR by using an APP Token.

```text
Push to main              Release published         workflow_dispatch
     │                          │                   (promote_quay=true)
     ▼                          │                         │
 publish-ghcr                   ▼                         ▼
     │                    verify-ghcr-source       verify-ghcr-source
     ▼                          │                         │
 sign-ghcr                      ▼                         ▼
     │                     promote-quay              promote-quay
     ▼                          │                         │
 ghcr.io/complytime/            ▼                         ▼
   complypack-ampel-      quay.io/complytime/       quay.io/complytime/
   branch-protection:       complypack-ampel-         complypack-ampel-
   sha-abc123               branch-protection:        branch-protection:
                            v1.0.0                    v0.5.0
```

## Workflows

### `reusable_publish_complypack.yml`

Reusable workflow that packs and pushes complypack OCI artifacts to GHCR.
Designed to be consumed by any repository that needs to publish complypacks
for any evaluator.

**Key inputs:**

| Input | Required | Description |
|-------|----------|-------------|
| `content_path` | yes | Directory containing policy files |
| `image_name` | yes | Image name without registry |
| `tag` | yes | Image tag |
| `evaluator_id` | yes | Evaluator ID (e.g., `ampel`, `opa`) |
| `complypack_id` | yes | Globally unique pack identifier |
| `complypack_version` | yes | Version to embed in config |
| `go_version` | no | Go version for CLI install (default: `stable`) |
| `complypack_cli_ref` | no | CLI install ref (default: `latest`) |
| `generate_attestations` | no | `auto` or `true` (default: `auto`) |

### `ci_publish_complypack.yml`

Consumer workflow specific to org-infra's ampel branch-protection policies.

**Triggers:**

- `push` to `main` with changes in `compliance/ampel/branch-protection/**`
- `release` published (any semver tag)
- `workflow_dispatch` with the following inputs:

| Input | Required | Description |
|-------|----------|-------------|
| `tag_override` | no | Custom GHCR tag (leave empty for default `sha-<commit>`) |
| `promote_quay` | no | Set `true` to skip GHCR publish and promote an existing GHCR artifact to Quay |
| `release_tag` | when `promote_quay=true` | Quay destination tag (e.g., `v0.5.0`) |
| `source_sha` | no | Source commit SHA to promote (defaults to current HEAD) |

## Cutting a Release

### Prerequisites

- Quay credentials (`QUAY_USERNAME`, `QUAY_PASSWORD`) must be configured as
  repository secrets in org-infra.
- The policy changes you want to release must already be merged to `main`
  (the GHCR artifact must exist for the tagged commit).

### Steps

1. **Verify the GHCR artifact exists** for the commit you want to release:

   ```bash
   # Check the publish workflow ran for the target commit
   gh run list \
     --repo complytime/org-infra \
     --workflow ci_publish_complypack.yml \
     --limit 5
   ```

2. **Create a GitHub Release** with a semver tag:

   ```bash
   gh release create v1.0.0 \
     --repo complytime/org-infra \
     --title "v1.0.0" \
     --notes "Publish ampel branch-protection complypack v1.0.0"
   ```

3. **Monitor the promotion** workflow:

   ```bash
   gh run watch \
     --repo complytime/org-infra
   ```

   The workflow will:
   - Verify the GHCR artifact exists at `sha-<tagged-commit>`
   - Promote it to `quay.io/complytime/complypack-ampel-branch-protection:v1.0.0`
   - Verify source signatures before copying

4. **Verify the Quay artifact**:

   ```bash
   # Using crane (or oras)
   crane manifest \
     quay.io/complytime/complypack-ampel-branch-protection:v1.0.0
   ```

### Troubleshooting

**Promotion fails with "No GHCR image found":**

The GHCR artifact for the tagged commit does not exist. This happens when:
- The policy files were not changed in the tagged commit (push trigger did
  not fire).
- The publish workflow failed on a previous push.

Fix: trigger a manual publish via `workflow_dispatch`, then re-run the release
workflow.

**Promotion fails with "destination tag already exists":**

Quay tags are immutable. You cannot overwrite an existing release. If you need
to republish, use a new version tag (e.g., `v1.0.1`).

## Manual Quay Promotion

### Why manual promotion exists

GitHub Actions has a known limitation: release events created by workflows
that authenticate with `GITHUB_TOKEN` do not trigger other workflows. This
means that if your release is cut by an automated workflow (or by any process
using `GITHUB_TOKEN`), the `release: published` trigger in
`ci_publish_complypack.yml` will not fire and the Quay promotion will not
happen.

Manual promotion via `workflow_dispatch` bypasses this limitation by letting
you promote an existing GHCR artifact to Quay without relying on the release
event trigger.

### Steps

1. **Identify the source commit** whose GHCR artifact you want to promote:

   ```bash
   # Find the commit SHA for the GHCR artifact you want to promote
   gh run list \
     --repo complytime/org-infra \
     --workflow ci_publish_complypack.yml \
     --limit 5
   ```

2. **Trigger the manual promotion**:

   ```bash
   gh workflow run ci_publish_complypack.yml \
     --repo complytime/org-infra \
     -f promote_quay=true \
     -f release_tag=v0.5.0 \
     -f source_sha=abc123def456
   ```

   Replace `v0.5.0` with the desired semver tag and `abc123def456` with the
   full commit SHA. If `source_sha` is omitted, the workflow uses the current
   HEAD of the default branch.

3. **Monitor the promotion**:

   ```bash
   gh run watch --repo complytime/org-infra
   ```

4. **Verify the Quay artifact**:

   ```bash
   crane manifest \
     quay.io/complytime/complypack-ampel-branch-protection:v0.5.0
   ```

### When to use manual promotion

- **Automated releases**: When a CI workflow creates the GitHub Release using
  `GITHUB_TOKEN`, the promotion workflow will not trigger automatically.
- **Retroactive promotion**: When you need to promote a specific older commit
  that already has a signed GHCR artifact.
- **Re-promotion after failure**: When the release-triggered promotion failed
  and you need to retry without creating a new release (use a new version tag
  since Quay tags are immutable).

## Local Testing

### Prerequisites

```bash
# Install the complypack CLI
go install github.com/complytime/complypack/cmd/complypack@latest

# Verify
complypack --help
```

### Pack locally (no push)

```bash
# Create a workspace
WORK=$(mktemp -d)
cp compliance/ampel/branch-protection/*.json "$WORK/"

# Generate config at workspace root (where the CLI expects it)
cat > complypack.yaml <<EOF
id: io.complytime.ampel-branch-protection
evaluator-id: ampel
version: 0.1.0-test
EOF

# Pack (--skip-validation required for non-OPA evaluators)
complypack pack --skip-validation "$WORK" \
  "ghcr.io/<your-username>/complypack-ampel-branch-protection:test"

# Cleanup
rm -f complypack.yaml
rm -rf "$WORK"
```

**Notes:**

- The `complypack.yaml` config must be at the **current working directory**,
  not inside the content directory. The CLI reads `./complypack.yaml` by
  default (override with `--config`).
- `--skip-validation` is required because `ampel` is not a registered
  evaluator in complypack (only OPA/Rego is built-in). The policy JSON files
  are packed as opaque content and consumed by the ampel provider.
- Pushing to GHCR requires authentication with `write:packages` scope. In CI,
  this is handled by `docker/login-action` with `GITHUB_TOKEN`.

## Consumer Configuration

Downstream repositories pull the complypack artifact in their
`complytime.yaml`:

```yaml
complypacks:
  - url: quay.io/complytime/complypack-ampel-branch-protection:v1.0.0
    id: ampel-bp-pack
```

The `complyctl get` command resolves the OCI reference, pulls the artifact,
and extracts the policy files for the compliance scan.

### Digest pinning

For production use, pin to a digest instead of a mutable tag. Digests are
immutable and ensure that every consumer pulls the exact same artifact.

1. **Get the digest** after Quay promotion:

   ```bash
   crane digest \
     quay.io/complytime/complypack-ampel-branch-protection:v1.0.0
   # Output: sha256:abc123...
   ```

2. **Pin to the digest** in `complytime.yaml`:

   ```yaml
   complypacks:
     - url: quay.io/complytime/complypack-ampel-branch-protection@sha256:abc123...
       id: ampel-bp-pack
   ```

Tag-based pins (e.g., `:v1.0.0`) are acceptable for development because Quay
tags are immutable in this pipeline (`fail_if_dest_exists: true`). Digest pins
provide an additional guarantee that the reference cannot be altered by
registry-side tag mutations.

### Updating dependent repositories after a release

After promoting a new version to Quay:

1. Retrieve the digest for the new tag (see above).
2. Update the `complypacks` entry in each dependent repository's
   `.complytime/complytime.yaml` to reference the new version or digest.
3. Open a PR in each dependent repository with the updated pin.

## Related

- [Issue #306](https://github.com/complytime/org-infra/issues/306) —
  Original issue for this feature.
- [Issue #307](https://github.com/complytime/org-infra/issues/307) —
  Remove TEMPORARY manual staging from `reusable_compliance.yml`
  (depends on downstream provider adoption of this complypack).
- [complypack](https://github.com/complytime/complypack) —
  The complypack library and CLI.
- [complyctl#536](https://github.com/complytime/complyctl/pull/536) —
  complyctl `complypack-pull` feature that consumes these artifacts.
