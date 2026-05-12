from __future__ import annotations

from github_dev_metrics.metrics import calculate_metrics
from github_dev_metrics.models import (
    CommitRecord,
    DeveloperMetrics,
    PullRequestCommit,
    PullRequestFile,
    PullRequestRecord,
    PullRequestReview,
)
from github_dev_metrics.report_markdown import render_markdown_report


def test_markdown_report_generation() -> None:
    data = DeveloperMetrics(
        developer="alan",
        org="my-org",
        repos=["my-org/frontend-app"],
        date_from="2026-03-01",
        date_to="2026-05-31",
        prs=[
            PullRequestRecord(
                repo="my-org/frontend-app",
                number=42,
                title="Add onboarding banner",
                url="https://github.com/my-org/frontend-app/pull/42",
                state="closed",
                author="alan",
                created_at="2026-03-10T10:00:00Z",
                merged_at="2026-03-12T12:00:00Z",
                closed_at="2026-03-12T12:00:00Z",
                additions=120,
                deletions=30,
                changed_files=5,
                reviews=[
                    PullRequestReview(user="reviewer", state="CHANGES_REQUESTED", submitted_at="2026-03-11T10:00:00Z"),
                ],
                files=[
                    PullRequestFile(filename="src/app.ts", additions=100, deletions=20, changes=120),
                    PullRequestFile(filename="src/app.test.ts", additions=20, deletions=10, changes=30),
                ],
                commits=[
                    PullRequestCommit(sha="a1", message="WIP add banner", url="https://github.com/my-org/frontend-app/commit/a1"),
                ],
            )
        ],
        commits=[
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a1",
                message="WIP add banner",
                url="https://github.com/my-org/frontend-app/commit/a1",
                authored_at="2026-03-10T10:00:00Z",
            )
        ],
    )

    rendered = render_markdown_report(calculate_metrics(data))

    assert "# GitHub Developer Metrics - alan" in rendered
    assert "## Executive Summary" in rendered
    assert "PRs opened | 1" in rendered
    assert "## Pull Request Evidence" in rendered
    assert "my-org/frontend-app#42" in rendered
    assert "## Suggested Follow-up Questions for a 1:1" in rendered

