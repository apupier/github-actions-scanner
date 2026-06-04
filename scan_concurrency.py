#!/usr/bin/env python3
"""
Script to scan GitHub Actions workflows for missing or incorrect concurrency configuration.

This script checks Apache project repositories for workflows that:
- Trigger on pull_request events
- Don't have concurrency.cancel-in-progress set to true or ${{ github.ref != 'refs/heads/main' }}

Usage:
    python scan_concurrency.py --repo apache/camel
    python scan_concurrency.py --org apache --all
"""

import argparse
import os
import sys
import time
import yaml
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WorkflowIssue:
    """Represents a workflow with concurrency configuration issues."""
    repo: str
    workflow_file: str
    issue_type: str
    details: str


class GitHubWorkflowScanner:
    """Scanner for GitHub Actions workflow concurrency configurations."""
    
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
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """
        Make a GitHub API request with rate limiting.
        
        Args:
            url: The API endpoint URL
            
        Returns:
            Response object or None if request failed
        """
        time.sleep(self.delay)
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}", file=sys.stderr)
            return None
    
    def get_workflow_files(self, repo: str) -> List[Dict]:
        """
        Get all workflow files from a repository.
        
        Args:
            repo: Repository in format 'owner/name'
            
        Returns:
            List of workflow file information dictionaries
        """
        url = f"{self.base_url}/repos/{repo}/contents/.github/workflows"
        response = self._make_request(url)
        
        if not response:
            return []
        
        try:
            files = response.json()
            # Filter for YAML/YML files
            return [f for f in files if f['name'].endswith(('.yml', '.yaml'))]
        except (ValueError, KeyError) as e:
            print(f"Error parsing workflow files for {repo}: {e}", file=sys.stderr)
            return []
    
    def get_workflow_content(self, repo: str, file_path: str) -> Optional[str]:
        """
        Get the content of a workflow file.
        
        Args:
            repo: Repository in format 'owner/name'
            file_path: Path to the workflow file
            
        Returns:
            Workflow file content as string or None
        """
        url = f"{self.base_url}/repos/{repo}/contents/{file_path}"
        response = self._make_request(url)
        
        if not response:
            return None
        
        try:
            file_data = response.json()
            # GitHub API returns base64 encoded content
            import base64
            content = base64.b64decode(file_data['content']).decode('utf-8')
            return content
        except (ValueError, KeyError, Exception) as e:
            print(f"Error getting content for {file_path} in {repo}: {e}", file=sys.stderr)
            return None
    
    def check_workflow_concurrency(self, repo: str, workflow_file: str, content: str) -> Optional[WorkflowIssue]:
        """
        Check if a workflow has proper concurrency configuration.
        
        Args:
            repo: Repository in format 'owner/name'
            workflow_file: Name of the workflow file
            content: Workflow file content
            
        Returns:
            WorkflowIssue if there's a problem, None otherwise
        """
        try:
            workflow = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return WorkflowIssue(
                repo=repo,
                workflow_file=workflow_file,
                issue_type="YAML_PARSE_ERROR",
                details=f"Failed to parse YAML: {e}"
            )
        
        if not isinstance(workflow, dict):
            return None
        
        # Check if workflow triggers on pull_request
        on_config = workflow.get('on') or workflow.get(True)
        if not on_config:
            return None
        
        has_pull_request = False
        if isinstance(on_config, str):
            has_pull_request = on_config == 'pull_request'
        elif isinstance(on_config, list):
            has_pull_request = 'pull_request' in on_config
        elif isinstance(on_config, dict):
            has_pull_request = 'pull_request' in on_config
        
        if not has_pull_request:
            return None  # Not triggered by pull_request, so no issue
        
        # Check concurrency configuration
        concurrency = workflow.get('concurrency')
        
        if not concurrency:
            return WorkflowIssue(
                repo=repo,
                workflow_file=workflow_file,
                issue_type="MISSING_CONCURRENCY",
                details="Workflow triggers on pull_request but has no concurrency configuration"
            )
        
        # Check cancel-in-progress setting
        cancel_in_progress = concurrency.get('cancel-in-progress')
        
        if cancel_in_progress is None:
            return WorkflowIssue(
                repo=repo,
                workflow_file=workflow_file,
                issue_type="MISSING_CANCEL_IN_PROGRESS",
                details="Concurrency defined but cancel-in-progress is not set"
            )
        
        # Check if cancel-in-progress is set correctly
        # It should be either:
        # - true (boolean)
        # - "${{ github.ref != 'refs/heads/main' }}" (string expression)
        valid_values = [
            True,
            "${{ github.ref != 'refs/heads/main' }}",
            "${{ github.ref != 'refs/heads/master' }}"  # Some repos use master
        ]
        
        if cancel_in_progress not in valid_values:
            return WorkflowIssue(
                repo=repo,
                workflow_file=workflow_file,
                issue_type="INCORRECT_CANCEL_IN_PROGRESS",
                details=f"cancel-in-progress is set to '{cancel_in_progress}' but should be true or ${{{{ github.ref != 'refs/heads/main' }}}}"
            )
        
        return None  # No issues found
    
    def scan_repository(self, repo: str) -> List[WorkflowIssue]:
        """
        Scan all workflows in a repository.
        
        Args:
            repo: Repository in format 'owner/name'
            
        Returns:
            List of WorkflowIssue objects
        """
        print(f"Scanning repository: {repo}")
        issues = []
        
        workflow_files = self.get_workflow_files(repo)
        if not workflow_files:
            print(f"  No workflow files found or unable to access repository")
            return issues
        
        print(f"  Found {len(workflow_files)} workflow file(s)")
        
        for workflow_file in workflow_files:
            file_name = workflow_file['name']
            file_path = workflow_file['path']
            print(f"  Checking: {file_name}")
            
            content = self.get_workflow_content(repo, file_path)
            if not content:
                continue
            
            issue = self.check_workflow_concurrency(repo, file_name, content)
            if issue:
                issues.append(issue)
                print(f"    ⚠️  Issue found: {issue.issue_type}")
            else:
                print(f"    ✓ OK")
        
        return issues
    
    def get_org_repositories(self, org: str) -> List[str]:
        """
        Get all repositories for an organization.
        
        Args:
            org: Organization name
            
        Returns:
            List of repository names in format 'owner/name'
        """
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
                
                repos.extend([f"{org}/{repo['name']}" for repo in page_repos])
                page += 1
            except (ValueError, KeyError) as e:
                print(f"Error getting repositories for {org}: {e}", file=sys.stderr)
                break
        
        return repos


def print_report(issues: List[WorkflowIssue]):
    """Print a formatted report of issues found."""
    if not issues:
        print("\n✅ No issues found! All workflows have proper concurrency configuration.")
        return
    
    print(f"\n⚠️  Found {len(issues)} issue(s):\n")
    print("=" * 80)
    
    # Group issues by repository
    issues_by_repo = {}
    for issue in issues:
        if issue.repo not in issues_by_repo:
            issues_by_repo[issue.repo] = []
        issues_by_repo[issue.repo].append(issue)
    
    for repo, repo_issues in issues_by_repo.items():
        print(f"\nRepository: {repo}")
        print("-" * 80)
        for issue in repo_issues:
            print(f"  File: {issue.workflow_file}")
            print(f"  Issue: {issue.issue_type}")
            print(f"  Details: {issue.details}")
            print()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Scan GitHub Actions workflows for concurrency configuration issues"
    )
    parser.add_argument(
        '--repo',
        help='Repository to scan in format owner/name (e.g., apache/camel)'
    )
    parser.add_argument(
        '--org',
        help='Organization to scan (e.g., apache)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scan all repositories in the organization (use with --org)'
    )
    parser.add_argument(
        '--token',
        help='GitHub personal access token (or set GITHUB_TOKEN env var)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay in seconds between API calls (default: 1.0)'
    )
    parser.add_argument(
        '--output',
        help='Output file for the report (optional, prints to stdout by default)'
    )
    
    args = parser.parse_args()
    
    if not args.repo and not (args.org and args.all):
        parser.error("Either --repo or --org with --all must be specified")
    
    # Initialize scanner
    scanner = GitHubWorkflowScanner(github_token=args.token, delay=args.delay)
    
    # Determine which repositories to scan
    repos_to_scan = []
    if args.repo:
        repos_to_scan = [args.repo]
    elif args.org and args.all:
        print(f"Fetching repositories for organization: {args.org}")
        repos_to_scan = scanner.get_org_repositories(args.org)
        print(f"Found {len(repos_to_scan)} repositories\n")
    
    # Scan repositories
    all_issues = []
    for repo in repos_to_scan:
        issues = scanner.scan_repository(repo)
        all_issues.extend(issues)
        print()  # Empty line between repos
    
    # Print report
    if args.output:
        original_stdout = sys.stdout
        with open(args.output, 'w') as f:
            sys.stdout = f
            print_report(all_issues)
        sys.stdout = original_stdout
        print(f"Report written to: {args.output}")
    else:
        print_report(all_issues)
    
    # Exit with error code if issues found
    sys.exit(1 if all_issues else 0)


if __name__ == '__main__':
    main()

# Made with Bob
