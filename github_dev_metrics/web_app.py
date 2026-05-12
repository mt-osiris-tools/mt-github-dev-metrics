from __future__ import annotations

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
    .report-view {
      border-radius: 18px;
      min-height: 300px;
    }
    .detail-shell {
      display: grid;
      gap: 16px;
    }
    .toc-shell {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 16px;
      align-items: start;
    }
    .toc-card {
      position: sticky;
      top: 20px;
      align-self: start;
      background: #fff;
      border: 1px solid #e5ded3;
      border-radius: 18px;
      padding: 16px;
    }
    .toc-card h3 {
      margin: 0 0 10px;
      font-size: 16px;
    }
    .toc-links {
      display: grid;
      gap: 8px;
    }
    .toc-links a {
      color: #0f766e;
      text-decoration: none;
      font-size: 14px;
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }
    .toc-links a:hover { text-decoration: underline; }
    .toc-count {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .detail-card {
      background: #fff;
      border: 1px solid #e5ded3;
      border-radius: 18px;
      padding: 18px;
    }
    .detail-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .detail-header h2 {
      margin: 4px 0 6px;
      font-size: 24px;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .detail-metric {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
    }
    .detail-metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .detail-metric .value {
      font-size: 26px;
      font-weight: 800;
      margin-top: 4px;
    }
    .detail-section-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 12px;
    }
    .detail-section-title h3 {
      margin: 0;
      font-size: 18px;
    }
    .summary-columns {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-box {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
    }
    .summary-box h4 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .summary-list {
      margin: 0;
      padding-left: 18px;
      color: #374151;
      display: grid;
      gap: 8px;
    }
    .summary-list li { line-height: 1.45; }
    .badge-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .badge.good { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
    .badge.warn { background: #fef3c7; color: #92400e; border-color: #fcd34d; }
    .badge.info { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
    .badge.neutral { background: #f3f4f6; color: #374151; border-color: #d1d5db; }
    .pr-list {
      display: grid;
      gap: 12px;
    }
    .filter-bar {
      display: grid;
      grid-template-columns: 1.1fr 0.7fr 0.7fr 0.5fr;
      gap: 10px;
      margin-bottom: 14px;
    }
    .filter-bar input, .filter-bar select {
      border-radius: 12px;
      padding: 10px 12px;
    }
    .filter-toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      background: #fff;
      font-size: 13px;
      color: #374151;
    }
    .filter-toggle input { width: auto; }
    .pr-card {
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      background: #fafafa;
      overflow: hidden;
    }
    .pr-card summary {
      list-style: none;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      padding: 14px 16px;
    }
    .pr-card summary::-webkit-details-marker { display: none; }
    .pr-card-body {
      border-top: 1px solid #e5e7eb;
      padding: 14px 16px 16px;
      background: #fff;
      display: grid;
      gap: 12px;
    }
    .pr-title {
      font-size: 15px;
      font-weight: 800;
      margin: 0 0 6px;
    }
    .pr-meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px 16px;
      color: #374151;
      font-size: 13px;
    }
    .pr-meta div strong { color: #111827; }
    .pill-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      background: #eef2ff;
      color: #3730a3;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
    }
    .signal-score {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 74px;
      height: 30px;
      border-radius: 999px;
      padding: 0 12px;
      font-size: 12px;
      font-weight: 800;
      color: white;
    }
    .signal-score.good { background: #059669; }
    .signal-score.warn { background: #d97706; }
    .signal-score.risk { background: #b91c1c; }
    .field-label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }
    .detail-list {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }
    .empty-state {
      color: var(--muted);
      border: 1px dashed #d1d5db;
      padding: 18px;
      border-radius: 16px;
      background: #fcfcfd;
    }
    .raw-pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #0b1020;
      color: #e5eefc;
      border-radius: 16px;
      padding: 16px;
      overflow: auto;
      max-height: 70vh;
    }
    .meta { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
    .summary-bars {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .bar-card {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
    }
    .bar-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
    }
    .bar-label { font-size: 13px; font-weight: 700; color: #111827; }
    .bar-value { font-size: 12px; color: var(--muted); font-weight: 700; }
    .bar-track {
      height: 12px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: inherit;
      width: 0%;
    }
    .bar-fill.good { background: linear-gradient(90deg, #10b981, #059669); }
    .bar-fill.warn { background: linear-gradient(90deg, #f59e0b, #d97706); }
    .bar-fill.risk { background: linear-gradient(90deg, #ef4444, #b91c1c); }
    .comparison-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .comparison-panel {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
    }
    .comparison-panel h4 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .comparison-panel p {
      margin: 0;
      color: #374151;
      font-size: 13px;
      line-height: 1.45;
    }
    @media (max-width: 980px) {
      .hero, .grid { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toc-shell, .filter-bar, .summary-bars, .comparison-grid { grid-template-columns: 1fr; }
      .detail-grid, .summary-columns, .pr-meta { grid-template-columns: 1fr; }
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
              <label for="cadence_target">Cadence target</label>
              <input id="cadence_target" name="cadence_target" type="number" min="0.1" max="1" step="0.05" value="0.6">
            </div>
            <div>
              <label for="cadence_min_days">Min active days</label>
              <input id="cadence_min_days" name="cadence_min_days" type="number" min="1" step="1" value="5">
              <div class="actions" style="margin-top: 10px;">
                <button type="button" class="secondary" id="reset-cadence">Reset cadence settings</button>
              </div>
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
          <button type="button" class="tab active" data-view="detail">Detail</button>
          <button type="button" class="tab" data-view="markdown">Markdown</button>
          <button type="button" class="tab" data-view="raw">Raw JSON</button>
        </div>
        <div class="actions" style="margin-top: 0; margin-bottom: 12px;">
          <a href="#" id="download-markdown" class="button-link secondary" download="github-dev-metrics.md">Download Markdown</a>
          <a href="#" id="download-json" class="button-link secondary" download="github-dev-metrics.json">Download JSON</a>
        </div>
        <div id="result" class="report-view">Use the form to generate a report.</div>
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
    const cadenceTargetInput = document.getElementById('cadence_target');
    const cadenceMinDaysInput = document.getElementById('cadence_min_days');
    const resetCadenceButton = document.getElementById('reset-cadence');
    let current = { detail: '', markdown: '', raw: '', report: null, defaultRiskOnly: false };
    let activeView = 'detail';
    const cadenceStorageKey = 'github-dev-metrics:cadence-settings';

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function fmtNumber(value) {
      if (value === null || value === undefined || value === '') return '-';
      if (typeof value === 'number' && Number.isInteger(value)) return String(value);
      if (typeof value === 'number') return value.toFixed(2);
      return String(value);
    }

    function listToHtml(items, emptyText = 'None') {
      if (!items || !items.length) {
        return `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
      }
      return `<ul class="summary-list">${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
    }

    function badge(text, kind = 'neutral') {
      return `<span class="badge ${kind}">${escapeHtml(text)}</span>`;
    }

    function pill(text) {
      return `<span class="pill">${escapeHtml(text)}</span>`;
    }

    function scoreClass(score) {
      if (score >= 4) return 'good';
      if (score >= 2) return 'warn';
      return 'risk';
    }

    function percent(part, total) {
      if (!total) return 0;
      return Math.max(0, Math.min(100, Math.round((part / total) * 100)));
    }

    function loadCadenceSettings() {
      try {
        const raw = window.localStorage.getItem(cadenceStorageKey);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          if (parsed.cadence_target !== undefined) {
            cadenceTargetInput.value = String(parsed.cadence_target);
          }
          if (parsed.cadence_min_days !== undefined) {
            cadenceMinDaysInput.value = String(parsed.cadence_min_days);
          }
        }
      } catch (error) {
        return;
      }
    }

    function saveCadenceSettings() {
      try {
        window.localStorage.setItem(
          cadenceStorageKey,
          JSON.stringify({
            cadence_target: cadenceTargetInput.value,
            cadence_min_days: cadenceMinDaysInput.value,
          }),
        );
      } catch (error) {
        return;
      }
    }

    function resetCadenceSettings() {
      cadenceTargetInput.value = '0.6';
      cadenceMinDaysInput.value = '5';
      try {
        window.localStorage.removeItem(cadenceStorageKey);
      } catch (error) {
        return;
      }
    }

    function prSignalMap(report) {
      const testing = report.metrics?.testing ?? {};
      const hygiene = report.metrics?.git_hygiene ?? {};
      const evidence = report.metrics?.evidence ?? {};
      const noisy = hygiene.prs_with_noisy_commits ?? [];
      const mergedWithoutTests = testing.merged_without_test_changes ?? [];
      const noisyMap = new Map(noisy.map(item => [`${item.repo}#${item.number}`, item.messages || []]));
      const mergedWithoutTestsSet = new Set(mergedWithoutTests.map(item => `${item.repo}#${item.number}`));
      return { noisyMap, mergedWithoutTestsSet, testing, evidence };
    }

    function renderPrCard(pr, report) {
      const key = `${pr.repo}#${pr.number}`;
      const { noisyMap, mergedWithoutTestsSet, testing, evidence } = prSignalMap(report);
      const testFiles = testing.pr_test_files?.[key] || [];
      const reviewStates = evidence.pr_review_states?.[key] || {};
      const reviewIterations = evidence.pr_review_iterations?.[key] ?? 0;
      const timeToMerge = evidence.pr_time_to_merge_days?.[key];
      const noisyMessages = noisyMap.get(key) || [];
      const riskReasons = [];
      if (pr.state === 'open') riskReasons.push('PR is still open');
      if (!testFiles.length) riskReasons.push('No obvious test files were touched');
      if (noisyMessages.length) riskReasons.push('Contains noisy commit messages');
      if (mergedWithoutTestsSet.has(key)) riskReasons.push('Merged without obvious test changes');
      if ((pr.review_comments || []).length) riskReasons.push('Has review comments');
      const riskScore = [
        pr.state === 'open' ? 1 : 0,
        testFiles.length ? 0 : 1,
        noisyMessages.length ? 1 : 0,
        mergedWithoutTestsSet.has(key) ? 1 : 0,
        (pr.review_comments || []).length ? 1 : 0,
      ].reduce((sum, value) => sum + value, 0);
      const badges = [];
      if (pr.merged_at) badges.push(badge('Merged', 'good'));
      else if (pr.state === 'open') badges.push(badge('Open', 'info'));
      else badges.push(badge('Closed', 'neutral'));
      if (testFiles.length) badges.push(badge('Touched tests', 'good'));
      else badges.push(badge('No tests', 'warn'));
      if (noisyMessages.length) badges.push(badge('Noisy commits', 'warn'));
      if (mergedWithoutTestsSet.has(key)) badges.push(badge('Merged without tests', 'warn'));

      const reviewStateEntries = Object.entries(reviewStates)
        .map(([state, count]) => `${state}: ${count}`)
        .join(', ');

      return `
        <details class="pr-card" data-risk-score="${riskScore}" data-status="${pr.merged_at ? 'merged' : pr.state}" data-has-tests="${testFiles.length ? '1' : '0'}" data-noisy="${noisyMessages.length ? '1' : '0'}">
          <summary>
            <div>
              <div class="pr-title">${escapeHtml(pr.repo)}#${pr.number} ${escapeHtml(pr.title)}</div>
              <div class="meta">${escapeHtml(pr.state)}${pr.merged_at ? ` · merged ${escapeHtml(pr.merged_at)}` : ''}</div>
            </div>
            <div class="pill-row">
              <span class="signal-score ${scoreClass(riskScore)}">${riskScore >= 4 ? 'High risk' : riskScore >= 2 ? 'Medium risk' : 'Low risk'}</span>
              ${badges.join('')}
            </div>
          </summary>
          <div class="pr-card-body">
            <div class="pr-meta">
              <div><strong>URL:</strong> <a href="${escapeHtml(pr.url)}" target="_blank" rel="noreferrer">${escapeHtml(pr.url)}</a></div>
              <div><strong>Created:</strong> ${escapeHtml(pr.created_at)}</div>
              <div><strong>Closed:</strong> ${escapeHtml(pr.closed_at || '-')}</div>
              <div><strong>Merged:</strong> ${escapeHtml(pr.merged_at || '-')}</div>
              <div><strong>Changes:</strong> +${fmtNumber(pr.additions)} / -${fmtNumber(pr.deletions)} / ${fmtNumber(pr.changed_files)} files</div>
              <div><strong>Time to merge:</strong> ${fmtNumber(timeToMerge)} days</div>
            </div>
            <div>
              <div class="field-label">Review state</div>
              <div>${escapeHtml(reviewStateEntries || 'No reviews found')}</div>
            </div>
            <div>
              <div class="field-label">Review iterations</div>
              <div>${fmtNumber(reviewIterations)}</div>
            </div>
            <div>
              <div class="field-label">Test files</div>
              <div>${listToHtml(testFiles, 'No obvious test files were touched.')}</div>
            </div>
            <div>
              <div class="field-label">Noisy commits</div>
              <div>${listToHtml(noisyMessages, 'No noisy commit messages detected.')}</div>
            </div>
            <div>
              <div class="field-label">Risk reasons</div>
              <div>${listToHtml(riskReasons, 'No obvious risk signals were detected.')}</div>
            </div>
          </div>
        </details>
      `;
    }

    function buildDetailHtml(report) {
      const metrics = report.metrics || {};
      const pullRequests = metrics.pull_requests || {};
      const testing = metrics.testing || {};
      const gitHygiene = metrics.git_hygiene || {};
      const commitActivity = metrics.commit_activity || {};
      const reviewParticipation = metrics.review_participation || {};
      const prs = report.prs || [];
      const summary = report.summary || {};
      const prsOpened = Number(pullRequests.opened || 0);
      const prsMerged = Number(pullRequests.merged || 0);
      const prsWithTests = Number(testing.prs_with_tests || 0);
      const prsWithoutTests = Number(testing.prs_without_tests || 0);
      const noisyPrs = Number(gitHygiene.prs_with_noisy_commits?.length || 0);
      const requestedChanges = Number(pullRequests.requested_changes || 0);
      const reviewComments = Number(reviewParticipation.review_comments || 0);
      const reviewSubmissions = Number(reviewParticipation.submitted_reviews || 0);
      const testCoveragePercent = percent(prsWithTests, prsOpened);
      const reviewFriction = requestedChanges + noisyPrs + reviewComments;
      const cadencePct = Math.round((Number(cadence.coverage_ratio || 0) * 100));
      const followUps = [
        'What validation steps were completed before opening the PR?',
        'Which parts of the implementation were covered by automated tests?',
        'What would help reduce review iterations on similar work?',
      ];

      return `
        <div class="detail-shell">
          <section class="detail-card" id="detail-summary">
            <div class="toc-shell">
              <div class="toc-card">
                <h3>On this page</h3>
                <div class="toc-links">
                  <a href="#detail-summary"><span>Summary</span><span class="toc-count">${fmtNumber(prsOpened)} PRs</span></a>
                  <a href="#detail-metrics"><span>Metrics overview</span><span class="toc-count">${fmtNumber(prsMerged)} merged</span></a>
                  <a href="#detail-prs"><span>Pull request evidence</span><span class="toc-count">${fmtNumber(prs.length)} items</span></a>
                  <a href="#detail-testing"><span>Testing evidence</span><span class="toc-count">${fmtNumber(prsWithTests)} with tests</span></a>
                  <a href="#detail-cadence"><span>Commit cadence</span><span class="toc-count">${fmtNumber(cadence.active_days || 0)}/${fmtNumber(cadence.period_days || 0)}</span></a>
                  <a href="#detail-git"><span>Git hygiene</span><span class="toc-count">${fmtNumber(noisyPrs)} noisy</span></a>
                  <a href="#detail-review"><span>Review participation</span><span class="toc-count">${fmtNumber(reviewSubmissions)} reviews</span></a>
                  <a href="#detail-followup"><span>Follow-up questions</span><span class="toc-count">3 prompts</span></a>
                </div>
              </div>
              <div>
                <div class="detail-header">
                  <div>
                    <div class="eyebrow">Detail page</div>
                    <h2>${escapeHtml(report.developer)}</h2>
                    <div class="meta">Period: ${escapeHtml(report.date_from)} to ${escapeHtml(report.date_to)}</div>
                  </div>
                  <div class="badge-row">
                    ${badge(`Repos: ${(report.repos || []).join(', ')}`, 'info')}
                    ${report.week ? badge(`Week ${report.week}`, 'neutral') : badge('Custom range', 'neutral')}
                  </div>
                </div>
                <div class="badge-row" style="margin-top: 14px;">
                  ${badge(`PRs ${fmtNumber(prsOpened)}`, prsOpened ? 'info' : 'neutral')}
                  ${badge(`Merged ${fmtNumber(prsMerged)}`, prsMerged ? 'good' : 'neutral')}
                  ${badge(`Noisy PRs ${fmtNumber(noisyPrs)}`, noisyPrs ? 'warn' : 'neutral')}
                  ${badge(`Cadence ${fmtNumber(cadence.active_days || 0)}/${fmtNumber(cadence.period_days || 0)} days`, cadence.has_almost_daily_cadence ? 'good' : 'neutral')}
                </div>
              </div>
            </div>
          </section>

          <section class="detail-grid" id="detail-metrics">
            <div class="detail-metric"><div class="label">PRs opened</div><div class="value">${fmtNumber(pullRequests.opened)}</div></div>
            <div class="detail-metric"><div class="label">PRs merged</div><div class="value">${fmtNumber(pullRequests.merged)}</div></div>
            <div class="detail-metric"><div class="label">Commits</div><div class="value">${fmtNumber(commitActivity.authored_commits)}</div></div>
            <div class="detail-metric"><div class="label">Tests touched</div><div class="value">${fmtNumber(testing.prs_with_tests)}</div></div>
          </section>

          <section class="detail-card">
            <div class="detail-section-title">
              <h3>Executive Summary</h3>
            </div>
            <div class="summary-columns">
              <div class="summary-box">
                <h4>Positive signals</h4>
                ${listToHtml(summary.positive_signals || [], 'No strong positive signals were identified from the available data.')}
              </div>
              <div class="summary-box">
                <h4>Areas of opportunity</h4>
                ${listToHtml(summary.opportunity_signals || [], 'No clear opportunities were identified from the available data.')}
              </div>
            </div>
            <div class="comparison-grid">
              <div class="comparison-panel">
                <h4>Positive signals count</h4>
                <div class="detail-metric" style="padding: 12px; margin-bottom: 10px;">
                  <div class="label">Items identified</div>
                  <div class="value">${fmtNumber((summary.positive_signals || []).length)}</div>
                </div>
                <p>These signals highlight ownership, throughput, and collaboration evidence that may support a positive performance narrative.</p>
              </div>
              <div class="comparison-panel">
                <h4>Opportunity signals count</h4>
                <div class="detail-metric" style="padding: 12px; margin-bottom: 10px;">
                  <div class="label">Items identified</div>
                  <div class="value">${fmtNumber((summary.opportunity_signals || []).length)}</div>
                </div>
                <p>These signals point to review friction, incomplete testing signals, or git hygiene concerns worth discussing in a 1:1.</p>
              </div>
            </div>
          </section>

          <section class="detail-card">
            <div class="detail-section-title">
              <h3>Metrics Overview</h3>
            </div>
            <div class="badge-row">
              ${badge(`Closed without merge: ${fmtNumber(pullRequests.closed_without_merge)}`, pullRequests.closed_without_merge ? 'warn' : 'neutral')}
              ${badge(`Open: ${fmtNumber(pullRequests.open)}`, pullRequests.open ? 'info' : 'neutral')}
              ${badge(`Requested changes: ${fmtNumber(pullRequests.requested_changes)}`, pullRequests.requested_changes ? 'warn' : 'neutral')}
              ${badge(`Multiple review iterations: ${fmtNumber(pullRequests.multiple_review_iterations)}`, pullRequests.multiple_review_iterations ? 'warn' : 'neutral')}
              ${badge(`With review comments: ${fmtNumber(pullRequests.with_review_comments)}`, pullRequests.with_review_comments ? 'info' : 'neutral')}
              ${badge(`Long time-to-merge: ${fmtNumber(pullRequests.long_time_to_merge)}`, pullRequests.long_time_to_merge ? 'warn' : 'neutral')}
              ${badge(`Noisy PRs: ${fmtNumber(noisyPrs)}`, noisyPrs ? 'warn' : 'neutral')}
            </div>
            <div class="summary-bars">
              <div class="bar-card">
                <div class="bar-top">
                  <div class="bar-label">Testing coverage</div>
                  <div class="bar-value">${fmtNumber(prsWithTests)} of ${fmtNumber(prsOpened)} PRs</div>
                </div>
                <div class="bar-track"><div class="bar-fill good" style="width: ${testCoveragePercent}%"></div></div>
              </div>
              <div class="bar-card">
                <div class="bar-top">
                  <div class="bar-label">Review friction</div>
                  <div class="bar-value">${fmtNumber(reviewFriction)} signals</div>
                </div>
                <div class="bar-track"><div class="bar-fill ${reviewFriction >= 4 ? 'risk' : reviewFriction >= 2 ? 'warn' : 'good'}" style="width: ${Math.min(100, reviewFriction * 20)}%"></div></div>
              </div>
              <div class="bar-card">
                <div class="bar-top">
                  <div class="bar-label">Commit cadence</div>
                  <div class="bar-value">${fmtNumber(cadence.active_days || 0)} of ${fmtNumber(cadence.period_days || 0)} days</div>
                </div>
                <div class="bar-track"><div class="bar-fill ${cadence.has_almost_daily_cadence ? 'good' : cadencePct >= 40 ? 'warn' : 'risk'}" style="width: ${cadencePct}%"></div></div>
              </div>
            </div>
          </section>

          <section class="detail-card" id="detail-cadence">
            <div class="detail-section-title">
              <h3>Commit Cadence Evidence</h3>
            </div>
            <div class="summary-columns">
              <div class="summary-box">
                <h4>Cadence summary</h4>
                ${listToHtml([
                  `Active days: ${fmtNumber(cadence.active_days || 0)} of ${fmtNumber(cadence.period_days || 0)}`,
                  `Coverage: ${cadencePct}%`,
                  cadence.has_almost_daily_cadence ? 'Matches the almost-daily commit practice.' : 'Below the almost-daily commit practice.',
                ])}
              </div>
              <div class="summary-box">
                <h4>Interpretation</h4>
                <p style="margin: 0; color: #374151; line-height: 1.45;">
                  This section treats a steady commit pattern as positive evidence. It includes WIP commits as valid signals, because the practice values showing up consistently even when work is still in progress.
                </p>
              </div>
            </div>
          </section>

          <section class="detail-card" id="detail-prs">
            <div class="detail-section-title">
              <h3>Pull Request Evidence</h3>
            </div>
            <div class="filter-bar">
              <input id="pr-filter-search" type="search" placeholder="Search PR title, repo, or number">
              <select id="pr-filter-status">
                <option value="all">All statuses</option>
                <option value="merged">Merged</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
              </select>
              <select id="pr-filter-signal">
                <option value="all">All signals</option>
                <option value="tests">Touched tests</option>
                <option value="no-tests">No tests</option>
                <option value="noisy">Noisy commits</option>
                <option value="high-risk">High risk</option>
              </select>
              <label class="filter-toggle"><input type="checkbox" id="pr-filter-focus"> Focus risky PRs</label>
              <button type="button" class="secondary" id="pr-filter-high-risk">High risk only</button>
              <button type="button" class="secondary" id="pr-filter-reset">Reset filters</button>
            </div>
            ${prs.length ? `<div class="pr-list">${prs.map(pr => renderPrCard(pr, report)).join('')}</div>` : '<div class="empty-state">No pull requests matched the selection.</div>'}
          </section>

          <section class="detail-card" id="detail-testing">
            <div class="detail-section-title">
              <h3>Testing Evidence</h3>
            </div>
            <div class="detail-list">
              ${Object.entries(testing.pr_test_files || {}).map(([key, files]) => `
                <div>
                  <div class="field-label">${escapeHtml(key)}</div>
                  <div>${listToHtml(files, 'No obvious test files were touched.')}</div>
                </div>
              `).join('') || '<div class="empty-state">No testing evidence available.</div>'}
            </div>
          </section>

          <section class="detail-card" id="detail-git">
            <div class="detail-section-title">
              <h3>Git Hygiene Evidence</h3>
            </div>
            <div class="detail-list">
              ${gitHygiene.prs_with_noisy_commits?.length ? gitHygiene.prs_with_noisy_commits.map(item => `
                <div>
                  <div class="field-label">${escapeHtml(item.repo)}#${item.number}</div>
                  <div>${listToHtml(item.messages || [], 'No noisy commit messages detected.')}</div>
                </div>
              `).join('') : '<div class="empty-state">No noisy commit messages were detected in matching PRs.</div>'}
              ${commitActivity.revert_commits?.length ? `
                <div>
                  <div class="field-label">Revert commits</div>
                  <div>${listToHtml(commitActivity.revert_commits, 'No revert commits detected.')}</div>
                </div>` : ''}
            </div>
          </section>

          <section class="detail-card" id="detail-review">
            <div class="detail-section-title">
              <h3>Review Participation Evidence</h3>
            </div>
            <div class="badge-row" style="margin-bottom: 12px;">
              ${badge(`Reviews submitted: ${fmtNumber(reviewSubmissions)}`, reviewSubmissions ? 'good' : 'neutral')}
              ${badge(`Review comments: ${fmtNumber(reviewComments)}`, reviewComments ? 'good' : 'neutral')}
            </div>
            ${reviewParticipation.items?.length ? `<div class="detail-list">${reviewParticipation.items.map(item => `
              <div>
                <div class="field-label">${escapeHtml(item.repo)}#${item.number} ${escapeHtml(item.title)}</div>
                <div>${fmtNumber(item.submitted_reviews?.length || 0)} review(s), ${fmtNumber(item.review_comments?.length || 0)} comment(s)</div>
              </div>
            `).join('')}</div>` : '<div class="empty-state">No review participation was found through best-effort API queries.</div>'}
          </section>

          <section class="detail-card" id="detail-followup">
            <div class="detail-section-title">
              <h3>Suggested Follow-up Questions for a 1:1</h3>
            </div>
            ${listToHtml(followUps)}
          </section>
        </div>
      `;
    }

    function renderCurrentView() {
      if (activeView === 'detail') {
        result.innerHTML = current.detail || '<div class="empty-state">Use the form to generate a report.</div>';
        attachPrFilters();
        return;
      }
      if (activeView === 'markdown') {
        result.innerHTML = `<pre class="raw-pre">${escapeHtml(current.markdown || 'No markdown available.')}</pre>`;
        return;
      }
      result.innerHTML = `<pre class="raw-pre">${escapeHtml(current.raw || 'No JSON available.')}</pre>`;
    }

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
      renderCurrentView();
    }

    function attachPrFilters() {
      const search = document.getElementById('pr-filter-search');
      const status = document.getElementById('pr-filter-status');
      const signal = document.getElementById('pr-filter-signal');
      const focus = document.getElementById('pr-filter-focus');
      const highRisk = document.getElementById('pr-filter-high-risk');
      const reset = document.getElementById('pr-filter-reset');
      const cards = Array.from(result.querySelectorAll('.pr-card'));
      if (!search || !status || !signal || !focus || !highRisk || !reset || !cards.length) {
        return;
      }
      if (current.defaultRiskOnly) {
        focus.checked = true;
        status.value = 'all';
        signal.value = 'high-risk';
        current.defaultRiskOnly = false;
      }
      const apply = () => {
        const q = search.value.trim().toLowerCase();
        const selectedStatus = status.value;
        const selectedSignal = signal.value;
        const focusMode = focus.checked;
        cards.forEach(card => {
          const text = card.textContent.toLowerCase();
          const cardStatus = card.dataset.status || '';
          const riskScore = Number(card.dataset.riskScore || 0);
          const hasTests = card.dataset.hasTests === '1';
          const isNoisy = card.dataset.noisy === '1';
          const scoreText = card.querySelector('.signal-score')?.textContent.toLowerCase() || '';
          const statusMatch = selectedStatus === 'all' || cardStatus === selectedStatus;
          const signalMatch =
            selectedSignal === 'all' ||
            (selectedSignal === 'tests' && hasTests) ||
            (selectedSignal === 'no-tests' && !hasTests) ||
            (selectedSignal === 'noisy' && isNoisy) ||
            (selectedSignal === 'high-risk' && scoreText.includes('high risk'));
          const searchMatch = !q || text.includes(q);
          const focusMatch = !focusMode || riskScore >= 2;
          card.style.display = statusMatch && signalMatch && searchMatch && focusMatch ? '' : 'none';
        });
      };
      search.oninput = apply;
      status.onchange = apply;
      signal.onchange = apply;
      focus.onchange = apply;
      highRisk.onclick = () => {
        focus.checked = true;
        status.value = 'all';
        signal.value = 'high-risk';
        search.value = '';
        apply();
      };
      reset.onclick = () => {
        search.value = '';
        status.value = 'all';
        signal.value = 'all';
        focus.checked = false;
        apply();
      };
      apply();
    }

    tabs.forEach(tab => {
      tab.addEventListener('click', () => setActiveView(tab.dataset.view));
    });

    loadCadenceSettings();
    cadenceTargetInput.addEventListener('input', saveCadenceSettings);
    cadenceMinDaysInput.addEventListener('input', saveCadenceSettings);
    resetCadenceButton.addEventListener('click', () => {
      resetCadenceSettings();
      setError('');
    });

    fillExample.addEventListener('click', () => {
      document.getElementById('developer').value = 'alan-guerrero';
      document.getElementById('org').value = 'MedTrainer365';
      document.getElementById('repos').value = 'medtrainer-react';
      document.getElementById('week').value = '2026-W18';
      document.getElementById('format').value = 'markdown';
      document.getElementById('cadence_target').value = '0.6';
      document.getElementById('cadence_min_days').value = '5';
      document.getElementById('date_from').value = '';
      document.getElementById('date_to').value = '';
      saveCadenceSettings();
      setError('');
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      setError('');
      result.innerHTML = '<div class="empty-state">Generating report...</div>';
      resultMeta.textContent = 'Working...';
      stats.hidden = true;

      const payload = {
        developer: document.getElementById('developer').value.trim(),
        org: document.getElementById('org').value.trim(),
        repos: document.getElementById('repos').value.trim(),
        week: document.getElementById('week').value.trim(),
        date_from: document.getElementById('date_from').value,
        date_to: document.getElementById('date_to').value,
        cadence_target: document.getElementById('cadence_target').value,
        cadence_min_days: document.getElementById('cadence_min_days').value,
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
          detail: buildDetailHtml(data.report),
          markdown: data.report.markdown,
          raw: JSON.stringify(data.report, null, 2),
          report: data.report,
          defaultRiskOnly: true,
        };
        resultMeta.textContent = `Period: ${data.report.date_from} to ${data.report.date_to}`;
        stats.hidden = false;
        document.getElementById('stat-prs-opened').textContent = data.report.metrics.pull_requests.opened;
        document.getElementById('stat-prs-merged').textContent = data.report.metrics.pull_requests.merged;
        document.getElementById('stat-commits').textContent = data.report.metrics.commit_activity.authored_commits;
        document.getElementById('stat-tests').textContent = data.report.metrics.testing.prs_with_tests;

        downloadMarkdown.href = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(data.report.markdown);
        downloadJson.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data.report.json, null, 2));
        setActiveView(payload.format === 'json' ? 'raw' : 'detail');
      } catch (error) {
        setError(error.message);
        resultMeta.textContent = 'No report generated.';
        result.innerHTML = '<div class="empty-state">Use the form to generate a report.</div>';
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
    cadence_target = float(payload.get("cadence_target", 0.6) or 0.6)
    cadence_min_days = int(payload.get("cadence_min_days", 5) or 5)
    if not 0 < cadence_target <= 1:
        raise ValueError("cadence_target must be a fraction between 0 and 1.")
    if cadence_min_days < 1:
        raise ValueError("cadence_min_days must be at least 1.")

    client = client or GithubClient.from_env()
    report = calculate_metrics(
        collect_metrics(
            client,
            developer=developer,
            org=org,
            repos=repos,
            date_from=start_of_day(parse_iso_date(from_value[:10])),
            date_to=end_of_day(parse_iso_date(to_value[:10])),
        ),
        cadence_target=cadence_target,
        cadence_min_active_days=cadence_min_days,
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
