# ============================================================
# CONFIGURATION — Update these three paths before first use
# ============================================================

PAGES_TEMPLATE_PATH = "/path/to/your/template.pages"
PDF_OUTPUT_FOLDER   = "/Users/shrav/Desktop/tailored_resume"
MASTER_RESUME_PATH  = "master_resume.json"

# ============================================================
# IMPORTS
# ============================================================

import os
import json
import re
import subprocess
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from jobspy import scrape_jobs
import anthropic
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

load_dotenv()

app    = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TRACKER_PATH = Path.home() / "Desktop" / "applications.xlsx"

SEARCH_QUERIES = [
    "entry level software engineer",
    "entry level machine learning engineer",
    "entry level data engineer",
    "entry level data analyst",
]

# Cache master resume at startup
_resume_path = Path(MASTER_RESUME_PATH)
if not _resume_path.is_absolute():
    _resume_path = Path(__file__).parent / MASTER_RESUME_PATH
try:
    with open(_resume_path) as _f:
        MASTER_RESUME = json.load(_f)
except Exception as _e:
    MASTER_RESUME = None
    print(f"Warning: could not load {_resume_path}: {_e}")

# ============================================================
# HTML
# ============================================================

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Resume Tailor v1.0</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: "Arial", sans-serif;
      font-size: 11px;
      background: #008080;
      min-height: 100vh;
      padding: 20px 12px 40px;
    }

    /* ── Window chrome ─────────────────────────────────── */
    .window {
      background: #c0c0c0;
      border-top: 2px solid #ffffff;
      border-left: 2px solid #ffffff;
      border-right: 2px solid #808080;
      border-bottom: 2px solid #808080;
      max-width: 980px;
      margin: 0 auto;
    }

    .titlebar {
      background: linear-gradient(to right, #000080, #1084d0);
      padding: 3px 4px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
    }
    .titlebar-left { display: flex; align-items: center; gap: 4px; }
    .titlebar-icon {
      width: 14px; height: 14px;
      background: #c0c0c0;
      border: 1px solid #808080;
      display: flex; align-items: center; justify-content: center;
      font-size: 9px; color: #000080; font-weight: 900;
    }
    .titlebar-text { color: #fff; font-size: 11px; font-weight: 700; }
    .titlebar-btns { display: flex; gap: 2px; }
    .tb-btn {
      width: 16px; height: 14px;
      background: #c0c0c0;
      border-top: 1px solid #fff; border-left: 1px solid #fff;
      border-right: 1px solid #404040; border-bottom: 1px solid #404040;
      font-size: 9px; font-weight: 700; color: #000;
      display: flex; align-items: center; justify-content: center;
      cursor: default;
    }

    /* ── Menu bar ──────────────────────────────────────── */
    .menubar {
      background: #c0c0c0;
      padding: 2px 4px;
      display: flex;
      border-bottom: 1px solid #808080;
    }
    .menu-item { font-size: 11px; color: #000; padding: 2px 6px; cursor: default; }
    .menu-item:hover { background: #000080; color: #fff; }

    /* ── Two-pane layout ───────────────────────────────── */
    .window-body {
      display: flex;
      flex-direction: row;
      height: 600px;
      overflow: hidden;
    }

    /* ── Left pane ─────────────────────────────────────── */
    .left-pane {
      width: 320px;
      min-width: 320px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: #c0c0c0;
    }

    .pane-divider {
      width: 4px;
      background: #c0c0c0;
      border-left: 1px solid #808080;
      border-right: 1px solid #fff;
      flex-shrink: 0;
    }

    /* ── Right pane ────────────────────────────────────── */
    .right-pane {
      flex: 1;
      overflow-y: auto;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 7px;
      min-width: 0;
    }

    /* ── Left toolbar ──────────────────────────────────── */
    .left-toolbar {
      padding: 5px 7px;
      border-bottom: 1px solid #808080;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .pane-title { font-size: 11px; font-weight: 700; color: #000; }

    /* ── List / detail view containers ────────────────── */
    #list-view, #detail-view {
      display: flex;
      flex-direction: column;
      flex: 1;
      overflow: hidden;
    }

    /* ── Job list ──────────────────────────────────────── */
    .job-list {
      flex: 1;
      overflow-y: auto;
      padding: 4px;
    }
    .no-jobs-msg {
      padding: 14px 8px;
      font-size: 11px;
      color: #808080;
      text-align: center;
    }

    /* ── Job card ──────────────────────────────────────── */
    .job-card {
      background: #c0c0c0;
      border-top: 1px solid #fff;
      border-left: 1px solid #fff;
      border-right: 1px solid #808080;
      border-bottom: 1px solid #808080;
      padding: 5px 7px;
      margin-bottom: 3px;
      cursor: pointer;
    }
    .job-card:hover,
    .job-card.selected {
      background: #000080;
    }
    .job-card:hover .job-card-title,
    .job-card.selected .job-card-title { color: #fff; }
    .job-card:hover .job-card-company,
    .job-card.selected .job-card-company,
    .job-card:hover .job-card-location,
    .job-card.selected .job-card-location { color: #c0c0c0; }
    .job-card:hover .job-tag.time,
    .job-card.selected .job-tag.time { color: #c0c0c0; background: #000080; border-color: #1084d0; }

    .job-card-title {
      font-size: 11px; font-weight: 700; color: #000;
      margin-bottom: 1px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .job-card-company {
      font-size: 10px; color: #000;
      margin-bottom: 1px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .job-card-location {
      font-size: 10px; color: #404040;
      margin-bottom: 3px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .job-card-footer { display: flex; gap: 4px; flex-wrap: wrap; }

    .job-tag {
      font-size: 9px; padding: 1px 5px;
      border: 1px solid #808080;
    }
    .job-tag.exp  { background: #000080; color: #fff; border-color: #000080; }
    .job-tag.time { background: #c0c0c0; color: #404040; }

    /* ── Detail view ───────────────────────────────────── */
    .detail-toolbar {
      padding: 5px 6px;
      border-bottom: 1px solid #808080;
      display: flex;
      gap: 4px;
      flex-shrink: 0;
    }
    .detail-meta {
      padding: 6px 8px;
      border-bottom: 1px solid #808080;
      flex-shrink: 0;
    }
    .detail-job-title { font-size: 11px; font-weight: 700; color: #000; margin-bottom: 2px; }
    .detail-meta-line { font-size: 10px; color: #404040; margin-bottom: 3px; }
    .detail-jd {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
      margin: 5px 6px 6px;
      font-size: 10px;
      line-height: 1.5;
      white-space: pre-wrap;
      color: #000;
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
    }

    /* ── Form controls ─────────────────────────────────── */
    .win-label { font-size: 11px; color: #000; margin-bottom: 2px; }
    .win-input {
      width: 100%; height: 22px;
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 2px 4px; font-size: 11px; font-family: Arial, sans-serif;
      color: #000; outline: none;
    }
    .win-textarea {
      width: 100%; height: 90px;
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 4px; font-size: 11px; font-family: Arial, sans-serif;
      color: #000; resize: vertical; outline: none;
    }
    .win-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

    /* ── Buttons ───────────────────────────────────────── */
    .win-btn {
      background: #c0c0c0;
      border-top: 2px solid #fff; border-left: 2px solid #fff;
      border-right: 2px solid #404040; border-bottom: 2px solid #404040;
      padding: 3px 10px; font-size: 11px; font-family: Arial, sans-serif;
      color: #000; cursor: pointer; min-width: 75px;
    }
    .win-btn:active {
      border-top: 2px solid #404040; border-left: 2px solid #404040;
      border-right: 2px solid #fff;  border-bottom: 2px solid #fff;
    }
    .win-btn:disabled { color: #808080; cursor: default; }
    .win-btn.primary {
      font-weight: 700;
      border: 2px solid #000;
      outline: 1px solid #000;
      outline-offset: -3px;
    }
    .btn-row { display: flex; gap: 6px; justify-content: center; margin-top: 2px; }

    /* ── Groupbox ──────────────────────────────────────── */
    .groupbox {
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 10px 8px 8px;
      position: relative; margin-top: 2px;
    }
    .groupbox-label {
      position: absolute; top: -7px; left: 8px;
      background: #c0c0c0;
      padding: 0 3px; font-size: 11px; font-weight: 700; color: #000;
    }

    /* ── Result boxes ──────────────────────────────────── */
    .result-box {
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 6px; font-size: 11px; color: #000; line-height: 1.6;
    }
    .score-row-win { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 6px 0; }
    .score-box-win {
      background: #c0c0c0;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 6px; text-align: center;
    }
    .score-num-win { font-size: 22px; font-weight: 700; color: #000080; }
    .score-lbl-win { font-size: 10px; color: #000; margin-top: 2px; }

    .flag-win { display: flex; align-items: flex-start; gap: 5px; font-size: 11px; color: #000; padding: 2px 0; }
    .flag-icon {
      width: 13px; height: 13px; flex-shrink: 0;
      background: #ffff00; border: 1px solid #808080;
      display: flex; align-items: center; justify-content: center;
      font-size: 9px; font-weight: 900; color: #000; margin-top: 1px;
    }

    .rec-badge {
      display: inline-block; background: #000080; color: #fff;
      font-size: 10px; padding: 1px 7px; font-weight: 700;
    }
    .rec-badge.green  { background: #008000; }
    .rec-badge.yellow { background: #808000; }
    .rec-badge.red    { background: #800000; }

    .kw-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 3px; }
    .kw-tag  { background: #000080; color: #fff; font-size: 10px; padding: 1px 6px; }
    .kw-tag.missing { background: #800000; }
    .kw-tag.neutral { background: #808080; }

    .feedback-item { padding: 2px 0; font-size: 11px; }
    .error-box {
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 6px; font-size: 11px; color: #800000;
    }
    .pdf-path {
      font-family: "Courier New", monospace;
      font-size: 10px; word-break: break-all; color: #000080;
    }

    /* ── Progress bar ──────────────────────────────────── */
    .win-progress {
      width: 100%; height: 18px;
      background: #fff;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      overflow: hidden; margin: 6px 0;
    }
    .win-progress-bar {
      height: 100%;
      background: repeating-linear-gradient(
        to right, #000080 0, #000080 10px, #1084d0 10px, #1084d0 20px
      );
      width: 0%; transition: width 0.3s;
    }

    /* ── Status bar ────────────────────────────────────── */
    .statusbar {
      background: #c0c0c0;
      border-top: 1px solid #808080;
      padding: 2px 6px;
      display: flex; gap: 6px;
    }
    .status-panel {
      flex: 1;
      background: #c0c0c0;
      border-top: 1px solid #808080; border-left: 1px solid #808080;
      border-right: 1px solid #fff;  border-bottom: 1px solid #fff;
      padding: 1px 4px; font-size: 10px; color: #000;
    }
  </style>
</head>
<body>

<div class="window">

  <!-- Title bar -->
  <div class="titlebar">
    <div class="titlebar-left">
      <div class="titlebar-icon">R</div>
      <span class="titlebar-text">Resume Tailor v1.0</span>
    </div>
    <div class="titlebar-btns">
      <div class="tb-btn">_</div>
      <div class="tb-btn">&#9633;</div>
      <div class="tb-btn">&#10005;</div>
    </div>
  </div>

  <!-- Menu bar -->
  <div class="menubar">
    <span class="menu-item">File</span>
    <span class="menu-item">Edit</span>
    <span class="menu-item">View</span>
    <span class="menu-item">Help</span>
  </div>

  <!-- Window body: two panes -->
  <div class="window-body">

    <!-- ── LEFT PANE ──────────────────────────────────── -->
    <div class="left-pane">

      <!-- List view -->
      <div id="list-view">
        <div class="left-toolbar">
          <span class="pane-title">Job Listings</span>
          <button class="win-btn" id="fetch-btn" onclick="fetchJobs()">Fetch Jobs</button>
        </div>
        <div id="job-list" class="job-list">
          <div class="no-jobs-msg">Click "Fetch Jobs" to load<br>entry-level listings.</div>
        </div>
      </div>

      <!-- Detail view -->
      <div id="detail-view" style="display:none">
        <div class="detail-toolbar">
          <button class="win-btn" onclick="showView('list')">&#8592; Back</button>
          <button class="win-btn primary" onclick="useThisJob()">Use this job &#8594;</button>
        </div>
        <div class="detail-meta">
          <div id="detail-title" class="detail-job-title"></div>
          <div id="detail-company" class="detail-meta-line"></div>
          <span id="detail-exp" class="job-tag exp"></span>
        </div>
        <div id="detail-jd" class="detail-jd"></div>
      </div>

    </div>

    <!-- Pane divider -->
    <div class="pane-divider"></div>

    <!-- ── RIGHT PANE ─────────────────────────────────── -->
    <div class="right-pane">

      <div class="win-row">
        <div>
          <div class="win-label">Company: *</div>
          <input type="text" id="company" class="win-input" placeholder="e.g. Stripe" />
        </div>
        <div>
          <div class="win-label">Role: *</div>
          <input type="text" id="role" class="win-input" placeholder="e.g. Software Engineer" />
        </div>
      </div>

      <div>
        <div class="win-label">Job URL: (optional)</div>
        <input type="text" id="url" class="win-input" placeholder="https://..." />
      </div>

      <div>
        <div class="win-label">Job Description: *</div>
        <textarea id="jd" class="win-textarea"
          placeholder="Paste a job description, or click a listing on the left then 'Use this job →'"></textarea>
      </div>

      <div class="btn-row">
        <button id="screen-btn" class="win-btn primary" onclick="screenJob()">Screen this job</button>
        <button class="win-btn" onclick="startOver()">Clear</button>
      </div>

      <!-- Screen results -->
      <div id="screen-card" class="groupbox" style="display:none">
        <span class="groupbox-label">Pre-screen results</span>
        <div id="screen-content"></div>
      </div>

      <!-- Tailor button + progress -->
      <div id="tailor-card" style="display:none">
        <div class="win-progress"><div id="progress-bar" class="win-progress-bar"></div></div>
        <div class="btn-row">
          <button id="tailor-btn" class="win-btn primary" onclick="tailorResume()">Tailor &amp; Export Resume</button>
          <button class="win-btn" onclick="startOver()">Cancel</button>
        </div>
      </div>

      <!-- Tailor results -->
      <div id="tailor-card-results" class="groupbox" style="display:none">
        <span class="groupbox-label">Tailoring results</span>
        <div id="tailor-content"></div>
      </div>

      <!-- Start over -->
      <div id="startover-wrap" style="display:none">
        <div class="btn-row">
          <button class="win-btn" onclick="startOver()">&#8635; New application</button>
        </div>
      </div>

    </div><!-- /right-pane -->

  </div><!-- /window-body -->

  <!-- Status bar -->
  <div class="statusbar">
    <div class="status-panel" id="status-text">Ready</div>
    <div class="status-panel" style="flex:0;min-width:90px;text-align:right">localhost:5001</div>
  </div>

</div><!-- /window -->

<script>
  let jobs = [];
  let selectedJobIdx = -1;
  let fitScore = 0;

  // ── VIEW TOGGLE ─────────────────────────────────────────────
  function showView(view) {
    document.getElementById('list-view').style.display   = view === 'list'   ? 'flex' : 'none';
    document.getElementById('detail-view').style.display = view === 'detail' ? 'flex' : 'none';
  }

  // ── FETCH JOBS ──────────────────────────────────────────────
  async function fetchJobs() {
    const btn = document.getElementById('fetch-btn');
    btn.textContent = 'Fetching...';
    btn.disabled = true;
    setStatus('Fetching job listings...');

    try {
      const res  = await fetch('/jobs');
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Request failed');
      jobs = data.jobs || [];
      renderJobList();
      setStatus(jobs.length + ' jobs found');
    } catch (err) {
      document.getElementById('job-list').innerHTML =
        '<div class="no-jobs-msg" style="color:#800000">&#9888; ' + escHtml(err.message) + '</div>';
      setStatus('Error fetching jobs');
    } finally {
      btn.textContent = 'Refresh';
      btn.disabled = false;
    }
  }

  function renderJobList() {
    const container = document.getElementById('job-list');
    if (!jobs.length) {
      container.innerHTML = '<div class="no-jobs-msg">No jobs found for today.</div>';
      return;
    }
    container.innerHTML = jobs.map((j, i) => `
      <div class="job-card${i === selectedJobIdx ? ' selected' : ''}" onclick="showDetail(${i})">
        <div class="job-card-title">${escHtml(j.title)}</div>
        <div class="job-card-company">${escHtml(j.company)}</div>
        <div class="job-card-location">${escHtml(j.location)}</div>
        <div class="job-card-footer">
          <span class="job-tag exp">${escHtml(j.experience)}</span>
          <span class="job-tag time">${timeAgo(j.posted)}</span>
        </div>
      </div>
    `).join('');
  }

  // ── JOB DETAIL ──────────────────────────────────────────────
  function showDetail(idx) {
    selectedJobIdx = idx;
    const j = jobs[idx];
    document.getElementById('detail-title').textContent   = j.title;
    document.getElementById('detail-company').textContent =
      j.company + (j.location ? ' · ' + j.location : '');
    document.getElementById('detail-exp').textContent = j.experience;
    document.getElementById('detail-jd').textContent  = j.description;
    renderJobList(); // refresh selected highlight
    showView('detail');
  }

  function useThisJob() {
    if (selectedJobIdx < 0) return;
    const j = jobs[selectedJobIdx];
    document.getElementById('company').value = j.company;
    document.getElementById('role').value    = j.title;
    document.getElementById('url').value     = j.url;
    document.getElementById('jd').value      = j.description;
    // Reset result sections (keep inputs)
    fitScore = 0;
    animateProgress(0);
    hide('screen-card');
    hide('tailor-card');
    hide('tailor-card-results');
    hide('startover-wrap');
    document.getElementById('screen-content').innerHTML = '';
    document.getElementById('tailor-content').innerHTML = '';
    document.getElementById('screen-btn').textContent = 'Screen this job';
    document.getElementById('screen-btn').disabled = false;
    setStatus('Job loaded — ready to screen');
    showView('list');
  }

  // ── SCREEN ──────────────────────────────────────────────────
  async function screenJob() {
    const company = document.getElementById('company').value.trim();
    const role    = document.getElementById('role').value.trim();
    const jd      = document.getElementById('jd').value.trim();

    if (!company || !role || !jd) {
      alert('Company, Role, and Job Description are required.');
      return;
    }

    const btn = document.getElementById('screen-btn');
    btn.textContent = 'Screening...';
    btn.disabled = true;
    setStatus('Calling Claude API...');
    hide('screen-card');
    hide('tailor-card');
    hide('tailor-card-results');
    hide('startover-wrap');

    try {
      const res  = await fetch('/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd })
      });
      const data = await res.json();
      show('screen-card');
      if (!res.ok) {
        document.getElementById('screen-content').innerHTML = errorBox(data.error || 'Screening failed.');
        setStatus('Error');
        return;
      }
      fitScore = data.fit_score;
      renderScreenResults(data);
      show('tailor-card');
      animateProgress(40);
      setStatus('Screening complete — ready to tailor');
    } catch (err) {
      show('screen-card');
      document.getElementById('screen-content').innerHTML = errorBox('Network error: ' + err.message);
      setStatus('Error');
    } finally {
      btn.textContent = 'Screen this job';
      btn.disabled = false;
    }
  }

  function renderScreenResults(d) {
    const recClass = { 'strong apply': 'green', 'apply': '', 'borderline': 'yellow', 'skip': 'red' }[d.recommendation] || '';
    let flagsHtml = '';
    (d.flags || []).forEach(f => {
      flagsHtml += `<div class="flag-win"><div class="flag-icon">!</div><span><strong>${f.type}:</strong> ${escHtml(f.detail)}</span></div>`;
    });
    document.getElementById('screen-content').innerHTML = `
      <div class="result-box" style="margin-bottom:6px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <span style="font-weight:700">Fit score: ${d.fit_score} / 100</span>
          <span class="rec-badge ${recClass}">${d.recommendation || 'unknown'}</span>
        </div>
        ${flagsHtml || '<span style="color:#008000">No flags detected</span>'}
      </div>`;
  }

  // ── TAILOR ──────────────────────────────────────────────────
  async function tailorResume() {
    const company = document.getElementById('company').value.trim();
    const role    = document.getElementById('role').value.trim();
    const url     = document.getElementById('url').value.trim();
    const jd      = document.getElementById('jd').value.trim();

    const btn = document.getElementById('tailor-btn');
    btn.textContent = 'Working...';
    btn.disabled = true;
    animateProgress(60);
    setStatus('Tailoring resume...');
    hide('tailor-card-results');
    hide('startover-wrap');

    try {
      const res  = await fetch('/tailor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company, role, url, jd, fit_score: fitScore })
      });
      const data = await res.json();
      show('tailor-card-results');
      if (!res.ok) {
        document.getElementById('tailor-content').innerHTML = errorBox(data.error || 'Tailoring failed.');
        setStatus('Error');
      } else {
        renderTailorResults(data);
        animateProgress(100);
        setStatus('Done — resume exported');
      }
    } catch (err) {
      show('tailor-card-results');
      document.getElementById('tailor-content').innerHTML = errorBox('Network error: ' + err.message);
      setStatus('Error');
    } finally {
      btn.textContent = 'Tailor & Export Resume';
      btn.disabled = false;
      show('startover-wrap');
    }
  }

  function renderTailorResults(d) {
    const matchedHtml  = (d.ats_matched_keywords || []).map(k => `<span class="kw-tag">${escHtml(k)}</span>`).join('');
    const missingHtml  = (d.ats_missing_keywords || []).map(k => `<span class="kw-tag missing">${escHtml(k)}</span>`).join('');
    const feedbackHtml = (d.recruiter_feedback   || []).map(f => `<div class="feedback-item">• ${escHtml(f)}</div>`).join('');
    const projectsHtml = (d.selected_projects    || []).map(p => `<span class="kw-tag">${escHtml(p)}</span>`).join('');
    const langHtml     = (d.selected_languages   || []).map(s => `<span class="kw-tag neutral">${escHtml(s)}</span>`).join('');
    const fwHtml       = (d.selected_frameworks  || []).map(s => `<span class="kw-tag neutral">${escHtml(s)}</span>`).join('');

    let pdfHtml = '';
    if (d.pdf_path)      pdfHtml = `<div style="margin-top:6px"><strong>PDF saved to:</strong><br><span class="pdf-path">${escHtml(d.pdf_path)}</span></div>`;
    else if (d.pdf_error) pdfHtml = `<div style="margin-top:6px">${errorBox('PDF export: ' + d.pdf_error)}</div>`;

    let trackerHtml = '';
    if (d.tracker_updated)      trackerHtml = `<div style="margin-top:4px;color:#008000;font-weight:700">✓ Logged to applications.xlsx</div>`;
    else if (d.tracker_error)   trackerHtml = `<div style="margin-top:4px">${errorBox('Tracker: ' + d.tracker_error)}</div>`;

    document.getElementById('tailor-content').innerHTML = `
      <div class="score-row-win">
        <div class="score-box-win"><div class="score-num-win">${d.ats_score}</div><div class="score-lbl-win">ATS Score</div></div>
        <div class="score-box-win"><div class="score-num-win">${d.recruiter_score}</div><div class="score-lbl-win">Recruiter Score</div></div>
      </div>
      <div class="result-box">
        <div style="margin-bottom:4px"><strong>Projects:</strong><div class="kw-list">${projectsHtml}</div></div>
        <div style="margin-bottom:4px"><strong>Languages:</strong><div class="kw-list">${langHtml}</div></div>
        <div style="margin-bottom:4px"><strong>Frameworks:</strong><div class="kw-list">${fwHtml}</div></div>
        <div style="margin-bottom:4px"><strong>Matched:</strong><div class="kw-list">${matchedHtml || '—'}</div></div>
        <div style="margin-bottom:4px"><strong>Missing:</strong><div class="kw-list">${missingHtml || '—'}</div></div>
        <div><strong>Feedback:</strong>${feedbackHtml}</div>
        ${pdfHtml}
        ${trackerHtml}
      </div>`;
  }

  // ── START OVER ───────────────────────────────────────────────
  function startOver() {
    document.getElementById('company').value = '';
    document.getElementById('role').value    = '';
    document.getElementById('url').value     = '';
    document.getElementById('jd').value      = '';
    fitScore = 0;
    animateProgress(0);
    setStatus('Ready');
    hide('screen-card');
    hide('tailor-card');
    hide('tailor-card-results');
    hide('startover-wrap');
    document.getElementById('screen-content').innerHTML = '';
    document.getElementById('tailor-content').innerHTML = '';
    document.getElementById('screen-btn').textContent = 'Screen this job';
    document.getElementById('screen-btn').disabled = false;
  }

  // ── HELPERS ─────────────────────────────────────────────────
  function setStatus(msg)       { document.getElementById('status-text').textContent = msg; }
  function animateProgress(pct) { document.getElementById('progress-bar').style.width = pct + '%'; }
  function show(id) { document.getElementById(id).style.display = 'block'; }
  function hide(id) { document.getElementById(id).style.display = 'none';  }

  function timeAgo(isoStr) {
    if (!isoStr) return '';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60)    return 'just now';
    if (diff < 3600)  return Math.round(diff / 60) + 'm ago';
    if (diff < 86400) return Math.round(diff / 3600) + 'h ago';
    return Math.round(diff / 86400) + 'd ago';
  }

  function errorBox(msg) {
    return `<div class="error-box">&#9888; ${escHtml(msg)}</div>`;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
</script>
</body>
</html>
"""

# ============================================================
# HELPERS
# ============================================================

def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def bullets_expr(bullets: list) -> str:
    if not bullets:
        return '""'
    return " & (return) & ".join(f'"• {esc(b)}"' for b in bullets)


def parse_claude_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text.strip())


def call_claude(prompt: str, max_tokens: int) -> dict:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_claude_json(message.content[0].text)


# ============================================================
# ROUTE — Main page
# ============================================================

@app.route("/")
def index():
    return render_template_string(HTML)


# ============================================================
# ROUTE — GET /jobs
# ============================================================

def _clean(val) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val)


def _jobspy_fetch(query: str) -> list:
    try:
        df = scrape_jobs(
            site_name=["indeed", "zip_recruiter", "glassdoor", "linkedin"],
            search_term=query,
            hours_old=24,
            results_wanted=15,
            country_indeed="USA",
            linkedin_fetch_description=True,
        )
        if df is None or df.empty:
            return []
        rows = []
        for _, row in df.iterrows():
            date_posted = row.get("date_posted")
            try:
                posted_str = date_posted.isoformat() if hasattr(date_posted, "isoformat") and not pd.isna(date_posted) else ""
            except Exception:
                posted_str = ""
            rows.append({
                "id":          _clean(row.get("id")) or _clean(row.get("job_url")),
                "title":       _clean(row.get("title")),
                "company":     _clean(row.get("company")),
                "location":    _clean(row.get("location")),
                "experience":  "Not specified",
                "posted":      posted_str,
                "url":         _clean(row.get("job_url")),
                "description": _clean(row.get("description")),
            })
        return rows
    except Exception as e:
        print(f"jobspy error for '{query}': {e}")
        return []


@app.route("/jobs")
def get_jobs():
    with ThreadPoolExecutor(max_workers=4) as ex:
        batches = list(ex.map(_jobspy_fetch, SEARCH_QUERIES))

    seen, jobs = set(), []
    for batch in batches:
        for j in batch:
            key = j["url"] or j["id"]
            if not key or key in seen:
                continue
            seen.add(key)
            jobs.append(j)

    return jsonify({"jobs": jobs, "count": len(jobs)})


# ============================================================
# ROUTE — POST /screen
# ============================================================

@app.route("/screen", methods=["POST"])
def screen():
    body = request.get_json(silent=True) or {}
    jd   = (body.get("jd") or "").strip()
    if not jd:
        return jsonify({"error": "Job description is required."}), 400

    prompt = f"""You are a job application screener. Analyze this job description and return a JSON object with EXACTLY these fields:

- fit_score: integer 0-100. Holistic estimate of how good a fit this role is for a recent CS graduate with ~2 years of project experience.
- flags: array of objects, each with "type" and "detail". Detect these types only:
    * "no_sponsorship" — JD says no visa sponsorship or requires authorization to work in the US
    * "seniority" — role clearly requires 5+ years of experience, or is Staff / Principal / Director / VP level
    * "security_clearance" — role requires any security clearance
  If none apply, return an empty array.
- flag_count: integer equal to the length of the flags array.
- recommendation: exactly one of: "strong apply", "apply", "borderline", "skip"
  Use this scale — strong apply (fit_score 80+, no bad flags), apply (60-79), borderline (40-59 or has one flag), skip (below 40 or has 2+ flags or security clearance).

Return ONLY the raw JSON object. No markdown, no explanation, no code fences.

Job Description:
{jd}"""

    try:
        return jsonify(call_claude(prompt, max_tokens=512))
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Claude returned invalid JSON: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Screening failed: {e}"}), 500


# ============================================================
# ROUTE — POST /tailor
# ============================================================

@app.route("/tailor", methods=["POST"])
def tailor():
    body      = request.get_json(silent=True) or {}
    company   = (body.get("company")   or "").strip()
    role      = (body.get("role")      or "").strip()
    url       = (body.get("url")       or "").strip()
    jd        = (body.get("jd")        or "").strip()
    fit_score = body.get("fit_score", 0)

    if not company or not role or not jd:
        return jsonify({"error": "Company, role, and job description are required."}), 400
    if MASTER_RESUME is None:
        return jsonify({"error": "master_resume.json could not be loaded. Check the path in the config block."}), 500

    prompt = f"""You are a resume tailoring expert. Given a job description and a master resume, select the best content for a targeted one-page resume.

IMPORTANT: The final resume must fit on ONE PAGE. Err on the side of selecting fewer items. It is better to have breathing room than to cram content.

The resume has two separate skills lines:
  Line 1 — "Programming languages: [values]"
  Line 2 — "Frameworks/Technologies: [values]"
Select separately from the languages list and the frameworks list in the master resume.

Return a JSON object with EXACTLY these fields:
- selected_languages: ordered array of language names from skills.languages. Pick the most relevant, up to 5.
- selected_frameworks: ordered array of framework/tool names from skills.frameworks. Pick the most relevant, up to 10.
- selected_projects: array of EXACTLY 3 project names from the master resume. Pick the 3 best matches.
- ats_score: integer 0-100. How well the selected content matches ATS keywords in the JD.
- ats_missing_keywords: array of important JD keywords NOT found in the selected content. List up to 8.
- ats_matched_keywords: array of JD keywords that DO appear in the selected content. List up to 12.
- recruiter_score: integer 0-100. How compelling this tailored resume would appear to a human recruiter.
- recruiter_feedback: array of exactly 2–3 short, specific, actionable feedback strings.

Return ONLY the raw JSON object. No markdown, no explanation, no code fences.

Job Description:
{jd}

Master Resume (JSON):
{json.dumps(MASTER_RESUME, indent=2)}"""

    try:
        result = call_claude(prompt, max_tokens=1024)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Claude returned invalid JSON: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Tailoring API call failed: {e}"}), 500

    project_map            = {p["name"]: p for p in MASTER_RESUME.get("projects", [])}
    selected_project_names = result.get("selected_projects", [])[:3]
    selected_projects      = [project_map[n] for n in selected_project_names if n in project_map]
    while len(selected_projects) < 3:
        selected_projects.append({"name": "Project", "bullets": []})

    languages_str  = ", ".join(result.get("selected_languages", []))
    frameworks_str = ", ".join(result.get("selected_frameworks", []))

    date_label   = datetime.date.today().strftime("%B%-d")
    company_safe = re.sub(r"[^A-Za-z0-9]", "", company)
    job_folder   = Path(PDF_OUTPUT_FOLDER) / f"{company_safe}_{date_label}"
    job_folder.mkdir(parents=True, exist_ok=True)
    pdf_path   = str(job_folder / "ShravanthiMurugesan_Resume.pdf")
    pages_path = str(job_folder / "ShravanthiMurugesan_Resume.pages")

    pdf_error = None
    try:
        run_pages_export(languages_str, frameworks_str, selected_projects, pdf_path, pages_path)
    except Exception as e:
        pdf_error = str(e)
        pdf_path  = None

    tracker_error = None
    try:
        log_to_tracker(company, role, url, jd, fit_score,
                       result.get("ats_score", 0), result.get("recruiter_score", 0),
                       pdf_path or "")
    except Exception as e:
        tracker_error = str(e)

    return jsonify({
        **result,
        "pdf_path":        pdf_path,
        "pdf_error":       pdf_error,
        "tracker_updated": tracker_error is None,
        "tracker_error":   tracker_error,
    })


# ============================================================
# HELPER — AppleScript: fill Pages template, export PDF
# Template tokens: {{skills_languages}}, {{skills_frameworks}},
#   {{project1_name}}, {{project1_bullets}}, (same for 2 and 3)
# ============================================================

def run_pages_export(languages_str, frameworks_str, projects, pdf_path, pages_path):
    p1, p2, p3 = projects[0], projects[1], projects[2]

    script = f"""
tell application "Pages"
    open POSIX file "{esc(PAGES_TEMPLATE_PATH)}"
    delay 2
    tell document 1
        replace "{{{{skills_languages}}}}"  with "{esc(languages_str)}"  replacing all true
        replace "{{{{skills_frameworks}}}}" with "{esc(frameworks_str)}" replacing all true
        replace "{{{{project1_name}}}}"     with "{esc(p1['name'])}"     replacing all true
        replace "{{{{project2_name}}}}"     with "{esc(p2['name'])}"     replacing all true
        replace "{{{{project3_name}}}}"     with "{esc(p3['name'])}"     replacing all true
        set p1b to {bullets_expr(p1.get('bullets', []))}
        set p2b to {bullets_expr(p2.get('bullets', []))}
        set p3b to {bullets_expr(p3.get('bullets', []))}
        replace "{{{{project1_bullets}}}}" with p1b replacing all true
        replace "{{{{project2_bullets}}}}" with p2b replacing all true
        replace "{{{{project3_bullets}}}}" with p3b replacing all true
        save in POSIX file "{esc(pages_path)}"
        export to POSIX file "{esc(pdf_path)}" as PDF
    end tell
end tell
"""

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "AppleScript failed with no error message.")


# ============================================================
# HELPER — Log one row to applications.xlsx
# ============================================================

def log_to_tracker(company, role, url, jd, fit_score, ats_score, recruiter_score, pdf_path):
    columns    = ["Company", "Position", "Referral?", "Date Applied", "Current Status",
                  "URL", "JD", "Fit Score", "ATS Score", "Recruiter Score", "PDF Path"]
    col_widths = [22, 32, 12, 14, 16, 40, 60, 10, 10, 16, 50]

    try:
        wb = openpyxl.load_workbook(TRACKER_PATH)
        ws = wb.active
    except FileNotFoundError:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Applications"
        for col_idx, header in enumerate(columns, start=1):
            ws.cell(row=1, column=col_idx, value=header).font = Font(bold=True)
        for col_idx, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.append([company, role, "", datetime.date.today().strftime("%Y-%m-%d"),
               "Applied", url, jd, fit_score, ats_score, recruiter_score, pdf_path])
    ws.cell(row=ws.max_row, column=7).alignment = Alignment(wrap_text=True)
    wb.save(TRACKER_PATH)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("Resume Tailor running at http://localhost:5002")
    print("Press Ctrl+C to stop.")
    app.run(debug=False, port=5002)
