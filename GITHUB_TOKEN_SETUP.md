# GitHub Token Setup Guide

## Why You Need a Token

Without a GitHub token:
- **Rate limit**: 60 requests per hour
- **Result**: Can only scan ~10-15 repositories before hitting the limit

With a GitHub token:
- **Rate limit**: 5,000 requests per hour
- **Result**: Can scan hundreds of repositories

## How to Create a GitHub Personal Access Token

1. Go to GitHub Settings: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Apache Workflow Scanner")
4. Select scopes:
   - ✅ `public_repo` (for public repositories)
   - OR ✅ `repo` (if you need private repo access)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)

## How to Use the Token

### Option 1: Environment Variable (Recommended)

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Then run the scan:
```bash
./scan_all_apache.sh
```

Or directly:
```bash
python scan_concurrency.py --org apache --all --delay 2.0
```

### Option 2: Command Line Parameter

```bash
python scan_concurrency.py --org apache --all --delay 2.0 --token ghp_your_token_here
```

### Option 3: Add to Shell Profile (Persistent)

Add to `~/.bashrc` or `~/.zshrc`:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Then reload:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Verify Token is Set

```bash
echo $GITHUB_TOKEN
```

Should display your token (or at least show it's set).

## Current Scan Status

The scan was attempted but hit rate limits after checking only a few repositories:
- Some repos don't have `.github/workflows` (404 errors - normal)
- Rate limit hit at apache/apr (403 errors - need token)

## Next Steps

1. Create and set your GitHub token
2. Run the scan again:
   ```bash
   python scan_concurrency.py --org apache --all --delay 2.0 2>&1 | tee reports/apache_full_scan.txt
   ```

3. The scan will show real-time progress for each repository
4. Results will be saved to `reports/apache_full_scan.txt`

## Estimated Time

With a 2-second delay between API calls:
- ~2000 Apache repositories
- ~3-5 workflow files per repo (average)
- Approximately 2-4 hours for a complete scan

## Alternative: Scan Specific Repositories

If you don't want to scan all Apache repos, you can scan specific ones:

```bash
# Scan multiple specific repos
for repo in camel kafka spark flink; do
  python scan_concurrency.py --repo apache/$repo --delay 1.5
done