from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import DeveloperMetrics, EvidenceSummary, PullRequestRecord


def is_test_file(filename: str) -> bool:
    normalized = filename.lower()
    return any(
        pattern in normalized
        for pattern in (".test.", ".spec.", "__tests__", "/tests/", "/test/")
    )


def is_noisy_commit_message(message: str) -> bool:
    normalized = message.lower().strip()
    noisy_patterns = ("wip", "fixup", "revert", "merge branch", "merge remote")
    return any(pattern in normalized for pattern in noisy_patterns)


def is_revert_commit(message: str) -> bool:
    normalized = message.lower().strip()
    return normalized.startswith("revert") or "revert" in normalized


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _days_between(start: str, end: str | None) -> float | None:
    dt_start = _parse_dt(start)
    dt_end = _parse_dt(end)
    if not dt_start or not dt_end:
        return None
    return (dt_end - dt_start).total_seconds() / 86400.0


def _review_state_counts(pr: PullRequestRecord) -> dict[str, int]:
    counts: dict[str, int] = {}
    for review in pr.reviews:
        counts[review.state] = counts.get(review.state, 0) + 1
    return counts


def _has_test_changes(pr: PullRequestRecord) -> tuple[bool, list[str]]:
    files = [file.filename for file in pr.files if is_test_file(file.filename)]
    return (len(files) > 0, files)


def calculate_metrics(data: DeveloperMetrics) -> DeveloperMetrics:
    prs = data.prs
    commits = data.commits

    merged_prs = [pr for pr in prs if pr.merged_at]
    closed_without_merge = [pr for pr in prs if pr.state == "closed" and not pr.merged_at]
    open_prs = [pr for pr in prs if pr.state == "open"]
    requested_changes = [pr for pr in prs if any(review.state == "CHANGES_REQUESTED" for review in pr.reviews)]
    multiple_review_iterations = [pr for pr in prs if len(pr.reviews) > 1]

    prs_with_tests: list[PullRequestRecord] = []
    prs_without_tests: list[PullRequestRecord] = []
    pr_test_files: dict[str, list[str]] = {}
    pr_noisy_commits: dict[str, list[str]] = {}
    pr_review_iterations: dict[str, int] = {}
    pr_time_to_merge_days: dict[str, float | None] = {}
    pr_review_states: dict[str, dict[str, int]] = {}
    pr_large_by_files = sorted(prs, key=lambda pr: pr.changed_files, reverse=True)
    pr_large_by_lines = sorted(prs, key=lambda pr: pr.additions + pr.deletions, reverse=True)
    average_pr_size = 0.0

    total_size = 0
    for pr in prs:
        has_tests, files = _has_test_changes(pr)
        if has_tests:
            prs_with_tests.append(pr)
            pr_test_files[f"{pr.repo}#{pr.number}"] = files
        else:
            prs_without_tests.append(pr)
            pr_test_files[f"{pr.repo}#{pr.number}"] = []

        noisy_commits = [commit.message for commit in pr.commits if is_noisy_commit_message(commit.message)]
        if noisy_commits:
            pr_noisy_commits[f"{pr.repo}#{pr.number}"] = noisy_commits
        pr_review_iterations[f"{pr.repo}#{pr.number}"] = len(pr.reviews)
        pr_review_states[f"{pr.repo}#{pr.number}"] = _review_state_counts(pr)
        if pr.merged_at:
            days = _days_between(pr.created_at, pr.merged_at)
            pr_time_to_merge_days[f"{pr.repo}#{pr.number}"] = days
        else:
            pr_time_to_merge_days[f"{pr.repo}#{pr.number}"] = None
        total_size += pr.additions + pr.deletions

    if prs:
        average_pr_size = total_size / len(prs)

    merged_without_test_changes = [
        pr for pr in merged_prs if not _has_test_changes(pr)[0]
    ]
    noisy_prs = [pr for pr in prs if f"{pr.repo}#{pr.number}" in pr_noisy_commits]
    long_time_to_merge = [
        pr for pr in merged_prs if (_days_between(pr.created_at, pr.merged_at) or 0) > 7
    ]

    submitted_reviews = sum(len(item.submitted_reviews) for item in data.review_participation)
    review_comments = sum(len(item.review_comments) for item in data.review_participation)
    commits_noisy = [commit for commit in commits if is_noisy_commit_message(commit.message)]
    revert_commits = [commit for commit in commits if is_revert_commit(commit.message)]

    positive_signals: list[str] = []
    if merged_prs:
        positive_signals.append(f"Merged {len(merged_prs)} PR(s) during the period.")
    if prs_with_tests:
        positive_signals.append(f"{len(prs_with_tests)} PR(s) touched automated test files.")
    if submitted_reviews:
        positive_signals.append(f"Submitted {submitted_reviews} review(s) on other PRs.")
    if commits:
        positive_signals.append(f"Authored {len(commits)} commit(s) in the selected repositories.")

    opportunity_signals: list[str] = []
    if merged_without_test_changes:
        opportunity_signals.append(
            f"{len(merged_without_test_changes)} merged PR(s) did not touch obvious test files."
        )
    if requested_changes:
        opportunity_signals.append(
            f"{len(requested_changes)} PR(s) received CHANGES_REQUESTED reviews."
        )
    if noisy_prs:
        opportunity_signals.append(f"{len(noisy_prs)} PR(s) included noisy commit messages.")
    if long_time_to_merge:
        opportunity_signals.append(
            f"{len(long_time_to_merge)} merged PR(s) took more than 7 days to merge."
        )
    if commits_noisy:
        opportunity_signals.append(
            f"{len(commits_noisy)} commit(s) used noisy commit messages."
        )

    metrics: dict[str, Any] = {
        "pull_requests": {
            "opened": len(prs),
            "merged": len(merged_prs),
            "closed_without_merge": len(closed_without_merge),
            "open": len(open_prs),
            "requested_changes": len(requested_changes),
            "multiple_review_iterations": len(multiple_review_iterations),
            "with_review_comments": sum(1 for pr in prs if pr.review_comments),
            "long_time_to_merge": len(long_time_to_merge),
            "merged_without_test_changes": len(merged_without_test_changes),
            "with_tests": len(prs_with_tests),
            "without_tests": len(prs_without_tests),
            "average_pr_size": average_pr_size,
            "largest_by_changed_files": [
                {
                    "repo": pr.repo,
                    "number": pr.number,
                    "title": pr.title,
                    "changed_files": pr.changed_files,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "url": pr.url,
                }
                for pr in pr_large_by_files[:5]
            ],
            "largest_by_line_changes": [
                {
                    "repo": pr.repo,
                    "number": pr.number,
                    "title": pr.title,
                    "changed_files": pr.changed_files,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "url": pr.url,
                }
                for pr in pr_large_by_lines[:5]
            ],
        },
        "testing": {
            "prs_with_tests": len(prs_with_tests),
            "prs_without_tests": len(prs_without_tests),
            "pr_test_files": pr_test_files,
            "merged_without_test_changes": [
                {"repo": pr.repo, "number": pr.number, "title": pr.title, "url": pr.url}
                for pr in merged_without_test_changes
            ],
        },
        "git_hygiene": {
            "prs_with_noisy_commits": [
                {
                    "repo": pr.repo,
                    "number": pr.number,
                    "title": pr.title,
                    "url": pr.url,
                    "messages": pr_noisy_commits[f"{pr.repo}#{pr.number}"],
                }
                for pr in noisy_prs
            ],
            "noisy_commit_messages": [commit.message for commit in commits_noisy],
            "revert_commits": [commit.message for commit in revert_commits],
        },
        "commit_activity": {
            "authored_commits": len(commits),
            "messages": [commit.message for commit in commits],
            "urls": [commit.url for commit in commits if commit.url],
            "noisy_commits": [commit.message for commit in commits_noisy],
            "revert_commits": [commit.message for commit in revert_commits],
        },
        "review_participation": {
            "submitted_reviews": submitted_reviews,
            "review_comments": review_comments,
            "items": [item.to_dict() for item in data.review_participation],
        },
        "evidence": {
            "pr_review_states": pr_review_states,
            "pr_review_iterations": pr_review_iterations,
            "pr_time_to_merge_days": pr_time_to_merge_days,
        },
    }

    data.metrics = metrics
    data.summary = EvidenceSummary(
        positive_signals=positive_signals,
        opportunity_signals=opportunity_signals,
    )
    return data
