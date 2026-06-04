from __future__ import annotations

from github_dev_metrics.github_client import GithubClient


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
