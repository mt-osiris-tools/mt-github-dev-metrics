from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import requests

from .models import RepoRef


class GithubError(RuntimeError):
    pass


class GithubAuthError(GithubError):
    pass


class GithubAPIError(GithubError):
    pass


def _to_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class GithubClient:
    token: str
    base_url: str = "https://api.github.com"
    session: requests.Session | None = None
    sleep_fn: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if not self.token:
            raise GithubAuthError(
                "Missing GitHub token. Set the GITHUB_TOKEN environment variable."
            )
        if self.session is None:
            self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-dev-metrics",
            }
        )

    @classmethod
    def from_env(cls) -> "GithubClient":
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            raise GithubAuthError(
                "Missing GitHub token. Set the GITHUB_TOKEN environment variable."
            )
        return cls(token=token)

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        assert self.session is not None
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, params=params, timeout=30)
        except requests.RequestException as exc:
            raise GithubAPIError(f"GitHub API request failed: {exc}") from exc
        if response.status_code == 401:
            raise GithubAuthError("GitHub authentication failed. Check GITHUB_TOKEN.")
        if response.status_code in {403, 429} and response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                wait_for = max(0.0, float(reset) - time.time()) + 1.0
                self.sleep_fn(wait_for)
                response = self.session.request(method, url, params=params, timeout=30)
        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise GithubAPIError(f"GitHub API request failed ({response.status_code}): {message}")
        return response

    def _extract_error_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:200] or "unknown error"
        if isinstance(payload, dict):
            message = payload.get("message")
            if message:
                return str(message)
        return "unknown error"

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", path, params=params)
        return response.json()

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        results: list[Any] = []
        while True:
            params["page"] = page
            response = self._request("GET", path, params=params)
            payload = response.json()
            if isinstance(payload, list):
                results.extend(payload)
            else:
                raise GithubAPIError(f"Expected list response from {path}")
            link = response.headers.get("Link", "")
            if 'rel="next"' not in link:
                break
            page += 1
        return results

    def list_repo_pulls(self, repo: RepoRef, state: str = "all") -> list[Any]:
        return self.paginate(f"/repos/{repo.full_name}/pulls", params={"state": state, "sort": "created", "direction": "desc"})

    def get_pull(self, repo: RepoRef, number: int) -> dict[str, Any]:
        return self.get_json(f"/repos/{repo.full_name}/pulls/{number}")

    def list_pull_files(self, repo: RepoRef, number: int) -> list[Any]:
        return self.paginate(f"/repos/{repo.full_name}/pulls/{number}/files")

    def list_pull_reviews(self, repo: RepoRef, number: int) -> list[Any]:
        return self.paginate(f"/repos/{repo.full_name}/pulls/{number}/reviews")

    def list_pull_review_comments(self, repo: RepoRef, number: int) -> list[Any]:
        return self.paginate(f"/repos/{repo.full_name}/pulls/{number}/comments")

    def list_pull_commits(self, repo: RepoRef, number: int) -> list[Any]:
        return self.paginate(f"/repos/{repo.full_name}/pulls/{number}/commits")

    def list_repo_commits(self, repo: RepoRef, author: str, since: datetime, until: datetime) -> list[Any]:
        return self.paginate(
            f"/repos/{repo.full_name}/commits",
            params={
                "author": author,
                "since": _to_datetime(since).isoformat(),
                "until": _to_datetime(until).isoformat(),
            },
        )

    def list_org_repos(self, org: str, include_archived: bool = False) -> list[RepoRef]:
        payload = self.paginate(f"/orgs/{org}/repos", params={"type": "all", "sort": "full_name", "direction": "asc"})
        repos: list[RepoRef] = []
        for item in payload:
            owner = str(item.get("owner", {}).get("login", "")).strip()
            name = str(item.get("name", "")).strip()
            if not owner or not name:
                continue
            if not include_archived and bool(item.get("archived")):
                continue
            repos.append(RepoRef(owner=owner, name=name))
        return repos

    def search_issues(self, query: str) -> list[Any]:
        payload = self.get_json("/search/issues", params={"q": query, "per_page": 100})
        if isinstance(payload, dict):
            return list(payload.get("items", []))
        raise GithubAPIError("Expected search results payload")
