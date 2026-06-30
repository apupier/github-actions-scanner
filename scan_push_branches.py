#!/usr/bin/env python3
"""
Script to scan GitHub Actions workflows for push triggers that don't restrict target branches.

A workflow with a push trigger and no branch filter fires on every commit pushed to any
branch.  When the same workflow also has a pull_request trigger this causes it to run
twice for the same code — once for the PR and once for the push — wasting runner resources.

The fix is to add a branches (or branches-ignore) filter to the push trigger, e.g.:
    on:
      push:
        branches:
          - main
      pull_request:

Reference best practice:
  https://cwiki.apache.org/confluence/pages/viewpage.action?pageId=430408443#GitHubActionsRecommendedPractices-Restrictthepushtriggertospecificbranches

Usage:
    python scan_push_branches.py --repo apache/atlas
    python scan_push_branches.py --repo apache/camel
    python scan_push_branches.py --repos-file reports/apache_workflows.txt
    python scan_push_branches.py --org apache --all
"""

import argparse
import base64
import os
import re
import sys
import time
import yaml
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class WorkflowIssue:
    """Represents a workflow whose push trigger has no branch filter."""
    repo: str
    workflow_file: str
    issue_type: str
    details: str
    workflow_url: str = field(default="")


class GitHubWorkflowScanner:
    """Scanner for GitHub Actions workflows missing push branch filters."""

    def __init__(self, github_token: Optional[str] = None, delay: float = 1.0):
        """
        Initialize the scanner.

        Args:
            github_token: GitHub personal access token (optional, but recommended)
            delay: Delay in seconds between API calls to avoid rate limiting
        """
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        self.delay = delay
        self.base_url = "https://api.github.com"
        self.headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'

    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make a GitHub API request with rate limiting."""
        time.sleep(self.delay)
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}", file=sys.stderr)
            return None

    def get_workflow_files(self, repo: str) -> List[Dict]:
        """Return all YAML workflow file descriptors for a repository."""
        url = f"{self.base_url}/repos/{repo}/contents/.github/workflows"
        response = self._make_request(url)
        if not response:
            return []
        try:
            files = response.json()
            return [f for f in files if f['name'].endswith(('.yml', '.yaml'))]
        except (ValueError, KeyError) as e:
            print(f"Error parsing workflow files for {repo}: {e}", file=sys.stderr)
            return []

    def get_workflow_content(self, repo: str, file_path: str) -> Optional[str]:
        """Return the decoded text content of a workflow file."""
        url = f"{self.base_url}/repos/{repo}/contents/{file_path}"
        response = self._make_request(url)
        if not response:
            return None
        try:
            file_data = response.json()
            return base64.b64decode(file_data['content']).decode('utf-8')
        except Exception as e:
            print(f"Error getting content for {file_path} in {repo}: {e}", file=sys.stderr)
            return None

    def check_push_branch_filter(
        self,
        repo: str,
        workflow_file: str,
        content: str,
        file_path: str = "",
    ) -> Optional[WorkflowIssue]:
        """
        Return a WorkflowIssue when the workflow's push trigger has no branch filter.

        A workflow is flagged when it has a push trigger AND that trigger carries
        neither a 'branches' nor a 'branches-ignore' filter — meaning it fires on
        every push to every branch.

        Args:
            repo: Repository in format 'owner/name'
            workflow_file: Name of the workflow file (for reporting)
            content: Raw YAML text of the workflow file
            file_path: Path inside the repo (used to build a permalink)

        Returns:
            WorkflowIssue if an issue is detected, None otherwise
        """
        try:
            workflow = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return WorkflowIssue(
                repo=repo,
                workflow_file=workflow_file,
                issue_type="YAML_PARSE_ERROR",
                details=f"Failed to parse YAML: {e}",
            )

        if not isinstance(workflow, dict):
            return None

        # PyYAML parses the bare 'on' key as boolean True
        on_config = workflow.get('on') or workflow.get(True)
        if not on_config:
            return None

        # Resolve the push trigger configuration
        push_config = None
        if isinstance(on_config, str):
            if on_config == 'push':
                push_config = {}          # bare "on: push" — no filter
        elif isinstance(on_config, list):
            if 'push' in on_config:
                push_config = {}          # e.g. [push, pull_request]
        elif isinstance(on_config, dict):
            if 'push' in on_config:
                push_config = on_config['push'] or {}

        if push_config is None:
            return None  # no push trigger — nothing to flag

        has_branch_filter = (
            isinstance(push_config, dict)
            and (
                push_config.get('branches') is not None
                or push_config.get('branches-ignore') is not None
            )
        )

        if has_branch_filter:
            return None  # correctly restricted

        workflow_url = ""
        if file_path:
            workflow_url = f"https://github.com/{repo}/blob/HEAD/{file_path}"

        return WorkflowIssue(
            repo=repo,
            workflow_file=workflow_file,
            issue_type="PUSH_TRIGGER_WITHOUT_BRANCH_FILTER",
            details=(
                "Workflow has a push trigger with no branches/branches-ignore filter. "
                "It will run on every commit pushed to any branch, likely causing "
                "duplicate runs alongside pull_request triggers."
            ),
            workflow_url=workflow_url,
        )

    def scan_repository(self, repo: str) -> List[WorkflowIssue]:
        """Scan all workflows in a repository and return detected issues."""
        print(f"Scanning repository: {repo}")
        issues = []

        workflow_files = self.get_workflow_files(repo)
        if not workflow_files:
            print("  No workflow files found or unable to access repository")
            return issues

        print(f"  Found {len(workflow_files)} workflow file(s)")

        for wf in workflow_files:
            file_name = wf['name']
            file_path = wf['path']
            print(f"  Checking: {file_name}")

            content = self.get_workflow_content(repo, file_path)
            if not content:
                continue

            issue = self.check_push_branch_filter(repo, file_name, content, file_path)
            if issue:
                issues.append(issue)
                print(f"    ⚠️  Issue found: {issue.issue_type}")
            else:
                print(f"    ✓ OK")

        return issues

    def get_org_repositories(self, org: str) -> List[str]:
        """Return all public, non-archived repo names ('owner/name') for an org."""
        repos = []
        page = 1
        per_page = 100

        while True:
            url = f"{self.base_url}/orgs/{org}/repos?page={page}&per_page={per_page}&type=public"
            response = self._make_request(url)
            if not response:
                break
            try:
                page_repos = response.json()
                if not page_repos:
                    break
                repos.extend([
                    f"{org}/{r['name']}"
                    for r in page_repos
                    if not r.get('archived', False)
                ])
                page += 1
            except (ValueError, KeyError) as e:
                print(f"Error getting repositories for {org}: {e}", file=sys.stderr)
                break

        return repos


# Extracts 'owner/name' from any line — handles these formats:
#   apache/camel                                     (plain list)
#   [18/2501] Checking apache/camel... ✓ (17 …)    (progress log)
#   Repository: apache/camel                         (final report section)
#
# Rules: each side must contain at least one letter (not purely numeric),
# and must be at least 2 characters long, to avoid matching "1/2501" counters.
_REPO_EXTRACT_RE = re.compile(
    r'\b([A-Za-z0-9_.-]{2,}/[A-Za-z0-9_.-]{2,})\b'
)
_REPO_HAS_LETTER_RE = re.compile(r'[A-Za-z]')


def load_repositories_from_file(file_path: str) -> List[str]:
    """
    Load repository names from a file.

    Accepts both a plain 'owner/name' list and the mixed-format progress log
    produced by list_repos_with_workflows.py (which contains progress lines like
    ``[18/2501] Checking apache/camel... ✓`` and report lines like
    ``Repository: apache/camel``).  Only the first 'owner/name' token on each
    line is used; blank lines and comment lines (starting with #) are skipped.
    Duplicate entries are silently dropped.
    """
    repos: List[str] = []
    seen: set = set()
    try:
        with open(file_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                # Scan all owner/name tokens on the line; skip pure-numeric ones
                # (e.g. "18/2501" from progress counters like "[18/2501] Checking …")
                for match in _REPO_EXTRACT_RE.finditer(stripped):
                    repo = match.group(1)
                    owner, name = repo.split('/', 1)
                    if not _REPO_HAS_LETTER_RE.search(owner) or not _REPO_HAS_LETTER_RE.search(name):
                        continue
                    if repo not in seen:
                        seen.add(repo)
                        repos.append(repo)
                    break  # take only the first valid token per line
    except OSError as e:
        print(f"Error reading repositories file {file_path}: {e}", file=sys.stderr)
        return []
    return repos


def print_report(issues: List[WorkflowIssue]) -> None:
    """Print a formatted report of detected issues."""
    if not issues:
        print("\n✅ No issues found! All push triggers restrict target branches.")
        return

    print(f"\n⚠️  Found {len(issues)} workflow(s) with unrestricted push triggers:\n")
    print("=" * 80)

    issues_by_repo: Dict[str, List[WorkflowIssue]] = {}
    for issue in issues:
        issues_by_repo.setdefault(issue.repo, []).append(issue)

    for repo, repo_issues in issues_by_repo.items():
        print(f"\nRepository: {repo}")
        print("-" * 80)
        for issue in repo_issues:
            print(f"  File:    {issue.workflow_file}")
            print(f"  Issue:   {issue.issue_type}")
            print(f"  Details: {issue.details}")
            if issue.workflow_url:
                print(f"  URL:     {issue.workflow_url}")
            print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan GitHub Actions workflows for push triggers that don't restrict "
            "target branches.  Such workflows run on every commit to every branch, "
            "potentially doubling runner usage when pull_request triggers are also present."
        )
    )
    parser.add_argument(
        '--repo',
        help='Single repository to scan in format owner/name (e.g., apache/atlas)',
    )
    parser.add_argument(
        '--org',
        help='Organization to scan (e.g., apache)',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scan all repositories in the organization (use with --org)',
    )
    parser.add_argument(
        '--repos-file',
        default='reports/apache_workflows.txt',
        help='File containing repositories to scan, one per line '
             '(default: reports/apache_workflows.txt).  '
             'Accepts both plain owner/name lists and the mixed-format log '
             'produced by list_repos_with_workflows.py.',
    )
    parser.add_argument(
        '--token',
        help='GitHub personal access token (or set GITHUB_TOKEN env var)',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay in seconds between API calls (default: 1.0)',
    )
    parser.add_argument(
        '--output',
        help='Output file for the report (optional, prints to stdout by default)',
    )

    args = parser.parse_args()

    if args.repo and (args.org or args.all):
        parser.error("--repo cannot be used with --org/--all")
    if bool(args.org) != bool(args.all):
        parser.error("--org and --all must be used together")

    token = args.token or os.environ.get('GITHUB_TOKEN')
    if not token:
        print(
            "Warning: No GitHub token provided. API rate limits will be restrictive.\n"
            "Set GITHUB_TOKEN environment variable or use --token option.",
            file=sys.stderr,
        )
        print()

    scanner = GitHubWorkflowScanner(github_token=token, delay=args.delay)

    # Determine repositories to scan
    repos_to_scan: List[str] = []
    if args.repo:
        repos_to_scan = [args.repo]
    elif args.org and args.all:
        print(f"Fetching repositories for organization: {args.org}")
        repos_to_scan = scanner.get_org_repositories(args.org)
        print(f"Found {len(repos_to_scan)} active repositories\n")
    else:
        print(f"Loading repositories from file: {args.repos_file}")
        repos_to_scan = load_repositories_from_file(args.repos_file)
        if not repos_to_scan:
            print("No repositories found to scan.", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(repos_to_scan)} repositories\n")

    # Scan
    all_issues: List[WorkflowIssue] = []
    for repo in repos_to_scan:
        all_issues.extend(scanner.scan_repository(repo))
        print()

    # Report
    if args.output:
        original_stdout = sys.stdout
        with open(args.output, 'w') as f:
            sys.stdout = f
            print_report(all_issues)
        sys.stdout = original_stdout
        print(f"Report written to: {args.output}")
    else:
        print_report(all_issues)

    sys.exit(1 if all_issues else 0)


if __name__ == '__main__':
    main()

# Made with Bob
