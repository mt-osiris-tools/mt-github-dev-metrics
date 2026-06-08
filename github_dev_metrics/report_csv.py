from __future__ import annotations

import csv
from io import StringIO

from .models import DeveloperMetrics, PullRequestRecord

CSV_COLUMNS = [
    "developer",
    "org",
    "date_from",
    "date_to",
    "repo_count",
    "repos",
    "repo",
    "pr_number",
    "pr_title",
    "pr_url",
    "pr_state",
    "pr_author",
    "created_at",
    "merged_at",
    "closed_at",
    "time_to_merge_days",
    "additions",
    "deletions",
    "changed_files",
    "total_line_changes",
    "review_count",
    "review_comment_count",
    "changes_requested_count",
    "approved_count",
    "commented_review_count",
    "review_iteration_count",
    "has_test_changes",
    "test_file_count",
    "test_files",
    "has_noisy_commits",
    "noisy_commit_count",
    "noisy_commit_messages",
    "is_merged",
    "is_closed_without_merge",
    "is_open",
    "is_long_time_to_merge",
    "is_merged_without_test_changes",
    "pr_commit_count",
    "pr_commit_messages",
]


def _join(values: list[str]) -> str:
    return "|".join(value for value in values if value)


def _pr_key(pr: PullRequestRecord) -> str:
    return f"{pr.repo}#{pr.number}"


def _review_state_count(pr: PullRequestRecord, state: str) -> int:
    return sum(1 for review in pr.reviews if review.state == state)


def _build_pr_row(
    data: DeveloperMetrics,
    pr: PullRequestRecord,
) -> dict[str, object]:
    metrics = data.metrics
    contributions = metrics.get("developer_contributions", {})
    evidence = metrics.get("evidence", {})
    testing = metrics.get("testing", {})
    noisy_map = {
        f"{item['repo']}#{item['number']}": item["messages"]
        for item in metrics.get("git_hygiene", {}).get("prs_with_noisy_commits", [])
    }
    merged_without_tests = {
        f"{item['repo']}#{item['number']}"
        for item in testing.get("merged_without_test_changes", [])
    }
    key = _pr_key(pr)
    test_files = testing.get("pr_test_files", {}).get(key, [])
    noisy_messages = noisy_map.get(key, [])
    review_comment_count = len(pr.review_comments)
    pr_commit_messages = [commit.message for commit in pr.commits if commit.message]

    return {
        "developer": data.developer,
        "org": data.org or "",
        "date_from": data.date_from,
        "date_to": data.date_to,
        "repo_count": contributions.get("repo_count", 0),
        "repos": _join(data.repos),
        "repo": pr.repo,
        "pr_number": pr.number,
        "pr_title": pr.title,
        "pr_url": pr.url,
        "pr_state": pr.state,
        "pr_author": pr.author,
        "created_at": pr.created_at,
        "merged_at": pr.merged_at or "",
        "closed_at": pr.closed_at or "",
        "time_to_merge_days": evidence.get("pr_time_to_merge_days", {}).get(key, ""),
        "additions": pr.additions,
        "deletions": pr.deletions,
        "changed_files": pr.changed_files,
        "total_line_changes": pr.additions + pr.deletions,
        "review_count": len(pr.reviews),
        "review_comment_count": review_comment_count,
        "changes_requested_count": _review_state_count(pr, "CHANGES_REQUESTED"),
        "approved_count": _review_state_count(pr, "APPROVED"),
        "commented_review_count": _review_state_count(pr, "COMMENTED"),
        "review_iteration_count": evidence.get("pr_review_iterations", {}).get(key, len(pr.reviews)),
        "has_test_changes": bool(test_files),
        "test_file_count": len(test_files),
        "test_files": _join(test_files),
        "has_noisy_commits": bool(noisy_messages),
        "noisy_commit_count": len(noisy_messages),
        "noisy_commit_messages": _join(noisy_messages),
        "is_merged": bool(pr.merged_at),
        "is_closed_without_merge": pr.state == "closed" and not pr.merged_at,
        "is_open": pr.state == "open",
        "is_long_time_to_merge": (
            evidence.get("pr_time_to_merge_days", {}).get(key) or 0
        ) > 7,
        "is_merged_without_test_changes": key in merged_without_tests,
        "pr_commit_count": len(pr.commits),
        "pr_commit_messages": _join(pr_commit_messages),
    }


def render_csv_report(data: DeveloperMetrics) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for pr in data.prs:
        writer.writerow(_build_pr_row(data, pr))
    return buffer.getvalue()
