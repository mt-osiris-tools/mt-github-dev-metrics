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
      --bg: #f3efe6;
      --bg-soft: #faf7f0;
      --panel: rgba(255, 255, 255, 0.88);
      --panel-solid: #ffffff;
      --text: #172033;
      --muted: #5f697d;
      --border: #d6cbb8;
      --border-strong: #c6b59c;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --accent-alt: #7c3aed;
      --shadow: 0 18px 55px rgba(15, 23, 42, 0.10);
      --shadow-soft: 0 10px 24px rgba(15, 23, 42, 0.06);
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background:
        radial-gradient(circle at 12% 8%, rgba(15, 118, 110, 0.14), transparent 22%),
        radial-gradient(circle at 88% 0%, rgba(124, 58, 237, 0.10), transparent 20%),
        linear-gradient(180deg, #faf7f0 0%, #f3efe6 100%);
      color: var(--text);
    }
    h1, .section-title, .detail-header h2, .detail-section-title h3, .toc-card h3, .comparison-panel h4, .bar-label {
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 36px 20px 56px;
    }
    .hero {
      display: grid;
      gap: 18px;
      grid-template-columns: 1.35fr 0.75fr;
      align-items: stretch;
      margin-bottom: 10px;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(18px);
      border: 1px solid rgba(214, 203, 184, 0.78);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }
    .hero-copy {
      padding: 24px;
      position: relative;
      overflow: hidden;
    }
    .hero-copy,
    .form-shell {
      isolation: isolate;
    }
    .hero-copy::before,
    .form-shell::before {
      content: '';
      position: absolute;
      inset: 0 0 auto 0;
      height: 5px;
      background: linear-gradient(90deg, rgba(15, 118, 110, 0.95), rgba(124, 58, 237, 0.78));
      pointer-events: none;
    }
    .hero-copy::after {
      content: '';
      position: absolute;
      inset: auto -80px -120px auto;
      width: 260px;
      height: 260px;
      background: radial-gradient(circle, rgba(15, 118, 110, 0.16), transparent 68%);
      pointer-events: none;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--accent);
      font-size: 11px;
      font-weight: 800;
    }
    h1 {
      margin: 8px 0 10px;
      font-size: clamp(1.95rem, 3.6vw, 3.1rem);
      line-height: 0.96;
      letter-spacing: -0.04em;
      max-width: 14ch;
    }
    .lede {
      margin: 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.6;
      max-width: 62ch;
    }
    .hero-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }
    .hero-badges .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(214, 203, 184, 0.72);
      color: #243042;
      font-size: 12px;
      font-weight: 700;
      box-shadow: var(--shadow-soft);
    }
    .hero-note {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(15, 118, 110, 0.16);
      background: rgba(15, 118, 110, 0.06);
      color: var(--accent-dark);
      font-size: 13px;
      font-weight: 700;
    }
    .hero-meta {
      display: grid;
      gap: 12px;
      padding: 20px;
      background:
        linear-gradient(180deg, rgba(15, 118, 110, 0.98) 0%, rgba(17, 94, 89, 0.98) 100%);
      color: white;
    }
    .hero-meta .meta-title {
      margin: 0 0 2px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: rgba(255, 255, 255, 0.75);
      font-weight: 800;
    }
    .hero-meta .meta-copy {
      margin: 0;
      font-size: 14px;
      line-height: 1.55;
      color: rgba(255, 255, 255, 0.88);
    }
    .hero-meta .chip {
      display: inline-flex; width: fit-content; align-items: center; gap: 8px;
      background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.22);
      padding: 7px 11px; border-radius: 999px; font-size: 12px; font-weight: 700;
    }
    .page-bridge {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 14px;
      align-items: center;
      margin: 0 0 12px;
    }
    .page-bridge::before,
    .page-bridge::after {
      content: '';
      height: 1px;
      background: linear-gradient(90deg, rgba(214, 203, 184, 0), rgba(214, 203, 184, 0.9), rgba(214, 203, 184, 0));
    }
    .page-bridge span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.8);
      border: 1px solid rgba(214, 203, 184, 0.72);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
      box-shadow: var(--shadow-soft);
    }
    .grid {
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 20px;
      align-items: start;
    }
    .form-shell {
      position: sticky;
      top: 20px;
      align-self: start;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.90), rgba(255, 255, 255, 0.84));
      overflow: hidden;
    }
    form {
      padding: 22px;
      margin-top: 5px;
    }
    .form-intro {
      display: grid;
      gap: 8px;
      margin-bottom: 16px;
      padding: 16px 16px 14px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(247, 244, 237, 0.92), rgba(255, 255, 255, 0.96));
      border: 1px solid rgba(214, 203, 184, 0.75);
      box-shadow: var(--shadow-soft);
    }
    .form-kicker {
      margin: 0;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      font-weight: 800;
      color: var(--accent);
    }
    .form-intro h2 {
      margin: 0;
      font-size: 20px;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }
    .form-intro p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
    }
    .section-title {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }
    .form-section {
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid rgba(214, 203, 184, 0.72);
    }
    .form-section:first-of-type {
      margin-top: 0;
      padding-top: 0;
      border-top: 0;
    }
    .form-section-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 10px;
    }
    .form-section-title h3 {
      margin: 0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: #44506b;
      font-weight: 800;
    }
    .form-section-title span {
      color: var(--muted);
      font-size: 12px;
    }
    label {
      display: block;
      margin: 14px 0 8px;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #44506b;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
      background: rgba(255, 255, 255, 0.95);
      color: var(--text);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
      transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: rgba(15, 118, 110, 0.55);
      box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
    }
    textarea { min-height: 90px; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .stack { display: grid; gap: 12px; }
    .field-hint {
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .actions {
      display: flex;
      gap: 10px;
      margin-top: 18px;
      flex-wrap: wrap;
    }
    .actions-primary {
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid rgba(214, 203, 184, 0.72);
    }
    .actions-primary .hint {
      margin-top: 12px;
    }
    button, .button-link {
      appearance: none;
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      font: inherit;
      background: linear-gradient(180deg, var(--accent) 0%, var(--accent-dark) 100%);
      color: white;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 18px rgba(15, 118, 110, 0.18);
      transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
    }
    button:hover, .button-link:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
    }
    button:active, .button-link:active { transform: translateY(0); box-shadow: 0 8px 16px rgba(15, 118, 110, 0.16); }
    button.secondary, .button-link.secondary {
      background: rgba(255, 255, 255, 0.9);
      color: #243042;
      border: 1px solid rgba(214, 203, 184, 0.95);
      box-shadow: none;
    }
    .hint {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      margin-top: 8px;
    }
    .error {
      color: var(--danger);
      font-weight: 600;
      margin-top: 12px;
      white-space: pre-wrap;
    }
    .error-banner {
      display: grid;
      gap: 6px;
      padding: 14px 16px;
      margin-top: 12px;
      border-radius: 18px;
      border: 1px solid rgba(180, 35, 24, 0.2);
      background: #fef2f2;
      color: #991b1b;
    }
    .error-banner strong { font-size: 14px; }
    .error-banner span { font-size: 13px; line-height: 1.45; color: #7f1d1d; }
    .output {
      padding: 20px;
      min-height: 260px;
      position: relative;
      overflow: hidden;
    }
    .output::before {
      content: '';
      position: absolute;
      inset: 0 auto auto 0;
      width: 100%;
      height: 6px;
      background: linear-gradient(90deg, rgba(15, 118, 110, 0.95), rgba(124, 58, 237, 0.82));
    }
    .result-intro {
      display: grid;
      gap: 8px;
      margin-bottom: 16px;
      padding: 16px 18px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(247, 244, 237, 0.92), rgba(255, 255, 255, 0.96));
      border: 1px solid rgba(214, 203, 184, 0.75);
      box-shadow: var(--shadow-soft);
    }
    .result-intro-top {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .result-kicker {
      margin: 0;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      font-weight: 800;
      color: var(--accent);
    }
    .result-intro h3 {
      margin: 4px 0 0;
      font-size: 20px;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }
    .result-intro p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
      max-width: 72ch;
    }
    .result-rail {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .result-rail .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.08);
      border: 1px solid rgba(15, 118, 110, 0.12);
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 800;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat {
      background: linear-gradient(180deg, rgba(249, 250, 251, 0.95), rgba(255, 255, 255, 0.96));
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
    }
    .stat .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .stat .value {
      font-size: 24px;
      font-weight: 800;
      margin-top: 4px;
      letter-spacing: -0.03em;
    }
    .tabs {
      display: inline-flex;
      gap: 8px;
      margin-bottom: 12px;
      flex-wrap: wrap;
      padding: 8px;
      border-radius: 18px;
      background: rgba(249, 250, 251, 0.72);
      border: 1px solid rgba(214, 203, 184, 0.78);
      box-shadow: var(--shadow-soft);
    }
    .tab {
      border: 1px solid transparent;
      background: transparent;
      color: #4b5563;
      border-radius: 999px;
      padding: 9px 14px;
      cursor: pointer;
      box-shadow: none;
      font-weight: 700;
      letter-spacing: 0.01em;
      transition: background 160ms ease, color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
    }
    .tab:hover {
      background: rgba(255, 255, 255, 0.78);
      color: #111827;
    }
    .tab.active {
      background: linear-gradient(180deg, var(--accent) 0%, var(--accent-dark) 100%);
      color: white;
      border-color: rgba(15, 118, 110, 0.2);
      box-shadow: 0 8px 18px rgba(15, 118, 110, 0.18);
    }
    .report-view {
      border-radius: 18px;
      min-height: 300px;
      padding-top: 4px;
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
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #e5ded3;
      border-radius: 18px;
      padding: 16px;
      box-shadow: var(--shadow-soft);
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
      padding: 6px 8px;
      margin: 0 -8px;
      border-radius: 10px;
    }
    .toc-links a:hover {
      text-decoration: none;
      background: rgba(15, 118, 110, 0.06);
    }
    .toc-count {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .detail-card {
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #e5ded3;
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow-soft);
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
      font-size: 28px;
      line-height: 1.08;
      letter-spacing: -0.03em;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .detail-metric {
      background: linear-gradient(180deg, rgba(249, 250, 251, 0.96), rgba(255, 255, 255, 0.98));
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
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
      letter-spacing: -0.04em;
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
      background: linear-gradient(180deg, rgba(249, 250, 251, 0.96), rgba(255, 255, 255, 0.98));
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
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
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.5) inset;
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
      grid-template-columns: 1.2fr 0.7fr 0.7fr auto auto auto;
      gap: 10px;
      margin-bottom: 14px;
      padding: 14px;
      border-radius: 18px;
      background: rgba(249, 250, 251, 0.78);
      border: 1px solid rgba(214, 203, 184, 0.72);
      box-shadow: var(--shadow-soft);
      align-items: center;
    }
    .filter-bar input, .filter-bar select {
      border-radius: 14px;
      padding: 11px 12px;
    }
    .filter-toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 11px 12px;
      background: rgba(255, 255, 255, 0.9);
      font-size: 13px;
      color: #374151;
      white-space: nowrap;
    }
    .filter-toggle input { width: auto; }
    .pr-card {
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(250, 250, 250, 0.98), rgba(255, 255, 255, 0.98));
      overflow: hidden;
      box-shadow: var(--shadow-soft);
    }
    .pr-card summary {
      list-style: none;
      cursor: pointer;
      display: grid;
      gap: 12px;
      padding: 16px 16px 14px;
    }
    .pr-card summary::-webkit-details-marker { display: none; }
    .pr-summary-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }
    .pr-summary-main {
      display: grid;
      gap: 7px;
      min-width: 0;
    }
    .pr-summary-kicker {
      display: inline-flex;
      align-items: center;
      width: fit-content;
      gap: 6px;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.08);
      border: 1px solid rgba(15, 118, 110, 0.12);
      color: var(--accent-dark);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .pr-summary-title {
      font-size: 18px;
      font-weight: 800;
      line-height: 1.25;
      letter-spacing: -0.02em;
      color: #111827;
      overflow-wrap: anywhere;
    }
    .pr-summary-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .pr-summary-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .pr-summary-stat {
      background: rgba(249, 250, 251, 0.94);
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      padding: 10px 12px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
    }
    .pr-summary-stat .label {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 2px;
    }
    .pr-summary-stat .value {
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: #111827;
    }
    .pr-card-body {
      border-top: 1px solid #e5e7eb;
      padding: 16px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(250, 250, 250, 0.96));
      display: grid;
      gap: 14px;
    }
    .pr-body-note {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(15, 118, 110, 0.06);
      border: 1px solid rgba(15, 118, 110, 0.10);
      color: #1f3b39;
      font-size: 13px;
      line-height: 1.5;
    }
    .pr-body-note strong {
      font-size: 13px;
      letter-spacing: 0.01em;
    }
    .pr-evidence-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .pr-evidence-card {
      background: rgba(255, 255, 255, 0.98);
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
    }
    .pr-evidence-card.wide {
      grid-column: 1 / -1;
    }
    .pr-evidence-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 10px;
    }
    .pr-evidence-head h4 {
      margin: 0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #1f2937;
    }
    .pr-evidence-head .meta {
      margin: 0;
      font-size: 12px;
      text-align: right;
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
      justify-content: flex-end;
      align-items: flex-start;
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
      background: linear-gradient(180deg, rgba(252, 252, 253, 0.96), rgba(255, 255, 255, 0.98));
    }
    .loading-state {
      display: grid;
      gap: 10px;
      place-items: start;
      color: #334155;
      border: 1px solid rgba(214, 203, 184, 0.72);
      background: linear-gradient(180deg, rgba(247, 244, 237, 0.92), rgba(255, 255, 255, 0.96));
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow-soft);
    }
    .loading-state .loading-label {
      margin: 0;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      font-weight: 800;
      color: var(--accent);
    }
    .loading-state h3 {
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.02em;
    }
    .loading-state p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      max-width: 60ch;
    }
    .raw-pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: linear-gradient(180deg, #0b1020 0%, #111827 100%);
      color: #e5eefc;
      border-radius: 16px;
      padding: 16px;
      overflow: auto;
      max-height: 70vh;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }
    .meta { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
    .summary-bars {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .bar-card {
      background: linear-gradient(180deg, rgba(249, 250, 251, 0.96), rgba(255, 255, 255, 0.98));
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
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
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow-soft);
    }
    .comparison-panel h4 {
      margin: 0 0 8px;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
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
      .detail-grid, .summary-columns, .pr-meta, .pr-summary-stats, .pr-evidence-grid, .row { grid-template-columns: 1fr; }
      .form-shell, .toc-card { position: static; top: auto; }
      .result-intro-top { align-items: stretch; }
      .pr-summary-top { flex-direction: column; }
      .pill-row { justify-content: flex-start; }
      .pr-evidence-head .meta { text-align: left; }
      .tabs { display: flex; }
      .filter-bar { justify-items: stretch; }
      .page-bridge { grid-template-columns: 1fr; }
      .page-bridge::before,
      .page-bridge::after { display: none; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="card hero-copy">
        <div class="eyebrow">GitHub Dev Metrics</div>
        <h1>Read GitHub work like a report, not a log.</h1>
        <p class="lede">Generate manager-friendly Markdown and JSON reports from GitHub activity across a date range or ISO week. The output is tuned for review conversations, not raw telemetry.</p>
        <div class="hero-badges">
          <span class="chip">Narrative-first summary</span>
          <span class="chip">Evidence-backed PR review</span>
          <span class="chip">Markdown and JSON exports</span>
        </div>
        <div class="hero-note">Fast local analysis with a cleaner report workflow and better evidence layout.</div>
      </div>
      <div class="card hero-meta">
        <p class="meta-title">At a glance</p>
        <p class="meta-copy">Use the same data engine as the CLI, preview the report here, and export a polished summary for a 1:1, a status note, or a performance discussion.</p>
        <div class="chip">Runs locally</div>
        <div class="chip">Uses GITHUB_TOKEN from your shell or .env</div>
        <div class="chip">Supports markdown and JSON output</div>
      </div>
    </div>

    <div class="page-bridge">
      <span>Review brief on the left, evidence surface on the right</span>
    </div>

    <div class="grid">
      <div class="card form-shell">
        <form id="report-form">
          <div class="form-intro">
            <p class="form-kicker">Inputs</p>
            <h2>Choose the review window and repository scope.</h2>
            <p>Keep the inputs narrow enough to tell a clean story. Use a week or a date range, then select the output you want to inspect.</p>
          </div>

          <div class="form-section">
            <div class="form-section-title">
              <h3>Scope</h3>
              <span>Who and where</span>
            </div>
            <div class="stack">
              <div>
                <label for="developer">Developer</label>
                <input id="developer" name="developer" placeholder="alan-guerrero" required>
              </div>
              <div>
                <label for="org">Organization</label>
                <input id="org" name="org" placeholder="MedTrainer365">
              </div>
              <div>
                <label for="repos">Repositories</label>
                <textarea id="repos" name="repos" placeholder="medtrainer-react,design-system or MedTrainer365/medtrainer-react" required></textarea>
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
                <label for="week">ISO Week</label>
                <input id="week" name="week" placeholder="2026-W18">
                <div class="field-hint">Use ISO week format like <code>2026-W18</code>.</div>
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
              <button type="button" class="secondary" id="fill-example">Fill example</button>
            </div>
          </div>
          <div class="error" id="form-error" hidden></div>
        </form>
      </div>

      <div class="card output">
        <h2 class="section-title">Result</h2>
        <div id="result-meta" class="meta">Ready to generate a report.</div>
        <div class="result-intro">
          <div class="result-intro-top">
            <div>
              <p class="result-kicker">Reading view</p>
              <h3>Evidence first, payload second.</h3>
            </div>
            <div class="result-rail">
              <span class="chip">Summary-led output</span>
              <span class="chip">Filterable PR evidence</span>
              <span class="chip">Exportable Markdown and JSON</span>
            </div>
          </div>
          <p>The detail tab is designed for a quick narrative read. Use the markdown and raw views only when you need the underlying output or want to copy it elsewhere.</p>
        </div>
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
        <div id="result" class="report-view">
          <div class="empty-state">Choose a developer, scope the repositories, and generate a report to see the narrative view here.</div>
        </div>
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
      const statusLabel = pr.merged_at ? 'Merged' : pr.state === 'open' ? 'Open' : 'Closed';
      const statusDetail = pr.merged_at ? `Merged ${escapeHtml(pr.merged_at)}` : escapeHtml(pr.state);
      const testSummary = testFiles.length ? `${fmtNumber(testFiles.length)} file(s)` : 'No test files';
      const noisySummary = noisyMessages.length ? `${fmtNumber(noisyMessages.length)} noisy commit(s)` : 'Clean commit trail';
      const riskLabel = riskScore >= 4 ? 'High risk' : riskScore >= 2 ? 'Medium risk' : 'Low risk';

      return `
        <details class="pr-card" data-risk-score="${riskScore}" data-status="${pr.merged_at ? 'merged' : pr.state}" data-has-tests="${testFiles.length ? '1' : '0'}" data-noisy="${noisyMessages.length ? '1' : '0'}">
          <summary>
            <div class="pr-summary-top">
              <div class="pr-summary-main">
                <div class="pr-summary-kicker">${escapeHtml(pr.repo)} · #${pr.number}</div>
                <div class="pr-summary-title">${escapeHtml(pr.title)}</div>
                <div class="pr-summary-meta">
                  <span>${escapeHtml(statusDetail)}</span>
                  <span>Created ${escapeHtml(pr.created_at)}</span>
                  <span>${fmtNumber(pr.changed_files)} files changed</span>
                </div>
              </div>
              <div class="pill-row">
                <span class="signal-score ${scoreClass(riskScore)}">${riskLabel}</span>
                ${badges.join('')}
              </div>
            </div>
            <div class="pr-summary-stats">
              <div class="pr-summary-stat">
                <div class="label">Status</div>
                <div class="value">${escapeHtml(statusLabel)}</div>
              </div>
              <div class="pr-summary-stat">
                <div class="label">Tests</div>
                <div class="value">${escapeHtml(testSummary)}</div>
              </div>
              <div class="pr-summary-stat">
                <div class="label">Commit trail</div>
                <div class="value">${escapeHtml(noisySummary)}</div>
              </div>
            </div>
          </summary>
          <div class="pr-card-body">
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
        result.innerHTML = current.detail || '<div class="empty-state">Generate a report to open the narrative view.</div>';
        attachPrFilters();
        return;
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
      result.innerHTML = '<div class="loading-state"><p class="loading-label">Generating</p><h3>Building the report narrative.</h3><p>Collecting GitHub activity, summarizing evidence, and shaping the output for review.</p></div>';
      resultMeta.textContent = 'Working on the report...';
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
        setError(
          'Report generation failed.',
          'Check the repository name, date range, cadence settings, and GitHub token access. Technical detail: ' + error.message,
        );
        resultMeta.textContent = 'No report generated yet.';
        result.innerHTML = '<div class="empty-state">The report could not be built. Adjust the inputs and try again.</div>';
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
