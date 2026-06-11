from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from .github_client import GithubClient, GithubError, GithubAPIError
from .models import (
    CommitRecord,
    DeveloperMetrics,
    EvidenceSummary,
    PullRequestCommit,
    PullRequestFile,
    PullRequestRecord,
    PullRequestReview,
    ReviewThread,
    ReviewThreadComment,
    RepoRef,
    ReviewParticipationRecord,
)


TEST_FILE_PATTERNS = (
    ".test.",
    ".spec.",
    "__tests__",
    "/tests/",
    "/test/",
)

NOISY_COMMIT_PATTERNS = (
    r"\bwip\b",
    r"\bfixup\b",
    r"\brevert\b",
    r"\bmerge branch\b",
    r"\bmerge remote\b",
)


def parse_iso_date(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date format '{value}'. Use YYYY-MM-DD.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def start_of_day(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)


def parse_iso_week(value: str) -> tuple[datetime, datetime]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid week format '{value}'. Use WW-YYYY or YYYY-Www, for example 05-2026 or 2026-W05."
        )

    if parts[0].isdigit() and len(parts[0]) == 4 and parts[1].startswith("W") and parts[1][1:].isdigit():
        year = int(parts[0])
        week = int(parts[1][1:])
    elif parts[0].isdigit() and parts[1].isdigit() and len(parts[1]) == 4:
        week = int(parts[0])
        year = int(parts[1])
    else:
        raise ValueError(
            f"Invalid week format '{value}'. Use WW-YYYY or YYYY-Www, for example 05-2026 or 2026-W05."
        )

    try:
        start = date.fromisocalendar(year, week, 1)
        end = date.fromisocalendar(year, week, 7)
    except ValueError as exc:
        raise ValueError(
            f"Invalid week value '{value}'. Use a valid ISO week like 05-2026 or 2026-W05."
        ) from exc
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc)
    return start_dt, end_dt


def normalize_repo_specs(repos: list[str], org: str | None) -> list[RepoRef]:
    normalized: list[RepoRef] = []
    for raw in repos:
        value = raw.strip()
        if not value:
            continue
        if "/" in value:
            parts = value.split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"Invalid repo format '{raw}'. Use 'repo' with --org or 'owner/repo'."
                )
            normalized.append(RepoRef(owner=parts[0], name=parts[1]))
            continue
        if not org:
            raise ValueError(
                f"Invalid repo format '{raw}'. Provide --org for repo names without an owner."
            )
        normalized.append(RepoRef(owner=org, name=value))
    if not normalized:
        raise ValueError("At least one repository must be provided.")
    return normalized


def is_test_file(filename: str) -> bool:
    normalized = filename.lower()
    return any(pattern in normalized for pattern in TEST_FILE_PATTERNS)


def is_noisy_commit_message(message: str) -> bool:
    normalized = message.lower().strip()
    return any(re.search(pattern, normalized) for pattern in NOISY_COMMIT_PATTERNS)


def is_revert_commit(message: str) -> bool:
    normalized = message.lower().strip()
    return normalized.startswith("revert") or "revert" in normalized


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _within_range(value: str | None, start: datetime, end: datetime) -> bool:
    dt = _parse_datetime(value)
    if dt is None:
        return False
    return start <= dt <= end


def _extract_pr_from_search_item(item: dict[str, Any]) -> tuple[str | None, int | None]:
    url = str(item.get("html_url") or item.get("pull_request", {}).get("url") or "")
    if not url:
        return None, None
    parts = url.rstrip("/").split("/")
    try:
        number = int(parts[-1])
        owner = parts[-4]
        repo = parts[-3]
        return f"{owner}/{repo}", number
    except (IndexError, ValueError):
        return None, None


def _pull_review_records(client: GithubClient, repo: RepoRef, number: int, developer: str) -> tuple[list[PullRequestReview], list[dict[str, Any]]]:
    reviews_raw = client.list_pull_reviews(repo, number)
    review_comments_raw = client.list_pull_review_comments(repo, number)
    reviews = [
        PullRequestReview(
            user=str(review.get("user", {}).get("login", "")),
            state=str(review.get("state", "")),
            submitted_at=review.get("submitted_at"),
            body=review.get("body"),
        )
        for review in reviews_raw
    ]
    review_comments = [
        {
            "user": str(comment.get("user", {}).get("login", "")),
            "body": comment.get("body"),
            "path": comment.get("path"),
            "created_at": comment.get("created_at"),
        }
        for comment in review_comments_raw
    ]
    return reviews, review_comments


def _pull_review_threads(client: GithubClient, repo: RepoRef, number: int) -> list[ReviewThread]:
    threads_raw = client.list_pull_review_threads(repo, number)
    threads: list[ReviewThread] = []
    for thread in threads_raw:
        comments_raw = thread.get("comments", {}).get("nodes", [])
        comments = [
            ReviewThreadComment(
                id=str(comment.get("id", "")),
                author=str(comment.get("author", {}).get("login", "")),
                body=comment.get("body"),
                created_at=comment.get("createdAt"),
                is_reply=bool(comment.get("replyTo")),
            )
            for comment in comments_raw
            if isinstance(comment, dict)
        ]
        threads.append(
            ReviewThread(
                id=str(thread.get("id", "")),
                is_resolved=bool(thread.get("isResolved")),
                resolved_by=thread.get("resolvedBy", {}).get("login") if thread.get("resolvedBy") else None,
                comments=comments,
            )
        )
    return threads


def collect_metrics(
    client: GithubClient,
    developer: str,
    org: str | None,
    repos: list[str],
    date_from: datetime,
    date_to: datetime,
    progress: Callable[[str], None] | None = None,
) -> DeveloperMetrics:
    repo_refs = normalize_repo_specs(repos, org)
    pr_records: list[PullRequestRecord] = []
    commit_records: list[CommitRecord] = []
    review_participation: list[ReviewParticipationRecord] = []
    limitations: list[str] = []
    review_thread_limitation_added = False

    for index, repo in enumerate(repo_refs, start=1):
        if progress is not None:
            progress(f"Collecting {repo.full_name} ({index}/{len(repo_refs)})...")
        pulls = client.list_repo_pulls(repo, state="all")
        for pull in pulls:
            author = str(pull.get("user", {}).get("login", ""))
            created_at = pull.get("created_at")
            if author != developer or not _within_range(created_at, date_from, date_to):
                continue
            number = int(pull["number"])
            detailed = client.get_pull(repo, number)
            files_raw = client.list_pull_files(repo, number)
            commits_raw = client.list_pull_commits(repo, number)
            reviews, review_comments = _pull_review_records(client, repo, number, developer)
            review_threads: list[ReviewThread] = []
            try:
                review_threads = _pull_review_threads(client, repo, number)
            except GithubError:
                if not review_thread_limitation_added:
                    limitations.append(
                        "Review thread resolution is best-effort; GitHub GraphQL access or visibility constraints may hide unresolved threads."
                    )
                    review_thread_limitation_added = True
            files = [
                PullRequestFile(
                    filename=str(item.get("filename", "")),
                    additions=int(item.get("additions", 0) or 0),
                    deletions=int(item.get("deletions", 0) or 0),
                    changes=int(item.get("changes", 0) or 0),
                    status=str(item.get("status", "")),
                )
                for item in files_raw
            ]
            commits = [
                PullRequestCommit(
                    sha=str(item.get("sha", "")),
                    message=str(item.get("commit", {}).get("message", "")),
                    url=item.get("html_url"),
                    authored_at=item.get("commit", {}).get("author", {}).get("date"),
                )
                for item in commits_raw
            ]
            pr_records.append(
                PullRequestRecord(
                    repo=repo.full_name,
                    number=number,
                    title=str(detailed.get("title", "")),
                    url=str(detailed.get("html_url", "")),
                    state=str(detailed.get("state", "")),
                    author=author,
                    created_at=str(detailed.get("created_at", created_at)),
                    merged_at=detailed.get("merged_at"),
                    closed_at=detailed.get("closed_at"),
                    additions=int(detailed.get("additions", 0) or 0),
                    deletions=int(detailed.get("deletions", 0) or 0),
                    changed_files=int(detailed.get("changed_files", len(files)) or 0),
                    reviews=reviews,
                    review_comments=review_comments,
                    review_threads=review_threads,
                    files=files,
                    commits=commits,
                    merged_by=detailed.get("merged_by", {}).get("login") if detailed.get("merged_by") else None,
                )
            )

        commits_raw = client.list_repo_commits(repo, developer, date_from, date_to)
        for item in commits_raw:
            commit_records.append(
                CommitRecord(
                    repo=repo.full_name,
                    sha=str(item.get("sha", "")),
                    message=str(item.get("commit", {}).get("message", "")),
                    url=item.get("html_url"),
                    authored_at=item.get("commit", {}).get("author", {}).get("date"),
                )
            )

        # Best-effort review participation search. GitHub search supports reviewed-by queries,
        # but it is limited to visible PRs and may miss some comments.
        try:
            search_results = client.search_issues(
                f'type:pr reviewed-by:{developer} repo:{repo.full_name} updated:{date_from.date()}..{date_to.date()}'
            )
            seen: set[tuple[str, int]] = set()
            for item in search_results:
                pr_repo, number = _extract_pr_from_search_item(item)
                if not pr_repo or number is None:
                    continue
                key = (pr_repo, number)
                if key in seen:
                    continue
                seen.add(key)
                repo_ref = RepoRef(*pr_repo.split("/", 1))
                reviews, review_comments = _pull_review_records(client, repo_ref, number, developer)
                submitted_reviews = [review for review in reviews if review.user == developer]
                submitted_comments = [comment for comment in review_comments if comment.get("user") == developer]
                if submitted_reviews or submitted_comments:
                    review_participation.append(
                        ReviewParticipationRecord(
                            repo=pr_repo,
                            number=number,
                            title=str(item.get("title", "")),
                            url=str(item.get("html_url", "")),
                            state=str(item.get("state", "")),
                            submitted_reviews=submitted_reviews,
                            review_comments=submitted_comments,
                        )
                    )
        except GithubError:
            limitations.append(
                "Review participation is best-effort; GitHub search or visibility constraints may hide some review activity."
            )

    if not pr_records and not commit_records:
        raise GithubAPIError(
            "No pull requests or commits were found for the requested developer, repositories, and date range."
        )

    return DeveloperMetrics(
        developer=developer,
        org=org,
        repos=[repo.full_name for repo in repo_refs],
        date_from=date_from.date().isoformat(),
        date_to=date_to.date().isoformat(),
        prs=pr_records,
        commits=commit_records,
        review_participation=review_participation,
        limitations=limitations,
    )
