#!/bin/bash
# Script to scan all Apache repositories for concurrency issues
# This will take a long time - use with caution!

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Warning: GITHUB_TOKEN environment variable is not set."
    echo "You may hit rate limits. Set it with: export GITHUB_TOKEN=your_token"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create output directory
OUTPUT_DIR="reports"
mkdir -p "$OUTPUT_DIR"

# Generate timestamp for the report
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$OUTPUT_DIR/apache_scan_$TIMESTAMP.txt"

echo "Starting scan of all Apache repositories..."
echo "Report will be saved to: $REPORT_FILE"
echo ""

# Run the scan with a 2-second delay to be extra safe
python scan_concurrency.py --org apache --all --delay 2.0 --output "$REPORT_FILE"

EXIT_CODE=$?

echo ""
echo "Scan complete!"
echo "Report saved to: $REPORT_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ No issues found in any repository!"
else
    echo "⚠️  Issues found. Check the report for details."
fi

exit $EXIT_CODE

# Made with Bob
