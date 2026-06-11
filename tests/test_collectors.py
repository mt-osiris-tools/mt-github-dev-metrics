from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from github_dev_metrics.cli import _load_local_env_file
from github_dev_metrics.collectors import (
    collect_metrics,
    normalize_repo_specs,
    parse_iso_date,
    parse_iso_week,
)
from github_dev_metrics.github_client import GithubAPIError


class FakeGithubClient:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads

    def list_repo_pulls(self, repo, state="all"):
        return self.payloads.get(f"pulls:{repo.full_name}", [])

    def get_pull(self, repo, number: int):
        return self.payloads.get(f"pull:{repo.full_name}:{number}", {})

    def list_pull_files(self, repo, number: int):
        return self.payloads.get(f"files:{repo.full_name}:{number}", [])

    def list_pull_commits(self, repo, number: int):
        return self.payloads.get(f"pr_commits:{repo.full_name}:{number}", [])

    def list_pull_reviews(self, repo, number: int):
        return self.payloads.get(f"reviews:{repo.full_name}:{number}", [])

    def list_pull_review_comments(self, repo, number: int):
        return self.payloads.get(f"review_comments:{repo.full_name}:{number}", [])

    def list_pull_review_threads(self, repo, number: int):
        value = self.payloads.get(f"review_threads:{repo.full_name}:{number}", [])
        if isinstance(value, Exception):
            raise value
        return value

    def list_repo_commits(self, repo, author, since, until):
        return self.payloads.get(f"commits:{repo.full_name}", [])

    def search_issues(self, query: str):
        return self.payloads.get("search", [])


def test_parse_iso_date_validates_format() -> None:
    assert parse_iso_date("2026-03-01").date().isoformat() == "2026-03-01"
    with pytest.raises(ValueError):
        parse_iso_date("03/01/2026")


def test_parse_iso_week_returns_week_range() -> None:
    start, end = parse_iso_week("2026-W18")
    assert start.date().isoformat() == "2026-04-27"
    assert end.date().isoformat() == "2026-05-03"
    alt_start, alt_end = parse_iso_week("18-2026")
    assert (alt_start, alt_end) == (start, end)
    with pytest.raises(ValueError):
        parse_iso_week("2026-18")
    with pytest.raises(ValueError):
        parse_iso_week("54-2026")


def test_normalize_repo_specs_validates_repo_format() -> None:
    assert normalize_repo_specs(["frontend-app"], "my-org")[0].full_name == "my-org/frontend-app"
    assert normalize_repo_specs(["my-org/frontend-app"], None)[0].full_name == "my-org/frontend-app"
    with pytest.raises(ValueError):
        normalize_repo_specs(["frontend-app"], None)


def test_collect_metrics_handles_empty_results() -> None:
    client = FakeGithubClient(
        {
            "pulls:my-org/frontend-app": [],
            "commits:my-org/frontend-app": [],
            "search": [],
        }
    )
    with pytest.raises(GithubAPIError, match="No pull requests or commits were found"):
        collect_metrics(
            client,  # type: ignore[arg-type]
            "alan",
            "my-org",
            ["frontend-app"],
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 5, 31, tzinfo=timezone.utc),
        )


def test_collect_metrics_builds_records() -> None:
    client = FakeGithubClient(
        {
            "pulls:my-org/frontend-app": [
                {
                    "number": 42,
                    "user": {"login": "alan"},
                    "created_at": "2026-03-10T10:00:00Z",
                }
            ],
            "pull:my-org/frontend-app:42": {
                "title": "Add onboarding banner",
                "html_url": "https://github.com/my-org/frontend-app/pull/42",
                "state": "closed",
                "created_at": "2026-03-10T10:00:00Z",
                "merged_at": "2026-03-12T12:00:00Z",
                "closed_at": "2026-03-12T12:00:00Z",
                "additions": 100,
                "deletions": 20,
                "changed_files": 3,
                "merged_by": {"login": "maintainer"},
            },
            "files:my-org/frontend-app:42": [
                {"filename": "src/app.ts", "additions": 80, "deletions": 10, "changes": 90},
                {"filename": "src/app.test.ts", "additions": 20, "deletions": 10, "changes": 30},
            ],
            "pr_commits:my-org/frontend-app:42": [
                {
                    "sha": "abc",
                    "commit": {"message": "Implement feature", "author": {"date": "2026-03-10T10:00:00Z"}},
                    "html_url": "https://github.com/my-org/frontend-app/commit/abc",
                }
            ],
            "reviews:my-org/frontend-app:42": [
                {"user": {"login": "reviewer"}, "state": "APPROVED", "submitted_at": "2026-03-11T10:00:00Z"}
            ],
            "review_comments:my-org/frontend-app:42": [],
            "review_threads:my-org/frontend-app:42": [
                {
                    "id": "thread-1",
                    "isResolved": False,
                    "resolvedBy": None,
                    "comments": {
                        "nodes": [
                            {
                                "id": "comment-1",
                                "body": "Please add coverage",
                                "createdAt": "2026-03-11T09:00:00Z",
                                "author": {"login": "reviewer"},
                                "replyTo": None,
                            }
                        ]
                    },
                }
            ],
            "commits:my-org/frontend-app": [
                {
                    "sha": "abc",
                    "commit": {"message": "Implement feature", "author": {"date": "2026-03-10T10:00:00Z"}},
                    "html_url": "https://github.com/my-org/frontend-app/commit/abc",
                }
            ],
            "search": [],
        }
    )

    metrics = collect_metrics(
        client,  # type: ignore[arg-type]
        "alan",
        "my-org",
        ["frontend-app"],
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert metrics.prs[0].title == "Add onboarding banner"
    assert metrics.commits[0].message == "Implement feature"
    assert metrics.prs[0].review_threads[0].id == "thread-1"
    assert metrics.prs[0].review_threads[0].comments[0].author == "reviewer"


def test_collect_metrics_reports_repo_progress_in_order() -> None:
    client = FakeGithubClient(
        {
            "pulls:my-org/frontend-app": [],
            "commits:my-org/frontend-app": [
                {
                    "sha": "abc",
                    "commit": {"message": "Implement feature", "author": {"date": "2026-03-10T10:00:00Z"}},
                    "html_url": "https://github.com/my-org/frontend-app/commit/abc",
                }
            ],
            "pulls:my-org/design-system": [],
            "commits:my-org/design-system": [
                {
                    "sha": "def",
                    "commit": {"message": "Update tokens", "author": {"date": "2026-03-11T10:00:00Z"}},
                    "html_url": "https://github.com/my-org/design-system/commit/def",
                }
            ],
            "search": [],
        }
    )
    progress_messages: list[str] = []

    metrics = collect_metrics(
        client,  # type: ignore[arg-type]
        "alan",
        "my-org",
        ["frontend-app", "design-system"],
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
        progress=progress_messages.append,
    )

    assert [record.repo for record in metrics.commits] == [
        "my-org/frontend-app",
        "my-org/design-system",
    ]
    assert progress_messages == [
        "Collecting my-org/frontend-app (1/2)...",
        "Collecting my-org/design-system (2/2)...",
    ]


def test_collect_metrics_adds_limitation_when_review_threads_fail() -> None:
    client = FakeGithubClient(
        {
            "pulls:my-org/frontend-app": [
                {
                    "number": 42,
                    "user": {"login": "alan"},
                    "created_at": "2026-03-10T10:00:00Z",
                }
            ],
            "pull:my-org/frontend-app:42": {
                "title": "Add onboarding banner",
                "html_url": "https://github.com/my-org/frontend-app/pull/42",
                "state": "closed",
                "created_at": "2026-03-10T10:00:00Z",
                "merged_at": "2026-03-12T12:00:00Z",
                "closed_at": "2026-03-12T12:00:00Z",
                "additions": 100,
                "deletions": 20,
                "changed_files": 3,
            },
            "files:my-org/frontend-app:42": [],
            "pr_commits:my-org/frontend-app:42": [],
            "reviews:my-org/frontend-app:42": [],
            "review_comments:my-org/frontend-app:42": [],
            "review_threads:my-org/frontend-app:42": GithubAPIError("GraphQL denied"),
            "commits:my-org/frontend-app": [
                {
                    "sha": "abc",
                    "commit": {"message": "Implement feature", "author": {"date": "2026-03-10T10:00:00Z"}},
                    "html_url": "https://github.com/my-org/frontend-app/commit/abc",
                }
            ],
            "search": [],
        }
    )

    metrics = collect_metrics(
        client,  # type: ignore[arg-type]
        "alan",
        "my-org",
        ["frontend-app"],
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert metrics.prs[0].review_threads == []
    assert metrics.limitations == [
        "Review thread resolution is best-effort; GitHub GraphQL access or visibility constraints may hide unresolved threads."
    ]


def test_load_local_env_file_reads_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=from-dotenv\nexport EXTRA_VALUE='hello'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("EXTRA_VALUE", raising=False)

    found = _load_local_env_file()

    assert found == env_file
    assert os.environ["GITHUB_TOKEN"] == "from-dotenv"
    assert os.environ["EXTRA_VALUE"] == "hello"
