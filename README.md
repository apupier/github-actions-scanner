# GitHub Actions Concurrency Scanner

A Python script to scan GitHub Actions workflows for missing or incorrect concurrency configuration in Apache projects.

## Purpose

This script identifies GitHub Actions workflows that:
- Trigger on `pull_request` events
- Don't have proper `concurrency.cancel-in-progress` configuration
- Should have `cancel-in-progress` set to `true` or `${{ github.ref != 'refs/heads/main' }}`

Proper concurrency configuration helps prevent wasted CI resources by canceling outdated workflow runs when new commits are pushed to a pull request.

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

## Usage

### Scan a single repository

```bash
python scan_concurrency.py --repo apache/camel
```

### Scan all repositories in an organization

```bash
python scan_concurrency.py --org apache --all
```

### With custom delay to avoid rate limiting

```bash
python scan_concurrency.py --repo apache/camel --delay 2.0
```

### Save report to file

```bash
python scan_concurrency.py --repo apache/camel --output report.txt
```

### With GitHub token

```bash
python scan_concurrency.py --repo apache/camel --token YOUR_TOKEN
```

## Command Line Options

- `--repo OWNER/NAME`: Scan a specific repository (e.g., `apache/camel`)
- `--org ORG`: Specify organization name (e.g., `apache`)
- `--all`: Scan all repositories in the organization (use with `--org`)
- `--token TOKEN`: GitHub personal access token (or set `GITHUB_TOKEN` env var)
- `--delay SECONDS`: Delay between API calls in seconds (default: 1.0)
- `--output FILE`: Save report to file instead of printing to stdout

## Issue Types

The script detects the following issues:

1. **MISSING_CONCURRENCY**: Workflow triggers on pull_request but has no concurrency configuration
2. **MISSING_CANCEL_IN_PROGRESS**: Concurrency is defined but `cancel-in-progress` is not set
3. **INCORRECT_CANCEL_IN_PROGRESS**: `cancel-in-progress` has an incorrect value
4. **YAML_PARSE_ERROR**: Unable to parse the workflow YAML file

## Example Output

```
Scanning repository: apache/camel
  Found 15 workflow file(s)
  Checking: build.yml
    ✓ OK
  Checking: pr-build.yml
    ⚠️  Issue found: MISSING_CONCURRENCY
  Checking: daily.yml
    ✓ OK

⚠️  Found 1 issue(s):

================================================================================

Repository: apache/camel
--------------------------------------------------------------------------------
  File: pr-build.yml
  Issue: MISSING_CONCURRENCY
  Details: Workflow triggers on pull_request but has no concurrency configuration
```

## Valid Concurrency Configurations

The script accepts the following as valid `cancel-in-progress` values:

1. Boolean `true`:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

2. Conditional expression (don't cancel on main branch):
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
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

## Testing on Apache Camel

To test the script on the Apache Camel project before running on all Apache repositories:

```bash
python scan_concurrency.py --repo apache/camel --delay 1.5
```

This will scan all workflow files in the apache/camel repository with a 1.5-second delay between API calls.

**Test Results**: The apache/camel repository has been tested and all 17 workflow files have proper concurrency configuration! ✅

## Scanning All Apache Repositories

A convenience script is provided to scan all Apache repositories:

```bash
./scan_all_apache.sh
```

This script will:
- Check if `GITHUB_TOKEN` is set (recommended)
- Create a `reports/` directory
- Generate a timestamped report file
- Scan all Apache repositories with a 2-second delay between API calls
- Save the results to `reports/apache_scan_TIMESTAMP.txt`

**Warning**: Scanning all Apache repositories will take a considerable amount of time and make many API calls. Make sure you have a GitHub token set to avoid rate limits.

## License

This script is provided as-is for scanning Apache project repositories.