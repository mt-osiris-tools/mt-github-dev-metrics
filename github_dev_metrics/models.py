from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class PullRequestFile:
    filename: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    status: str = ""

    @property
    def is_test_file(self) -> bool:
        from .metrics import is_test_file

        return is_test_file(self.filename)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PullRequestReview:
    user: str
    state: str
    submitted_at: str | None = None
    body: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewThreadComment:
    id: str
    author: str
    body: str | None = None
    created_at: str | None = None
    is_reply: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewThread:
    id: str
    is_resolved: bool
    resolved_by: str | None = None
    comments: list[ReviewThreadComment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "is_resolved": self.is_resolved,
            "resolved_by": self.resolved_by,
            "comments": [comment.to_dict() for comment in self.comments],
        }


@dataclass
class PullRequestCommit:
    sha: str
    message: str
    url: str | None = None
    authored_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PullRequestRecord:
    repo: str
    number: int
    title: str
    url: str
    state: str
    author: str
    created_at: str
    merged_at: str | None
    closed_at: str | None
    additions: int
    deletions: int
    changed_files: int
    reviews: list[PullRequestReview] = field(default_factory=list)
    review_comments: list[dict[str, Any]] = field(default_factory=list)
    review_threads: list[ReviewThread] = field(default_factory=list)
    files: list[PullRequestFile] = field(default_factory=list)
    commits: list[PullRequestCommit] = field(default_factory=list)
    merged_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "state": self.state,
            "author": self.author,
            "created_at": self.created_at,
            "merged_at": self.merged_at,
            "closed_at": self.closed_at,
            "additions": self.additions,
            "deletions": self.deletions,
            "changed_files": self.changed_files,
            "merged_by": self.merged_by,
            "reviews": [review.to_dict() for review in self.reviews],
            "review_comments": self.review_comments,
            "review_threads": [thread.to_dict() for thread in self.review_threads],
            "files": [file.to_dict() for file in self.files],
            "commits": [commit.to_dict() for commit in self.commits],
        }


@dataclass
class CommitRecord:
    repo: str
    sha: str
    message: str
    url: str | None
    authored_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewParticipationRecord:
    repo: str
    number: int
    title: str
    url: str
    state: str
    submitted_reviews: list[PullRequestReview] = field(default_factory=list)
    review_comments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "state": self.state,
            "submitted_reviews": [review.to_dict() for review in self.submitted_reviews],
            "review_comments": self.review_comments,
        }


@dataclass
class EvidenceSummary:
    positive_signals: list[str] = field(default_factory=list)
    opportunity_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeveloperMetrics:
    developer: str
    org: str | None
    repos: list[str]
    date_from: str
    date_to: str
    prs: list[PullRequestRecord] = field(default_factory=list)
    commits: list[CommitRecord] = field(default_factory=list)
    review_participation: list[ReviewParticipationRecord] = field(default_factory=list)
    summary: EvidenceSummary = field(default_factory=EvidenceSummary)
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "developer": self.developer,
            "org": self.org,
            "repos": self.repos,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "prs": [pr.to_dict() for pr in self.prs],
            "commits": [commit.to_dict() for commit in self.commits],
            "review_participation": [item.to_dict() for item in self.review_participation],
            "summary": self.summary.to_dict(),
            "metrics": self.metrics,
            "limitations": self.limitations,
        }
