from __future__ import annotations

from pathlib import Path

import pytest

from github_dev_metrics.cli import _parse_github_remote, _resolve_repos, build_parser


def test_parse_github_remote_supports_https_and_ssh() -> None:
    assert _parse_github_remote("https://github.com/example-org/frontend-app.git") == "example-org/frontend-app"
    assert _parse_github_remote("git@github.com:example-org/frontend-app.git") == "example-org/frontend-app"
    assert _parse_github_remote("ssh://git@github.com/example-org/frontend-app.git") == "example-org/frontend-app"


def test_parse_github_remote_rejects_non_github_values() -> None:
    assert _parse_github_remote("git@gitlab.com:example-org/frontend-app.git") is None
    assert _parse_github_remote("https://github.com/example-org/frontend-app/extra") is None


def test_resolve_repos_prefers_explicit_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("github_dev_metrics.cli._detect_repo_from_git", lambda start_dir=None: "ignored/repo")

    repos = _resolve_repos("frontend-app,design-system", "example-org")

    assert repos == ["frontend-app", "design-system"]


def test_resolve_repos_uses_detected_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("github_dev_metrics.cli._detect_repo_from_git", lambda start_dir=None: "example-org/frontend-app")

    repos = _resolve_repos(None, None, start_dir=tmp_path)

    assert repos == ["example-org/frontend-app"]


def test_resolve_repos_requires_git_context_or_explicit_repos(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Run inside a git repository with a GitHub 'origin' remote or provide --repos explicitly"):
        _resolve_repos(None, None, start_dir=tmp_path)


def test_parser_defaults_to_markdown_format() -> None:
    args = build_parser().parse_args(["--developer", "octocat", "--week", "2026-W18"])

    assert args.format == "markdown"
