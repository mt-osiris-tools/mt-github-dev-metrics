from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from github_dev_metrics.cli import (
    _discover_org_repos,
    _default_output_path,
    _parse_github_remote,
    _resolve_repos,
    _resolve_output_path,
    build_parser,
    main,
)


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


def test_discover_org_repos_reports_progress() -> None:
    class FakeClient:
        def list_org_repos(self, org: str):
            assert org == "example-org"
            return [
                type("Repo", (), {"full_name": "example-org/frontend-app"})(),
                type("Repo", (), {"full_name": "example-org/design-system"})(),
            ]

    progress_messages: list[str] = []

    repos = _discover_org_repos(FakeClient(), "example-org", progress=progress_messages.append)  # type: ignore[arg-type]

    assert repos == ["example-org/frontend-app", "example-org/design-system"]
    assert progress_messages == [
        "Discovering repositories in example-org...",
        "Discovered 2 repositories in example-org.",
    ]


def test_resolve_repos_uses_org_fallback_outside_git_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("github_dev_metrics.cli._detect_repo_from_git", lambda start_dir=None: None)

    class FakeClient:
        pass

    progress_messages: list[str] = []
    monkeypatch.setattr(
        "github_dev_metrics.cli._discover_org_repos",
        lambda client, org, progress=None: progress("Discovered 1 repositories in example-org.") or ["example-org/frontend-app"],
    )

    repos = _resolve_repos(None, "example-org", client=FakeClient(), start_dir=tmp_path, progress=progress_messages.append)

    assert repos == ["example-org/frontend-app"]
    assert progress_messages == ["Discovered 1 repositories in example-org."]


def test_resolve_repos_requires_git_context_or_explicit_repos_or_org(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError,
        match="Run inside a git repository with a GitHub 'origin' remote, provide --repos explicitly, or pass --org",
    ):
        _resolve_repos(None, None, start_dir=tmp_path)


def test_parser_defaults_to_markdown_format() -> None:
    args = build_parser().parse_args(["--developer", "octocat", "--week", "05-2026"])

    assert args.format == "markdown"


def test_parser_accepts_csv_format() -> None:
    args = build_parser().parse_args(["--developer", "octocat", "--week", "05-2026", "--format", "csv"])

    assert args.format == "csv"


def test_default_output_path_uses_report_directory_for_markdown() -> None:
    path = _default_output_path(
        "octocat",
        "markdown",
        datetime(2026, 4, 27, tzinfo=timezone.utc),
        datetime(2026, 5, 3, tzinfo=timezone.utc),
        week="05-2026",
    )

    assert path == Path("report/octocat_week-05-2026.md")


def test_default_output_path_uses_json_extension() -> None:
    path = _default_output_path(
        "octocat",
        "json",
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert path == Path("report/octocat_2026-03-01_to_2026-05-31.json")


def test_default_output_path_uses_csv_extension() -> None:
    path = _default_output_path(
        "octocat",
        "csv",
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert path == Path("report/octocat_2026-03-01_to_2026-05-31.csv")


def test_resolve_output_path_prefers_explicit_value() -> None:
    path = _resolve_output_path(
        "custom/output.md",
        "octocat",
        "markdown",
        datetime(2026, 3, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert path == Path("custom/output.md")


def test_main_writes_default_report_file_and_prints_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("github_dev_metrics.cli._load_local_env_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("github_dev_metrics.cli.GithubClient.from_env", lambda: object())
    monkeypatch.setattr("github_dev_metrics.cli._resolve_repos", lambda *args, **kwargs: ["example-org/frontend-app"])
    monkeypatch.setattr("github_dev_metrics.cli.collect_metrics", lambda *args, **kwargs: object())
    monkeypatch.setattr("github_dev_metrics.cli.calculate_metrics", lambda metrics, **kwargs: metrics)
    monkeypatch.setattr("github_dev_metrics.cli.render_markdown_report", lambda metrics: "# report\n")

    exit_code = main(["--developer", "octocat", "--week", "05-2026"])

    assert exit_code == 0
    report_path = tmp_path / "report" / "octocat_week-05-2026.md"
    assert report_path.read_text(encoding="utf-8") == "# report\n"
    captured = capsys.readouterr()
    assert captured.out == f"Wrote {Path('report/octocat_week-05-2026.md')}\n"
    assert captured.err == (
        "Resolving repositories and GitHub client...\n"
        "Collecting GitHub activity...\n"
        "Calculating metrics...\n"
        "Rendering markdown report...\n"
        "Writing report to report/octocat_week-05-2026.md...\n"
    )


def test_main_writes_csv_report_file_and_prints_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("github_dev_metrics.cli._load_local_env_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("github_dev_metrics.cli.GithubClient.from_env", lambda: object())
    monkeypatch.setattr("github_dev_metrics.cli._resolve_repos", lambda *args, **kwargs: ["example-org/frontend-app"])
    monkeypatch.setattr("github_dev_metrics.cli.collect_metrics", lambda *args, **kwargs: object())
    monkeypatch.setattr("github_dev_metrics.cli.calculate_metrics", lambda metrics, **kwargs: metrics)
    monkeypatch.setattr("github_dev_metrics.cli.render_csv_report", lambda metrics: "repo,pr_number\nexample-org/frontend-app,42\n")

    exit_code = main(["--developer", "octocat", "--week", "05-2026", "--format", "csv"])

    assert exit_code == 0
    report_path = tmp_path / "report" / "octocat_week-05-2026.csv"
    assert report_path.read_text(encoding="utf-8") == "repo,pr_number\nexample-org/frontend-app,42\n"
    captured = capsys.readouterr()
    assert captured.out == f"Wrote {Path('report/octocat_week-05-2026.csv')}\n"
    assert captured.err == (
        "Resolving repositories and GitHub client...\n"
        "Collecting GitHub activity...\n"
        "Calculating metrics...\n"
        "Rendering csv report...\n"
        "Writing report to report/octocat_week-05-2026.csv...\n"
    )


def test_main_writes_repo_progress_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("github_dev_metrics.cli._load_local_env_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("github_dev_metrics.cli.GithubClient.from_env", lambda: object())
    monkeypatch.setattr("github_dev_metrics.cli._resolve_repos", lambda *args, **kwargs: ["example-org/frontend-app"])

    def fake_collect_metrics(*args, **kwargs):
        progress = kwargs["progress"]
        progress("Collecting example-org/frontend-app (1/1)...")
        return object()

    monkeypatch.setattr("github_dev_metrics.cli.collect_metrics", fake_collect_metrics)
    monkeypatch.setattr("github_dev_metrics.cli.calculate_metrics", lambda metrics, **kwargs: metrics)
    monkeypatch.setattr("github_dev_metrics.cli.render_markdown_report", lambda metrics: "# report\n")

    exit_code = main(["--developer", "octocat", "--week", "05-2026"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Collecting example-org/frontend-app (1/1)...\n" in captured.err


def test_main_supports_org_fallback_outside_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("github_dev_metrics.cli._load_local_env_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("github_dev_metrics.cli._detect_repo_from_git", lambda *args, **kwargs: None)
    monkeypatch.setattr("github_dev_metrics.cli.GithubClient.from_env", lambda: object())
    monkeypatch.setattr(
        "github_dev_metrics.cli._discover_org_repos",
        lambda client, org, progress=None: ["example-org/frontend-app", "example-org/design-system"],
    )
    monkeypatch.setattr("github_dev_metrics.cli.collect_metrics", lambda *args, **kwargs: object())
    monkeypatch.setattr("github_dev_metrics.cli.calculate_metrics", lambda metrics, **kwargs: metrics)
    monkeypatch.setattr("github_dev_metrics.cli.render_markdown_report", lambda metrics: "# report\n")

    exit_code = main(["--developer", "octocat", "--week", "05-2026", "--org", "example-org"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Collecting GitHub activity...\n" in captured.err
