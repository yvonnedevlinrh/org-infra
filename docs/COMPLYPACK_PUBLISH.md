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
| `quay.io/complytime/complypack-ampel-branch-protection` | Production | `v1.0.0` (semver) | GitHub Release published |

GHCR is the staging area. Every push to `main` that modifies files under
`compliance/ampel/branch-protection/` triggers a publish to GHCR with a
commit-based tag. The artifact is signed with Sigstore keyless signing and
includes SLSA provenance and SBOM attestations.

Quay is the production registry. When a GitHub Release is published, the
workflow promotes the GHCR artifact to Quay using `cosign copy` with source
signature verification. Quay tags are immutable — publishing the same tag
twice fails.

```text
Push to main                        Release published
     │                                    │
     ▼                                    ▼
 publish-ghcr                     verify-ghcr-source
     │                                    │
     ▼                                    ▼
 sign-ghcr                         promote-quay
     │                                    │
     ▼                                    ▼
 ghcr.io/complytime/              quay.io/complytime/
   complypack-ampel-                complypack-ampel-
   branch-protection:               branch-protection:
   sha-abc123                       v1.0.0
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
- `workflow_dispatch` with optional `tag_override` input

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
  - quay.io/complytime/complypack-ampel-branch-protection:v1.0.0
```

The `complyctl get` command resolves the OCI reference, pulls the artifact,
and extracts the policy files for the compliance scan.

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
