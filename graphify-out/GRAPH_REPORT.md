# Graph Report - mt-github-dev-metrics  (2026-06-01)

## Corpus Check
- 19 files · ~13,459 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 158 nodes · 378 edges · 14 communities (7 shown, 7 thin omitted)
- Extraction: 78% EXTRACTED · 22% INFERRED · 0% AMBIGUOUS · INFERRED: 82 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c73d678d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `GithubClient` - 23 edges
2. `collect_metrics()` - 20 edges
3. `calculate_metrics()` - 18 edges
4. `GithubAPIError` - 17 edges
5. `build_report_payload()` - 15 edges
6. `main()` - 14 edges
7. `FakeGithubClient` - 13 edges
8. `GithubAuthError` - 13 edges
9. `DeveloperMetrics` - 13 edges
10. `FakeGithubClient` - 10 edges

## Surprising Connections (you probably didn't know these)
- `FakeGithubClient` --uses--> `GithubAPIError`  [INFERRED]
  tests/test_collectors.py → github_dev_metrics/github_client.py
- `test_parse_iso_date_validates_format()` --calls--> `parse_iso_date()`  [INFERRED]
  tests/test_collectors.py → github_dev_metrics/collectors.py
- `test_parse_iso_week_returns_week_range()` --calls--> `parse_iso_week()`  [INFERRED]
  tests/test_collectors.py → github_dev_metrics/collectors.py
- `test_normalize_repo_specs_validates_repo_format()` --calls--> `normalize_repo_specs()`  [INFERRED]
  tests/test_collectors.py → github_dev_metrics/collectors.py
- `test_load_local_env_file_reads_dotenv()` --calls--> `_load_local_env_file()`  [INFERRED]
  tests/test_collectors.py → github_dev_metrics/cli.py

## Communities (14 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.17
Nodes (23): Any, build_parser(), _load_local_env_file(), main(), _parse_env_line(), _write_output(), collect_metrics(), end_of_day() (+15 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (23): calculate_metrics(), _commit_cadence(), _days_between(), _has_test_changes(), is_noisy_commit_message(), is_revert_commit(), is_test_file(), _parse_dt() (+15 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (9): from_env(), GithubAPIError, GithubAuthError, GithubClient, GithubError, _to_datetime(), RepoRef, GithubClient (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.18
Nodes (10): CLI Usage, Environment, github-dev-metrics, GitHub Token Permissions, Installation, Known Limitations, Project Layout, Running Tests (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.35
Nodes (6): BaseHTTPRequestHandler, main(), run_server(), WebHandler, int, str

### Community 7 - "Community 7"
Cohesion: 0.73
Nodes (5): fmt_cadence(), _fmt_date(), _fmt_number(), _pr_line(), render_markdown_report()

### Community 13 - "Community 13"
Cohesion: 0.29
Nodes (4): _extract_pr_from_search_item(), _parse_datetime(), _pull_review_records(), _within_range()

## Knowledge Gaps
- **13 isolated node(s):** `PreToolUse`, `Installation`, `Environment`, `CLI Usage`, `Supported Metrics` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GithubAPIError` connect `Community 2` to `Community 0`, `Community 3`, `Community 13`, `Community 6`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `build_report_payload()` connect `Community 0` to `Community 1`, `Community 2`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `GithubClient` connect `Community 2` to `Community 0`, `Community 13`, `Community 6`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `GithubClient` (e.g. with `Any` and `RepoRef`) actually correct?**
  _`GithubClient` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `collect_metrics()` (e.g. with `main()` and `GithubAPIError`) actually correct?**
  _`collect_metrics()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `calculate_metrics()` (e.g. with `main()` and `EvidenceSummary`) actually correct?**
  _`calculate_metrics()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `GithubAPIError` (e.g. with `Any` and `collect_metrics()`) actually correct?**
  _`GithubAPIError` has 8 INFERRED edges - model-reasoned connections that need verification._