from __future__ import annotations

from github_dev_metrics.metrics import calculate_metrics, is_noisy_commit_message, is_test_file
from github_dev_metrics.models import (
    CommitRecord,
    DeveloperMetrics,
    PullRequestCommit,
    PullRequestFile,
    PullRequestRecord,
    PullRequestReview,
    ReviewThread,
    ReviewThreadComment,
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
                review_threads=[
                    ReviewThread(
                        id="thread-1",
                        is_resolved=False,
                        comments=[
                            ReviewThreadComment(
                                id="comment-1",
                                author="reviewer",
                                body="Please add a test",
                                created_at="2026-03-11T09:00:00Z",
                            )
                        ],
                    )
                ],
                files=[
                    PullRequestFile(filename="src/app.ts", additions=100, deletions=20, changes=120),
                    PullRequestFile(filename="src/app.test.ts", additions=20, deletions=10, changes=30),
                ],
                commits=[
                    PullRequestCommit(sha="a1", message="WIP add banner", url="https://github.com/my-org/frontend-app/commit/a1"),
                    PullRequestCommit(sha="a2", message="Implement banner", url="https://github.com/my-org/frontend-app/commit/a2"),
                ],
                included_events=["created", "merged"],
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
                included_events=["created"],
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
    assert calculated.metrics["pull_requests"]["unresolved_review_threads_closed"] == 1
    assert calculated.metrics["pull_requests"]["prs_with_unresolved_review_threads_closed"] == 1
    assert calculated.metrics["testing"]["prs_without_tests"] == 1
    assert calculated.metrics["commit_activity"]["authored_commits"] == 1
    assert calculated.metrics["git_hygiene"]["prs_with_noisy_commits"]
    assert calculated.metrics["review_participation"]["submitted_reviews"] == 0
    assert calculated.metrics["developer_contributions"] == {
        "authored_prs": 2,
        "merged_prs": 1,
        "authored_commits": 1,
        "reviews_submitted": 0,
        "review_comments": 0,
        "repos_contributed_to": ["my-org/design-system", "my-org/frontend-app"],
        "repo_count": 2,
        "total_contribution_events": 3,
        "contribution_mix": {
            "pull_requests": 2,
            "commits": 1,
            "reviews": 0,
            "review_comments": 0,
        },
        "per_repo": {
            "my-org/design-system": {
                "pull_requests": {"selected": 0, "opened": 0, "merged": 0, "closed_without_merge": 0},
                "commits": {
                    "authored": 0,
                    "cadence": {
                        "active_days": 0,
                        "period_days": 0,
                        "coverage_ratio": 0.0,
                        "has_almost_daily_cadence": False,
                        "max_gap_days": None,
                    },
                },
                "review_participation": {"submitted_reviews": 0, "review_comments": 0},
                "total_contribution_events": 0,
            },
            "my-org/frontend-app": {
                "pull_requests": {"selected": 2, "opened": 2, "merged": 1, "closed_without_merge": 0},
                "commits": {
                    "authored": 1,
                    "cadence": {
                        "active_days": 1,
                        "period_days": 92,
                        "coverage_ratio": 1 / 92,
                        "has_almost_daily_cadence": False,
                        "max_gap_days": 0,
                    },
                },
                "review_participation": {"submitted_reviews": 0, "review_comments": 0},
                "total_contribution_events": 3,
            },
        },
    }
    assert calculated.summary.positive_signals
    assert calculated.summary.opportunity_signals
    assert any("unresolved review thread" in signal for signal in calculated.summary.opportunity_signals)


def test_pr_metrics_use_event_timestamps_not_current_state() -> None:
    data = DeveloperMetrics(
        developer="alan",
        org="my-org",
        repos=["my-org/frontend-app"],
        date_from="2026-05-01",
        date_to="2026-05-31",
        prs=[
            PullRequestRecord(
                repo="my-org/frontend-app",
                number=42,
                title="Created in April, merged in May",
                url="https://github.com/my-org/frontend-app/pull/42",
                state="closed",
                author="alan",
                created_at="2026-04-29T10:00:00Z",
                merged_at="2026-05-03T12:00:00Z",
                closed_at="2026-05-03T12:00:00Z",
                additions=10,
                deletions=2,
                changed_files=1,
                included_events=["merged"],
            ),
            PullRequestRecord(
                repo="my-org/frontend-app",
                number=43,
                title="Created in May, merged in June",
                url="https://github.com/my-org/frontend-app/pull/43",
                state="closed",
                author="alan",
                created_at="2026-05-20T10:00:00Z",
                merged_at="2026-06-02T12:00:00Z",
                closed_at="2026-06-02T12:00:00Z",
                additions=12,
                deletions=4,
                changed_files=1,
                included_events=["created"],
            ),
        ],
    )

    calculated = calculate_metrics(data)

    assert calculated.metrics["pull_requests"]["opened"] == 1
    assert calculated.metrics["pull_requests"]["merged"] == 1
    assert calculated.metrics["developer_contributions"]["merged_prs"] == 1


def test_per_repo_breakdown_stays_stable_for_lms_medtrainer_overlap() -> None:
    shared_pr = PullRequestRecord(
        repo="MedTrainer365/lms-medtrainer",
        number=9427,
        title="LMS change",
        url="https://github.com/MedTrainer365/lms-medtrainer/pull/9427",
        state="closed",
        author="IrvingSG-dev",
        created_at="2026-05-10T10:00:00Z",
        merged_at="2026-05-12T12:00:00Z",
        closed_at="2026-05-12T12:00:00Z",
        additions=25,
        deletions=5,
        changed_files=3,
        included_events=["created", "merged"],
    )
    shared_commit = CommitRecord(
        repo="MedTrainer365/lms-medtrainer",
        sha="abc123",
        message="LMS commit",
        url="https://github.com/MedTrainer365/lms-medtrainer/commit/abc123",
        authored_at="2026-05-11T09:00:00Z",
    )

    lms_only = calculate_metrics(
        DeveloperMetrics(
            developer="IrvingSG-dev",
            org="MedTrainer365",
            repos=["MedTrainer365/lms-medtrainer"],
            date_from="2026-05-01",
            date_to="2026-05-31",
            prs=[shared_pr],
            commits=[shared_commit],
        )
    )
    combined = calculate_metrics(
        DeveloperMetrics(
            developer="IrvingSG-dev",
            org="MedTrainer365",
            repos=["MedTrainer365/form-builder-api", "MedTrainer365/lms-medtrainer"],
            date_from="2026-05-01",
            date_to="2026-05-31",
            prs=[
                shared_pr,
                PullRequestRecord(
                    repo="MedTrainer365/form-builder-api",
                    number=66,
                    title="Form builder change",
                    url="https://github.com/MedTrainer365/form-builder-api/pull/66",
                    state="closed",
                    author="IrvingSG-dev",
                    created_at="2026-05-15T10:00:00Z",
                    merged_at="2026-05-16T12:00:00Z",
                    closed_at="2026-05-16T12:00:00Z",
                    additions=40,
                    deletions=10,
                    changed_files=4,
                    included_events=["created", "merged"],
                ),
            ],
            commits=[
                shared_commit,
                CommitRecord(
                    repo="MedTrainer365/form-builder-api",
                    sha="def456",
                    message="Form builder commit",
                    url="https://github.com/MedTrainer365/form-builder-api/commit/def456",
                    authored_at="2026-05-15T09:00:00Z",
                ),
            ],
        )
    )

    assert (
        lms_only.metrics["developer_contributions"]["per_repo"]["MedTrainer365/lms-medtrainer"]
        == combined.metrics["developer_contributions"]["per_repo"]["MedTrainer365/lms-medtrainer"]
    )


def test_commit_cadence_flags_almost_daily_pattern() -> None:
    data = DeveloperMetrics(
        developer="alan",
        org="my-org",
        repos=["my-org/frontend-app"],
        date_from="2026-05-01",
        date_to="2026-05-07",
        commits=[
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a1",
                message="WIP update banner",
                url="https://github.com/my-org/frontend-app/commit/a1",
                authored_at="2026-05-01T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a2",
                message="Fix banner copy",
                url="https://github.com/my-org/frontend-app/commit/a2",
                authored_at="2026-05-02T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a3",
                message="WIP refine header",
                url="https://github.com/my-org/frontend-app/commit/a3",
                authored_at="2026-05-04T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a4",
                message="Final polish",
                url="https://github.com/my-org/frontend-app/commit/a4",
                authored_at="2026-05-05T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a5",
                message="Tweak layout",
                url="https://github.com/my-org/frontend-app/commit/a5",
                authored_at="2026-05-06T10:00:00Z",
            ),
        ],
    )

    calculated = calculate_metrics(data)

    cadence = calculated.metrics["commit_activity"]["cadence"]
    assert cadence["active_days"] == 5
    assert cadence["period_days"] == 7
    assert cadence["has_almost_daily_cadence"] is True
    assert any("almost-daily practice" in signal for signal in calculated.summary.positive_signals)


def test_commit_cadence_respects_custom_thresholds() -> None:
    data = DeveloperMetrics(
        developer="alan",
        org="my-org",
        repos=["my-org/frontend-app"],
        date_from="2026-05-01",
        date_to="2026-05-07",
        commits=[
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a1",
                message="WIP update banner",
                url="https://github.com/my-org/frontend-app/commit/a1",
                authored_at="2026-05-01T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a2",
                message="Fix banner copy",
                url="https://github.com/my-org/frontend-app/commit/a2",
                authored_at="2026-05-02T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a3",
                message="WIP refine header",
                url="https://github.com/my-org/frontend-app/commit/a3",
                authored_at="2026-05-04T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a4",
                message="Final polish",
                url="https://github.com/my-org/frontend-app/commit/a4",
                authored_at="2026-05-05T10:00:00Z",
            ),
            CommitRecord(
                repo="my-org/frontend-app",
                sha="a5",
                message="Tweak layout",
                url="https://github.com/my-org/frontend-app/commit/a5",
                authored_at="2026-05-06T10:00:00Z",
            ),
        ],
    )

    calculated = calculate_metrics(data, cadence_target=0.8, cadence_min_active_days=6)

    cadence = calculated.metrics["commit_activity"]["cadence"]
    assert cadence["has_almost_daily_cadence"] is False
    assert any("below the almost-daily target" in signal for signal in calculated.summary.opportunity_signals)
