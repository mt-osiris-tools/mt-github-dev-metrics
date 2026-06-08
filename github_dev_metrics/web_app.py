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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;800&display=swap" rel="stylesheet">
  <style>
    :root {
      color-scheme: light;
      --bg: #fdfdfd;
      --bg-soft: #f4f4f5;
      --panel: rgba(255, 255, 255, 0.75);
      --panel-solid: #ffffff;
      --text: #18181b;
      --muted: #71717a;
      --border: rgba(0, 0, 0, 0.08);
      --border-strong: rgba(0, 0, 0, 0.15);
      --accent: #09090b;
      --accent-dark: #000000;
      --accent-alt: #3f3f46;
      --shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.08);
      --shadow-soft: 0 4px 14px rgba(0, 0, 0, 0.03);
      --danger: #ef4444;
      --danger-dark: #b91c1c;
      --good: #10b981;
      --good-bg: rgba(16, 185, 129, 0.1);
      --warn: #f59e0b;
      --warn-bg: rgba(245, 158, 11, 0.1);
      --info: #3b82f6;
      --info-bg: rgba(59, 130, 246, 0.1);
      --radius: 16px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, hsla(210, 100%, 97%, 1) 0px, transparent 50%),
        radial-gradient(at 100% 100%, hsla(250, 100%, 97%, 1) 0px, transparent 50%);
      background-attachment: fixed;
      color: var(--text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    h1, h2, h3, h4, h5, .section-title, .detail-header h2, .detail-section-title h3, .toc-card h3, .comparison-panel h4, .bar-label, .value {
      font-family: 'Outfit', sans-serif;
      font-weight: 600;
      color: var(--accent);
    }
    a { color: var(--info); text-decoration: none; transition: 0.2s; }
    a:hover { color: var(--info); opacity: 0.8; }
    .wrap {
      width: 100%; max-width: 1400px; margin: 0 auto; padding: 32px;
    }
    .hero { display: grid; gap: 24px; grid-template-columns: 1.5fr 1fr; align-items: stretch; margin-bottom: 32px; }
    .card, .detail-card, .summary-box, .pr-card, .pr-overview-card, .bar-card, .comparison-panel, .dashboard-panel, .dashboard-kpi, .dashboard-signal, .empty-state, .loading-state {
      background: var(--panel);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-soft);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .card:hover, .pr-card:hover, .bar-card:hover, .comparison-panel:hover {
      box-shadow: var(--shadow);
      border-color: var(--border-strong);
      transform: translateY(-2px);
    }
    .eyebrow {
      text-transform: uppercase; letter-spacing: 0.15em; color: var(--muted);
      font-size: 11px; font-weight: 700; margin-bottom: 8px; display: block;
    }
    h1 { margin: 0 0 16px; font-size: 2.5rem; line-height: 1.1; letter-spacing: -0.03em; }
    .admin-header {
      display: flex; flex-wrap: wrap; justify-content: space-between; gap: 24px; align-items: center;
      padding: 32px 40px; margin-bottom: 32px; background: var(--panel-solid);
    }
    .admin-header-copy p { margin: 0; color: var(--muted); font-size: 1.1rem; max-width: 60ch; }
    .admin-header-actions { display: flex; flex-direction: column; gap: 16px; align-items: flex-end; }
    .meta, .hint, .subtext { color: var(--muted); }
    .dashboard-tag, .form-kicker {
      display: inline-flex; align-items: center; gap: 8px; width: fit-content;
      padding: 6px 10px; border-radius: 999px; background: var(--bg-soft);
      color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
    }
    .command-palette {
      display: flex; flex-direction: column; gap: 8px; width: 300px;
    }
    .command-palette .command-label { font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--muted); }
    .command-palette input { width: 100%; border-radius: 8px; padding: 10px 14px; border: 1px solid var(--border); background: var(--bg-soft); }
    .admin-pills { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .admin-pill {
      display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 20px;
      background: var(--bg-soft); color: var(--muted); font-size: 12px; font-weight: 600;
    }
    .app-shell { display: grid; grid-template-columns: 380px 1fr; gap: 32px; align-items: start; }
    .scope-guide { padding: 32px; }
    .scope-guide h2 { margin: 16px 0; font-size: 20px; }
    .scope-guide p { color: var(--muted); margin-bottom: 24px; }
    .scope-guide-list { list-style: none; padding: 0; display: grid; gap: 12px; margin-bottom: 24px; }
    .scope-guide-list li {
      position: relative; padding-left: 20px; color: var(--muted); font-size: 14px;
    }
    .scope-guide-list li::before {
      content: ''; position: absolute; left: 0; top: 8px; width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    }
    .scope-guide-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .badge {
      display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 12px;
      font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .badge.info { background: var(--info-bg); color: var(--info); }
    .badge.neutral { background: var(--bg-soft); color: var(--muted); }
    .badge.good { background: var(--good-bg); color: var(--good); }
    .badge.warn { background: var(--warn-bg); color: var(--warn); }
    .badge.risk, .badge.danger { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
    .form-shell { padding: 32px; }
    .form-intro { margin-bottom: 32px; }
    .form-intro h2 { font-size: 24px; margin: 8px 0; }
    .form-intro p { color: var(--muted); margin: 0 0 24px 0; }
    .scope-command {
      background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 20px; display: grid; gap: 16px;
    }
    .scope-command-head h3 { margin: 0 0 4px; font-size: 16px; }
    .scope-command-head p { margin: 0; font-size: 13px; color: var(--muted); }
    .scope-command-code code {
      display: block; font-family: monospace; font-size: 12px; background: var(--panel-solid);
      padding: 16px; border-radius: 8px; border: 1px solid var(--border); white-space: pre-wrap;
    }
    .scope-command-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .form-section { border-top: 1px solid var(--border); padding-top: 32px; margin-top: 32px; }
    .form-section:first-child { border-top: none; padding-top: 0; margin-top: 0; }
    .form-section-title { margin-bottom: 24px; }
    .form-section-title h3 { margin: 0 0 4px; font-size: 16px; text-transform: uppercase; letter-spacing: 0.05em; }
    .form-section-title span { color: var(--muted); font-size: 13px; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
    .stack { display: grid; gap: 20px; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text); }
    input, select, textarea {
      width: 100%; padding: 12px 16px; border-radius: 10px; border: 1px solid var(--border);
      background: var(--panel-solid); color: var(--text); font-family: inherit; font-size: 14px;
      transition: 0.2s; box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
    }
    input:focus, select:focus, textarea:focus {
      outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,0,0,0.05);
    }
    textarea { min-height: 100px; resize: vertical; }
    .field-hint { font-size: 12px; color: var(--muted); margin-top: 6px; }
    button, .button-link {
      display: inline-flex; align-items: center; justify-content: center;
      padding: 12px 24px; border-radius: 10px; font-weight: 600; font-size: 14px;
      border: none; cursor: pointer; transition: 0.2s;
      background: var(--accent); color: #fff; text-decoration: none;
    }
    button:hover:not(:disabled), .button-link:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); opacity: 0.9; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    input:disabled, select:disabled, textarea:disabled { opacity: 0.7; cursor: not-allowed; background-color: var(--bg-soft); }
    button.secondary, .button-link.secondary {
      background: var(--panel-solid); color: var(--text); border: 1px solid var(--border); box-shadow: var(--shadow-soft);
    }
    button.secondary:hover, .button-link.secondary:hover { background: var(--bg-soft); color: var(--accent); }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; }
    .actions-primary { margin-top: 32px; padding-top: 32px; border-top: 1px solid var(--border); }
    .sidebar-column { position: sticky; top: 32px; display: grid; gap: 24px; max-height: calc(100vh - 64px); overflow-y: auto; padding-right: 8px; }
    .sidebar-nav { padding: 24px; display: grid; gap: 24px; }
    .sidebar-brand h2 { margin: 0 0 4px; font-size: 18px; }
    .sidebar-brand p { margin: 0; font-size: 13px; color: var(--muted); }
    .sidebar-badge { display: inline-block; margin-top: 12px; font-size: 11px; padding: 4px 8px; background: var(--good-bg); color: var(--good); border-radius: 12px; font-weight: 700; text-transform: uppercase; }
    .sidebar-group-label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; letter-spacing: 0.05em; }
    .sidebar-links { display: grid; gap: 4px; }
    .sidebar-links a {
      display: flex; justify-content: space-between; align-items: center; padding: 10px 12px;
      border-radius: 8px; color: var(--muted); font-size: 14px; font-weight: 500;
    }
    .sidebar-links a:hover { background: var(--bg-soft); color: var(--text); }
    .sidebar-links a.active { background: var(--accent); color: #fff; }
    .sidebar-links a.active .hint { color: rgba(255,255,255,0.7); }
    .sidebar-links .hint { font-size: 12px; font-weight: 400; }
    .sidebar-section { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; }
    .sidebar-section h3 { margin: 0 0 16px; font-size: 14px; text-transform: uppercase; }
    .sidebar-stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .sidebar-stat { background: var(--panel-solid); border: 1px solid var(--border); padding: 12px; border-radius: 8px; }
    .sidebar-stat .label { font-size: 11px; color: var(--muted); text-transform: uppercase; margin: 0; }
    .sidebar-stat .value { font-size: 20px; font-weight: 700; color: var(--text); margin: 4px 0 0; }
    .sidebar-note { font-size: 13px; color: var(--muted); margin: 16px 0 0; }
    .main-column { min-width: 0; display: grid; gap: 32px; }
    .workspace-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; padding: 24px 32px; }
    .workspace-toolbar .meta { color: var(--muted); font-size: 14px; }
    .workspace-toolbar-actions { display: flex; gap: 12px; }
    .output { padding: 32px; min-height: 500px; }
    .dashboard-shell { margin-bottom: 32px; }
    .workspace-hero-panel { padding: 24px; }
    .dashboard-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }
    .dashboard-kpi { padding: 20px; display: grid; gap: 8px; border-top: 4px solid var(--border); border-radius: 12px; background: var(--panel-solid); }
    .dashboard-kpi.good { border-top-color: var(--good); }
    .dashboard-kpi.warn { border-top-color: var(--warn); }
    .dashboard-kpi.risk { border-top-color: var(--danger); }
    .dashboard-kpi.info { border-top-color: var(--info); }
    .dashboard-kpi .label { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; }
    .dashboard-kpi .value { font-size: 32px; font-weight: 800; color: var(--text); line-height: 1; }
    .dashboard-kpi .subtext { font-size: 13px; color: var(--muted); }
    .dashboard-stack { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-top: 16px; }
    .dashboard-signal { padding: 16px; border-radius: 12px; background: var(--panel-solid); }
    .dashboard-signal-head { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 14px; font-weight: 600; }
    .dashboard-signal-track { height: 6px; background: var(--bg-soft); border-radius: 3px; overflow: hidden; }
    .dashboard-signal-fill { height: 100%; border-radius: 3px; }
    .dashboard-signal-fill.good { background: var(--good); }
    .dashboard-signal-fill.warn { background: var(--warn); }
    .dashboard-signal-fill.risk { background: var(--danger); }
    .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px; }
    .dashboard-panel { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
    .dashboard-panel.wide { grid-column: 1 / -1; }
    .dashboard-panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
    .dashboard-panel-head h3 { margin: 0; font-size: 18px; }
    .dashboard-panel-head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
    .dashboard-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
    .dashboard-list li { display: flex; gap: 12px; align-items: center; padding: 12px; background: var(--panel-solid); border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }
    .dashboard-list li::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
    .dashboard-list li.good::before { background: var(--good); }
    .dashboard-list li.warn::before { background: var(--warn); }
    .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
    .tab { background: transparent; color: var(--muted); border: none; font-size: 15px; font-weight: 600; padding: 8px 16px; cursor: pointer; position: relative; }
    .tab:hover { color: var(--text); }
    .tab.active { color: var(--accent); }
    .tab.active::after { content: ''; position: absolute; bottom: -17px; left: 0; width: 100%; height: 2px; background: var(--accent); }
    .detail-shell { display: grid; gap: 32px; }
    .detail-card { padding: 32px; }
    .toc-shell { display: grid; grid-template-columns: minmax(220px, 280px) 1fr; gap: 24px; align-items: start; }
    .toc-card { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 20px; position: sticky; top: 32px; }
    .toc-card h3 { margin: 0 0 12px; font-size: 16px; }
    .toc-links { display: grid; gap: 8px; }
    .toc-links a {
      display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px;
      border-radius: 8px; background: var(--panel-solid); border: 1px solid transparent; color: var(--text);
    }
    .toc-links a:hover { border-color: var(--border); }
    .toc-count { color: var(--muted); font-size: 12px; }
    .detail-header h2 { font-size: 28px; margin: 0 0 8px; }
    .detail-section-title { border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
    .detail-section-title h3 { font-size: 20px; margin: 0; }
    .detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
    .detail-metric { background: var(--panel-solid); padding: 20px; border-radius: 12px; border: 1px solid var(--border); }
    .detail-metric .label { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; }
    .detail-metric .value { font-size: 32px; font-weight: 800; color: var(--text); }
    .summary-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; }
    .summary-box { padding: 24px; }
    .summary-box h4 { margin: 0 0 16px; font-size: 16px; }
    .summary-list { padding-left: 20px; margin: 0; display: grid; gap: 8px; color: var(--muted); }
    .detail-list { display: grid; gap: 20px; }
    .field-label {
      margin-bottom: 8px; font-size: 12px; font-weight: 700; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    .pr-overview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 24px; }
    .pr-overview-card { padding: 20px; }
    .pr-overview-card h4 { margin: 0 0 12px; font-size: 16px; }
    .pr-overview-kpis { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
    .pr-overview-note { font-size: 13px; color: var(--muted); margin: 0; }
    .filter-bar { display: flex; gap: 16px; flex-wrap: wrap; padding: 16px; background: var(--bg-soft); border-radius: 12px; margin-bottom: 24px; align-items: center; }
    .filter-bar input, .filter-bar select { flex: 1; min-width: 150px; }
    .filter-toggle { background: var(--panel-solid); border: 1px solid var(--border); padding: 10px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
    .pr-list { display: grid; gap: 16px; }
    .pr-table-item { background: var(--panel-solid); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; transition: 0.2s; }
    .pr-table-item:hover { border-color: var(--border-strong); }
    .pr-table-item summary { padding: 20px; cursor: pointer; display: flex; flex-direction: column; gap: 12px; list-style: none; }
    .pr-table-item summary::-webkit-details-marker { display: none; }
    .pr-table-row { display: grid; grid-template-columns: minmax(0, 2.1fr) repeat(4, minmax(120px, 1fr)) minmax(110px, 0.8fr); gap: 16px; align-items: center; }
    .pr-table-cell { min-width: 0; }
    .pr-table-summary { display: flex; flex-direction: column; gap: 4px; }
    .pr-table-title { display: flex; gap: 12px; align-items: center; font-size: 15px; font-weight: 600; }
    .pr-table-title span { color: var(--muted); font-weight: 400; }
    .pr-table-meta { color: var(--muted); font-size: 13px; }
    .pr-table-item[open] { box-shadow: var(--shadow-soft); }
    .pr-table-details { padding: 24px; border-top: 1px solid var(--border); background: var(--bg-soft); }
    .pr-card-body { display: grid; gap: 24px; }
    .pr-body-note { padding: 16px; background: var(--info-bg); color: var(--info); border-radius: 8px; font-size: 14px; }
    .pr-evidence-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }
    .pr-evidence-card { background: var(--panel-solid); padding: 16px; border-radius: 8px; border: 1px solid var(--border); }
    .pr-evidence-card.wide { grid-column: 1 / -1; }
    .pr-evidence-head { display: flex; justify-content: space-between; margin-bottom: 12px; }
    .pr-evidence-head h4 { margin: 0; font-size: 14px; }
    .pr-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; color: var(--muted); }
    .pr-meta strong { color: var(--text); }
    .pill-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .pill { background: var(--bg-soft); color: var(--text); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
    .signal-score { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 700; color: #fff; display: inline-block; text-align: center; }
    .signal-score.good { background: var(--good); }
    .signal-score.warn { background: var(--warn); }
    .signal-score.risk { background: var(--danger); }
    .signal-score.neutral { background: var(--muted); }
    .error-banner { background: var(--danger); color: #fff; padding: 16px; border-radius: 12px; margin-top: 24px; }
    .raw-pre { background: var(--accent); color: #fff; padding: 24px; border-radius: 12px; overflow: auto; font-size: 13px; }
    .loading-state { padding: 40px; text-align: center; color: var(--muted); font-size: 16px; }
    .loading-label { margin: 0 0 8px; font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
    .empty-state { padding: 60px 40px; text-align: center; border: 2px dashed var(--border); border-radius: 16px; color: var(--muted); font-size: 16px; }
    .bar-card { padding: 20px; }
    .bar-top { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 14px; font-weight: 600; }
    .bar-value { color: var(--muted); }
    .bar-track { height: 8px; background: var(--bg-soft); border-radius: 4px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 4px; transition: 0.5s ease-out; }
    .bar-fill.good { background: var(--good); }
    .bar-fill.warn { background: var(--warn); }
    .bar-fill.risk { background: var(--danger); }
    .comparison-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
    .comparison-panel { padding: 20px; }
    .comparison-panel h4 { margin: 0 0 12px; font-size: 16px; }
    .comparison-panel p { margin: 0; color: var(--muted); font-size: 14px; }
    .pr-table-head { display: none; }
    .badge-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    .pr-table-cell .signal-score { padding: 6px 16px; font-size: 13px; border-radius: 16px; }
    @media (max-width: 980px) {
      .wrap { padding: 20px; }
      .admin-header { padding: 24px; }
      .app-shell, .toc-shell, .pr-table-row { grid-template-columns: 1fr; }
      .sidebar-column, .toc-card { position: relative; top: 0; max-height: none; overflow: visible; padding-right: 0; }
      .workspace-toolbar, .output { padding: 24px; }
      .command-palette { width: 100%; }
    }

  </style>
</head>

<body>
  <div class="wrap">
    <div class="card admin-header">
      <div class="admin-header-copy">
        <div class="eyebrow">Shadcn-style Admin Dashboard</div>
        <h1>GitHub Dev Metrics</h1>
        <p>Generate manager-friendly reports from GitHub activity and review them in a cleaner admin dashboard layout. The page is tuned for high-signal summaries, fast filtering, and PR-level drill-downs.</p>
      </div>
      <div class="admin-header-actions">
        <label class="command-palette" for="global-search">
          <span class="command-label">Global Search</span>
          <input id="global-search" type="search" placeholder="Search PRs, titles, or repos">
        </label>
        <div class="admin-pills">
          <span class="admin-pill">Sidebar navigation</span>
          <span class="admin-pill">Dashboard summary</span>
          <span class="admin-pill">PR detail drawer</span>
        </div>
      </div>
    </div>

    <div class="app-shell">
      <aside class="sidebar-column">
        <div class="card form-shell">
        <form id="report-form">
          <div class="form-intro">
            <p class="form-kicker">Command panel</p>
            <h2>Define the report before you read the dashboard.</h2>
            <p>Enter the developer, repositories, and time window here. Everything else on the page is driven by this scope.</p>
<!-- Example scope removed -->
          </div>

          <div class="form-section">
            <div class="form-section-title">
              <h3>Scope</h3>
              <span>Who and where</span>
            </div>
            <div class="row">
              <div>
                <label for="developer">Developer</label>
                <input id="developer" name="developer" placeholder="octocat" required>
              </div>
              <div>
                <label for="org">Organization</label>
                <input id="org" name="org" placeholder="example-org">
              </div>
              <div style="grid-column: 1 / -1;">
                <label for="repos">Repositories</label>
                <textarea id="repos" name="repos" placeholder="frontend-app,design-system or example-org/frontend-app" required></textarea>
                <div class="field-hint">Comma-separated repositories. If you only enter repo names, the organization field is used as the owner.</div>
              </div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">
              <h3>Window</h3>
              <span>Week or date range</span>
            </div>
            <div class="row">
              <div>
                <label for="week">Week</label>
                <input id="week" name="week" placeholder="05-2026">
                <div class="field-hint">Use <code>05-2026</code> or <code>2026-W05</code>.</div>
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
            <div class="field-hint">Use either week or from/to, not both.</div>
          </div>

          <div class="form-section">
            <div class="form-section-title">
              <h3>Cadence</h3>
              <span>How strict to be</span>
            </div>
            <div class="row">
              <div>
                <label for="cadence_target">Cadence target</label>
                <input id="cadence_target" name="cadence_target" type="number" min="0.1" max="1" step="0.05" value="0.6">
                <div class="field-hint">Fraction of active days you want to treat as strong cadence.</div>
              </div>
              <div>
                <label for="cadence_min_days">Min active days</label>
                <input id="cadence_min_days" name="cadence_min_days" type="number" min="1" step="1" value="5">
                <div class="field-hint">Minimum active days before cadence is considered meaningful.</div>
              </div>
            </div>
            <div class="actions" style="margin-top: 10px;">
              <button type="button" class="secondary" id="reset-cadence">Reset cadence settings</button>
            </div>
          </div>

          <div class="actions-primary">
            <div class="actions">
              <button type="submit">Generate report</button>
            </div>
          </div>
          <div class="error" id="form-error" hidden></div>
        </form>
      </div>

      <div class="card scope-guide">
        <div class="dashboard-tag">Start here</div>
        <h2>Use this scope to keep the report focused.</h2>
        <p>The strongest reports come from a narrow window and a clear repository list. If this setup is broad, the dashboard will be broad too.</p>
        <ul class="scope-guide-list">
          <li>Pick one developer first, then add only the repositories that matter for this review.</li>
          <li>Use a week or a date range. Mixing both makes the output harder to read.</li>
          <li>Keep the cadence settings stable unless you want to change how strict the report feels.</li>
        </ul>
        <div class="scope-guide-actions">
          <span class="badge info">Developer + repos</span>
          <span class="badge neutral">Week or date range</span>
          <span class="badge good">Report ready</span>
        </div>
      </div>
        <div class="card sidebar-nav">
          <div class="sidebar-brand">
            <div>
              <h2>Control Center</h2>
              <p>Scope the report, then jump to the evidence panels.</p>
            </div>
            <span class="sidebar-badge">Live</span>
          </div>
          <div class="sidebar-group">
            <p class="sidebar-group-label">Overview</p>
            <nav class="sidebar-links" aria-label="Overview sections">
              <a class="active" href="#detail-summary"><span>Summary</span><span class="hint">Top line</span></a>
              <a href="#detail-metrics"><span>Metrics</span><span class="hint">Signals</span></a>
            </nav>
          </div>
          <div class="sidebar-group">
            <p class="sidebar-group-label">Evidence</p>
            <nav class="sidebar-links" aria-label="Evidence sections">
              <a href="#detail-prs"><span>Pull requests</span><span class="hint">Grid</span></a>
              <a href="#detail-testing"><span>Testing</span><span class="hint">Coverage</span></a>
              <a href="#detail-cadence"><span>Cadence</span><span class="hint">Rhythm</span></a>
              <a href="#detail-review"><span>Reviews</span><span class="hint">Participation</span></a>
            </nav>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>Current run</h3>
          <div class="sidebar-stat-grid" id="stats" hidden></div>
          <p class="sidebar-note">Generate a report to populate the dashboard summary and PR signals. The same inputs drive the detail table below.</p>
        </div>
      </aside>

      <main class="main-column">
      <div class="card workspace-toolbar">
        <div>
          <h2 class="section-title" style="margin-bottom: 8px;">Workspace</h2>
          <div id="result-meta" class="meta">Ready to generate a report.</div>
        </div>
        <div class="workspace-toolbar-actions">
          <a href="#" id="download-markdown" class="button-link secondary" download="github-dev-metrics.md">Download Markdown</a>
          <a href="#" id="download-json" class="button-link secondary" download="github-dev-metrics.json">Download JSON</a>
        </div>
      </div>

      <div class="card output">
        <div class="dashboard-shell" id="workspace-hero" hidden></div>
        <div class="tabs">
          <button type="button" class="tab active" data-view="detail">Detail</button>
          <button type="button" class="tab" data-view="markdown">Markdown</button>
          <button type="button" class="tab" data-view="raw">Raw JSON</button>
        </div>
        <div id="result" class="report-view">
          <div class="empty-state">Choose a developer, scope the repositories, and generate a report to see the narrative view here.</div>
        </div>
      </div>
      </main>
    </div>
  </div>

  <script>
    const form = document.getElementById('report-form');
    const formError = document.getElementById('form-error');
    const result = document.getElementById('result');
    const resultMeta = document.getElementById('result-meta');
    const workspaceHero = document.getElementById('workspace-hero');
    const stats = document.getElementById('stats');
    const downloadMarkdown = document.getElementById('download-markdown');
    const downloadJson = document.getElementById('download-json');
    const tabs = document.querySelectorAll('.tab');
    const globalSearch = document.getElementById('global-search');
    const cadenceTargetInput = document.getElementById('cadence_target');
    const cadenceMinDaysInput = document.getElementById('cadence_min_days');
    const resetCadenceButton = document.getElementById('reset-cadence');
    const sidebarLinks = document.querySelectorAll('.sidebar-links a');
    let current = { detail: '', markdown: '', raw: '', report: null, defaultRiskOnly: false };
    let activeView = 'detail';
    const cadenceStorageKey = 'github-dev-metrics:cadence-settings';
    let detailSectionObserver = null;

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

    function renderSidebarStat(label, value, subtext = '') {
      return `
        <div class="sidebar-stat">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
          ${subtext ? `<div class="subtext" style="font-size: 11px; line-height: 1.35; margin-top: 4px;">${escapeHtml(subtext)}</div>` : ''}
        </div>
      `;
    }

    function renderDashboardKpi(label, value, subtext = '', tone = 'neutral') {
      return `
        <div class="dashboard-kpi ${tone}">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
          ${subtext ? `<div class="subtext">${escapeHtml(subtext)}</div>` : ''}
        </div>
      `;
    }

    function renderSignalRow(label, value, percentValue, tone = 'neutral') {
      return `
        <div class="dashboard-signal">
          <div class="dashboard-signal-head">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
          </div>
          <div class="dashboard-signal-track">
            <div class="dashboard-signal-fill ${tone}" style="width: ${Math.max(0, Math.min(100, percentValue))}%;"></div>
          </div>
        </div>
      `;
    }

    function buildDashboardHtml(report) {
      const metrics = report.metrics || {};
      const pullRequests = metrics.pull_requests || {};
      const testing = metrics.testing || {};
      const gitHygiene = metrics.git_hygiene || {};
      const commitActivity = metrics.commit_activity || {};
      const reviewParticipation = metrics.review_participation || {};
      const contributions = metrics.developer_contributions || {};
      const summary = report.summary || {};
      const cadence = commitActivity.cadence || {};
      const prsOpened = Number(pullRequests.opened || 0);
      const prsMerged = Number(pullRequests.merged || 0);
      const prsOpen = Number(pullRequests.open || 0);
      const requestedChanges = Number(pullRequests.requested_changes || 0);
      const prsWithTests = Number(testing.prs_with_tests || 0);
      const prsWithoutTests = Number(testing.prs_without_tests || 0);
      const noisyPrs = Number(gitHygiene.prs_with_noisy_commits?.length || 0);
      const reviewComments = Number(reviewParticipation.review_comments || 0);
      const reviewSubmissions = Number(reviewParticipation.submitted_reviews || 0);
      const contributionEvents = Number(contributions.total_contribution_events || 0);
      const cadencePct = Math.round(Number(cadence.coverage_ratio || 0) * 100);
      const testCoveragePercent = percent(prsWithTests, prsOpened);
      const reviewFriction = requestedChanges + noisyPrs + reviewComments;
      const positiveSignals = (summary.positive_signals || []).slice(0, 3);
      const opportunitySignals = (summary.opportunity_signals || []).slice(0, 3);

      return `
        ${renderSidebarStat('PRs opened', fmtNumber(prsOpened), `${fmtNumber(prsMerged)} merged`)}
        ${renderSidebarStat('Open PRs', fmtNumber(prsOpen), `${fmtNumber(prsWithTests)} with tests`)}
        ${renderSidebarStat('Contributions', fmtNumber(contributionEvents), `${fmtNumber(contributions.repo_count || 0)} repos`)}
        ${renderSidebarStat('Test coverage', `${fmtNumber(testCoveragePercent)}%`, `${fmtNumber(prsWithoutTests)} without tests`)}
        ${renderSidebarStat('Risk', fmtNumber(reviewFriction), `${fmtNumber(noisyPrs)} noisy PRs`)}
      `;
    }

    function buildWorkspaceHeroHtml(report) {
      const metrics = report.metrics || {};
      const pullRequests = metrics.pull_requests || {};
      const testing = metrics.testing || {};
      const gitHygiene = metrics.git_hygiene || {};
      const commitActivity = metrics.commit_activity || {};
      const reviewParticipation = metrics.review_participation || {};
      const contributions = metrics.developer_contributions || {};
      const summary = report.summary || {};
      const cadence = commitActivity.cadence || {};
      const prsOpened = Number(pullRequests.opened || 0);
      const prsMerged = Number(pullRequests.merged || 0);
      const prsOpen = Number(pullRequests.open || 0);
      const requestedChanges = Number(pullRequests.requested_changes || 0);
      const prsWithTests = Number(testing.prs_with_tests || 0);
      const prsWithoutTests = Number(testing.prs_without_tests || 0);
      const noisyPrs = Number(gitHygiene.prs_with_noisy_commits?.length || 0);
      const reviewComments = Number(reviewParticipation.review_comments || 0);
      const reviewSubmissions = Number(reviewParticipation.submitted_reviews || 0);
      const contributionEvents = Number(contributions.total_contribution_events || 0);
      const cadencePct = Math.round(Number(cadence.coverage_ratio || 0) * 100);
      const testCoveragePercent = percent(prsWithTests, prsOpened);
      const reviewFriction = requestedChanges + noisyPrs + reviewComments;
      const repoLabel = (report.repos || []).join(', ') || 'No repositories selected';

      return `
        <div class="dashboard-grid">
          <div class="dashboard-panel wide workspace-hero-panel">
            <div class="dashboard-panel-head">
              <div>
                <div class="dashboard-tag">At a glance</div>
                <h3>${escapeHtml(report.developer)} · ${escapeHtml(report.date_from)} to ${escapeHtml(report.date_to)}</h3>
                <p>${escapeHtml(repoLabel)}</p>
              </div>
              <div class="dashboard-tag">${report.week ? `Week ${escapeHtml(report.week)}` : 'Custom range'}</div>
            </div>
            <div class="dashboard-kpi-grid">
              ${renderDashboardKpi('PRs opened', fmtNumber(prsOpened), `${fmtNumber(prsMerged)} merged`, prsOpen ? 'warn' : 'good')}
              ${renderDashboardKpi('Open PRs', fmtNumber(prsOpen), `${fmtNumber(reviewSubmissions)} reviews submitted`, prsOpen ? 'warn' : 'good')}
              ${renderDashboardKpi('Contributions', fmtNumber(contributionEvents), `${fmtNumber(contributions.repo_count || 0)} repos`, contributionEvents ? 'good' : 'neutral')}
              ${renderDashboardKpi('Test coverage', `${fmtNumber(testCoveragePercent)}%`, `${fmtNumber(prsWithoutTests)} without tests`, testCoveragePercent >= 70 ? 'good' : testCoveragePercent >= 40 ? 'warn' : 'risk')}
              ${renderDashboardKpi('Review friction', fmtNumber(reviewFriction), `${fmtNumber(noisyPrs)} noisy PRs`, reviewFriction >= 4 ? 'risk' : reviewFriction >= 2 ? 'warn' : 'good')}
            </div>
            <div class="dashboard-stack">
              ${renderSignalRow('Testing coverage', `${fmtNumber(testCoveragePercent)}%`, testCoveragePercent, testCoveragePercent >= 70 ? 'good' : testCoveragePercent >= 40 ? 'warn' : 'risk')}
              ${renderSignalRow('Review friction', fmtNumber(reviewFriction), Math.min(100, reviewFriction * 20), reviewFriction >= 4 ? 'risk' : reviewFriction >= 2 ? 'warn' : 'good')}
              ${renderSignalRow('Cadence', `${fmtNumber(cadencePct)}%`, cadencePct, cadence.has_almost_daily_cadence ? 'good' : cadencePct >= 40 ? 'warn' : 'risk')}
            </div>
          </div>
        </div>
      `;
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
      const statusLabel = pr.merged_at ? 'Merged' : pr.state === 'open' ? 'Open' : 'Closed';
      const statusDetail = pr.merged_at ? `Merged ${escapeHtml(pr.merged_at)}` : escapeHtml(pr.state);
      const testSummary = testFiles.length ? `${fmtNumber(testFiles.length)} file(s)` : 'No test files';
      const noisySummary = noisyMessages.length ? `${fmtNumber(noisyMessages.length)} noisy commit(s)` : 'Clean commit trail';
      const riskLabel = riskScore >= 4 ? 'High risk' : riskScore >= 2 ? 'Medium risk' : 'Low risk';

      return `
        <details class="pr-table-item" data-risk-score="${riskScore}" data-status="${pr.merged_at ? 'merged' : pr.state}" data-has-tests="${testFiles.length ? '1' : '0'}" data-noisy="${noisyMessages.length ? '1' : '0'}" data-sort-risk="${riskScore}" data-sort-files="${pr.changed_files}" data-sort-review="${reviewIterations}" data-sort-created="${escapeHtml(pr.created_at)}" data-sort-title="${escapeHtml(pr.title.toLowerCase())}">
          <summary>
            <div class="pr-table-row">
              <div class="pr-table-cell">
                <div class="pr-table-summary">
                  <div class="pr-table-title">
                    <strong>${escapeHtml(pr.repo)}#${pr.number}</strong>
                    <span>${escapeHtml(pr.title)}</span>
                  </div>
                  <div class="pr-table-meta">Created ${escapeHtml(pr.created_at)} · ${fmtNumber(pr.changed_files)} files changed</div>
                </div>
              </div>
              <div class="pr-table-cell">
                <div class="badge-row" style="margin-top: 0;">
                  ${badges[0]}
                </div>
                <div class="pr-table-meta">${escapeHtml(statusDetail)}</div>
              </div>
              <div class="pr-table-cell">
                <div class="badge-row" style="margin-top: 0;">
                  ${badges.slice(1).join('')}
                </div>
                <div class="pr-table-meta">${escapeHtml(testSummary)} · ${escapeHtml(noisySummary)}</div>
              </div>
              <div class="pr-table-cell">
                <div class="pr-table-meta">${fmtNumber(reviewIterations)} iteration(s)</div>
                <div class="pr-table-meta">${escapeHtml(reviewStateEntries || 'No reviews found')}</div>
              </div>
              <div class="pr-table-cell">
                <span class="signal-score ${scoreClass(riskScore)}">${riskLabel}</span>
              </div>
              <div class="pr-table-cell" style="text-align: right;">
                <div class="pr-table-meta">${fmtNumber(pr.additions)} + / ${fmtNumber(pr.deletions)} -</div>
                <div class="pr-table-meta">${fmtNumber(pr.changed_files)} files</div>
              </div>
            </div>
          </summary>
          <div class="pr-table-details">
            <div class="pr-body-note">
              <strong>${escapeHtml(pr.repo)}#${pr.number}</strong>
              <span>${escapeHtml(pr.title)}</span>
            </div>
            <div class="pr-evidence-grid">
              <div class="pr-evidence-card">
                <div class="pr-evidence-head">
                  <h4>Timeline</h4>
                  <div class="meta">${escapeHtml(statusLabel)}</div>
                </div>
                <div class="pr-meta">
                  <div><strong>URL:</strong> <a href="${escapeHtml(pr.url)}" target="_blank" rel="noreferrer">${escapeHtml(pr.url)}</a></div>
                  <div><strong>Created:</strong> ${escapeHtml(pr.created_at)}</div>
                  <div><strong>Closed:</strong> ${escapeHtml(pr.closed_at || '-')}</div>
                  <div><strong>Merged:</strong> ${escapeHtml(pr.merged_at || '-')}</div>
                  <div><strong>Changes:</strong> +${fmtNumber(pr.additions)} / -${fmtNumber(pr.deletions)} / ${fmtNumber(pr.changed_files)} files</div>
                  <div><strong>Time to merge:</strong> ${fmtNumber(timeToMerge)} days</div>
                </div>
              </div>
              <div class="pr-evidence-card">
                <div class="pr-evidence-head">
                  <h4>Review</h4>
                  <div class="meta">${fmtNumber(reviewIterations)} iteration(s)</div>
                </div>
                <div class="field-label">Review state</div>
                <div>${escapeHtml(reviewStateEntries || 'No reviews found')}</div>
              </div>
              <div class="pr-evidence-card">
                <div class="pr-evidence-head">
                  <h4>Testing</h4>
                  <div class="meta">${fmtNumber(testFiles.length)} file(s)</div>
                </div>
                <div>${listToHtml(testFiles, 'No obvious test files were touched.')}</div>
              </div>
              <div class="pr-evidence-card">
                <div class="pr-evidence-head">
                  <h4>Commit hygiene</h4>
                  <div class="meta">${fmtNumber(noisyMessages.length)} noisy</div>
                </div>
                <div>${listToHtml(noisyMessages, 'No noisy commit messages detected.')}</div>
              </div>
              <div class="pr-evidence-card wide">
                <div class="pr-evidence-head">
                  <h4>Risk reasons</h4>
                  <div class="meta">${fmtNumber(riskReasons.length)} signal(s)</div>
                </div>
                <div>${listToHtml(riskReasons, 'No obvious risk signals were detected.')}</div>
              </div>
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
      const contributions = metrics.developer_contributions || {};
      const prs = report.prs || [];
      const summary = report.summary || {};
      const cadence = commitActivity.cadence || {};
      const prsOpened = Number(pullRequests.opened || 0);
      const prsMerged = Number(pullRequests.merged || 0);
      const prsWithTests = Number(testing.prs_with_tests || 0);
      const prsWithoutTests = Number(testing.prs_without_tests || 0);
      const noisyPrs = Number(gitHygiene.prs_with_noisy_commits?.length || 0);
      const requestedChanges = Number(pullRequests.requested_changes || 0);
      const reviewComments = Number(reviewParticipation.review_comments || 0);
      const reviewSubmissions = Number(reviewParticipation.submitted_reviews || 0);
      const contributionEvents = Number(contributions.total_contribution_events || 0);
      const contributionMix = contributions.contribution_mix || {};
      const contributedRepos = contributions.repos_contributed_to || [];
      const testCoveragePercent = percent(prsWithTests, prsOpened);
      const reviewFriction = requestedChanges + noisyPrs + reviewComments;
      const cadencePct = Math.round((Number(cadence.coverage_ratio || 0) * 100));
      const prStatusCounts = prs.reduce((acc, pr) => {
        if (pr.merged_at) acc.merged += 1;
        else if (pr.state === 'open') acc.open += 1;
        else acc.closed += 1;
        return acc;
      }, { open: 0, merged: 0, closed: 0 });
      const prSignalCounts = prs.reduce((acc, pr) => {
        const key = `${pr.repo}#${pr.number}`;
        const testFiles = testing.pr_test_files?.[key] || [];
        const noisyMessages = gitHygiene.prs_with_noisy_commits?.find(item => item.repo === pr.repo && item.number === pr.number)?.messages || [];
        const riskScore = [
          pr.state === 'open' ? 1 : 0,
          testFiles.length ? 0 : 1,
          noisyMessages.length ? 1 : 0,
          (pr.review_comments || []).length ? 1 : 0,
          (testing.merged_without_test_changes || []).some(item => item.repo === pr.repo && item.number === pr.number) ? 1 : 0,
        ].reduce((sum, value) => sum + value, 0);
        if (testFiles.length) acc.withTests += 1;
        else acc.noTests += 1;
        if (noisyMessages.length) acc.noisy += 1;
        if (riskScore >= 2) acc.highRisk += 1;
        return acc;
      }, { withTests: 0, noTests: 0, noisy: 0, highRisk: 0 });
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
                  <a href="#detail-contributions"><span>Developer contributions</span><span class="toc-count">${fmtNumber(contributionEvents)} events</span></a>
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

          <section class="detail-card" id="detail-contributions">
            <div class="detail-section-title">
              <h3>Developer Contributions</h3>
            </div>
            <div class="summary-columns">
              <div class="summary-box">
                <h4>Contribution totals</h4>
                ${listToHtml([
                  `Authored PRs: ${fmtNumber(contributions.authored_prs || 0)}`,
                  `Merged PRs: ${fmtNumber(contributions.merged_prs || 0)}`,
                  `Authored commits: ${fmtNumber(contributions.authored_commits || 0)}`,
                  `Reviews submitted: ${fmtNumber(contributions.reviews_submitted || 0)}`,
                  `Review comments: ${fmtNumber(contributions.review_comments || 0)}`,
                  `Total contribution events: ${fmtNumber(contributionEvents)}`,
                ])}
              </div>
              <div class="summary-box">
                <h4>Repo breadth and mix</h4>
                ${listToHtml([
                  `Repositories contributed to: ${fmtNumber(contributions.repo_count || 0)}`,
                  `PRs: ${fmtNumber(contributionMix.pull_requests || 0)}`,
                  `Commits: ${fmtNumber(contributionMix.commits || 0)}`,
                  `Reviews: ${fmtNumber(contributionMix.reviews || 0)}`,
                  `Review comments: ${fmtNumber(contributionMix.review_comments || 0)}`,
                ])}
              </div>
            </div>
            <div class="detail-list">
              <div>
                <div class="field-label">Repositories contributed to</div>
                <div>${contributedRepos.length ? contributedRepos.map(repo => pill(repo)).join('') : 'No repositories contributed to.'}</div>
              </div>
            </div>
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
            <div class="pr-overview-grid">
              <div class="pr-overview-card">
                <h4>Status mix</h4>
                <div class="pr-overview-kpis">
                  ${badge(`Open ${fmtNumber(prStatusCounts.open)}`, prStatusCounts.open ? 'warn' : 'neutral')}
                  ${badge(`Merged ${fmtNumber(prStatusCounts.merged)}`, prStatusCounts.merged ? 'good' : 'neutral')}
                  ${badge(`Closed ${fmtNumber(prStatusCounts.closed)}`, prStatusCounts.closed ? 'info' : 'neutral')}
                </div>
                <p class="pr-overview-note">Shows the shape of delivery at a glance so you can see whether the window was mostly active work, completed work, or cleanup.</p>
              </div>
              <div class="pr-overview-card">
                <h4>Evidence signals</h4>
                <div class="pr-overview-kpis">
                  ${badge(`With tests ${fmtNumber(prSignalCounts.withTests)}`, prSignalCounts.withTests ? 'good' : 'neutral')}
                  ${badge(`No tests ${fmtNumber(prSignalCounts.noTests)}`, prSignalCounts.noTests ? 'warn' : 'neutral')}
                  ${badge(`Noisy ${fmtNumber(prSignalCounts.noisy)}`, prSignalCounts.noisy ? 'warn' : 'neutral')}
                  ${badge(`High risk ${fmtNumber(prSignalCounts.highRisk)}`, prSignalCounts.highRisk ? 'warn' : 'neutral')}
                </div>
                <p class="pr-overview-note">This highlights which PRs deserve the first review pass, especially when testing or commit hygiene is weak.</p>
              </div>
              <div class="pr-overview-card">
                <h4>Fast actions</h4>
                <div class="pr-overview-kpis">
                  ${badge(`Risk ${fmtNumber(reviewFriction)}`, reviewFriction ? 'warn' : 'good')}
                  ${badge(`Tests ${fmtNumber(testCoveragePercent)}%`, testCoveragePercent >= 70 ? 'good' : testCoveragePercent >= 40 ? 'warn' : 'neutral')}
                  ${badge(`Cadence ${fmtNumber(cadencePct)}%`, cadence.has_almost_daily_cadence ? 'good' : cadencePct >= 40 ? 'warn' : 'neutral')}
                </div>
                <p class="pr-overview-note">Use the filter bar to isolate test coverage, noisy commits, or high-risk PRs after scanning the summary.</p>
              </div>
            </div>
            <div class="hint" style="margin: 0 0 12px;">
              Search by title, repo, or PR number, then narrow the evidence to the signal you want to review.
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
              <select id="pr-sort">
                <option value="risk-desc">Sort: risk</option>
                <option value="changes-desc">Sort: changes</option>
                <option value="review-desc">Sort: review</option>
                <option value="newest">Sort: newest</option>
                <option value="oldest">Sort: oldest</option>
                <option value="title-asc">Sort: title</option>
              </select>
              <label class="filter-toggle"><input type="checkbox" id="pr-filter-focus"> Focus risky PRs</label>
              <button type="button" class="secondary" id="pr-filter-high-risk">High risk only</button>
              <button type="button" class="secondary" id="pr-filter-reset">Reset filters</button>
            </div>
            ${prs.length ? `
              <div class="pr-table">
                <div class="pr-table-head">
                  <div>Pull Request</div>
                  <div>Status</div>
                  <div>Evidence</div>
                  <div>Review</div>
                  <div>Risk</div>
                  <div>Changes</div>
                </div>
                <div class="pr-list">${prs.map(pr => renderPrCard(pr, report)).join('')}</div>
              </div>
            ` : '<div class="empty-state">No pull requests matched the selection.</div>'}
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
        result.innerHTML = current.detail || '<div class="empty-state">Generate a report to open the narrative view.</div>';
        attachPrFilters();
        attachDetailSectionObserver();
        return;
      }
      if (detailSectionObserver) {
        detailSectionObserver.disconnect();
        detailSectionObserver = null;
      }
      if (activeView === 'markdown') {
        result.innerHTML = `<pre class="raw-pre">${escapeHtml(current.markdown || 'Markdown export will appear here after a report is generated.')}</pre>`;
        return;
      }
      result.innerHTML = `<pre class="raw-pre">${escapeHtml(current.raw || 'Raw JSON will appear here after a report is generated.')}</pre>`;
    }

    function setError(message, detail = '') {
      if (!message) {
        formError.hidden = true;
        formError.innerHTML = '';
        return;
      }
      formError.hidden = false;
      const safeMessage = escapeHtml(message);
      const safeDetail = detail ? `<span>${escapeHtml(detail)}</span>` : '';
      formError.innerHTML = `<div class="error-banner"><strong>${safeMessage}</strong>${safeDetail}</div>`;
    }

    function setActiveView(view) {
      activeView = view;
      tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.view === view));
      renderCurrentView();
    }

    function setActiveSidebarLink(targetId) {
      sidebarLinks.forEach(link => {
        const href = link.getAttribute('href') || '';
        link.classList.toggle('active', href === `#${targetId}`);
      });
    }

    function attachDetailSectionObserver() {
      if (detailSectionObserver) {
        detailSectionObserver.disconnect();
        detailSectionObserver = null;
      }
      if (!('IntersectionObserver' in window)) {
        return;
      }
      const sections = document.querySelectorAll('[id^="detail-"]');
      if (!sections.length) {
        return;
      }
      detailSectionObserver = new IntersectionObserver(entries => {
        const visible = entries
          .filter(entry => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
        if (visible?.target?.id) {
          setActiveSidebarLink(visible.target.id);
        }
      }, { rootMargin: '-20% 0px -60% 0px', threshold: [0.1, 0.25, 0.5] });
      sections.forEach(section => detailSectionObserver.observe(section));
    }

    function syncGlobalSearch(value) {
      if (!current.detail) {
        return;
      }
      if (activeView !== 'detail') {
        setActiveView('detail');
      }
      window.requestAnimationFrame(() => {
        const search = document.getElementById('pr-filter-search');
        if (!search) {
          return;
        }
        search.value = value;
        search.dispatchEvent(new Event('input'));
        if (!value) {
          return;
        }
        const prsSection = document.getElementById('detail-prs');
        if (prsSection) {
          prsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }

    function attachPrFilters() {
      const search = document.getElementById('pr-filter-search');
      const status = document.getElementById('pr-filter-status');
      const signal = document.getElementById('pr-filter-signal');
      const sort = document.getElementById('pr-sort');
      const focus = document.getElementById('pr-filter-focus');
      const highRisk = document.getElementById('pr-filter-high-risk');
      const reset = document.getElementById('pr-filter-reset');
      const cards = Array.from(result.querySelectorAll('.pr-table-item'));
      const list = cards[0]?.parentElement;
      if (!search || !status || !signal || !sort || !focus || !highRisk || !reset || !cards.length || !list) {
        return;
      }
      if (current.defaultRiskOnly) {
        focus.checked = true;
        status.value = 'all';
        signal.value = 'high-risk';
        current.defaultRiskOnly = false;
      }
      const sortCards = () => {
        const comparator = (left, right) => {
          const sortKey = sort.value;
          if (sortKey === 'title-asc') {
            return (left.dataset.sortTitle || '').localeCompare(right.dataset.sortTitle || '');
          }
          if (sortKey === 'newest' || sortKey === 'oldest') {
            const leftDate = Date.parse(left.dataset.sortCreated || '') || 0;
            const rightDate = Date.parse(right.dataset.sortCreated || '') || 0;
            return sortKey === 'newest' ? rightDate - leftDate : leftDate - rightDate;
          }
          if (sortKey === 'changes-desc') {
            return Number(right.dataset.sortFiles || 0) - Number(left.dataset.sortFiles || 0);
          }
          if (sortKey === 'review-desc') {
            return Number(right.dataset.sortReview || 0) - Number(left.dataset.sortReview || 0);
          }
          return Number(right.dataset.sortRisk || 0) - Number(left.dataset.sortRisk || 0);
        };
        [...cards].sort(comparator).forEach(card => list.appendChild(card));
      };
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
        sortCards();
      };
      search.oninput = apply;
      status.onchange = apply;
      signal.onchange = apply;
      sort.onchange = apply;
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
        sort.value = 'risk-desc';
        focus.checked = false;
        apply();
      };
      apply();
    }

    tabs.forEach(tab => {
      tab.addEventListener('click', () => setActiveView(tab.dataset.view));
    });

    sidebarLinks.forEach(link => {
      link.addEventListener('click', () => {
        const targetId = (link.getAttribute('href') || '').replace('#', '');
        if (targetId) {
          setActiveSidebarLink(targetId);
        }
      });
    });

    if (globalSearch) {
      globalSearch.addEventListener('input', () => syncGlobalSearch(globalSearch.value.trim()));
      globalSearch.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          syncGlobalSearch(globalSearch.value.trim());
        }
      });
    }

    loadCadenceSettings();
    cadenceTargetInput.addEventListener('input', saveCadenceSettings);
    cadenceMinDaysInput.addEventListener('input', saveCadenceSettings);
    resetCadenceButton.addEventListener('click', () => {
      resetCadenceSettings();
      setError('');
    });

    // Example fill logic removed

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn.textContent;
      const formElements = form.querySelectorAll('input, select, textarea, button');

      formElements.forEach(el => el.disabled = true);
      submitBtn.textContent = 'Generating...';

      setError('');
      result.innerHTML = '<div class="loading-state"><p class="loading-label">Generating</p><h3>Building the report narrative.</h3><p>Collecting GitHub activity, summarizing evidence, and shaping the output for review.</p></div>';
      resultMeta.textContent = 'Working on the report...';
      workspaceHero.hidden = true;
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
        workspaceHero.innerHTML = buildWorkspaceHeroHtml(data.report);
        workspaceHero.hidden = false;
        stats.innerHTML = buildDashboardHtml(data.report);
        stats.hidden = false;

        downloadMarkdown.href = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(data.report.markdown);
        downloadJson.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data.report.json, null, 2));
        setActiveView(payload.format === 'json' ? 'raw' : 'detail');
      } catch (error) {
        setError(
          'Report generation failed.',
          'Check the repository name, date range, cadence settings, and GitHub token access. Technical detail: ' + error.message,
        );
        resultMeta.textContent = 'No report generated yet.';
        workspaceHero.hidden = true;
        result.innerHTML = '<div class="empty-state">The report could not be built. Adjust the inputs and try again.</div>';
      } finally {
        formElements.forEach(el => el.disabled = false);
        submitBtn.textContent = originalBtnText;
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
    server = None
    bound_port = port
    for candidate_port in range(port, port + 11):
        try:
            server = ThreadingHTTPServer((host, candidate_port), WebHandler)
            bound_port = candidate_port
            break
        except OSError as exc:
            if getattr(exc, "errno", None) != 98:
                raise
    if server is None:
        raise OSError(f"Unable to bind to any port from {port} to {port + 10}.")
    print(f"GitHub Dev Metrics UI available at http://{host}:{bound_port}")
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
