#!/usr/bin/env python3
"""
Rank repositories from a workflows-without-push-branches-configured.txt report
by how impactful fixing their push trigger would be.

Scoring formula
---------------
  base_score  = stars + forks * 2
  recency bonus:
    +500  if pushed within the last 30 days
    +200  if pushed within the last 90 days
    +0    otherwise
  dependabot/renovate multiplier:
    × 1.5 if .github/dependabot.yml OR a renovate config is detected

Repos are ranked highest → lowest score.

Usage:
    python rank_push_impact.py
    python rank_push_impact.py --input reports/workflows-without-push-branches-configured.txt
    python rank_push_impact.py --output reports/ranked-push-impact.txt
    python rank_push_impact.py --token <token>
"""

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RepoImpact:
    repo: str
    flagged_workflows: List[str] = field(default_factory=list)
    # enriched fields
    stars: int = 0
    forks: int = 0
    last_pushed: Optional[datetime] = None
    has_dependabot: bool = False
    enriched: bool = False
    score: float = 0.0


# ---------------------------------------------------------------------------
# Parsing the existing report
# ---------------------------------------------------------------------------

# Matches lines like:  Repository: apache/zookeeper
_REPO_LINE_RE = re.compile(r'^Repository:\s+(\S+)')
# Matches lines like:  File:    e2e.yaml
_FILE_LINE_RE = re.compile(r'^\s+File:\s+(\S+)')


def parse_report(path: str) -> Dict[str, RepoImpact]:
    """Parse the push-branches report and return a dict keyed by repo name."""
    impacts: Dict[str, RepoImpact] = {}
    current_repo: Optional[str] = None

    try:
        with open(path) as fh:
            for raw_line in fh:
                line = raw_line.rstrip()
                repo_m = _REPO_LINE_RE.match(line)
                if repo_m:
                    current_repo = repo_m.group(1)
                    if current_repo not in impacts:
                        impacts[current_repo] = RepoImpact(repo=current_repo)
                    continue

                if current_repo is None:
                    continue

                file_m = _FILE_LINE_RE.match(line)
                if file_m:
                    impacts[current_repo].flagged_workflows.append(file_m.group(1))

    except OSError as exc:
        print(f"Error reading report {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    return impacts


# ---------------------------------------------------------------------------
# GitHub API enrichment
# ---------------------------------------------------------------------------

class GitHubClient:
    RENOVATE_PATHS = [
        "renovate.json",
        "renovate.json5",
        ".github/renovate.json",
        ".github/renovate.json5",
        ".renovaterc",
        ".renovaterc.json",
    ]
    DEPENDABOT_PATH = ".github/dependabot.yml"

    def __init__(self, token: Optional[str], delay: float = 0.5):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def _get(self, url: str) -> Optional[requests.Response]:
        time.sleep(self.delay)
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None          # expected "not found"
            print(f"  HTTP error {exc.response.status_code if exc.response else '?'} for {url}",
                  file=sys.stderr)
            return None
        except requests.exceptions.RequestException as exc:
            print(f"  Request error for {url}: {exc}", file=sys.stderr)
            return None

    def enrich(self, impact: RepoImpact) -> None:
        """Fetch repo metadata + dependabot/renovate presence and update impact in-place."""
        base = f"https://api.github.com/repos/{impact.repo}"

        # --- repo metadata ---
        resp = self._get(base)
        if resp is None:
            print(f"  Could not fetch metadata for {impact.repo}", file=sys.stderr)
            return

        data = resp.json()
        impact.stars = data.get("stargazers_count", 0)
        impact.forks = data.get("forks_count", 0)
        pushed_raw = data.get("pushed_at")
        if pushed_raw:
            impact.last_pushed = datetime.fromisoformat(
                pushed_raw.replace("Z", "+00:00")
            )

        # --- dependabot ---
        dep_resp = self._get(f"{base}/contents/{self.DEPENDABOT_PATH}")
        if dep_resp is not None:
            impact.has_dependabot = True

        # --- renovate (first match wins) ---
        if not impact.has_dependabot:
            for path in self.RENOVATE_PATHS:
                rv_resp = self._get(f"{base}/contents/{path}")
                if rv_resp is not None:
                    impact.has_dependabot = True   # reuse flag; label in output says "dependabot/renovate"
                    break

        impact.enriched = True


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_score(impact: RepoImpact) -> float:
    if not impact.enriched:
        return 0.0

    base = impact.stars + impact.forks * 2

    # Recency bonus
    recency = 0
    if impact.last_pushed:
        now = datetime.now(timezone.utc)
        age_days = (now - impact.last_pushed).days
        if age_days <= 30:
            recency = 500
        elif age_days <= 90:
            recency = 200

    score = base + recency

    # Dependabot/renovate multiplier
    if impact.has_dependabot:
        score *= 1.5

    return round(score, 1)


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------

def format_date(dt: Optional[datetime]) -> str:
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d")


def print_ranked_report(ranked: List[RepoImpact], total_workflows: int) -> None:
    print(f"⚠️  Impact ranking for {len(ranked)} repositories "
          f"({total_workflows} flagged workflow(s) total)\n")
    print("Scoring: stars + forks×2 + recency bonus (≤30d +500, ≤90d +200) × 1.5 if dependabot/renovate")
    print("=" * 80)

    for rank, impact in enumerate(ranked, start=1):
        dep_label = "✓ dependabot/renovate" if impact.has_dependabot else "✗ no dependabot"
        last_push = format_date(impact.last_pushed)
        enriched_note = "" if impact.enriched else "  [enrichment failed — placed last]"

        print(f"\n#{rank:>3}  {impact.repo}{enriched_note}")
        print(f"       Score:      {impact.score:>8.0f}")
        print(f"       Stars:      {impact.stars:>8,}")
        print(f"       Forks:      {impact.forks:>8,}")
        print(f"       Last push:  {last_push:>10}")
        print(f"       Dependabot: {dep_label}")
        print(f"       Flagged workflows ({len(impact.flagged_workflows)}):")
        for wf in impact.flagged_workflows:
            print(f"         - {wf}")

    print("\n" + "=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rank repos from a push-branches report by fix impact "
            "(stars + forks + recency, boosted when dependabot/renovate is present)."
        )
    )
    parser.add_argument(
        "--input",
        default="reports/workflows-without-push-branches-configured.txt",
        help="Path to the workflows-without-push-branches-configured.txt report "
             "(default: reports/workflows-without-push-branches-configured.txt)",
    )
    parser.add_argument(
        "--output",
        help="Write the ranked report to this file instead of stdout",
    )
    parser.add_argument(
        "--token",
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between GitHub API calls (default: 0.5)",
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "Warning: no GitHub token — API rate limits will be very restrictive.\n"
            "Set GITHUB_TOKEN or use --token.",
            file=sys.stderr,
        )

    # 1. Parse existing report
    print(f"Parsing report: {args.input}", file=sys.stderr)
    impacts = parse_report(args.input)
    print(f"Found {len(impacts)} unique repositories to enrich.", file=sys.stderr)

    # 2. Enrich via GitHub API
    client = GitHubClient(token=token, delay=args.delay)
    for i, impact in enumerate(impacts.values(), start=1):
        print(f"  [{i}/{len(impacts)}] Enriching {impact.repo} …", file=sys.stderr)
        client.enrich(impact)

    # 3. Score + sort (unenriched repos go last)
    for impact in impacts.values():
        impact.score = compute_score(impact)

    ranked = sorted(
        impacts.values(),
        key=lambda x: (x.enriched, x.score),
        reverse=True,
    )

    # 4. Count total flagged workflows
    total_workflows = sum(len(r.flagged_workflows) for r in ranked)

    # 5. Output
    if args.output:
        import io
        buf = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = buf
        print_ranked_report(ranked, total_workflows)
        sys.stdout = original_stdout
        content = buf.getvalue()
        with open(args.output, "w") as fh:
            fh.write(content)
        print(f"Report written to: {args.output}", file=sys.stderr)
        # Also print to stdout so the user sees a summary
        print(content)
    else:
        print_ranked_report(ranked, total_workflows)


if __name__ == "__main__":
    main()

# Made with Bob
