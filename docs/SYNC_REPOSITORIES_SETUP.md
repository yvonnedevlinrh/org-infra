# Repository Sync Setup Guide

This guide explains how to set up and use the automated repository synchronization workflow that maintains consistent standards across all organization repositories.

## Overview

The sync workflow uses a **fork-based approach** with **GitHub App authentication**:

1. **Forks** target repositories to the GitHub App's account
2. **Makes changes** in the fork
3. **Creates PRs** from fork to upstream repository
4. **No write access** required to target repositories

This approach follows GitHub's security best practices and only requires read access to target repositories.

## Architecture

```
┌─────────────────┐
│   org-infra     │  (Source of truth for standards)
└────────┬────────┘
         │
         v
┌─────────────────┐
│ GitHub App      │  (Authenticated as bot)
│ + Token         │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Peribolos.yml  │  (List of repos to sync)
│  in .github     │
└────────┬────────┘
         │
         v
┌─────────────────────────────────────┐
│  For each repository:               │
│  1. Fork repo (if not exists)       │
│  2. Clone fork                      │
│  3. Sync with upstream              │
│  4. Apply changes                   │
│  5. Push to fork                    │
│  6. Create PR: fork -> upstream     │
└─────────────────────────────────────┘
```

## Prerequisites

- Organization admin access
- Ability to create GitHub Apps
- Ability to manage organization secrets

## Step 1: Create GitHub App

### 1.1 Create the App

1. Go to your organization settings: `https://github.com/organizations/complytime/settings/apps`
2. Click **"New GitHub App"**
3. Configure the app:

   **Basic Information:**
   - **GitHub App name:** `complytime-sync-bot`
   - **Homepage URL:** `https://github.com/complytime/org-infra`
   - **Webhook:** Uncheck "Active" (not needed)

   **Repository Permissions:**
   - **Contents:** Read-only (to read target repos)
   - **Pull requests:** Read and write (to create PRs)
   - **Metadata:** Read-only (required by default)

   **Organization Permissions:**
   - None required

   **Where can this GitHub App be installed?**
   - Select **"Only on this account"**

4. Click **"Create GitHub App"**

### 1.2 Generate Private Key

1. After creating the app, scroll to **"Private keys"** section
2. Click **"Generate a private key"**
3. Save the downloaded `.pem` file securely
4. Note the **App ID** (shown at the top of the page)

### 1.3 Install the App

1. Go to **"Install App"** in the left sidebar
2. Click **"Install"** next to your organization
3. Choose **"All repositories"**
4. Click **"Install"**

## Step 2: Configure Secrets

### 2.1 Add App Credentials to Org-Infra Repository

1. Go to `https://github.com/complytime/org-infra/settings/secrets/actions`
2. Add two new repository secrets:

   **Secret 1: `SYNC_APP_CLIENT_ID`**
   - Value: Your GitHub App Client ID (e.g., `123456`)

   **Secret 2: `SYNC_APP_PRIVATE_KEY`**
   - Value: Contents of the `.pem` file you downloaded
   - Copy the entire file including:
     ```
     -----BEGIN RSA PRIVATE KEY-----
     ...
     -----END RSA PRIVATE KEY-----
     ```

## Step 3: Configure Sync Settings

### 3.1 Update `sync-config.yml`

Edit `/sync-config.yml` to specify which files should be synced:

```yaml
# Repositories to exclude from synchronization
exclude_repos:
  - .github       # Organization config repository
  - org-infra     # This repository itself

# Files and workflows to synchronize
files_to_sync:
  # GitHub Workflows
  - source: .github/workflows/ci_checks.yml
    destination: .github/workflows/ci_checks.yml
  
  # Configuration Files
  - source: .github/dependabot.yml
    destination: .github/dependabot.yml
  
  # Exclude specific repos for certain files
  - source: ruff.toml
    destination: ruff.toml
    exclude_repos:
      - non-python-repo
```

### 3.2 Verify peribolos.yaml

Ensure your `.github` repository contains `peribolos.yaml` with repository definitions:

```yaml
orgs:
  your-org:
    repos:
      repo-1:
        default_branch: main
      repo-2:
        default_branch: main
```

## Step 4: Test the Workflow

### 4.1 Dry Run

Test without making changes:

1. Go to **Actions** tab in org-infra repository
2. Select **"Sync Organization Repositories"** workflow
3. Click **"Run workflow"**
4. Configure:
   - **Dry run:** ✅ Checked
   - **Repositories:** Leave empty (or specify one repo for testing)
5. Click **"Run workflow"**
6. Review the output to see what would be changed

### 4.2 Test on Single Repository

Test on one repository first:

1. Run workflow manually
2. Configure:
   - **Dry run:** ❌ Unchecked
   - **Repositories:** `your-test-repo`
3. Click **"Run workflow"**
4. Verify:
   - Fork was created under the GitHub App account
   - PR was created in the target repository
   - Changes look correct

## Step 5: Enable Automated Sync

Once testing is successful, the workflow will run automatically:

- **On push to main:** When standards files are updated
- **Weekly schedule:** Every Monday at 00:00 UTC
- **Manual trigger:** Anytime via workflow_dispatch

## Troubleshooting

### Authentication Errors

**Error:** `Failed to get authenticated user`

**Solution:**
- Verify `SYNC_APP_CLIENT_ID` and `SYNC_APP_PRIVATE_KEY` are correctly set
- Check that the app is installed on your organization
- Ensure the private key format is correct (including header/footer)

### Permission Errors

**Error:** `Failed to create fork (HTTP 403)`

**Solution:**
- Verify the GitHub App has "Contents: Read" permission
- Verify the GitHub App has "Pull requests: Read and write" permission
- Reinstall the app if permissions were changed

### Fork Sync Issues

**Error:** `Could not sync with upstream`

**Solution:**
- This is usually non-fatal; the workflow will continue
- Check if the default branch name is correct (e.g.: main vs master)
- Verify the fork exists and is accessible

### Rate Limiting

**Error:** `API rate limit exceeded`

**Solution:**
- GitHub Apps have higher rate limits (5000 req/hour)
- Reduce the number of repositories processed concurrently
- Consider refactoring to reduce API calls
- Add delays between API calls if needed

## Security Considerations

1. **Private Key Security:**
   - Never commit the `.pem` file to git
   - Store only in GitHub Secrets
   - Rotate periodically

2. **Least Privilege:**
   - The app only has read access to repository contents
   - Write access only to PRs (cannot force push)
   - Cannot modify repository settings

3. **Fork Management:**
   - Forks are created under the app's account
   - Forks can be deleted if no longer needed
   - Only the fork is modified, not the original repo

4. **Review Process:**
   - All changes require PR approval
   - Repository owners maintain control
   - Changes are transparent and auditable

## Maintenance

### Updating Synced Files

1. Update the file in `org-infra` repository
2. Commit to a branch and create PR
3. After merging to main, workflow will run automatically
4. PRs will be created in target repositories

### Adding New Repositories

1. Add repository to `peribolos.yaml` in `.github` repo
2. Next workflow run will include the new repository

### Removing Repositories

1. Add repository name to `exclude_repos` in `sync-config.yml`
2. Commit and push

### Cleaning Up Forks

Forks can be deleted manually from the GitHub App's account if no longer needed:

```bash
gh repo delete YOUR_APP_NAME/repo-name
```

## Advanced Configuration

### Custom Commit Messages

Edit the script to customize commit messages:

```python
commit_message = "chore: sync repository standards\n\nUpdated files:\n"
```

### Custom PR Body

Edit the PR body template in the script:

```python
pr_body = """Custom PR description...
```

### Parallel Processing

To process multiple repositories concurrently, modify the main loop to use threading or asyncio.

## Support

For issues or questions:
- Open an issue in the `org-infra` repository
- Review workflow run logs in Actions tab
- Check GitHub App installation settings

## References

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [Creating GitHub App Tokens in Actions](https://github.com/actions/create-github-app-token)
- [Peribolos Documentation](https://docs.prow.k8s.io/docs/components/cli-tools/peribolos/)
