from __future__ import annotations

from datetime import datetime, timezone

from github_dev_metrics.web_app import _resolve_period, build_report_payload


class FakeGithubClient:
    def list_repo_pulls(self, repo, state="all"):
        return [
            {
                "number": 42,
                "user": {"login": "alan"},
                "created_at": "2026-05-01T10:00:00Z",
            }
        ]

    def list_repo_branches(self, repo):
        return [{"name": "main"}]

    def get_pull(self, repo, number: int):
        return {
            "title": "Add onboarding banner",
            "html_url": "https://github.com/example-org/frontend-app/pull/42",
            "state": "closed",
            "created_at": "2026-05-01T10:00:00Z",
            "merged_at": "2026-05-02T12:00:00Z",
            "closed_at": "2026-05-02T12:00:00Z",
            "additions": 10,
            "deletions": 2,
            "changed_files": 1,
        }

    def list_pull_files(self, repo, number: int):
        return [{"filename": "src/app.test.ts", "additions": 1, "deletions": 0, "changes": 1}]

    def list_pull_commits(self, repo, number: int):
        return [
            {
                "sha": "abc",
                "commit": {"message": "Implement feature", "author": {"date": "2026-05-01T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc",
            }
        ]

    def list_pull_reviews(self, repo, number: int):
        return []

    def list_pull_review_comments(self, repo, number: int):
        return []

    def list_pull_review_threads(self, repo, number: int):
        return [
            {
                "id": "thread-1",
                "isResolved": False,
                "resolvedBy": None,
                "comments": {
                    "nodes": [
                        {
                            "id": "comment-1",
                            "body": "Need a test",
                            "createdAt": "2026-05-02T10:00:00Z",
                            "author": {"login": "reviewer"},
                            "replyTo": None,
                        }
                    ]
                },
            }
        ]

    def list_repo_commits(self, repo, author, since, until, sha=None):
        return [
            {
                "sha": "abc1",
                "commit": {"message": "WIP update banner", "author": {"date": "2026-04-27T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc1",
            },
            {
                "sha": "abc2",
                "commit": {"message": "Fix banner copy", "author": {"date": "2026-04-28T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc2",
            },
            {
                "sha": "abc3",
                "commit": {"message": "WIP refine header", "author": {"date": "2026-04-30T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc3",
            },
            {
                "sha": "abc4",
                "commit": {"message": "Final polish", "author": {"date": "2026-05-01T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc4",
            },
            {
                "sha": "abc5",
                "commit": {"message": "Tweak layout", "author": {"date": "2026-05-02T10:00:00Z"}},
                "html_url": "https://github.com/example-org/frontend-app/commit/abc5",
            }
        ]

    def search_issues(self, query: str):
        return []


def test_resolve_period_supports_week() -> None:
    start, end, week = _resolve_period({"week": "2026-W18"})
    assert week == "2026-W18"
    assert start.startswith("2026-04-27")
    assert end.startswith("2026-05-03")
    alt_start, alt_end, alt_week = _resolve_period({"week": "18-2026"})
    assert alt_week == "18-2026"
    assert (alt_start, alt_end) == (start, end)


def test_build_report_payload_returns_renderable_report() -> None:
    payload = build_report_payload(
        {
            "developer": "alan",
            "org": "example-org",
            "repos": "frontend-app",
            "week": "2026-W18",
            "cadence_target": "0.7",
            "cadence_min_days": "4",
            "format": "markdown",
        },
        client=FakeGithubClient(),
    )

    assert payload["developer"] == "alan"
    assert payload["week"] == "2026-W18"
    assert "GitHub Developer Metrics - alan" in payload["markdown"]
    assert payload["metrics"]["pull_requests"]["opened"] == 1
    assert payload["metrics"]["pull_requests"]["unresolved_review_threads_closed"] == 1
    assert payload["metrics"]["commit_activity"]["cadence"]["has_almost_daily_cadence"] is True
    assert payload["metrics"]["developer_contributions"] == {
        "authored_prs": 1,
        "merged_prs": 1,
        "authored_commits": 5,
        "reviews_submitted": 0,
        "review_comments": 0,
        "repos_contributed_to": ["example-org/frontend-app"],
        "repo_count": 1,
        "total_contribution_events": 6,
        "contribution_mix": {
            "pull_requests": 1,
            "commits": 5,
            "reviews": 0,
            "review_comments": 0,
        },
    }
    assert "## Developer Contributions" in payload["markdown"]
    assert payload["json"]["prs"][0]["review_threads"][0]["id"] == "thread-1"
    assert payload["json"]["developer"] == "alan"
