from __future__ import annotations

from github_dev_metrics.github_client import GithubClient
from github_dev_metrics.models import RepoRef


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = {}
        self.text = ""

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.posts = []

    def post(self, url, json=None, timeout=30):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        return self.responses.pop(0)


def test_list_org_repos_excludes_archived_by_default(monkeypatch) -> None:
    client = GithubClient(token="test-token")

    monkeypatch.setattr(
        client,
        "paginate",
        lambda path, params=None: [
            {"owner": {"login": "example-org"}, "name": "frontend-app", "archived": False},
            {"owner": {"login": "example-org"}, "name": "legacy-app", "archived": True},
            {"owner": {"login": "example-org"}, "name": "forked-tool", "archived": False, "fork": True},
        ],
    )

    repos = client.list_org_repos("example-org")

    assert [repo.full_name for repo in repos] == [
        "example-org/frontend-app",
        "example-org/forked-tool",
    ]


def test_list_org_repos_can_include_archived(monkeypatch) -> None:
    client = GithubClient(token="test-token")

    monkeypatch.setattr(
        client,
        "paginate",
        lambda path, params=None: [
            {"owner": {"login": "example-org"}, "name": "frontend-app", "archived": False},
            {"owner": {"login": "example-org"}, "name": "legacy-app", "archived": True},
        ],
    )

    repos = client.list_org_repos("example-org", include_archived=True)

    assert [repo.full_name for repo in repos] == [
        "example-org/frontend-app",
        "example-org/legacy-app",
    ]


def test_list_pull_review_threads_paginates_graphql_results() -> None:
    session = FakeSession(
        [
            FakeResponse(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [{"id": "thread-1", "isResolved": False, "resolvedBy": None, "comments": {"nodes": []}}],
                                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                                }
                            }
                        }
                    }
                }
            ),
            FakeResponse(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [{"id": "thread-2", "isResolved": True, "resolvedBy": {"login": "maintainer"}, "comments": {"nodes": []}}],
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    }
                }
            ),
        ]
    )
    client = GithubClient(token="test-token", session=session)

    threads = client.list_pull_review_threads(RepoRef(owner="my-org", name="frontend-app"), 42)

    assert [thread["id"] for thread in threads] == ["thread-1", "thread-2"]
    assert session.posts[0]["json"]["variables"]["after"] is None
    assert session.posts[1]["json"]["variables"]["after"] == "cursor-1"
