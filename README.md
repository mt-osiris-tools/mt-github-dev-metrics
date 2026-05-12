# github-dev-metrics

`github-dev-metrics` is a Python CLI for collecting GitHub activity metrics for a specific developer across one or more repositories. It is intended for performance reviews, onboarding reviews, growth plans, and manager 1:1 preparation.

## Installation

```bash
pip install -e .
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

The included `.envrc` will load `.env` if present.

## CLI Usage

```bash
github-dev-metrics \
  --developer alan-guerrero \
  --org my-org \
  --repos frontend-app,design-system \
  --from 2026-03-01 \
  --to 2026-05-31 \
  --format markdown \
  --output reports/alan-github-metrics.md
```

You can also use an ISO week shortcut:

```bash
github-dev-metrics \
  --developer alan-guerrero \
  --org my-org \
  --repos frontend-app,design-system \
  --week 2026-W18 \
  --format markdown \
  --output reports/alan-github-metrics.md
```

The commit cadence signal is configurable:

```bash
github-dev-metrics \
  --developer alan-guerrero \
  --org MedTrainer365 \
  --repos medtrainer-react \
  --week 2026-W18 \
  --cadence-target 0.7 \
  --cadence-min-days 4 \
  --format markdown
```

```bash
github-dev-metrics \
  --developer alan-guerrero \
  --repos my-org/frontend-app,my-org/design-system \
  --from 2026-03-01 \
  --to 2026-05-31 \
  --format json \
  --output reports/alan-github-metrics.json
```

If `--output` is omitted, the report is written to stdout.

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
- Suggested follow-up questions for a 1:1

## GitHub Token Permissions

The tool uses the GitHub REST API. The token should have enough access to read the target repositories and pull request metadata.

Recommended token types:

- Fine-grained personal access token with read access to the selected repositories
- Classic personal access token with `repo` scope for private repositories

## Known Limitations

- Review participation is best-effort. GitHub search and visibility rules can prevent a complete picture of review activity.
- Commit author matching depends on GitHub associating commits with the provided username through the REST API.
- The tool detects test files using filename patterns only; it does not understand test semantics.
- “Long time-to-merge” is currently flagged at more than 7 days from PR creation to merge.
- The built-in `.env` loader is intentionally small and supports simple `KEY=VALUE` lines.
- If you use `direnv`, you must run `direnv allow` once after cloning or changing `.envrc`.
- `--week` expects ISO week format `YYYY-Www`.

## Running Tests

```bash
python -m pytest
```

If you prefer a single command flow:

```bash
make install
make test
make run ARGS="--help"
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
