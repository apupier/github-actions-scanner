# Quick Start Guide

## Prerequisites

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. (Recommended) Set GitHub token to avoid rate limits:
```bash
export GITHUB_TOKEN=your_github_personal_access_token
```

## Basic Usage

### Test on a single repository (apache/camel)
```bash
python scan_concurrency.py --repo apache/camel --delay 1.5
```

### Scan all Apache repositories
```bash
./scan_all_apache.sh
```

This will create a report in `reports/apache_scan_TIMESTAMP.txt`

## What the Script Checks

The script looks for GitHub Actions workflows that:
1. Trigger on `pull_request` events
2. Are missing `concurrency` configuration OR
3. Have `concurrency` but `cancel-in-progress` is not set correctly

## Valid Configurations

✅ **Option 1: Always cancel**
```yaml
on:
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

✅ **Option 2: Cancel except on main branch**
```yaml
on:
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

## Understanding the Output

### No Issues Found
```
✅ No issues found! All workflows have proper concurrency configuration.
```

### Issues Found
```
⚠️  Found 2 issue(s):

Repository: apache/example
--------------------------------------------------------------------------------
  File: build.yml
  Issue: MISSING_CONCURRENCY
  Details: Workflow triggers on pull_request but has no concurrency configuration

  File: test.yml
  Issue: INCORRECT_CANCEL_IN_PROGRESS
  Details: cancel-in-progress is set to 'false' but should be true or ${{ github.ref != 'refs/heads/main' }}
```

## Rate Limiting Tips

- **Without token**: 60 requests/hour (very limited)
- **With token**: 5000 requests/hour (recommended)
- Default delay: 1 second between requests
- Increase delay with `--delay 2.0` for extra safety
- The script automatically adds delays between API calls

## Common Commands

```bash
# Single repo with custom delay
python scan_concurrency.py --repo apache/camel --delay 2.0

# Save output to file
python scan_concurrency.py --repo apache/camel --output report.txt

# Scan with explicit token
python scan_concurrency.py --repo apache/camel --token YOUR_TOKEN

# All Apache repos (takes a long time!)
python scan_concurrency.py --org apache --all --delay 2.0
```

## Troubleshooting

### Rate Limit Errors
- Set `GITHUB_TOKEN` environment variable
- Increase `--delay` value
- Wait and try again later

### Permission Errors
- Ensure your GitHub token has `repo` scope
- Check if the repository is public or if you have access

### YAML Parse Errors
- The workflow file may have syntax errors
- Check the file manually on GitHub