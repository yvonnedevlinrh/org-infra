# Go Toolchain Patch Automation

Automated Go version patch updates via Renovate, running as a
centralized workflow in org-infra. Creates PRs to bump Go version
directives (`go` and `toolchain`) in `go.mod` when newer patch
versions are available.

## Overview

```text
┌─────────────────────────────────────────────────────────────┐
│  org-infra                                                  │
│  ├── .github/workflows/ci_renovate.yml  (daily cron)        │
│  ├── go-toolchain-patches.json          (shared preset)     │
│  └── renovate-config.js                 (global config)     │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────┐                            │
│  │ complytime-renovate[bot]    │                            │
│  │ permissions:                │                            │
│  │   contents: write           │                            │
│  │   pull-requests: write      │                            │
│  └─────────────┬───────────────┘                            │
│                │                                            │
│      ┌─────────┼─────────┬──────────────┐                   │
│      ▼         ▼         ▼              ▼                   │
│  complyctl  complytime  complytime-  complytime-collector-  │
│                         providers    components             │
│                                                             │
│  Result: PR per repo with Go version patch bump              │
│  Example: chore(deps): update dependency go to v1.25.11     │
└─────────────────────────────────────────────────────────────┘
```

Dependabot manages Go module dependencies but does not support the
`toolchain` directive
([dependabot-core#13520](https://github.com/dependabot/dependabot-core/issues/13520)).
Renovate fills this gap, scoped to Go version patch updates only.

## Configuration

### Files

| File | Purpose |
|------|---------|
| `ci_renovate.yml` | Workflow: daily schedule + manual dispatch with dry-run |
| `go-toolchain-patches.json` | Preset: three-rule pattern restricting to Go version patches |
| `renovate-config.js` | Global config: target repos, `globalExtends`, `onboarding: false` |

### Preset rules (`go-toolchain-patches.json`)

The preset uses three package rules to achieve patch-only filtering:

1. **Disable all gomod deps** -- prevents Renovate from touching
   module dependencies (Dependabot's responsibility)
2. **Re-enable Go version deps** -- with `separateMinorPatch: true`
   so Renovate generates separate entries for patch vs minor updates
3. **Suppress minor/major** -- disables non-patch Go version updates
   after version lookup

This three-rule pattern is required because `matchUpdateTypes`
needs a version lookup to determine the update type, but lookups
only run for enabled deps.

### Adding a new Go repository

1. Add the repo to the `repositories` array in `renovate-config.js`
2. Install `complytime-renovate[bot]` on the repo (GitHub settings)
3. The next daily run (or manual dispatch) will scan the new repo

### Secrets

| Secret | Location | Purpose |
|--------|----------|---------|
| `RENOVATE_APP_CLIENT_ID` | org-infra repo secrets | GitHub App client ID |
| `RENOVATE_APP_PRIVATE_KEY` | org-infra repo secrets | GitHub App private key |

## Manual dispatch

Trigger via GitHub Actions UI or CLI:

```bash
# Dry-run (no PRs created)
gh workflow run ci_renovate.yml -f dry_run=full

# Normal operation
gh workflow run ci_renovate.yml -f dry_run=none
```

## Local testing

Validate the preset config:

```bash
npx --yes --package renovate renovate-config-validator go-toolchain-patches.json
```

Run a dry-run against a real repo (no PRs or branches created):

```bash
export RENOVATE_TOKEN=$(gh auth token)

RENOVATE_DRY_RUN=full \
RENOVATE_ONBOARDING=false \
RENOVATE_REQUIRE_CONFIG=optional \
RENOVATE_ENABLED_MANAGERS='["gomod"]' \
RENOVATE_DEPENDENCY_DASHBOARD=false \
RENOVATE_POST_UPDATE_OPTIONS='["gomodTidy","gomodVendor"]' \
RENOVATE_REPORT_TYPE=file \
RENOVATE_REPORT_PATH=/tmp/renovate-report.json \
RENOVATE_PACKAGE_RULES='[{"matchManagers":["gomod"],"enabled":false},{"matchManagers":["gomod"],"matchDepNames":["go"],"enabled":true,"separateMinorPatch":true,"automerge":false,"labels":["dependencies"]},{"matchManagers":["gomod"],"matchDepNames":["go"],"matchUpdateTypes":["minor","major"],"enabled":false}]' \
npx --yes --package renovate renovate \
  --platform=github \
  --token="$RENOVATE_TOKEN" \
  complytime/complyctl
```

Inspect the report:

```bash
python3 -c "
import json
with open('/tmp/renovate-report.json') as f:
    r = json.load(f)
for repo, data in r['repositories'].items():
    print(f'\n{repo}:')
    if not data['branches']:
        print('  No updates')
    for b in data['branches']:
        for u in b['upgrades']:
            print(f'  {u[\"currentValue\"]} -> {u[\"newValue\"]} ({u[\"updateType\"]})')
            print(f'  Branch: {b[\"branchName\"]}')
            print(f'  PR title: {b[\"prTitle\"]}')
"
```

## Troubleshooting

### No updates proposed

Check whether the repo is already on the latest patch:

```bash
gh api repos/complytime/<repo>/contents/go.mod --jq '.content' \
  | base64 -d | grep -E "^(go |toolchain )"
curl -s 'https://go.dev/dl/?mode=json' \
  | python3 -c "import json,sys; [print(r['version']) for r in json.load(sys.stdin) if r['version'].startswith('go1.25')]"
```

If the versions match, there is nothing to update.

### Renovate creates an onboarding PR

The global config must set `onboarding: false` and
`requireConfig: 'optional'`. Verify these values in
`renovate-config.js`.

### CI does not trigger on Renovate PRs

Ensure the GitHub App is installed on the target repo. PRs created
with the App token trigger CI; PRs from `GITHUB_TOKEN` do not.

### Workflow fails at token generation

Check that `RENOVATE_APP_CLIENT_ID` and `RENOVATE_APP_PRIVATE_KEY`
are set in org-infra repo secrets and that the App installation has
not been revoked.

### Run report

Each workflow run uploads a `renovate-report` artifact (JSON, 30-day
retention). Download from the GitHub Actions run page to inspect
which repos were scanned, what updates were found, and what actions
were taken.

### Merge conflicts with Dependabot PRs

Renovate runs `go mod tidy` and `go mod vendor` after bumping the
Go version (`postUpdateOptions` in the preset). This
regenerates `go.sum` and vendor contents. If a Dependabot PR
modifying the same `go.sum` is open concurrently, the second PR to
merge will encounter a merge conflict.

Resolution options:

- **Rebase the conflicting PR** manually or via the GitHub UI
  "Update branch" button.
- **Merge the smaller PR first** -- Renovate Go version patches are
  typically one-line `go.mod` changes and resolve cleanly after
  rebase.

This is a timing issue, not a functional conflict. Dependabot manages
module dependencies; Renovate manages Go version directives. They do
not overlap in scope.

## Further reading

- [Renovate gomod manager](https://docs.renovatebot.com/modules/manager/gomod/)
- [Renovate self-hosted configuration](https://docs.renovatebot.com/self-hosted-configuration/)
- [Renovate package rules](https://docs.renovatebot.com/configuration-options/#packagerules)
- [renovatebot/github-action](https://github.com/renovatebot/github-action)
