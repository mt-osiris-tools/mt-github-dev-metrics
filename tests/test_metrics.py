from __future__ import annotations

from github_dev_metrics.metrics import calculate_metrics, is_noisy_commit_message, is_test_file
from github_dev_metrics.models import (
    CommitRecord,
    DeveloperMetrics,
    PullRequestCommit,
    PullRequestFile,
    PullRequestRecord,
    PullRequestReview,
    ReviewParticipationRecord,
)


def test_test_file_detection() -> None:
    assert is_test_file("src/components/button.test.tsx")
    assert is_test_file("packages/ui/__tests__/button.spec.ts")
    assert is_test_file("src/tests/button.py")
    assert not is_test_file("src/components/button.tsx")


def test_noisy_commit_detection() -> None:
    assert is_noisy_commit_message("WIP: add auth flow")
    assert is_noisy_commit_message("fixup! extract helper")
    assert is_noisy_commit_message("revert \"bad change\"")
    assert is_noisy_commit_message("merge branch 'main' into feature")
    assert not is_noisy_commit_message("Add validation for email input")


def test_pr_metrics_calculation() -> None:
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
                    PullRequestReview(user="reviewer", state="APPROVED", submitted_at="2026-03-12T10:00:00Z"),
                ],
                files=[
                    PullRequestFile(filename="src/app.ts", additions=100, deletions=20, changes=120),
                    PullRequestFile(filename="src/app.test.ts", additions=20, deletions=10, changes=30),
                ],
                commits=[
                    PullRequestCommit(sha="a1", message="WIP add banner", url="https://github.com/my-org/frontend-app/commit/a1"),
                    PullRequestCommit(sha="a2", message="Implement banner", url="https://github.com/my-org/frontend-app/commit/a2"),
                ],
            ),
            PullRequestRecord(
                repo="my-org/frontend-app",
                number=43,
                title="Refactor header",
                url="https://github.com/my-org/frontend-app/pull/43",
                state="open",
                author="alan",
                created_at="2026-04-10T10:00:00Z",
                merged_at=None,
                closed_at=None,
                additions=50,
                deletions=10,
                changed_files=2,
                reviews=[],
                files=[PullRequestFile(filename="src/header.ts", additions=50, deletions=10, changes=60)],
                commits=[PullRequestCommit(sha="b1", message="Add header refactor", url=None)],
            ),
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
        review_participation=[
            ReviewParticipationRecord(
                repo="my-org/design-system",
                number=88,
                title="Improve button docs",
                url="https://github.com/my-org/design-system/pull/88",
                state="open",
                submitted_reviews=[],
                review_comments=[],
            )
        ],
    )

    calculated = calculate_metrics(data)

    assert calculated.metrics["pull_requests"]["opened"] == 2
    assert calculated.metrics["pull_requests"]["merged"] == 1
    assert calculated.metrics["pull_requests"]["requested_changes"] == 1
    assert calculated.metrics["pull_requests"]["with_tests"] == 1
    assert calculated.metrics["testing"]["prs_without_tests"] == 1
    assert calculated.metrics["commit_activity"]["authored_commits"] == 1
    assert calculated.metrics["git_hygiene"]["prs_with_noisy_commits"]
    assert calculated.metrics["review_participation"]["submitted_reviews"] == 0
    assert calculated.summary.positive_signals
    assert calculated.summary.opportunity_signals

