from __future__ import annotations

import argparse
import os
import re
import subprocess
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


def _run_git_command(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return completed.stdout.strip()


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


def _parse_github_remote(remote_url: str) -> str | None:
    normalized = remote_url.strip()
    if not normalized:
        return None
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    if normalized.startswith("git@github.com:"):
        repo = normalized.split(":", 1)[1]
    elif normalized.startswith("https://github.com/"):
        repo = normalized[len("https://github.com/") :]
    elif normalized.startswith("ssh://git@github.com/"):
        repo = normalized[len("ssh://git@github.com/") :]
    else:
        return None

    parts = [part for part in repo.split("/") if part]
    if len(parts) != 2:
        return None
    return "/".join(parts)


def _detect_repo_from_git(start_dir: Path | None = None) -> str | None:
    cwd = (start_dir or Path.cwd()).resolve()
    try:
        repo_root = _run_git_command(["rev-parse", "--show-toplevel"], cwd=cwd)
        remote_url = _run_git_command(["config", "--get", "remote.origin.url"], cwd=Path(repo_root))
    except (OSError, subprocess.CalledProcessError):
        return None
    return _parse_github_remote(remote_url)


def _resolve_repos(repos_arg: str | None, org: str | None, start_dir: Path | None = None) -> list[str]:
    if repos_arg:
        repos = [repo.strip() for repo in repos_arg.split(",") if repo.strip()]
        if not repos:
            raise ValueError("At least one repository must be provided.")
        normalize_repo_specs(repos, org)
        return repos

    detected_repo = _detect_repo_from_git(start_dir=start_dir)
    if detected_repo:
        return [detected_repo]

    raise ValueError(
        "Unable to determine repositories automatically. Run inside a git repository with a GitHub "
        "'origin' remote or provide --repos explicitly."
    )


def _slugify_filename_part(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return slug.strip("._-") or "report"


def _normalize_week_label(value: str) -> str:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid week format '{value}'. Use WW-YYYY or YYYY-Www, for example 05-2026 or 2026-W05."
        )
    if parts[0].isdigit() and len(parts[0]) == 4 and parts[1].startswith("W") and parts[1][1:].isdigit():
        return f"{int(parts[1][1:]):02d}-{parts[0]}"
    if parts[0].isdigit() and parts[1].isdigit() and len(parts[1]) == 4:
        return f"{int(parts[0]):02d}-{parts[1]}"
    raise ValueError(
        f"Invalid week format '{value}'. Use WW-YYYY or YYYY-Www, for example 05-2026 or 2026-W05."
    )


def _default_output_path(
    developer: str,
    report_format: str,
    date_from,
    date_to,
    week: str | None = None,
) -> Path:
    extension = "md" if report_format == "markdown" else "json"
    if week:
        period = f"week-{_normalize_week_label(week)}"
    else:
        period = f"{date_from.date().isoformat()}_to_{date_to.date().isoformat()}"
    filename = f"{_slugify_filename_part(developer)}_{period}.{extension}"
    return Path("report") / filename


def _resolve_output_path(
    output: str | None,
    developer: str,
    report_format: str,
    date_from,
    date_to,
    week: str | None = None,
) -> Path:
    if output:
        return Path(output)
    return _default_output_path(developer, report_format, date_from, date_to, week=week)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-dev-metrics",
        description="Collect GitHub developer metrics for a specified date range and repository list.",
    )
    parser.add_argument("--developer", required=True, help="GitHub username to analyze.")
    parser.add_argument("--org", help="Default organization for repository names without an owner.")
    parser.add_argument(
        "--repos",
        help="Comma-separated list of repositories, either repo names or owner/repo values. Defaults to the current git repo when available.",
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
        help="Week selector in WW-YYYY or YYYY-Www format, for example 05-2026 or 2026-W05. Overrides --from and --to.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
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
        help="Write the report to this path. If omitted, a file is written under report/ automatically.",
    )
    return parser


def _write_output(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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
        repos = _resolve_repos(args.repos, args.org)
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
        output_path = _resolve_output_path(
            args.output,
            args.developer,
            args.format,
            date_from,
            date_to,
            week=args.week,
        )
        written_path = _write_output(report, output_path)
        sys.stdout.write(f"Wrote {written_path}\n")
        return 0
    except (ValueError, GithubAuthError, GithubAPIError) as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
