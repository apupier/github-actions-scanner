# Queued Workflows Report Usage Guide

## Overview

The `report_queued_workflows.py` script identifies GitHub Actions workflow runs that have been stuck in the "queued" state for longer than a specified threshold (default: 2 days / 48 hours).

This is useful for detecting:
- Workflow runs waiting for unavailable runners
- Stuck jobs that may need manual intervention
- Resource allocation issues in your CI/CD pipeline

## Quick Start

### Test on a Single Repository (Recommended First)

```bash
python3 report_queued_workflows.py --repo apache/camel
```

### Scan All Apache Repositories with Workflows

```bash
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt
```

### Use Default Settings

```bash
# If no arguments provided, uses reports/apache_workflows.txt by default
python3 report_queued_workflows.py
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--repo` | Single repository to check (e.g., `apache/camel`) | None |
| `--repos-file` | File containing list of repositories | `reports/apache_workflows.txt` |
| `--threshold-hours` | Minimum hours a run must be queued to report | `48` (2 days) |
| `--token` | GitHub token (or use `GITHUB_TOKEN` env var) | From environment |
| `--delay` | Delay in seconds between API calls | `0.5` |
| `--output` | Save report to file instead of stdout | None (prints to console) |

## Usage Examples

### 1. Test with Different Threshold

```bash
# Report runs queued for more than 3 days (72 hours)
python3 report_queued_workflows.py --repo apache/camel --threshold-hours 72
```

### 2. Scan Multiple Repositories and Save Report

```bash
# Scan all repos and save to file
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt --output reports/queued_report.txt
```

### 3. Use Custom Delay for Rate Limiting

```bash
# Use 1 second delay between API calls (more conservative)
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt --delay 1.0
```

### 4. Check for Recently Queued Runs

```bash
# Report runs queued for more than 12 hours
python3 report_queued_workflows.py --repo apache/camel --threshold-hours 12
```

## Example Output

```
Testing on single repository: apache/camel

Scanning 1 repositories for workflow runs queued longer than 48 hours...
Threshold time: 2026-06-03 08:10:23.786554+00:00

[1/1] Checking apache/camel... ⚠️  Found 1 queued run(s)

================================================================================
QUEUED WORKFLOW RUNS REPORT
Threshold: 48 hours (2 days)
Report generated: 2026-06-05 08:10:24 UTC
================================================================================

⚠️  Found 1 workflow run(s) queued longer than threshold:


Repository: apache/camel
--------------------------------------------------------------------------------
  Workflow: Build and test
  Run ID: #18180 (26442254234)
  Branch: fix/CAMEL-23588 (9e54367)
  Queued since: 2026-05-26 08:49:44 UTC
  Duration: 9d 23h 20m
  URL: https://github.com/apache/camel/actions/runs/26442254234

================================================================================
SUMMARY
================================================================================
Total repositories affected: 1
Total queued runs: 1
Average queue time: 9d 23h 20m
Longest queue time: 9d 23h 20m (apache/camel)
```

## Input File Format

The script can read repository lists from files like `reports/apache_workflows.txt`. It expects lines in this format:

```
[123/456] Checking apache/camel... ✓ (4 workflow(s))
[124/456] Checking apache/kafka... ✓ (8 workflow(s))
```

The script extracts repository names (e.g., `apache/camel`) from lines containing `✓` and `Checking`.

## API Rate Limits

- **Without token**: 60 requests/hour
- **With token**: 5,000 requests/hour

Each repository requires 1+ API calls to fetch queued workflow runs (depending on pagination).

For scanning all Apache repositories (~800 with workflows):
- Estimated API calls: 800-1,600
- Estimated time with 0.5s delay: 7-13 minutes

## Exit Codes

- `0`: Success, no queued runs found exceeding threshold
- `1`: Queued runs found OR error occurred

This allows the script to be used in CI/CD pipelines:

```bash
if python3 report_queued_workflows.py --repo apache/camel; then
    echo "No stuck workflows"
else
    echo "Warning: Found stuck workflows!"
fi
```

## Integration with Other Scripts

This script complements the existing workflow scanners:

1. **list_repos_with_workflows.py** - Identifies which repos have workflows
2. **scan_concurrency.py** - Checks workflow concurrency configuration
3. **report_queued_workflows.py** - Monitors queued workflow runs (NEW)

Typical workflow:
```bash
# 1. Find repos with workflows
python3 list_repos_with_workflows.py --org apache --output reports/apache_workflows.txt

# 2. Check for configuration issues
python3 scan_concurrency.py --repos-file reports/apache_workflows.txt

# 3. Monitor for stuck runs
python3 report_queued_workflows.py --repos-file reports/apache_workflows.txt
```

## GitHub API Documentation

This script uses the GitHub Actions API:
- [List workflow runs for a repository](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository)
- Status filter: `queued`
- API version: `2022-11-28`