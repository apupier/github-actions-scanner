#!/usr/bin/env python3
"""
Script to list GitHub repositories that use GitHub Actions workflows.

This script retrieves all public repositories from the Apache organization
and identifies which ones have GitHub Actions workflows configured.

Usage:
    python list_repos_with_workflows.py
    python list_repos_with_workflows.py --org apache
    python list_repos_with_workflows.py --org apache --output repos_with_workflows.txt
"""

import argparse
import os
import sys
import time
import requests
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RepoWithWorkflows:
    """Represents a repository that has GitHub Actions workflows."""
    name: str
    full_name: str
    url: str
    workflow_count: int
    workflow_files: List[str]


class GitHubRepoScanner:
    """Scanner for GitHub repositories with workflows."""
    
    def __init__(self, github_token: Optional[str] = None, delay: float = 0.5):
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
    
    def get_org_repositories(self, org: str) -> Tuple[List[Tuple[str, str]], int]:
        """
        Get all public, non-archived repositories for an organization.
        
        Args:
            org: Organization name
            
        Returns:
            Tuple of (list of (repo_full_name, repo_url), archived_count)
        """
        repos = []
        archived_count = 0
        page = 1
        per_page = 100
        
        print(f"Fetching repositories for organization: {org}")
        
        while True:
            url = f"{self.base_url}/orgs/{org}/repos?page={page}&per_page={per_page}&type=public"
            response = self._make_request(url)
            
            if not response:
                break
            
            try:
                page_repos = response.json()
                if not page_repos:
                    break
                
                for repo in page_repos:
                    # Skip archived repositories
                    if repo.get('archived', False):
                        archived_count += 1
                        continue
                    
                    repos.append((
                        f"{org}/{repo['name']}",
                        repo['html_url']
                    ))
                
                print(f"  Fetched page {page} ({len(page_repos)} repos, {archived_count} archived so far)")
                page += 1
            except (ValueError, KeyError) as e:
                print(f"Error getting repositories for {org}: {e}", file=sys.stderr)
                break
        
        if archived_count > 0:
            print(f"  Skipped {archived_count} archived repositories")
        
        return repos, archived_count
    
    def has_workflows(self, repo: str) -> Tuple[bool, List[str]]:
        """
        Check if a repository has GitHub Actions workflows.
        
        Args:
            repo: Repository in format 'owner/name'
            
        Returns:
            Tuple of (has_workflows, list_of_workflow_files)
        """
        url = f"{self.base_url}/repos/{repo}/contents/.github/workflows"
        response = self._make_request(url)
        
        if not response:
            return False, []
        
        try:
            files = response.json()
            # Filter for YAML/YML files
            workflow_files = [f['name'] for f in files if f['name'].endswith(('.yml', '.yaml'))]
            return len(workflow_files) > 0, workflow_files
        except (ValueError, KeyError) as e:
            # Directory doesn't exist or other error
            return False, []
    
    def scan_organization(self, org: str, progress_file=None) -> List[RepoWithWorkflows]:
        """
        Scan all repositories in an organization for workflows.
        
        Args:
            org: Organization name
            progress_file: Optional file handle to write progress to
            
        Returns:
            List of RepoWithWorkflows objects
        """
        repos_with_workflows = []
        
        # Get all repositories
        all_repos, archived_count = self.get_org_repositories(org)
        msg = f"\nFound {len(all_repos)} active repositories"
        if archived_count > 0:
            msg += f" ({archived_count} archived repositories excluded)"
        print(msg)
        if progress_file:
            progress_file.write(msg + "\n")
            progress_file.flush()
        
        msg = f"Checking for GitHub Actions workflows...\n"
        print(msg)
        if progress_file:
            progress_file.write(msg + "\n")
            progress_file.flush()
        
        # Check each repository for workflows
        for i, (repo_full_name, repo_url) in enumerate(all_repos, 1):
            status_msg = f"[{i}/{len(all_repos)}] Checking {repo_full_name}..."
            print(status_msg, end=" ")
            if progress_file:
                progress_file.write(status_msg + " ")
                progress_file.flush()
            
            has_wf, workflow_files = self.has_workflows(repo_full_name)
            
            if has_wf:
                result_msg = f"✓ ({len(workflow_files)} workflow(s))"
                print(result_msg)
                if progress_file:
                    progress_file.write(result_msg + "\n")
                    progress_file.flush()
                repos_with_workflows.append(RepoWithWorkflows(
                    name=repo_full_name.split('/')[-1],
                    full_name=repo_full_name,
                    url=repo_url,
                    workflow_count=len(workflow_files),
                    workflow_files=workflow_files
                ))
            else:
                result_msg = "✗"
                print(result_msg)
                if progress_file:
                    progress_file.write(result_msg + "\n")
                    progress_file.flush()
        
        return repos_with_workflows


def print_report(repos: List[RepoWithWorkflows], org: str):
    """Print a formatted report of repositories with workflows."""
    print("\n" + "=" * 80)
    print(f"REPOSITORIES WITH GITHUB ACTIONS WORKFLOWS")
    print(f"Organization: {org}")
    print("=" * 80)
    
    if not repos:
        print("\nNo repositories with GitHub Actions workflows found.")
        return
    
    print(f"\nFound {len(repos)} repositories with workflows:\n")
    
    for repo in sorted(repos, key=lambda r: r.full_name):
        print(f"Repository: {repo.full_name}")
        print(f"  URL: {repo.url}")
        print(f"  Workflows: {repo.workflow_count}")
        print(f"  Files: {', '.join(repo.workflow_files)}")
        print()


def print_simple_list(repos: List[RepoWithWorkflows]):
    """Print a simple list of repository names."""
    for repo in sorted(repos, key=lambda r: r.full_name):
        print(repo.full_name)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="List GitHub repositories that use GitHub Actions workflows"
    )
    parser.add_argument(
        '--org',
        default='apache',
        help='Organization to scan (default: apache)'
    )
    parser.add_argument(
        '--token',
        help='GitHub personal access token (or set GITHUB_TOKEN env var)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay in seconds between API calls (default: 0.5)'
    )
    parser.add_argument(
        '--output',
        help='Output file for the report (optional, prints to stdout by default)'
    )
    parser.add_argument(
        '--simple',
        action='store_true',
        help='Output simple list of repository names only'
    )
    
    args = parser.parse_args()
    
    # Check for GitHub token
    token = args.token or os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Warning: No GitHub token provided. API rate limits will be restrictive.", file=sys.stderr)
        print("Set GITHUB_TOKEN environment variable or use --token option.", file=sys.stderr)
        print()
    
    # Initialize scanner
    scanner = GitHubRepoScanner(github_token=token, delay=args.delay)
    
    # Scan organization with optional progress logging
    progress_file = None
    if args.output:
        # Open file for writing progress in real-time
        progress_file = open(args.output, 'w')
        progress_file.write(f"Scanning organization: {args.org}\n")
        progress_file.write("=" * 80 + "\n\n")
        progress_file.flush()
    
    try:
        repos_with_workflows = scanner.scan_organization(args.org, progress_file)
        
        # Write final report
        if args.output and progress_file:
            progress_file.write("\n" + "=" * 80 + "\n")
            progress_file.write("FINAL REPORT\n")
            progress_file.write("=" * 80 + "\n")
            progress_file.flush()
            
            original_stdout = sys.stdout
            sys.stdout = progress_file
            if args.simple:
                print_simple_list(repos_with_workflows)
            else:
                print_report(repos_with_workflows, args.org)
            sys.stdout = original_stdout
            
            print(f"\nReport written to: {args.output}")
            print(f"Total repositories with workflows: {len(repos_with_workflows)}")
        else:
            if args.simple:
                print_simple_list(repos_with_workflows)
            else:
                print_report(repos_with_workflows, args.org)
    finally:
        if progress_file:
            progress_file.close()


if __name__ == '__main__':
    main()

# Made with Bob