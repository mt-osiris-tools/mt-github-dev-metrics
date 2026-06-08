from __future__ import annotations

import csv
from io import StringIO

from github_dev_metrics.metrics import calculate_metrics
from github_dev_metrics.models import (
    CommitRecord,
    DeveloperMetrics,
    PullRequestCommit,
    PullRequestFile,
    PullRequestRecord,
    PullRequestReview,
)
from github_dev_metrics.report_csv import CSV_COLUMNS, render_csv_report


def _build_metrics() -> DeveloperMetrics:
    return calculate_metrics(
        DeveloperMetrics(
            developer="alan",
            org="my-org",
            repos=["my-org/frontend-app", "my-org/design-system"],
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
                    created_at="2026-03-01T10:00:00Z",
                    merged_at="2026-03-10T12:00:00Z",
                    closed_at="2026-03-10T12:00:00Z",
                    additions=120,
                    deletions=30,
                    changed_files=5,
                    reviews=[
                        PullRequestReview(
                            user="reviewer-a",
                            state="CHANGES_REQUESTED",
                            submitted_at="2026-03-02T10:00:00Z",
                        ),
                        PullRequestReview(
                            user="reviewer-b",
                            state="APPROVED",
                            submitted_at="2026-03-04T10:00:00Z",
                        ),
                        PullRequestReview(
                            user="reviewer-c",
                            state="COMMENTED",
                            submitted_at="2026-03-05T10:00:00Z",
                        ),
                    ],
                    review_comments=[{"id": 1, "body": "Needs copy cleanup"}],
                    files=[
                        PullRequestFile(filename="src/app.ts", additions=100, deletions=20, changes=120),
                        PullRequestFile(filename="src/app.test.ts", additions=20, deletions=10, changes=30),
                    ],
                    commits=[
                        PullRequestCommit(
                            sha="a1",
                            message="WIP add banner",
                            url="https://github.com/my-org/frontend-app/commit/a1",
                        ),
                        PullRequestCommit(
                            sha="a2",
                            message="Refine banner copy",
                            url="https://github.com/my-org/frontend-app/commit/a2",
                        ),
                    ],
                ),
                PullRequestRecord(
                    repo="my-org/design-system",
                    number=7,
                    title="Tighten color tokens",
                    url="https://github.com/my-org/design-system/pull/7",
                    state="closed",
                    author="alan",
                    created_at="2026-03-20T09:00:00Z",
                    merged_at="2026-03-21T11:00:00Z",
                    closed_at="2026-03-21T11:00:00Z",
                    additions=40,
                    deletions=5,
                    changed_files=2,
                    files=[
                        PullRequestFile(filename="src/colors.ts", additions=40, deletions=5, changes=45),
                    ],
                    commits=[
                        PullRequestCommit(
                            sha="b1",
                            message="Ship final palette",
                            url="https://github.com/my-org/design-system/commit/b1",
                        ),
                    ],
                ),
            ],
            commits=[
                CommitRecord(
                    repo="my-org/frontend-app",
                    sha="a1b2c3d4",
                    message="WIP add banner",
                    url="https://github.com/my-org/frontend-app/commit/a1",
                    authored_at="2026-03-01T10:00:00Z",
                ),
                CommitRecord(
                    repo="my-org/frontend-app",
                    sha="a2b3c4d5",
                    message="Refine banner copy",
                    url="https://github.com/my-org/frontend-app/commit/a2",
                    authored_at="2026-03-03T10:00:00Z",
                ),
                CommitRecord(
                    repo="my-org/design-system",
                    sha="b1c2d3e4",
                    message="Ship final palette",
                    url="https://github.com/my-org/design-system/commit/b1",
                    authored_at="2026-03-20T09:00:00Z",
                ),
            ],
        )
    )


def test_csv_report_writes_header_and_one_row_per_pr() -> None:
    rendered = render_csv_report(_build_metrics())

    rows = list(csv.DictReader(StringIO(rendered)))

    assert rendered.splitlines()[0] == ",".join(CSV_COLUMNS)
    assert len(rows) == 2


def test_csv_report_flattens_machine_friendly_pr_fields() -> None:
    rendered = render_csv_report(_build_metrics())
    rows = {row["pr_number"]: row for row in csv.DictReader(StringIO(rendered))}

    pr_42 = rows["42"]
    assert pr_42["developer"] == "alan"
    assert pr_42["org"] == "my-org"
    assert pr_42["repos"] == "my-org/frontend-app|my-org/design-system"
    assert pr_42["repo_count"] == "2"
    assert pr_42["has_test_changes"] == "True"
    assert pr_42["test_file_count"] == "1"
    assert pr_42["test_files"] == "src/app.test.ts"
    assert pr_42["has_noisy_commits"] == "True"
    assert pr_42["noisy_commit_count"] == "1"
    assert pr_42["noisy_commit_messages"] == "WIP add banner"
    assert pr_42["changes_requested_count"] == "1"
    assert pr_42["approved_count"] == "1"
    assert pr_42["commented_review_count"] == "1"
    assert pr_42["review_count"] == "3"
    assert pr_42["review_comment_count"] == "1"
    assert pr_42["review_iteration_count"] == "3"
    assert pr_42["total_line_changes"] == "150"
    assert pr_42["is_merged"] == "True"
    assert pr_42["is_closed_without_merge"] == "False"
    assert pr_42["is_open"] == "False"
    assert pr_42["is_long_time_to_merge"] == "True"
    assert pr_42["is_merged_without_test_changes"] == "False"
    assert pr_42["pr_commit_count"] == "2"
    assert pr_42["pr_commit_messages"] == "WIP add banner|Refine banner copy"
    assert pr_42["time_to_merge_days"] == "9.083333333333334"

    pr_7 = rows["7"]
    assert pr_7["has_test_changes"] == "False"
    assert pr_7["test_file_count"] == "0"
    assert pr_7["test_files"] == ""
    assert pr_7["has_noisy_commits"] == "False"
    assert pr_7["noisy_commit_count"] == "0"
    assert pr_7["is_merged_without_test_changes"] == "True"
    assert pr_7["pr_commit_messages"] == "Ship final palette"


def test_csv_report_writes_header_only_when_no_prs_exist() -> None:
    rendered = render_csv_report(
        calculate_metrics(
            DeveloperMetrics(
                developer="alan",
                org="my-org",
                repos=["my-org/frontend-app"],
                date_from="2026-03-01",
                date_to="2026-05-31",
            )
        )
    )

    assert rendered == ",".join(CSV_COLUMNS) + "\n"
