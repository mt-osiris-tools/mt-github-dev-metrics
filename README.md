# github-dev-metrics

`github-dev-metrics` is a Python CLI for collecting GitHub activity metrics for a specific developer across one or more repositories. It is intended for developer activity reviews, team health conversations, and engineering retrospectives.

When you run it inside a git repository, it can infer the current GitHub repository from the local `origin` remote. In that mode, the only required inputs are the developer plus either a week or a from/to date range, and the CLI writes a Markdown report into `report/` by default unless you pass `--format json` or `--format csv`.

If you run it outside a git repository and omit `--repos`, pass `--org` to scan the accessible non-archived repositories in that GitHub organization.

## Requirements

- `python3` 3.11 or newer
- `git`
- `curl` for the one-line install and update flow

## Global Install

```bash
curl -fsSL https://raw.githubusercontent.com/mt-osiris-tools/mt-github-dev-metrics/main/scripts/install.sh | bash
```

Then run the CLI directly:

```bash
github-dev-metrics --help
```

## Quick Start

```bash
github-dev-metrics \
  --developer octocat \
  --week 05-2026
```

Outside a repository, use `--org` for org-wide collection:

```bash
github-dev-metrics \
  --developer octocat \
  --week 05-2026 \
  --org example-org
```

Update an existing global install:

```bash
curl -fsSL https://raw.githubusercontent.com/mt-osiris-tools/mt-github-dev-metrics/main/scripts/install.sh | bash -s -- --update
```

## Local Checkout

If you want to work from a repo checkout instead of a global install:

```bash
make install
.venv/bin/python -m github_dev_metrics.cli --help
```

## Environment

Set a GitHub token in `GITHUB_TOKEN`.

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

You can also place the token in a local `.env` file at the project root:

```env
GITHUB_TOKEN=ghp_your_token_here
```

The CLI automatically loads `.env` from the current directory or any parent directory before it checks for `GITHUB_TOKEN`.

If you use `direnv`, you can let it load the token automatically when you enter the repo:

```bash
direnv allow
```

Copy `.envrc.example` to `.envrc` if you want a local `direnv` file:

```bash
cp .envrc.example .envrc
```

## CLI Usage

```bash
github-dev-metrics \
  --developer octocat \
  --from 2026-03-01 \
  --to 2026-05-31
```

You can also use an ISO week shortcut:

```bash
github-dev-metrics \
  --developer octocat \
  --week 05-2026
```

The commit cadence signal is configurable:

```bash
github-dev-metrics \
  --developer octocat \
  --week 05-2026 \
  --cadence-target 0.7 \
  --cadence-min-days 4
```

```bash
github-dev-metrics \
  --developer octocat \
  --repos example-org/frontend-app,example-org/design-system \
  --from 2026-03-01 \
  --to 2026-05-31 \
  --format csv
```

If `--output` is omitted, the CLI writes the report to `report/<developer>_<period>.md`, `.json`, or `.csv` and prints the written path.

If `--repos` is omitted, the CLI first tries to use the current git repository by reading `remote.origin.url`. Supported auto-detected remote formats include:

- `git@github.com:owner/repo.git`
- `https://github.com/owner/repo.git`
- `ssh://git@github.com/owner/repo.git`

If auto-detection is not possible, pass `--repos` explicitly or provide `--org` to scan the accessible non-archived repositories in that organization.

Run `github-dev-metrics --help` to see all supported options.

## Supported Metrics

Pull request activity:

- PRs opened
- PRs merged
- PRs closed without merge
- PRs still open
- PR titles, URLs, numbers, created date, merged date, closed date
- PR additions, deletions, changed files
- Average PR size
- Largest PRs by changed files and line changes

PR review and quality signals:

- PRs with `CHANGES_REQUESTED`
- PRs with multiple review iterations
- PRs with review comments
- PRs with long time-to-merge
- PRs merged without obvious test changes
- PRs with noisy commit messages such as WIP, fixup, revert, merge branch, and merge remote

Testing signals:

- PRs that touched test files
- PRs that did not touch test files
- Test file detection for `.test.`, `.spec.`, `__tests__`, `/tests/`, and `/test/`

Commit activity:

- Commits authored by the developer in the date range
- Commit messages
- Commit URLs when available
- Noisy commit messages
- Revert commits
- Commit cadence based on active days in the selected period, including WIP commits as valid evidence of consistency
- Commit cadence threshold can be adjusted with `--cadence-target` and `--cadence-min-days`

Review participation:

- Reviews submitted by the developer on other PRs, best-effort
- Review comments submitted by the developer, best-effort

Report interpretation:

- Executive summary
- Positive signals
- Areas of opportunity
- Pull request evidence
- Testing evidence
- Git hygiene evidence
- Review participation evidence
- Suggested follow-up questions for a review conversation

CSV export:

- One row per pull request for analytics-friendly ingestion
- Flattened scalar columns for dates, counts, sizes, and boolean flags
- Pipe-delimited detail columns for repository lists, test files, and PR commit messages

## GitHub Token Permissions

The tool uses the GitHub REST API. The token should have enough access to read the target repositories and pull request metadata.

Recommended token types:

- Fine-grained personal access token with read access to the selected repositories or organization repositories you want to scan
- Classic personal access token with `repo` scope for private repositories

## Known Limitations

- Review participation is best-effort. GitHub search and visibility rules can prevent a complete picture of review activity.
- Commit author matching depends on GitHub associating commits with the provided username through the REST API.
- The tool detects test files using filename patterns only; it does not understand test semantics.
- “Long time-to-merge” is currently flagged at more than 7 days from PR creation to merge.
- The built-in `.env` loader is intentionally small and supports simple `KEY=VALUE` lines.
- If you use `direnv`, you must run `direnv allow` once after creating or changing `.envrc`.
- `--week` accepts `WW-YYYY` and `YYYY-Www`.
- Org-wide mode only includes repositories visible to the token and can take noticeably longer on large organizations.

## Running Tests

```bash
make install
make test
.venv/bin/python -m github_dev_metrics.cli --help
make ui HOST=127.0.0.1 PORT=8501
```

## Web UI

Run the local UI with:

```bash
make ui HOST=127.0.0.1 PORT=8501
```

Then open the printed URL in your browser.

The UI uses the same GitHub token loading behavior as the CLI:

- shell `GITHUB_TOKEN`
- local `.env`
- `direnv` if enabled

## Project Layout

```text
github-dev-metrics/
├── github_dev_metrics/
│   ├── __init__.py
│   ├── cli.py
│   ├── web_app.py
│   ├── github_client.py
│   ├── collectors.py
│   ├── metrics.py
│   ├── report_markdown.py
│   ├── report_json.py
│   └── models.py
├── tests/
│   ├── test_metrics.py
│   ├── test_report_markdown.py
│   └── test_collectors.py
├── .env.example
├── README.md
├── pyproject.toml
├── Makefile
└── requirements.txt
```
