#!/usr/bin/env python3
"""
Script to report GitHub Actions workflow runs that have been queued for more than a specified time.

This script checks Apache project repositories for workflow runs that are in 'queued' status
and have been waiting longer than a threshold (default: 2 days).

Usage:
    # Test on a single repository first
    python report_queued_workflows.py --repo apache/camel
    
    # Scan all repositories from file
    python report_queued_workflows.py --repos-file reports/apache_workflows.txt
    
    # Custom threshold (in hours)
    python report_queued_workflows.py --repo apache/camel --threshold-hours 48
    
    # Save report to file
    python report_queued_workflows.py --repos-file reports/apache_workflows.txt --output reports/queued_workflows_report.txt
"""

import argparse
import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class QueuedWorkflowRun:
    """Represents a workflow run that has been queued for too long."""
    repo: str
    workflow_name: str
    run_id: int
    run_number: int
    created_at: datetime
    queued_duration: timedelta
    html_url: str
    head_branch: str
    head_sha: str


class QueuedWorkflowScanner:
    """Scanner for queued GitHub Actions workflow runs."""
    
    def __init__(self, github_token: Optional[str] = None, delay: float = 0.5):
        """
        Initialize the scanner.
        
        Args:
            github_token: GitHub personal access token (required for API access)
            delay: Delay in seconds between API calls to avoid rate limiting
        """
        self.github_token = github_token or os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or use --token option.")
        
        self.delay = delay
        self.base_url = "https://api.github.com"
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.github_token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """
        Make a GitHub API request with rate limiting.
        
        Args:
            url: The API endpoint URL
            params: Optional query parameters
            
        Returns:
            Response object or None if request failed
        """
        time.sleep(self.delay)
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}", file=sys.stderr)
            return None
    
    def get_queued_workflow_runs(self, repo: str, threshold_hours: int) -> List[QueuedWorkflowRun]:
        """
        Get all workflow runs that have been queued for longer than the threshold.
        
        Args:
            repo: Repository in format 'owner/name'
            threshold_hours: Minimum hours a run must be queued to be reported
            
        Returns:
            List of QueuedWorkflowRun objects
        """
        queued_runs = []
        threshold_time = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
        
        # API endpoint for workflow runs
        url = f"{self.base_url}/repos/{repo}/actions/runs"
        params = {
            'status': 'queued',
            'per_page': 100
        }
        
        page = 1
        while True:
            params['page'] = page
            response = self._make_request(url, params)
            
            if not response:
                break
            
            try:
                data = response.json()
                workflow_runs = data.get('workflow_runs', [])
                
                if not workflow_runs:
                    break
                
                for run in workflow_runs:
                    created_at_str = run.get('created_at')
                    if not created_at_str:
                        continue
                    
                    # Parse the created_at timestamp
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    
                    # Check if it's been queued longer than threshold
                    if created_at < threshold_time:
                        queued_duration = datetime.now(timezone.utc) - created_at
                        
                        queued_runs.append(QueuedWorkflowRun(
                            repo=repo,
                            workflow_name=run.get('name', 'Unknown'),
                            run_id=run.get('id'),
                            run_number=run.get('run_number'),
                            created_at=created_at,
                            queued_duration=queued_duration,
                            html_url=run.get('html_url', ''),
                            head_branch=run.get('head_branch', 'unknown'),
                            head_sha=run.get('head_sha', '')[:7]  # Short SHA
                        ))
                
                # Check if there are more pages
                if len(workflow_runs) < params['per_page']:
                    break
                
                page += 1
                
            except (ValueError, KeyError) as e:
                print(f"Error parsing workflow runs for {repo}: {e}", file=sys.stderr)
                break
        
        return queued_runs
    
    def scan_repositories(self, repos: List[str], threshold_hours: int) -> List[QueuedWorkflowRun]:
        """
        Scan multiple repositories for queued workflow runs.
        
        Args:
            repos: List of repository names in format 'owner/name'
            threshold_hours: Minimum hours a run must be queued to be reported
            
        Returns:
            List of all QueuedWorkflowRun objects found
        """
        all_queued_runs = []
        
        print(f"Scanning {len(repos)} repositories for workflow runs queued longer than {threshold_hours} hours...")
        print(f"Threshold time: {datetime.now(timezone.utc) - timedelta(hours=threshold_hours)}")
        print()
        
        for i, repo in enumerate(repos, 1):
            print(f"[{i}/{len(repos)}] Checking {repo}...", end=" ")
            sys.stdout.flush()
            
            queued_runs = self.get_queued_workflow_runs(repo, threshold_hours)
            
            if queued_runs:
                print(f"⚠️  Found {len(queued_runs)} queued run(s)")
                all_queued_runs.extend(queued_runs)
            else:
                print("✓")
        
        return all_queued_runs


def parse_repos_file(file_path: str) -> List[str]:
    """
    Parse the repositories file to extract repository names.
    
    Args:
        file_path: Path to the file containing repository information
        
    Returns:
        List of repository names in format 'owner/name'
    """
    repos = []
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Look for lines that contain repository checks with checkmarks
                # Format: "[123/456] Checking apache/repo-name... ✓ (N workflow(s))"
                if '✓' in line and 'Checking' in line:
                    # Extract repo name between "Checking " and "..."
                    start = line.find('Checking ') + len('Checking ')
                    end = line.find('...', start)
                    if start > 0 and end > start:
                        repo_name = line[start:end].strip()
                        if '/' in repo_name:  # Ensure it's in owner/name format
                            repos.append(repo_name)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
    
    return repos


def format_duration(duration: timedelta) -> str:
    """Format a timedelta as a human-readable string."""
    total_seconds = int(duration.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    
    return " ".join(parts)


def print_report(queued_runs: List[QueuedWorkflowRun], threshold_hours: int):
    """Print a formatted report of queued workflow runs."""
    print("\n" + "=" * 80)
    print(f"QUEUED WORKFLOW RUNS REPORT")
    print(f"Threshold: {threshold_hours} hours ({threshold_hours // 24} days)")
    print(f"Report generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    if not queued_runs:
        print("\n✅ No workflow runs have been queued longer than the threshold.")
        return
    
    print(f"\n⚠️  Found {len(queued_runs)} workflow run(s) queued longer than threshold:\n")
    
    # Group by repository
    runs_by_repo = {}
    for run in queued_runs:
        if run.repo not in runs_by_repo:
            runs_by_repo[run.repo] = []
        runs_by_repo[run.repo].append(run)
    
    # Sort repositories by name
    for repo in sorted(runs_by_repo.keys()):
        runs = runs_by_repo[repo]
        print(f"\nRepository: {repo}")
        print("-" * 80)
        
        # Sort runs by queued duration (longest first)
        for run in sorted(runs, key=lambda r: r.queued_duration, reverse=True):
            print(f"  Workflow: {run.workflow_name}")
            print(f"  Run ID: #{run.run_number} ({run.run_id})")
            print(f"  Branch: {run.head_branch} ({run.head_sha})")
            print(f"  Queued since: {run.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Duration: {format_duration(run.queued_duration)}")
            print(f"  URL: {run.html_url}")
            print()
    
    # Summary statistics
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total repositories affected: {len(runs_by_repo)}")
    print(f"Total queued runs: {len(queued_runs)}")
    
    # Calculate average and max duration
    avg_duration = sum((r.queued_duration.total_seconds() for r in queued_runs), 0) / len(queued_runs)
    max_duration = max(queued_runs, key=lambda r: r.queued_duration)
    
    print(f"Average queue time: {format_duration(timedelta(seconds=avg_duration))}")
    print(f"Longest queue time: {format_duration(max_duration.queued_duration)} ({max_duration.repo})")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Report GitHub Actions workflow runs queued for longer than a threshold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test on a single repository (recommended for first run)
  python report_queued_workflows.py --repo apache/camel
  
  # Specify custom threshold (in hours)
  python report_queued_workflows.py --repo apache/camel --threshold-hours 72
  
  # Scan all repositories from file
  python report_queued_workflows.py --repos-file reports/apache_workflows.txt
  
  # Save report to file
  python report_queued_workflows.py --repos-file reports/apache_workflows.txt --output queued_report.txt
        """
    )
    parser.add_argument(
        '--repo',
        help='Single repository to check in format owner/name (e.g., apache/camel)'
    )
    parser.add_argument(
        '--repos-file',
        help='File containing list of repositories to check (default: reports/apache_workflows.txt if --repo not specified)'
    )
    parser.add_argument(
        '--threshold-hours',
        type=int,
        default=48,
        help='Minimum hours a workflow must be queued to be reported (default: 48, i.e., 2 days)'
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
    
    args = parser.parse_args()
    
    # Check for GitHub token
    token = args.token or os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Error: GitHub token is required.", file=sys.stderr)
        print("Set GITHUB_TOKEN environment variable or use --token option.", file=sys.stderr)
        print("See GITHUB_TOKEN_SETUP.md for instructions.", file=sys.stderr)
        sys.exit(1)
    
    # Determine which repositories to scan
    repos = []
    if args.repo:
        # Single repository mode
        repos = [args.repo]
        print(f"Testing on single repository: {args.repo}\n")
    elif args.repos_file:
        # Multiple repositories from file
        print(f"Reading repositories from: {args.repos_file}")
        repos = parse_repos_file(args.repos_file)
        
        if not repos:
            print("Error: No repositories found in the file.", file=sys.stderr)
            sys.exit(1)
        
        print(f"Found {len(repos)} repositories with workflows\n")
    else:
        # Default to repos file if neither specified
        default_file = 'reports/apache_workflows.txt'
        print(f"No --repo or --repos-file specified, using default: {default_file}")
        repos = parse_repos_file(default_file)
        
        if not repos:
            print("Error: No repositories found in the file.", file=sys.stderr)
            sys.exit(1)
        
        print(f"Found {len(repos)} repositories with workflows\n")
    
    # Initialize scanner
    try:
        scanner = QueuedWorkflowScanner(github_token=token, delay=args.delay)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Scan repositories
    queued_runs = scanner.scan_repositories(repos, args.threshold_hours)
    
    # Print or save report
    if args.output:
        original_stdout = sys.stdout
        with open(args.output, 'w') as f:
            sys.stdout = f
            print_report(queued_runs, args.threshold_hours)
        sys.stdout = original_stdout
        print(f"\nReport written to: {args.output}")
        print(f"Total queued runs found: {len(queued_runs)}")
    else:
        print_report(queued_runs, args.threshold_hours)
    
    # Exit with error code if queued runs found
    sys.exit(1 if queued_runs else 0)


if __name__ == '__main__':
    main()

# Made with Bob