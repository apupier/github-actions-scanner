# GitHub Workflow Repository Scanner

## Overview

The [`list_repos_with_workflows.py`](list_repos_with_workflows.py:1) script retrieves all public, non-archived repositories from a GitHub organization (default: Apache) and identifies which ones use GitHub Actions workflows.

## Features

- Scans all public, non-archived repositories in an organization
- Identifies repositories with GitHub Actions workflows
- Lists workflow files for each repository
- Supports detailed or simple output formats
- Respects GitHub API rate limits
- Factorized code structure from [`scan_concurrency.py`](scan_concurrency.py:1)

## Prerequisites

1. Python 3.6 or higher
2. Required packages (install via `pip install -r requirements.txt`):
   - `requests`
   - `PyYAML`

3. GitHub Personal Access Token (recommended for higher rate limits)
   - See [`GITHUB_TOKEN_SETUP.md`](GITHUB_TOKEN_SETUP.md:1) for setup instructions

## Usage

### Basic Usage

Scan Apache organization (default):
```bash
python list_repos_with_workflows.py
```

### Scan a Different Organization

```bash
python list_repos_with_workflows.py --org kubernetes
```

### Output to File (with Progress)

When using `--output`, both progress and the final report are written to the file in real-time:

```bash
python list_repos_with_workflows.py --output reports/apache_workflows.txt
```

**You'll see progress on screen AND in the file simultaneously:**
- Terminal shows: `[1/2000] Checking apache/camel... ✓ (5 workflow(s))`
- File contains the same progress in real-time
- File ends with the formatted final report

### Simple List Format

Get just repository names (useful for piping to other commands):
```bash
python list_repos_with_workflows.py --simple
```

### With GitHub Token

```bash
# Using command line argument
python list_repos_with_workflows.py --token YOUR_GITHUB_TOKEN

# Or set environment variable
export GITHUB_TOKEN=YOUR_GITHUB_TOKEN
python list_repos_with_workflows.py
```

### Adjust API Rate Limiting

```bash
# Increase delay between API calls (default: 0.5 seconds)
python list_repos_with_workflows.py --delay 1.0
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--org` | Organization to scan | `apache` |
| `--token` | GitHub personal access token | `$GITHUB_TOKEN` |
| `--delay` | Delay in seconds between API calls | `0.5` |
| `--output` | Output file path | stdout |
| `--simple` | Output simple list of repo names only | `false` |

## Output Formats

### Detailed Format (Default)

```
================================================================================
REPOSITORIES WITH GITHUB ACTIONS WORKFLOWS
Organization: apache
================================================================================

Found 1955 active repositories (45 archived repositories excluded)
Checking for GitHub Actions workflows...

[1/1955] Checking apache/camel... ✓ (5 workflow(s))
[2/1955] Checking apache/kafka... ✓ (3 workflow(s))
...

Found 150 repositories with workflows:

Repository: apache/camel
  URL: https://github.com/apache/camel
  Workflows: 5
  Files: build.yml, test.yml, release.yml, docs.yml, security.yml

Repository: apache/kafka
  URL: https://github.com/apache/kafka
  Workflows: 3
  Files: ci.yml, release.yml, docs.yml
...
```

### Simple Format (--simple)

```
apache/camel
apache/kafka
apache/spark
...
```

## Examples

### Example 1: Scan Apache with Progress Logging

```bash
# Progress shown on screen AND written to file in real-time
python list_repos_with_workflows.py --output reports/apache_workflows.txt

# You can monitor progress while it runs:
tail -f reports/apache_workflows.txt
```

### Example 2: Get Simple List for Further Processing

```bash
# Get list of repos with workflows
python list_repos_with_workflows.py --simple > repos.txt

# Use with scan_concurrency.py
while read repo; do
    python scan_concurrency.py --repo "$repo"
done < repos.txt
```

### Example 3: Scan Multiple Organizations

```bash
for org in apache kubernetes docker; do
    echo "Scanning $org..."
    python list_repos_with_workflows.py --org "$org" --output "reports/${org}_workflows.txt"
done
```

## Code Structure

The script is factorized from [`scan_concurrency.py`](scan_concurrency.py:1) and shares common patterns:

- **[`GitHubRepoScanner`](list_repos_with_workflows.py:24)** class: Main scanner with API interaction methods
- **[`_make_request()`](list_repos_with_workflows.py:42)**: Handles GitHub API requests with rate limiting
- **[`get_org_repositories()`](list_repos_with_workflows.py:62)**: Fetches all repositories from an organization
- **[`has_workflows()`](list_repos_with_workflows.py:97)**: Checks if a repository has workflow files
- **[`scan_organization()`](list_repos_with_workflows.py:117)**: Main scanning logic

## Rate Limits

- **Without token**: 60 requests/hour
- **With token**: 5,000 requests/hour

For large organizations like Apache (2000+ repos), a GitHub token is highly recommended.

## Troubleshooting

### Rate Limit Exceeded

If you hit rate limits:
1. Use a GitHub token (see [`GITHUB_TOKEN_SETUP.md`](GITHUB_TOKEN_SETUP.md:1))
2. Increase the `--delay` parameter
3. Wait for the rate limit to reset

### No Repositories Found

- Verify the organization name is correct
- Check your GitHub token has appropriate permissions
- Ensure you have network connectivity

### API Errors

- Check your GitHub token is valid
- Verify the organization exists and is public
- Review error messages in stderr

## Related Scripts

- [`scan_concurrency.py`](scan_concurrency.py:1): Scans workflows for concurrency configuration issues
- [`scan_all_apache.sh`](scan_all_apache.sh:1): Bash script for scanning Apache repositories

## License

This script is part of the scan-concurrency project.