# GitHub Actions Scanner

A collection of Python scripts to analyze and monitor GitHub Actions workflows in Apache projects.

## Available Scripts

### 1. Push Branch Filter Scanner (`scan_push_branches.py`)

Identifies GitHub Actions workflows that:
- Trigger on `push` events
- Have **no `branches` or `branches-ignore` filter** on the push trigger

Without a branch filter the workflow fires on every commit pushed to every branch. When a `pull_request` trigger is also present this causes duplicate runs — once for the PR and once for the push — wasting runner resources.

See the [Apache best practices guide](https://cwiki.apache.org/confluence/pages/viewpage.action?pageId=430408443#GitHubActionsRecommendedPractices-Restrictthepushtriggertospecificbranches) for details.

### 2. Concurrency Scanner (`scan_concurrency.py`)

Identifies GitHub Actions workflows that:
- Trigger on `pull_request` events
- Don't have proper `concurrency.cancel-in-progress` configuration
- Should have `cancel-in-progress` set to `true` or `${{ github.ref != 'refs/heads/main' }}`

Proper concurrency configuration helps prevent wasted CI resources by canceling outdated workflow runs when new commits are pushed to a pull request.

See [WORKFLOW_SCANNER_USAGE.md](WORKFLOW_SCANNER_USAGE.md) for detailed usage.

### 3. Queued Workflows Reporter (`report_queued_workflows.py`)

Reports GitHub Actions workflow runs that have been stuck in "queued" state for longer than a specified threshold (default: 2 days).

This helps identify:
- Workflow runs waiting for unavailable runners
- Stuck jobs that may need manual intervention
- Resource allocation issues in your CI/CD pipeline

See [QUEUED_WORKFLOWS_USAGE.md](QUEUED_WORKFLOWS_USAGE.md) for detailed usage.

### 4. Repository Workflow Lister (`list_repos_with_workflows.py`)

Lists all repositories in an organization that have GitHub Actions workflows configured.

See [QUICK_START.md](QUICK_START.md) for detailed usage.

## Requirements

- Python 3.7+
- GitHub personal access token (optional but recommended to avoid rate limits)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Set up GitHub token:
```bash
export GITHUB_TOKEN=your_github_token_here
```

## Quick Start

### Detect Unrestricted Push Triggers

```bash
# Test on a single repository (the example from issue #5)
python3 scan_push_branches.py --repo apache/atlas

# Scan a curated list of repos (plain list or mixed-format log both accepted)
python3 scan_push_branches.py --repos-file reports/apache_workflows.txt

# Scan all repositories in an org
python3 scan_push_branches.py --org apache --all
```

### Check for Concurrency Issues

```bash
# Test on a single repository
python3 scan_concurrency.py --repo apache/camel

# Scan all repositories with workflows from the default file
python3 scan_concurrency.py

# Scan all Apache repositories
python3 scan_concurrency.py --org apache --all
```

### Monitor Queued Workflows

```bash
# Test on a single repository
python3 report_queued_workflows.py --repo apache/camel

# Scan all repositories with workflows
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt
```

### List Repositories with Workflows

```bash
# List all Apache repositories with workflows
python3 list_repos_with_workflows.py --org apache --output reports/apache_workflows.txt
```

## Common Options

All scripts support these common options:

- `--token TOKEN`: GitHub personal access token (or set `GITHUB_TOKEN` env var)
- `--delay SECONDS`: Delay between API calls in seconds
- `--output FILE`: Save report to file instead of printing to stdout

See individual script documentation for specific options.

## Example Workflow

A typical workflow for monitoring Apache repositories:

```bash
# 1. Find all repositories with workflows
python3 list_repos_with_workflows.py --org apache --output reports/apache_workflows.txt

# 2. Detect push triggers without branch filters
python3 scan_push_branches.py --output reports/push_branch_issues.txt

# 3. Check for concurrency configuration issues
python3 scan_concurrency.py --output reports/concurrency_issues.txt

# 4. Monitor for stuck workflow runs
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt --output reports/queued_runs.txt
```

## Rate Limiting

The script includes built-in rate limiting with a configurable delay between API calls (default: 1 second). This helps avoid hitting GitHub's API rate limits.

For scanning many repositories:
- Use a GitHub token to get higher rate limits (5000 requests/hour vs 60 requests/hour)
- Increase the delay with `--delay` if needed
- Consider scanning repositories in batches

## Exit Codes

- `0`: No issues found
- `1`: Issues found or errors occurred

## Documentation

- [QUICK_START.md](QUICK_START.md) - Quick start guide for listing repositories
- [WORKFLOW_SCANNER_USAGE.md](WORKFLOW_SCANNER_USAGE.md) - Concurrency scanner usage
- [QUEUED_WORKFLOWS_USAGE.md](QUEUED_WORKFLOWS_USAGE.md) - Queued workflows reporter usage
- [GITHUB_TOKEN_SETUP.md](GITHUB_TOKEN_SETUP.md) - GitHub token setup instructions

## Related Issues

- [#5 — Provide script to detect jobs which are building all commits on all branches](https://github.com/apupier/github-actions-scanner/issues/5): implemented by `scan_push_branches.py`

## License

This script is provided as-is for scanning Apache project repositories.