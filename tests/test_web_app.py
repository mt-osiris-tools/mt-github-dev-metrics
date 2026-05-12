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

    def get_pull(self, repo, number: int):
        return {
            "title": "Add onboarding banner",
            "html_url": "https://github.com/MedTrainer365/medtrainer-react/pull/42",
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
                "html_url": "https://github.com/MedTrainer365/medtrainer-react/commit/abc",
            }
        ]

    def list_pull_reviews(self, repo, number: int):
        return []

    def list_pull_review_comments(self, repo, number: int):
        return []

    def list_repo_commits(self, repo, author, since, until):
        return [
            {
                "sha": "abc",
                "commit": {"message": "Implement feature", "author": {"date": "2026-05-01T10:00:00Z"}},
                "html_url": "https://github.com/MedTrainer365/medtrainer-react/commit/abc",
            }
        ]

    def search_issues(self, query: str):
        return []


def test_resolve_period_supports_week() -> None:
    start, end, week = _resolve_period({"week": "2026-W18"})
    assert week == "2026-W18"
    assert start.startswith("2026-04-27")
    assert end.startswith("2026-05-03")


def test_build_report_payload_returns_renderable_report() -> None:
    payload = build_report_payload(
        {
            "developer": "alan",
            "org": "MedTrainer365",
            "repos": "medtrainer-react",
            "week": "2026-W18",
            "format": "markdown",
        },
        client=FakeGithubClient(),
    )

    assert payload["developer"] == "alan"
    assert payload["week"] == "2026-W18"
    assert "GitHub Developer Metrics - alan" in payload["markdown"]
    assert payload["metrics"]["pull_requests"]["opened"] == 1
    assert payload["json"]["developer"] == "alan"

