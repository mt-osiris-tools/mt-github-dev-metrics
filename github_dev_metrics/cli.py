from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .collectors import (
    collect_metrics,
    end_of_day,
    normalize_repo_specs,
    parse_iso_date,
    parse_iso_week,
    start_of_day,
)
from .github_client import GithubAPIError, GithubAuthError, GithubClient
from .metrics import calculate_metrics
from .report_json import render_json_report
from .report_markdown import render_markdown_report


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].lstrip()
    if "=" not in text:
        return None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return key, value


def _load_local_env_file(start_dir: Path | None = None) -> Path | None:
    current = (start_dir or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        env_path = directory / ".env"
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)
        return env_path
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-dev-metrics",
        description="Collect GitHub developer metrics for a specified date range and repository list.",
    )
    parser.add_argument("--developer", required=True, help="GitHub username to analyze.")
    parser.add_argument("--org", help="Default organization for repository names without an owner.")
    parser.add_argument(
        "--repos",
        required=True,
        help="Comma-separated list of repositories, either repo names or owner/repo values.",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        help="Start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        help="End date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--week",
        help="ISO week in YYYY-Www format, for example 2026-W18. Overrides --from and --to.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--cadence-target",
        type=float,
        default=0.6,
        help="Commit cadence coverage target as a fraction (default: 0.6).",
    )
    parser.add_argument(
        "--cadence-min-days",
        type=int,
        default=5,
        help="Minimum number of active commit days for the cadence signal (default: 5).",
    )
    parser.add_argument(
        "--output",
        help="Write the report to this path instead of stdout.",
    )
    return parser


def _write_output(text: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _load_local_env_file()
        if args.week:
            if args.date_from or args.date_to:
                raise ValueError("Use either --week or --from/--to, not both.")
            date_from, date_to = parse_iso_week(args.week)
        else:
            if not args.date_from or not args.date_to:
                raise ValueError("Provide either --week or both --from and --to.")
            date_from = start_of_day(parse_iso_date(args.date_from))
            date_to = end_of_day(parse_iso_date(args.date_to))
        if date_from > date_to:
            raise ValueError("--from must be earlier than or equal to --to.")
        if not 0 < args.cadence_target <= 1:
            raise ValueError("--cadence-target must be a fraction between 0 and 1.")
        if args.cadence_min_days < 1:
            raise ValueError("--cadence-min-days must be at least 1.")
        repos = [repo.strip() for repo in args.repos.split(",") if repo.strip()]
        if not repos:
            raise ValueError("At least one repository must be provided.")
        # Validate early so errors are user-friendly before any API calls happen.
        normalize_repo_specs(repos, args.org)
        client = GithubClient.from_env()
        metrics = collect_metrics(client, args.developer, args.org, repos, date_from, date_to)
        calculated = calculate_metrics(
            metrics,
            cadence_target=args.cadence_target,
            cadence_min_active_days=args.cadence_min_days,
        )
        if args.format == "markdown":
            report = render_markdown_report(calculated)
        else:
            report = render_json_report(calculated)
        _write_output(report, args.output)
        return 0
    except (ValueError, GithubAuthError, GithubAPIError) as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
