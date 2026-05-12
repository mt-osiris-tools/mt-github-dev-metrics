from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .cli import _load_local_env_file
from .collectors import (
    collect_metrics,
    end_of_day,
    normalize_repo_specs,
    parse_iso_date,
    parse_iso_week,
    start_of_day,
)
from .github_client import GithubAPIError, GithubAuthError, GithubClient
from .metrics import calculate_metrics
from .report_json import render_json_report
from .report_markdown import render_markdown_report


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitHub Dev Metrics</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f0e8;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #d1c7b7;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 26%),
                  linear-gradient(180deg, #f8f4ed 0%, #f4f0e8 100%);
      color: var(--text);
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }
    .hero {
      display: grid;
      gap: 18px;
      grid-template-columns: 1.35fr 0.65fr;
      align-items: stretch;
      margin-bottom: 24px;
    }
    .card {
      background: var(--panel);
      border: 1px solid rgba(209, 199, 183, 0.75);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }
    .hero-copy { padding: 28px; }
    .eyebrow { text-transform: uppercase; letter-spacing: 0.14em; color: var(--accent); font-size: 12px; font-weight: 700; }
    h1 { margin: 10px 0 12px; font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1.02; }
    .lede { margin: 0; color: var(--muted); font-size: 1rem; max-width: 62ch; }
    .hero-meta {
      display: grid;
      gap: 14px;
      padding: 24px;
      background: linear-gradient(180deg, #0f766e 0%, #115e59 100%);
      color: white;
    }
    .hero-meta .chip {
      display: inline-flex; width: fit-content; align-items: center; gap: 8px;
      background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.24);
      padding: 8px 12px; border-radius: 999px; font-size: 13px;
    }
    .grid {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 20px;
      align-items: start;
    }
    form { padding: 20px; }
    .section-title { margin: 0 0 14px; font-size: 18px; }
    label { display: block; margin: 14px 0 8px; font-size: 13px; font-weight: 700; color: #374151; }
    input, select, textarea {
      width: 100%; border: 1px solid var(--border); border-radius: 12px;
      padding: 12px 14px; font: inherit; background: white; color: var(--text);
    }
    textarea { min-height: 84px; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .actions { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
    button, .button-link {
      appearance: none; border: 0; border-radius: 12px; padding: 12px 16px; font: inherit;
      background: var(--accent); color: white; cursor: pointer; text-decoration: none; display: inline-flex;
      align-items: center; justify-content: center;
    }
    button.secondary, .button-link.secondary { background: #e5e7eb; color: #111827; }
    button:hover, .button-link:hover { filter: brightness(0.97); }
    .hint { color: var(--muted); font-size: 13px; line-height: 1.45; margin-top: 8px; }
    .error { color: var(--danger); font-weight: 600; margin-top: 12px; white-space: pre-wrap; }
    .output { padding: 20px; min-height: 260px; }
    .stats {
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px;
    }
    .stat {
      background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 16px; padding: 14px;
    }
    .stat .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
    .stat .value { font-size: 24px; font-weight: 800; margin-top: 4px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    .tab {
      border: 1px solid var(--border); background: #f9fafb; color: #111827; border-radius: 999px;
      padding: 8px 14px; cursor: pointer;
    }
    .tab.active { background: var(--accent); color: white; border-color: var(--accent); }
    pre {
      margin: 0; white-space: pre-wrap; word-break: break-word;
      background: #0b1020; color: #e5eefc; border-radius: 16px; padding: 16px; overflow: auto;
      max-height: 65vh;
    }
    .meta { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
    @media (max-width: 980px) {
      .hero, .grid { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="card hero-copy">
        <div class="eyebrow">GitHub Dev Metrics</div>
        <h1>Local review reports for developers.</h1>
        <p class="lede">Generate manager-friendly Markdown and JSON reports from GitHub activity across a date range or ISO week. The app reuses the same metric engine as the CLI.</p>
      </div>
      <div class="card hero-meta">
        <div class="chip">Runs locally</div>
        <div class="chip">Uses GITHUB_TOKEN from your shell or .env</div>
        <div class="chip">Supports markdown and JSON output</div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <form id="report-form">
          <h2 class="section-title">Report inputs</h2>
          <label for="developer">Developer</label>
          <input id="developer" name="developer" placeholder="alan-guerrero" required>

          <label for="org">Organization</label>
          <input id="org" name="org" placeholder="MedTrainer365">

          <label for="repos">Repositories</label>
          <textarea id="repos" name="repos" placeholder="medtrainer-react,design-system or MedTrainer365/medtrainer-react" required></textarea>
          <div class="hint">Use comma-separated repo names. If you provide only repo names, the organization field fills in the owner.</div>

          <div class="row">
            <div>
              <label for="week">ISO Week</label>
              <input id="week" name="week" placeholder="2026-W18">
            </div>
            <div>
              <label for="format">Output</label>
              <select id="format" name="format">
                <option value="markdown">Markdown preview</option>
                <option value="json">JSON preview</option>
              </select>
            </div>
          </div>

          <div class="row">
            <div>
              <label for="date_from">From</label>
              <input id="date_from" name="date_from" type="date">
            </div>
            <div>
              <label for="date_to">To</label>
              <input id="date_to" name="date_to" type="date">
            </div>
          </div>

          <div class="actions">
            <button type="submit">Generate report</button>
            <button type="button" class="secondary" id="fill-example">Fill example</button>
          </div>
          <div class="error" id="form-error" hidden></div>
          <div class="hint">Use either week or from/to, not both.</div>
        </form>
      </div>

      <div class="card output">
        <h2 class="section-title">Result</h2>
        <div id="result-meta" class="meta">No report generated yet.</div>
        <div class="stats" id="stats" hidden>
          <div class="stat"><div class="label">PRs opened</div><div class="value" id="stat-prs-opened">0</div></div>
          <div class="stat"><div class="label">PRs merged</div><div class="value" id="stat-prs-merged">0</div></div>
          <div class="stat"><div class="label">Commits</div><div class="value" id="stat-commits">0</div></div>
          <div class="stat"><div class="label">Tests touched</div><div class="value" id="stat-tests">0</div></div>
        </div>
        <div class="tabs">
          <button type="button" class="tab active" data-view="rendered">Rendered</button>
          <button type="button" class="tab" data-view="raw">Raw JSON</button>
        </div>
        <div class="actions" style="margin-top: 0; margin-bottom: 12px;">
          <a href="#" id="download-markdown" class="button-link secondary" download="github-dev-metrics.md">Download Markdown</a>
          <a href="#" id="download-json" class="button-link secondary" download="github-dev-metrics.json">Download JSON</a>
        </div>
        <pre id="result">Use the form to generate a report.</pre>
      </div>
    </div>
  </div>

  <script>
    const form = document.getElementById('report-form');
    const formError = document.getElementById('form-error');
    const result = document.getElementById('result');
    const resultMeta = document.getElementById('result-meta');
    const stats = document.getElementById('stats');
    const downloadMarkdown = document.getElementById('download-markdown');
    const downloadJson = document.getElementById('download-json');
    const tabs = document.querySelectorAll('.tab');
    const fillExample = document.getElementById('fill-example');
    let current = { rendered: '', raw: '', markdown: '', json: '' };
    let activeView = 'rendered';

    function setError(message) {
      if (!message) {
        formError.hidden = true;
        formError.textContent = '';
        return;
      }
      formError.hidden = false;
      formError.textContent = message;
    }

    function setActiveView(view) {
      activeView = view;
      tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.view === view));
      result.textContent = current[view] || 'No content available.';
    }

    tabs.forEach(tab => {
      tab.addEventListener('click', () => setActiveView(tab.dataset.view));
    });

    fillExample.addEventListener('click', () => {
      document.getElementById('developer').value = 'alan-guerrero';
      document.getElementById('org').value = 'MedTrainer365';
      document.getElementById('repos').value = 'medtrainer-react';
      document.getElementById('week').value = '2026-W18';
      document.getElementById('format').value = 'markdown';
      document.getElementById('date_from').value = '';
      document.getElementById('date_to').value = '';
      setError('');
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      setError('');
      result.textContent = 'Generating report...';
      resultMeta.textContent = 'Working...';
      stats.hidden = true;

      const payload = {
        developer: document.getElementById('developer').value.trim(),
        org: document.getElementById('org').value.trim(),
        repos: document.getElementById('repos').value.trim(),
        week: document.getElementById('week').value.trim(),
        date_from: document.getElementById('date_from').value,
        date_to: document.getElementById('date_to').value,
        format: document.getElementById('format').value,
      };

      try {
        const response = await fetch('/api/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to generate report.');
        }
        current = {
          rendered: data.report.markdown,
          raw: JSON.stringify(data.report, null, 2),
          markdown: data.report.markdown,
          json: JSON.stringify(data.report.json, null, 2),
        };
        resultMeta.textContent = `Period: ${data.report.date_from} to ${data.report.date_to}`;
        stats.hidden = false;
        document.getElementById('stat-prs-opened').textContent = data.report.metrics.pull_requests.opened;
        document.getElementById('stat-prs-merged').textContent = data.report.metrics.pull_requests.merged;
        document.getElementById('stat-commits').textContent = data.report.metrics.commit_activity.authored_commits;
        document.getElementById('stat-tests').textContent = data.report.metrics.testing.prs_with_tests;

        downloadMarkdown.href = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(data.report.markdown);
        downloadJson.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data.report.json, null, 2));
        setActiveView(payload.format === 'json' ? 'raw' : 'rendered');
      } catch (error) {
        setError(error.message);
        resultMeta.textContent = 'No report generated.';
        result.textContent = 'Use the form to generate a report.';
      }
    });
  </script>
</body>
</html>
"""


def _resolve_period(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    week = str(payload.get("week", "")).strip()
    date_from = str(payload.get("date_from", "")).strip()
    date_to = str(payload.get("date_to", "")).strip()
    if week and (date_from or date_to):
        raise ValueError("Use either week or from/to, not both.")
    if week:
        start, end = parse_iso_week(week)
        return start.isoformat(), end.isoformat(), week
    if not date_from or not date_to:
        raise ValueError("Provide either week or both from/to dates.")
    start = start_of_day(parse_iso_date(date_from))
    end = end_of_day(parse_iso_date(date_to))
    if start > end:
        raise ValueError("From must be earlier than or equal to to.")
    return start.isoformat(), end.isoformat(), None


def build_report_payload(payload: dict[str, Any], client: GithubClient | None = None) -> dict[str, Any]:
    developer = str(payload.get("developer", "")).strip()
    if not developer:
        raise ValueError("Developer is required.")
    org = str(payload.get("org", "")).strip() or None
    repos_raw = str(payload.get("repos", "")).strip()
    if not repos_raw:
        raise ValueError("At least one repository is required.")
    repos = [repo.strip() for repo in repos_raw.split(",") if repo.strip()]
    normalize_repo_specs(repos, org)
    from_value, to_value, week = _resolve_period(payload)

    client = client or GithubClient.from_env()
    report = calculate_metrics(
        collect_metrics(
            client,
            developer=developer,
            org=org,
            repos=repos,
            date_from=start_of_day(parse_iso_date(from_value[:10])),
            date_to=end_of_day(parse_iso_date(to_value[:10])),
        )
    )
    markdown = render_markdown_report(report)
    json_report = report.to_dict()
    return {
        "developer": developer,
        "org": org,
        "repos": repos,
        "week": week,
        "date_from": report.date_from,
        "date_to": report.date_to,
        "markdown": markdown,
        "json": json_report,
        "metrics": report.metrics,
    }


class WebHandler(BaseHTTPRequestHandler):
    server_version = "github-dev-metrics/0.1.0"

    def _send_html(self, content: str, status: int = HTTPStatus.OK) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/":
            self._send_html(HTML_TEMPLATE)
            return
        if urlparse(self.path).path == "/health":
            self._send_json({"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/report":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        content_type = self.headers.get("Content-Type", "")
        try:
            if "application/json" in content_type:
                payload = json.loads(raw or "{}")
            else:
                payload = {key: values[0] for key, values in parse_qs(raw).items()}
            report = build_report_payload(payload)
            response = {"report": report}
            self._send_json(response)
        except (ValueError, GithubAuthError, GithubAPIError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive
            self._send_json({"error": f"Unexpected error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def run_server(host: str = "127.0.0.1", port: int = 8501) -> None:
    _load_local_env_file()
    server = ThreadingHTTPServer((host, port), WebHandler)
    print(f"GitHub Dev Metrics UI available at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Launch the GitHub developer metrics UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8501, type=int)
    args = parser.parse_args(argv)
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
