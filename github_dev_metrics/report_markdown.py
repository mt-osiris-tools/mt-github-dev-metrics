from __future__ import annotations

from typing import Any

from .models import DeveloperMetrics, PullRequestRecord


def _fmt_number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _fmt_date(value: str | None) -> str:
    return value or "-"


def fmt_cadence(cadence: dict[str, Any]) -> str:
    if not cadence:
        return "-"
    active_days = _fmt_number(cadence.get("active_days", 0))
    period_days = _fmt_number(cadence.get("period_days", 0))
    coverage_ratio = _fmt_number(cadence.get("coverage_ratio", 0) * 100)
    marker = "almost-daily" if cadence.get("has_almost_daily_cadence") else "below target"
    return f"{active_days}/{period_days} days ({coverage_ratio}%) - {marker}"


def _pr_line(pr: PullRequestRecord, metrics: dict[str, Any]) -> str:
    key = f"{pr.repo}#{pr.number}"
    review_states = metrics.get("evidence", {}).get("pr_review_states", {}).get(key, {})
    noisy = metrics.get("git_hygiene", {}).get("prs_with_noisy_commits", [])
    noisy_messages = next((item["messages"] for item in noisy if item["repo"] == pr.repo and item["number"] == pr.number), [])
    test_files = metrics.get("testing", {}).get("pr_test_files", {}).get(key, [])
    time_to_merge = metrics.get("evidence", {}).get("pr_time_to_merge_days", {}).get(key)
    review_iterations = metrics.get("evidence", {}).get("pr_review_iterations", {}).get(key, 0)
    return (
        f"- **{pr.repo}#{pr.number}** {pr.title}\n"
        f"  - URL: {pr.url}\n"
        f"  - State: {pr.state}\n"
        f"  - Created: {pr.created_at}\n"
        f"  - Merged: {_fmt_date(pr.merged_at)}\n"
        f"  - Closed: {_fmt_date(pr.closed_at)}\n"
        f"  - Additions / deletions / changed files: {pr.additions} / {pr.deletions} / {pr.changed_files}\n"
        f"  - Time to merge (days): {_fmt_number(time_to_merge)}\n"
        f"  - Review states: {review_states or '{}'}\n"
        f"  - Review iterations: {review_iterations}\n"
        f"  - Test files touched: {', '.join(test_files) if test_files else 'No'}\n"
        f"  - Noisy commit messages: {', '.join(noisy_messages) if noisy_messages else 'No'}"
    )


def render_markdown_report(data: DeveloperMetrics) -> str:
    metrics = data.metrics
    prs = data.prs
    lines: list[str] = []
    lines.append(f"# GitHub Developer Metrics - {data.developer}")
    lines.append("")
    lines.append(f"Period: {data.date_from} to {data.date_to}")
    lines.append("")
    lines.append("## Executive Summary")
    if data.summary.positive_signals or data.summary.opportunity_signals:
        summary_bits = []
        if data.summary.positive_signals:
            summary_bits.append("Positive signals included " + "; ".join(data.summary.positive_signals).rstrip(".") + ".")
        if data.summary.opportunity_signals:
            summary_bits.append("Opportunity signals included " + "; ".join(data.summary.opportunity_signals).rstrip(".") + ".")
        lines.append(" ".join(summary_bits))
    else:
        lines.append("No GitHub activity matched the selected repositories and date range.")
    lines.append("")
    lines.append("## Metrics Overview")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    pull_requests = metrics.get("pull_requests", {})
    commit_activity = metrics.get("commit_activity", {})
    cadence = commit_activity.get("cadence", {})
    testing = metrics.get("testing", {})
    git_hygiene = metrics.get("git_hygiene", {})
    lines.extend(
        [
            f"| PRs opened | {_fmt_number(pull_requests.get('opened', 0))} |",
            f"| PRs merged | {_fmt_number(pull_requests.get('merged', 0))} |",
            f"| Commits authored | {_fmt_number(commit_activity.get('authored_commits', 0))} |",
            f"| Commit cadence | {fmt_cadence(cadence)} |",
            f"| PRs with tests | {_fmt_number(testing.get('prs_with_tests', 0))} |",
            f"| PRs without tests | {_fmt_number(testing.get('prs_without_tests', 0))} |",
            f"| PRs with requested changes | {_fmt_number(pull_requests.get('requested_changes', 0))} |",
            f"| PRs with noisy commits | {_fmt_number(len(git_hygiene.get('prs_with_noisy_commits', [])))} |",
        ]
    )
    lines.append("")
    lines.append("## Positive Signals")
    if data.summary.positive_signals:
        for item in data.summary.positive_signals:
            lines.append(f"- {item}")
    else:
        lines.append("- No strong positive signals were identified from the available data.")
    lines.append("")
    lines.append("## Areas of Opportunity")
    if data.summary.opportunity_signals:
        for item in data.summary.opportunity_signals:
            lines.append(f"- {item}")
    else:
        lines.append("- No clear opportunities were identified from the available data.")
    lines.append("")
    lines.append("## Pull Request Evidence")
    if prs:
        for pr in prs:
            lines.append(_pr_line(pr, metrics))
    else:
        lines.append("- No pull requests matched the selection.")
    lines.append("")
    lines.append("## Testing Evidence")
    if testing.get("pr_test_files"):
        for key, files in testing["pr_test_files"].items():
            lines.append(f"- {key}: {', '.join(files) if files else 'No obvious test files touched'}")
    else:
        lines.append("- No testing evidence available.")
    lines.append("")
    lines.append("## Git Hygiene Evidence")
    if git_hygiene.get("prs_with_noisy_commits"):
        for item in git_hygiene["prs_with_noisy_commits"]:
            lines.append(f"- {item['repo']}#{item['number']}: {', '.join(item['messages'])}")
    else:
        lines.append("- No noisy commit messages were detected in matching PRs.")
    if commit_activity.get("revert_commits"):
        lines.append(f"- Revert commits: {', '.join(commit_activity['revert_commits'])}")
    lines.append("")
    lines.append("## Commit Cadence Evidence")
    if cadence:
        lines.append(
            f"- Active commit days: {_fmt_number(cadence.get('active_days', 0))} of {_fmt_number(cadence.get('period_days', 0))} ({_fmt_number(cadence.get('coverage_ratio', 0) * 100)}%)"
        )
        if cadence.get("has_almost_daily_cadence"):
            lines.append("- The commit pattern is consistent with an almost-daily habit.")
        else:
            lines.append("- The commit pattern is less frequent than an almost-daily habit.")
        if cadence.get("max_gap_days") is not None:
            lines.append(f"- Largest gap between active days: {_fmt_number(cadence.get('max_gap_days'))} day(s)")
    else:
        lines.append("- No commit cadence data was available.")
    lines.append("")
    lines.append("## Review Participation Evidence")
    review_participation = metrics.get("review_participation", {})
    lines.append(
        f"- Reviews submitted: {_fmt_number(review_participation.get('submitted_reviews', 0))}"
    )
    lines.append(
        f"- Review comments submitted: {_fmt_number(review_participation.get('review_comments', 0))}"
    )
    items = review_participation.get("items", [])
    if items:
        for item in items:
            lines.append(
                f"- {item['repo']}#{item['number']} {item['title']} ({len(item['submitted_reviews'])} review(s), {len(item['review_comments'])} comment(s))"
            )
    else:
        lines.append("- No review participation was found through best-effort API queries.")
    lines.append("")
    lines.append("## Suggested Follow-up Questions for a 1:1")
    lines.extend(
        [
            "- What validation steps were completed before opening the PR?",
            "- Which parts of the implementation were covered by automated tests?",
            "- What would help reduce review iterations on similar work?",
        ]
    )
    if data.limitations:
        lines.append("")
        lines.append("## Limitations")
        for limitation in data.limitations:
            lines.append(f"- {limitation}")
    return "\n".join(lines).strip() + "\n"
