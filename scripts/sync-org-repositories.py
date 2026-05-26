#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""
Script to synchronize standard files and workflows across all repositories
defined in peribolos.yml from the .github repository.

This script uses a direct-push workflow with GitHub App authentication:
1. Clones the target repository directly
2. Creates a feature branch
3. Copies synced files and generates dependabot config
4. Pushes branch and creates a PR against the default branch

Security guardrails:
- API endpoint allowlist restricts which GitHub API calls are permitted
- Branch name prefix enforcement (only sync-repo-standards-* branches)
- No force push allowed
- Branch protection on main prevents direct pushes (human review required)
"""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import yaml
import requests

from datetime import datetime
from git import GitCommandError
from git.repo import Repo
from pathlib import Path
from typing import Dict, List, Optional, Tuple


GITHUB_API = "https://api.github.com"

# YAML truthy values that must be quoted to avoid yamllint truthy rule violations
_YAML_TRUTHY_VALUES = frozenset({"true", "false", "yes", "no", "on", "off"})


class _IndentedListDumper(yaml.SafeDumper):
    """YAML dumper that indents list items under their parent key.

    PyYAML's default SafeDumper produces indentless sequences:
        updates:
        - package-ecosystem: ...

    This violates yamllint's ``indentation: spaces: consistent`` rule.
    Overriding ``increase_indent`` to never use indentless mode produces:
        updates:
          - package-ecosystem: ...
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    """Quote YAML truthy string values to prevent misinterpretation."""
    if data in _YAML_TRUTHY_VALUES:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_IndentedListDumper.add_representer(str, _str_representer)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", os.getenv("GITHUB_PAT"))
DEFAULT_CONFIG_FILE = "sync-config.yml"
SYNC_BRANCH_PREFIX = "sync-repo-standards-"
SYNC_PR_TITLE = "chore: sync repository standards"
SOURCE_REPO = "org-infra"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sync repository standards across organization repositories"
    )
    parser.add_argument(
        "--org",
        required=True,
        help="GitHub organization name",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to sync configuration file (default: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        help="Specific repositories to sync (default: all from peribolos.yml)",
    )
    parser.add_argument(
        "--release-ref",
        default=None,
        help=(
            "Release tag to use for workflow ref "
            "transformation (e.g., v0.3.0). Auto-detects "
            "latest release if not provided."
        ),
    )
    return parser.parse_args()


def load_sync_config(config_path: str) -> dict:
    """Load the sync configuration file."""
    script_dir = Path(__file__).parent.parent
    full_path = f"{script_dir}/{config_path}"
    with open(full_path, "r") as f:
        return yaml.safe_load(f)


def validate_github_api_request(endpoint: str, method: str) -> bool:
    """Validate that a GitHub API request is in the allowlist.

    Only permits the minimum set of endpoints needed for the sync workflow:
    - GET repo info (check repo exists)
    - GET/POST pull requests (check existing, create new)
    - GET file contents (read existing dependabot.yml)
    """
    allowed_patterns = [
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+$", "GET"),
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/pulls$", "GET"),
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/pulls$", "POST"),
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/contents/.+$", "GET"),
        # Release detection
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/releases/latest$", "GET"),
        # Tag-to-SHA resolution
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/git/ref/tags/.+$", "GET"),
        # Annotated tag dereferencing
        (r"^" + re.escape(GITHUB_API) + r"/repos/[^/]+/[^/]+/git/tags/[a-f0-9]+$", "GET"),
    ]
    return any(
        re.match(pattern, endpoint) and method == allowed_method
        for pattern, allowed_method in allowed_patterns
    )


def github_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Tuple[int, Dict]:
    """Make a GitHub API request using the requests library.

    Args:
        endpoint: Full API URL (e.g., "https://api.github.com/repos/org/repo")
        method: HTTP method (GET, POST, etc.)
        data: Optional JSON body to send
        params: Optional query parameters

    Returns:
        Tuple of (status_code, response_data)
    """
    if not validate_github_api_request(endpoint, method):
        print(f"Error: Endpoint {endpoint} with method {method} is not allowed")
        return 403, {"error": "Endpoint not allowed"}

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.request(
            method=method,
            url=endpoint,
            headers=headers,
            json=data,
            params=params,
            timeout=30,
        )
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw": response.text}
        return response.status_code, response_data
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return 500, {"error": str(e)}


def validate_branch_name(branch_name: str) -> bool:
    """Validate that a branch name uses the required sync prefix.

    This guardrail ensures the script never pushes to unexpected branches
    (e.g., main, develop, or arbitrary branch names).
    """
    return bool(branch_name) and branch_name.startswith(SYNC_BRANCH_PREFIX)


def check_existing_sync_pr(org: str, repo_name: str) -> Optional[Dict[str, str]]:
    """Check if an open sync PR already exists for the target repository.

    Args:
        org: GitHub organization name
        repo_name: Repository name

    Returns:
        A dict with ``url`` and ``branch`` keys if an open sync PR
        exists.  A dict with an ``error`` key if the API call failed
        (callers must treat this as "unknown" and avoid creating
        duplicates).  ``None`` when no matching PR was found.
    """
    url = f"{GITHUB_API}/repos/{org}/{repo_name}/pulls"
    status, data = github_api_request(url, method="GET", params={"state": "open", "per_page": 100})

    if status != 200:
        print(f"Warning: Could not check existing PRs (HTTP {status})")
        return {"error": f"API returned HTTP {status}"}

    if not isinstance(data, list):
        return {"error": "Unexpected API response format"}

    for pr in data:
        if pr.get("title") == SYNC_PR_TITLE:
            head = pr.get("head", {})
            return {
                "url": pr.get("html_url", ""),
                "branch": head.get("ref", ""),
            }

    return None


def fetch_peribolos_file(org: str) -> dict:
    """Fetch peribolos.yaml from the organization's .github repository."""
    peribolos_repo = ".github"
    github_repo_url = f"https://github.com/{org}/{peribolos_repo}.git"
    print(f"Fetching peribolos configuration from {github_repo_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            cmd = ["git", "clone", "--quiet", "--depth", "1", github_repo_url]
            subprocess.check_call(cmd, cwd=tmpdir)

            repo_path = os.path.join(tmpdir, peribolos_repo)
            peribolos_path = os.path.join(repo_path, "peribolos.yaml")
            if os.path.exists(peribolos_path):
                with open(peribolos_path, "r") as f:
                    return yaml.safe_load(f)
            print(f"Error: peribolos.yaml not found in {peribolos_repo} repository")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning {peribolos_repo} repository: {e}")
            sys.exit(1)


def extract_repositories(peribolos_data: dict, org: str) -> list:
    """Extract list of repositories from peribolos data."""
    repos: list = []

    if "orgs" in peribolos_data and org in peribolos_data["orgs"]:
        org_data = peribolos_data["orgs"][org]
        if "repos" in org_data:
            repos = list(org_data["repos"].keys())

    print(f"Found {len(repos)} repositories in peribolos configuration for {org}")
    return repos


def compare_files(source_file: str, dest_file: str) -> bool:
    """Compare two files and return True if they are identical."""
    if not os.path.exists(dest_file):
        return False
    return filecmp.cmp(source_file, dest_file, shallow=False)


def sync_file(source_path: str, dest_path: str, relative_path: str) -> bool:
    """Sync a file from source to destination.

    Returns True if file was copied/updated, False if identical.
    """
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if os.path.exists(dest_path):
        if compare_files(source_path, dest_path):
            print(f"{relative_path} is up to date")
            return False
        else:
            print(f"{relative_path} needs update")
    else:
        print(f"{relative_path} is missing")

    shutil.copy2(source_path, dest_path)
    return True


def resolve_file_vars(file_config: dict, repo_name: str) -> Dict[str, str]:
    """Resolve per-file variable values for a target repository.

    Each variable in the ``vars`` config has a ``default`` value and an
    optional ``repos`` map of per-repo overrides.  The resolved value is
    the repo-specific override when present, otherwise the default.

    Args:
        file_config: A single entry from ``files_to_sync`` in sync config.
        repo_name: Target repository name.

    Returns:
        Dict mapping variable names to their resolved string values.
        Empty dict when the file entry has no ``vars`` key.
    """
    vars_config = file_config.get("vars")
    if not vars_config:
        return {}

    resolved: Dict[str, str] = {}
    for var_name, var_def in vars_config.items():
        default_value = str(var_def.get("default", ""))
        repo_overrides = var_def.get("repos", {})
        resolved[var_name] = str(repo_overrides.get(repo_name, default_value))
    return resolved


def apply_file_vars(content: str, resolved_vars: Dict[str, str]) -> str:
    """Apply variable substitutions to file content via regex.

    For each variable, finds ``<var_name>: <value>`` in the content and
    replaces ``<value>`` with the resolved value.  All other content
    (comments, indentation, SHA references) is preserved.

    Args:
        content: The source file content as a string.
        resolved_vars: Dict of ``{var_name: resolved_value}`` pairs.

    Returns:
        The content with substitutions applied.
    """
    for var_name, resolved_value in resolved_vars.items():
        pattern = rf"({re.escape(var_name)}:\s*)\S+"
        new_content = re.sub(pattern, rf"\g<1>{resolved_value}", content)
        if new_content == content:
            print(f"Warning: var '{var_name}' not found in file content")
        content = new_content
    return content


def get_latest_release(
    org: str, repo_name: str,
) -> Tuple[str, str]:
    """Fetch the latest release tag and resolve it to a commit SHA.

    Queries the GitHub API for the latest published release, then
    resolves the tag to a full commit SHA.  Handles both lightweight
    tags (object.type == "commit") and annotated tags (object.type ==
    "tag") by dereferencing the tag object when needed.

    Args:
        org: GitHub organization name.
        repo_name: Repository name within the organization.

    Returns:
        Tuple of (tag_name, commit_sha).

    Raises:
        SystemExit: If no release is found or the tag cannot be
            resolved.
    """
    release_url = (
        f"{GITHUB_API}/repos/{org}/{repo_name}"
        f"/releases/latest"
    )
    status, data = github_api_request(release_url)
    if status != 200:
        print(
            f"No release found for {org}/{repo_name}. "
            f"Use --release-ref <tag> to specify a "
            f"release tag."
        )
        sys.exit(1)

    tag_name = data["tag_name"]

    ref_url = (
        f"{GITHUB_API}/repos/{org}/{repo_name}"
        f"/git/ref/tags/{tag_name}"
    )
    ref_status, ref_data = github_api_request(ref_url)
    if ref_status != 200:
        print(
            f"Error: Could not resolve tag '{tag_name}' "
            f"for {org}/{repo_name}."
        )
        sys.exit(1)

    obj = ref_data.get("object", {})
    if obj.get("type") == "tag":
        # Annotated tag — dereference to get the commit SHA
        tag_url = (
            f"{GITHUB_API}/repos/{org}/{repo_name}"
            f"/git/tags/{obj['sha']}"
        )
        tag_status, tag_data = github_api_request(tag_url)
        if tag_status != 200:
            print(
                f"Error: Could not dereference tag object "
                f"for {org}/{repo_name}."
            )
            sys.exit(1)
        commit_sha = tag_data.get("object", {}).get("sha", "")
    else:
        # Lightweight tag — SHA points directly to the commit
        commit_sha = obj.get("sha", "")

    return tag_name, commit_sha


def transform_workflow_refs(
    content: str,
    org: str,
    source_repo: str,
    sha: str,
    tag: str,
) -> str:
    """Replace local workflow path refs with SHA-pinned cross-repo refs.

    Finds ``uses: ./.github/workflows/reusable_<name>.yml`` patterns
    and replaces them with
    ``uses: <org>/<source_repo>/.github/workflows/reusable_<name>.yml@<sha>  # <tag>``.

    Only matches lines where the value starts with
    ``./.github/workflows/reusable_`` to avoid transforming
    non-reusable workflow references.

    Args:
        content: Workflow file content as a string.
        org: GitHub organization name (e.g., ``complytime``).
        source_repo: Source repository name (e.g., ``org-infra``).
        sha: Full 40-character commit SHA to pin to.
        tag: Release tag for the inline version comment.

    Returns:
        Content with local refs replaced by SHA-pinned cross-repo
        refs.

    Raises:
        ValueError: If ``sha`` is not a valid 40-character hex string.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError(f"Invalid SHA format: {sha!r}")

    pattern = (
        r"(uses:\s*)"
        r"\./\.github/workflows/(reusable_\S+\.yml)"
    )
    replacement = (
        rf"\g<1>{org}/{source_repo}/"
        rf".github/workflows/\g<2>@{sha} # {tag}"
    )
    return re.sub(pattern, replacement, content)


def setup_git_credentials(repo_path: str, org: str, repo_name: str) -> None:
    """Configure git credentials for authenticated pushes to the target repo.

    Note: the token is embedded in the remote URL, which is the standard
    pattern for short-lived GitHub App installation tokens in CI.  The
    token auto-expires (~1 hour) and is revoked in the workflow post-job
    step.  A more defensive approach (GIT_ASKPASS / credential helper)
    could prevent the token from appearing in git error output but is
    deferred to a future improvement.
    """
    repo = Repo(repo_path)
    auth_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{org}/{repo_name}.git"
    try:
        repo.remote("origin").set_url(auth_url)
    except Exception:
        repo.create_remote("origin", auth_url)


def create_branch_and_commit(
    repo_path: str,
    branch_name: str,
    files_changed: List[str],
    commit_message: str,
) -> bool:
    """Create a new branch, commit changes, and push to origin.

    Enforces branch name validation and never uses force push.
    """
    if not validate_branch_name(branch_name):
        print(
            f"Error: Branch name '{branch_name}' does not match "
            f"required prefix '{SYNC_BRANCH_PREFIX}'"
        )
        return False

    repo = Repo(repo_path)

    try:
        repo.git.checkout("-b", branch_name)

        for file_path in files_changed:
            repo.git.add(file_path)

        repo.index.commit(commit_message)

        # Push without --force (standard push only)
        repo.git.push("--set-upstream", "origin", branch_name)
        print(f"Pushed branch: {branch_name}")
        return True
    except GitCommandError as e:
        print(f"Git operation failed: {e}")
        return False


def create_pull_request(
    org: str,
    repo_name: str,
    branch_name: str,
    title: str,
    body: str,
    base_branch: str = "main",
) -> bool:
    """Create a pull request from a branch in the target repository.

    Args:
        org: Organization name
        repo_name: Repository name
        branch_name: Source branch name
        title: PR title
        body: PR body/description
        base_branch: Target branch (default: main)
    """
    data = {
        "title": title,
        "body": body,
        "base": base_branch,
        "head": branch_name,
    }

    url = f"{GITHUB_API}/repos/{org}/{repo_name}/pulls"
    status, response_data = github_api_request(url, method="POST", data=data)

    if status == 201:
        pr_url = response_data.get("html_url", "")
        print(f"Pull request created successfully: {pr_url}")
        return True
    else:
        error_msg = response_data.get("message", "Unknown error")
        print(f"Failed to create PR (HTTP {status}): {error_msg}")
        return False


def generate_dependabot_config(repo_name: str, config: dict) -> Optional[List[dict]]:
    """Build the managed set of Dependabot entries for a repository.

    Starts with common entries, then applies per-repo overrides.
    An override for the same package-ecosystem replaces the common entry.

    Args:
        repo_name: Target repository name
        config: Full sync configuration

    Returns:
        List of managed Dependabot update entries, or None if the repo
        is excluded from Dependabot sync.
    """
    dependabot_config = config.get("dependabot")
    if dependabot_config is None:
        return None

    dependabot_exclude = dependabot_config.get("exclude_repos", [])
    if repo_name in dependabot_exclude:
        return None

    common_entries = dependabot_config.get("common", [])
    overrides = dependabot_config.get("overrides", {})
    repo_overrides = overrides.get(repo_name, [])

    # Build managed set keyed by package-ecosystem.
    # Overrides replace common entries for the same ecosystem.
    managed: Dict[str, dict] = {}
    for entry in common_entries:
        ecosystem = entry["package-ecosystem"]
        managed[ecosystem] = dict(entry)

    for entry in repo_overrides:
        ecosystem = entry["package-ecosystem"]
        managed[ecosystem] = dict(entry)

    return list(managed.values())


def merge_dependabot_entries(
    managed_entries: List[dict],
    existing_path: str,
) -> str:
    """Merge managed entries with unmanaged entries from the existing file.

    Reads the existing dependabot.yml, identifies entries whose
    package-ecosystem is NOT in the managed set (unmanaged), and
    combines managed + unmanaged into the final YAML output.

    Args:
        managed_entries: Entries managed by org-infra
        existing_path: Path to the existing dependabot.yml in the cloned repo

    Returns:
        The rendered dependabot.yml content as a string.
    """
    managed_ecosystems = {entry["package-ecosystem"] for entry in managed_entries}

    unmanaged_entries: List[dict] = []
    if os.path.exists(existing_path):
        with open(existing_path, "r") as f:
            existing_data = yaml.safe_load(f)
        if existing_data and "updates" in existing_data:
            for entry in existing_data["updates"]:
                if entry.get("package-ecosystem") not in managed_ecosystems:
                    unmanaged_entries.append(entry)

    all_entries = managed_entries + unmanaged_entries

    dependabot_data = {
        "version": 2,
        "updates": all_entries,
    }

    header = (
        "# Dependabot configuration managed by org-infra.\n"
        "# Entries for managed ecosystems are overwritten on sync.\n"
        "# Additional ecosystem entries not managed by org-infra"
        " are preserved.\n"
        "# See: https://docs.github.com/code-security/dependabot/"
        "dependabot-version-updates/"
        "configuration-options-for-the-dependabot.yml-file\n\n"
    )

    rendered_yaml = yaml.dump(
        dependabot_data,
        Dumper=_IndentedListDumper,
        default_flow_style=False,
        sort_keys=False,
    )

    # yaml.dump appends a trailing newline; strip it to avoid a double
    # blank line at end-of-file (yamllint empty-lines rule).
    return header + rendered_yaml.rstrip("\n") + "\n"


def sync_repository(
    org: str,
    repo_name: str,
    config: dict,
    dry_run: bool = False,
    release_tag: Optional[str] = None,
    release_sha: Optional[str] = None,
) -> bool:
    """Sync a single repository with standard files using direct push.

    Args:
        org: Organization name
        repo_name: Repository name
        config: Sync configuration
        dry_run: If True, only show what would be done
        release_tag: Release tag for workflow ref transformation
        release_sha: Commit SHA for workflow ref pinning
    """
    print(f"\n{'=' * 60}")
    print(f"Processing: {org}/{repo_name}")
    print(f"{'=' * 60}")

    source_root = Path(__file__).parent.parent
    files_to_sync = config.get("files_to_sync", [])
    base_branch = config.get("default_base_branch", "main")

    repo_url = f"https://github.com/{org}/{repo_name}.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Step 1: Clone the target repository
            print(f"Cloning {repo_url}...")
            cmd = ["git", "clone", "--quiet", repo_url]
            subprocess.check_call(cmd, cwd=tmpdir, stderr=subprocess.DEVNULL)
            repo_path = os.path.join(tmpdir, repo_name)

            # Step 2: Setup credentials and check for existing PR
            # This must happen BEFORE any file changes to keep the
            # working tree clean for a potential branch checkout.
            existing_pr: Optional[Dict[str, str]] = None
            if not dry_run:
                setup_git_credentials(repo_path, org, repo_name)
                existing_pr = check_existing_sync_pr(org, repo_name)

                # If the API check failed, abort to avoid creating
                # duplicate PRs on transient failures.
                if existing_pr and "error" in existing_pr:
                    print(
                        f"Error: Cannot verify existing PRs for "
                        f"{repo_name}: {existing_pr['error']}. "
                        f"Skipping to avoid duplicates."
                    )
                    return False

                if existing_pr and existing_pr.get("branch"):
                    pr_branch = existing_pr["branch"]
                    if not validate_branch_name(pr_branch):
                        print(
                            f"Error: Existing PR branch '{pr_branch}' "
                            f"does not match prefix "
                            f"'{SYNC_BRANCH_PREFIX}'"
                        )
                        return False

                    print(
                        f"Open sync PR exists: {existing_pr['url']}"
                        f" — checking out branch '{pr_branch}'"
                    )
                    repo = Repo(repo_path)
                    try:
                        repo.git.fetch("origin", pr_branch)
                        repo.git.checkout("-B", pr_branch, f"origin/{pr_branch}")
                    except GitCommandError as e:
                        print(f"Failed to checkout PR branch: {e}")
                        return False

            # Step 3: Process static files to sync
            files_changed: List[str] = []
            for file_config in files_to_sync:
                source_rel_path = file_config["source"]
                dest_rel_path = file_config.get("destination", source_rel_path)

                source_path = source_root / source_rel_path
                dest_path = os.path.join(repo_path, dest_rel_path)

                if not source_path.exists():
                    print(f"Source file not found: {source_rel_path}")
                    continue

                if "exclude_repos" in file_config:
                    if repo_name in file_config["exclude_repos"]:
                        print(f"{source_rel_path} excluded for this repo")
                        continue

                resolved_vars = resolve_file_vars(
                    file_config, repo_name,
                )

                is_ci_workflow = (
                    source_rel_path.startswith(
                        ".github/workflows/ci_",
                    )
                    and source_rel_path.endswith(".yml")
                )
                needs_content_transform = bool(
                    resolved_vars,
                ) or (
                    is_ci_workflow
                    and release_tag
                    and release_sha
                )

                if needs_content_transform:
                    # Content-transform path: read source,
                    # apply vars and/or workflow ref
                    # transformation, then compare.
                    source_content = source_path.read_text()

                    if resolved_vars:
                        source_content = apply_file_vars(
                            source_content, resolved_vars,
                        )
                        if dry_run:
                            for vn, vv in resolved_vars.items():
                                print(
                                    f"[DRY RUN] var {vn}={vv}",
                                )

                    if is_ci_workflow and release_sha:
                        source_content = (
                            transform_workflow_refs(
                                source_content,
                                org,
                                SOURCE_REPO,
                                release_sha,
                                release_tag or "",
                            )
                        )
                        if dry_run:
                            print(
                                "[DRY RUN] workflow refs "
                                "transformed"
                            )

                    resolved_content = source_content

                    existing_content = ""
                    if os.path.exists(dest_path):
                        with open(dest_path, "r") as f:
                            existing_content = f.read()

                    if resolved_content != existing_content:
                        if dry_run:
                            action = (
                                "add"
                                if not existing_content
                                else "update"
                            )
                            print(
                                f"[DRY RUN] Would {action}: "
                                f"{dest_rel_path}"
                            )
                        else:
                            os.makedirs(
                                os.path.dirname(dest_path),
                                exist_ok=True,
                            )
                            with open(dest_path, "w") as f:
                                f.write(resolved_content)
                            print(
                                f"{dest_rel_path} updated "
                                f"(content transformed)"
                            )
                        files_changed.append(dest_rel_path)
                    else:
                        print(f"{dest_rel_path} is up to date")
                elif dry_run:
                    if not os.path.exists(dest_path):
                        print(
                            f"[DRY RUN] Would add: "
                            f"{dest_rel_path}"
                        )
                        files_changed.append(dest_rel_path)
                    elif not compare_files(
                        str(source_path), dest_path,
                    ):
                        print(
                            f"[DRY RUN] Would update: "
                            f"{dest_rel_path}"
                        )
                        files_changed.append(dest_rel_path)
                    else:
                        print(f"{dest_rel_path} is up to date")
                else:
                    if sync_file(
                        str(source_path),
                        dest_path,
                        dest_rel_path,
                    ):
                        files_changed.append(dest_rel_path)

            # Step 4: Generate and sync dependabot.yml
            managed_entries = generate_dependabot_config(repo_name, config)
            if managed_entries is not None:
                dependabot_dest = os.path.join(repo_path, ".github", "dependabot.yml")
                rendered = merge_dependabot_entries(managed_entries, dependabot_dest)
                dependabot_rel = ".github/dependabot.yml"

                os.makedirs(os.path.dirname(dependabot_dest), exist_ok=True)

                existing_content = ""
                if os.path.exists(dependabot_dest):
                    with open(dependabot_dest, "r") as f:
                        existing_content = f.read()

                if rendered != existing_content:
                    if dry_run:
                        print(f"[DRY RUN] Would update: {dependabot_rel} (generated)")
                    else:
                        with open(dependabot_dest, "w") as f:
                            f.write(rendered)
                        print(f"{dependabot_rel} updated (generated)")
                    files_changed.append(dependabot_rel)
                else:
                    print(f"{dependabot_rel} is up to date")

            if not files_changed:
                print(f"All files up to date for {repo_name}")
                return True

            if dry_run:
                print(f"[DRY RUN] Would create PR with {len(files_changed)} file(s)")
                return True

            # Step 5: Commit and push
            commit_message = "chore: sync repository standards\n\nUpdated files:\n" + "\n".join(
                f"- {f}" for f in files_changed
            )

            if existing_pr and existing_pr.get("branch"):
                # Push updates to the existing PR branch
                pr_branch = existing_pr["branch"]
                repo = Repo(repo_path)
                for fp in files_changed:
                    repo.git.add(fp)

                if not repo.is_dirty(index=True):
                    print("PR branch already up to date")
                    return True

                repo.index.commit(commit_message)
                try:
                    repo.git.push("origin", pr_branch)
                    print(f"Updated PR branch: {pr_branch}")
                except GitCommandError as e:
                    print(f"Failed to push to PR branch: {e}")
                    return False
                return True

            # Step 6: Create new branch, commit, push, and open PR
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            branch_name = f"{SYNC_BRANCH_PREFIX}{timestamp}"

            print("\nCreating branch and committing changes...")
            if not create_branch_and_commit(repo_path, branch_name, files_changed, commit_message):
                return False

            pr_body = (
                "This PR synchronizes repository standards from "
                "org-infra.\n\n"
                "## Files Updated\n" + "\n".join(f"- `{f}`" for f in files_changed) + "\n\n"
                "## Description\n"
                "This is an automated PR to ensure repository settings "
                "are consistent across the organization.\n\n"
                "---\n"
                "*This PR was automatically generated by the "
                "sync_org_repositories workflow.*\n"
            )

            print("Creating pull request...")
            return create_pull_request(
                org,
                repo_name,
                branch_name,
                SYNC_PR_TITLE,
                pr_body,
                base_branch,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error processing {repo_name}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error processing {repo_name}: {e}")
            import traceback

            traceback.print_exc()
            return False


def main() -> None:
    """Entry point for the sync script."""
    args = parse_args()

    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN or GITHUB_PAT environment variable not set")
        sys.exit(1)

    config = load_sync_config(args.config)

    # Detect or resolve release for workflow ref transformation
    release_tag: Optional[str] = None
    release_sha: Optional[str] = None

    if args.release_ref:
        # User provided an explicit tag — resolve it to SHA
        print(f"Using release override: {args.release_ref}")
        release_tag = args.release_ref
        ref_endpoint = (
            f"{GITHUB_API}/repos/{args.org}/{SOURCE_REPO}"
            f"/git/ref/tags/{release_tag}"
        )
        status, data = github_api_request(ref_endpoint)
        if status != 200:
            print(
                f"Error: Tag '{release_tag}' not found "
                f"for {args.org}/{SOURCE_REPO}."
            )
            sys.exit(1)
        # Handle annotated vs lightweight tags
        if data.get("object", {}).get("type") == "tag":
            tag_endpoint = (
                f"{GITHUB_API}/repos/{args.org}"
                f"/{SOURCE_REPO}"
                f"/git/tags/{data['object']['sha']}"
            )
            tag_status, tag_data = github_api_request(
                tag_endpoint,
            )
            if tag_status != 200:
                print(
                    f"Error: Could not dereference "
                    f"tag object for "
                    f"{args.org}/{SOURCE_REPO}."
                )
                sys.exit(1)
            release_sha = tag_data.get(
                "object", {},
            ).get("sha")
        else:
            release_sha = data.get(
                "object", {},
            ).get("sha")
    else:
        # Auto-detect latest release
        release_tag, release_sha = get_latest_release(
            args.org, SOURCE_REPO,
        )

    if release_tag and release_sha:
        print(
            f"Release ref: {release_tag} "
            f"({release_sha[:12]})"
        )

    # Fetch and parse peribolos.yml
    peribolos_data = fetch_peribolos_file(args.org)
    repositories = extract_repositories(peribolos_data, args.org)

    if not repositories:
        print("No repositories found in peribolos configuration")
        sys.exit(0)

    if args.repos:
        repositories = [r for r in repositories if r in args.repos]
        print(f"Filtering to {len(repositories)} specified repository(ies)")

    # Skip excluded repos
    excluded_repos = config.get("exclude_repos", ["org-infra"])
    repositories = [r for r in repositories if r not in excluded_repos]

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)

    excluded_list = "\n- ".join(excluded_repos)
    print(f"{len(excluded_repos)} repositories were excluded in this sync:\n- {excluded_list}")
    print(f"\nWill process {len(repositories)} repository(ies)")

    success_count = 0
    for repo_name in repositories:
        try:
            if sync_repository(
                args.org, repo_name, config, args.dry_run,
                release_tag=release_tag,
                release_sha=release_sha,
            ):
                success_count += 1
        except Exception as e:
            print(f"Failed to process {repo_name}: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Summary: Successfully processed {success_count}/{len(repositories)} repositories")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
