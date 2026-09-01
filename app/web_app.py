import json
import logging
import os
import tempfile
import threading
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from app.assistant_session import RohaSession
from app.microphone import record_wake_audio
from app.stt import transcribe_audio
from app.wake_detector import wait_for_wake_word

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ROHA // AI WORKSPACE</title>
  <style>
    :root {
      --bg-main: #000000;
      --bg-sidebar: #09090b;
      --bg-card: #121214;
      --bg-card-hover: #18181b;
      --bg-input: #0c0c0e;
      --border-subtle: #27272a;
      --border-strong: #3f3f46;
      --border-focus: #ffffff;
      --text-main: #ffffff;
      --text-muted: #a1a1aa;
      --text-dim: #71717a;
      --font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg-main);
      color: var(--text-main);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.5;
      height: 100vh;
      display: flex;
      overflow: hidden;
    }

    /* Left App Sidebar */
    aside.workspace-sidebar {
      width: 240px;
      background: var(--bg-sidebar);
      border-right: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .brand-header {
      padding: 16px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand-logo {
      width: 28px;
      height: 28px;
      background: #ffffff;
      color: #000000;
      font-family: var(--font-mono);
      font-weight: 900;
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
    }

    .brand-title {
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    .nav-section {
      padding: 12px 8px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;
      overflow-y: auto;
    }

    .nav-label {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--text-dim);
      padding: 8px 8px 4px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 10px;
      border-radius: 4px;
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 120ms ease;
    }

    .nav-item:hover {
      background: var(--bg-card);
      color: var(--text-main);
    }

    .nav-item.active {
      background: var(--bg-card);
      color: var(--text-main);
      border: 1px solid var(--border-strong);
    }

    .nav-icon {
      font-family: var(--font-mono);
      font-size: 11px;
      width: 16px;
      text-align: center;
      color: var(--text-dim);
    }

    .nav-item.active .nav-icon {
      color: var(--text-main);
    }

    .sidebar-footer {
      padding: 12px 16px;
      border-top: 1px solid var(--border-subtle);
      font-size: 11px;
      color: var(--text-dim);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    /* Main Center Workspace */
    main.workspace-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: var(--bg-main);
      min-width: 0;
    }

    /* Header Bar */
    header.workspace-header {
      height: 48px;
      background: var(--bg-sidebar);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .header-badge {
      font-family: var(--font-mono);
      font-size: 11px;
      padding: 2px 8px;
      border: 1px solid var(--border-subtle);
      border-radius: 3px;
      color: var(--text-muted);
      background: var(--bg-card);
    }

    .header-badge.highlight {
      border-color: var(--border-strong);
      color: var(--text-main);
    }

    .header-badge.backend-local {
      border-color: #22c55e;
      color: #22c55e;
      background: rgba(34, 197, 94, 0.1);
    }

    .header-badge.backend-cloud {
      border-color: #f59e0b;
      color: #f59e0b;
      background: rgba(245, 158, 11, 0.1);
      cursor: pointer;
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .btn-mono {
      font-family: var(--font-sans);
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      background: var(--bg-card);
      color: var(--text-muted);
      border: 1px solid var(--border-subtle);
      border-radius: 3px;
      cursor: pointer;
      transition: all 120ms ease;
    }

    .btn-mono:hover {
      background: var(--bg-card-hover);
      color: var(--text-main);
      border-color: var(--border-strong);
    }

    .btn-mono.primary {
      background: #ffffff;
      color: #000000;
      border-color: #ffffff;
    }

    .btn-mono.primary:hover {
      background: #e4e4e7;
    }

    select {
      background: #0d0d10 !important;
      color: #ffffff !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 4px;
      padding: 4px 6px;
      outline: none;
      font-family: var(--font-mono);
      font-size: 11px;
    }
    select:focus {
      border-color: #ffffff !important;
    }
    select option {
      background: #0d0d10 !important;
      color: #ffffff !important;
      padding: 6px 10px;
    }

    /* Content Area: Chat View & Memory Inspector */
    .workspace-content {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 360px;
      overflow: hidden;
    }

    /* Chat / Prompt Section */
    .chat-section {
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--border-subtle);
      background: var(--bg-main);
      overflow: hidden;
    }

    .chat-feed {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .message-card {
      padding: 14px 16px;
      border-radius: 4px;
      border: 1px solid var(--border-subtle);
      background: var(--bg-card);
      display: flex;
      flex-direction: column;
      gap: 6px;
      animation: fadeIn 150ms ease-out;
    }

    .message-card.user {
      border-color: var(--border-strong);
      background: #0d0d10;
    }

    .message-card.assistant {
      border-left: 2px solid #ffffff;
      background: var(--bg-card);
    }

    .message-card.system-note {
      border-style: dashed;
      background: transparent;
      color: var(--text-dim);
      font-size: 11px;
    }

    .message-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      font-weight: 700;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .message-card.user .message-header { color: var(--text-main); }
    .message-card.assistant .message-header { color: #ffffff; }

    .message-body {
      color: var(--text-main);
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
      line-height: 1.6;
    }

    .tool-badge-item {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 10px;
      padding: 1px 6px;
      border: 1px solid var(--border-strong);
      background: #000000;
      color: #ffffff;
      border-radius: 2px;
      margin-left: 6px;
      margin-top: 2px;
    }

    /* Composer Input Bar */
    .composer-area {
      padding: 14px 16px;
      background: var(--bg-sidebar);
      border-top: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .composer-box {
      display: flex;
      gap: 8px;
      align-items: center;
      background: var(--bg-input);
      border: 1px solid var(--border-subtle);
      border-radius: 4px;
      padding: 4px 8px;
    }

    .composer-box:focus-within {
      border-color: var(--border-focus);
    }

    .composer-box input {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-main);
      font-size: 13px;
      font-family: inherit;
      padding: 8px 4px;
      outline: none;
    }

    .composer-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: var(--text-dim);
    }

    /* Right Inspector / Knowledge Panel */
    .inspector-panel {
      background: var(--bg-sidebar);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .inspector-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-subtle);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .inspector-scroll {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .inspector-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 4px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .inspector-card-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #ffffff;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 6px;
    }

    .rag-snippet {
      padding: 8px;
      background: #0a0a0c;
      border: 1px solid var(--border-strong);
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      white-space: pre-wrap;
      word-break: break-word;
    }

    .stat-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      padding-bottom: 4px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }

    .stat-row:last-child {
      border-bottom: none;
    }

    .stat-label { color: var(--text-dim); }
    .stat-value { font-weight: 600; color: #ffffff; font-family: var(--font-mono); }

    .tool-chip-group {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .tool-chip {
      font-family: var(--font-mono);
      font-size: 10px;
      padding: 3px 8px;
      background: #000000;
      color: var(--text-muted);
      border: 1px solid var(--border-subtle);
      border-radius: 3px;
    }

    /* Passphrase Gate Modal Overlay */
    .gate-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.88);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .gate-overlay.hidden { display: none; }

    .gate-modal {
      background: #0d0d10;
      border: 1px solid var(--border-strong);
      border-radius: 6px;
      padding: 24px;
      width: 420px;
      max-width: 90%;
      display: flex;
      flex-direction: column;
      gap: 16px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
    }

    .gate-modal h2 {
      font-size: 14px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .gate-modal p {
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
    }

    .gate-modal input {
      background: #000000;
      border: 1px solid var(--border-strong);
      border-radius: 4px;
      color: #ffffff;
      font-family: var(--font-mono);
      padding: 10px 12px;
      font-size: 13px;
      outline: none;
    }

    .gate-modal input:focus {
      border-color: #ffffff;
    }

    .gate-btn-group {
      display: flex;
      gap: 8px;
    }

    /* Step timeline design */
    .step-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
      border-left: 2px solid var(--border-strong);
      padding-left: 12px;
      margin-bottom: 8px;
      position: relative;
    }
    
    .step-item::before {
      content: '';
      position: absolute;
      left: -5px;
      top: 4px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--border-strong);
    }

    .step-item.pending_approval {
      border-left-color: #ef4444;
    }
    
    .step-item.pending_approval::before {
      background: #ef4444;
    }

    .step-item.completed {
      border-left-color: #ffffff;
    }
    
    .step-item.completed::before {
      background: #ffffff;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 960px) {
      aside.workspace-sidebar { display: none; }
      .workspace-content { grid-template-columns: 1fr; }
      .inspector-panel { display: none; }
    }
  </style>
</head>
<body>

  <!-- Passphrase Gate Modal -->
  <div class="gate-overlay hidden" id="gateOverlay">
    <div class="gate-modal">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2>ROHA // AUTHENTICATION GATE</h2>
        <button type="button" id="gateCloseBtn" class="btn-mono" style="padding: 2px 8px; font-size: 13px; border: none; background: transparent; color: var(--text-muted); cursor: pointer;" title="Close (Esc)">✕</button>
      </div>
      <p id="gateDescription">Enter owner passphrase / PIN (default: <strong>1430</strong>) to unlock creator privileges, workspace file tools, and full RAG memory.</p>
      <form id="gateForm" style="display: flex; flex-direction: column; gap: 12px;">
        <input type="password" id="gatePinInput" placeholder="ENTER PASSPHRASE / PIN..." autocomplete="off" />
        <div class="gate-btn-group">
          <button type="submit" class="btn-mono primary" id="gateSubmitBtn" style="flex: 1; padding: 10px;">UNLOCK CREATOR ACCESS</button>
          <button type="button" class="btn-mono" id="gateLockBtn" style="display: none; padding: 10px;">LOCK SESSION</button>
          <button type="button" class="btn-mono" id="gateGuestBtn" style="padding: 10px;">DISMISS</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Left Sidebar -->
  <aside class="workspace-sidebar">
    <div>
      <div class="brand-header">
        <div class="brand-logo">R</div>
        <div class="brand-title">ROHA WORKSPACE</div>
      </div>
      <div class="nav-section">
        <div class="nav-label">Workspace Modules</div>
        <div class="nav-item active" id="navChat"><span class="nav-icon">&gt;_</span> AI Chat &amp; ReAct Agent</div>
        <div class="nav-item" id="navMemory"><span class="nav-icon">[]</span> SQLite RAG Vault</div>
        <div class="nav-item" id="navTools"><span class="nav-icon">{}</span> Active Skills &amp; Tools</div>
        <div class="nav-item" id="navCookbook"><span class="nav-icon">#</span> Hardware Profiler</div>
        
        <div class="nav-label" style="margin-top: 12px;">Security &amp; Auth</div>
        <div class="nav-item" id="navSecurity"><span class="nav-icon">*</span> Creator Access Gate</div>
      </div>
    </div>
    <div class="sidebar-footer">
      <span>LOCAL HOST: 8000</span>
      <span id="sidebarStatus">ONLINE</span>
    </div>
  </aside>

  <!-- Main Center Workspace -->
  <main class="workspace-main">
    <!-- Header -->
    <header class="workspace-header">
      <div class="header-left">
        <span style="font-weight: 700;">WORKSPACE // CONSOLE</span>
        <span class="header-badge backend-local" id="headerBackend" title="Click to toggle backend">🏠 LOCAL</span>
        <span class="header-badge" id="headerModel">qwen2.5:3b-instruct</span>
        <span class="header-badge" id="headerLatency">0.00s</span>
        <span class="header-badge" id="headerState">IDLE</span>
      </div>
      <div class="header-right">
        <canvas id="waveformCanvas" width="90" height="20" style="border-radius: 3px; display: none; background: #000; border: 1px solid var(--border-subtle); margin-right: 8px;"></canvas>
        <span class="header-badge highlight" id="headerAuth" style="cursor: pointer;" title="Click to open Passphrase Gate">GUEST MODE</span>
        <button class="btn-mono" id="ttsToggleBtn" title="Toggle voice speech response">SPEECH: ON 🔊</button>
        <button class="btn-mono" id="clearBtn">CLEAR</button>
        <button class="btn-mono" id="micToggleBtn">MIC</button>
      </div>
    </header>

    <!-- Workspace Content (Chat + Inspector) -->
    <div id="chatViewContainer" class="workspace-content">
      
      <!-- Chat Feed & Composer -->
      <section class="chat-section">
        <div class="chat-feed" id="chatFeed">
          <div class="message-card system-note">
            <div class="message-header">SYSTEM // INITIALIZATION</div>
            <div class="message-body">Roha AI Agent online. Type your instruction or command below. Local RAG memory active.</div>
          </div>
        </div>

        <!-- Real-time Step Execution Timeline Container -->
        <div id="executionStepsContainer" style="display: none; flex-direction: column; padding: 12px 16px; background: #070708; border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle); max-height: 220px; overflow-y: auto;"></div>

        <div class="composer-area">
          <form class="composer-box" id="composerForm">
            <input id="promptInput" autocomplete="off" placeholder="Ask Roha, execute tools, or inspect files..." />
            <button type="submit" class="btn-mono primary">SEND</button>
          </form>
          <div class="composer-actions">
            <span>Press Enter to send • ReAct Multi-step Autonomous Loop</span>
            <span id="charCounter">Ready</span>
          </div>
        </div>
      </section>

      <!-- Right Knowledge & Memory Inspector -->
      <aside class="inspector-panel">
        <div class="inspector-header">
          <span>RAG MEMORY &amp; STATS</span>
          <span style="font-family: var(--font-mono); font-size: 10px;">SQLITE 3</span>
        </div>

        <div class="inspector-scroll">
          
          <!-- Voice Settings Card -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>VOICE &amp; SPEECH SETTINGS</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <div style="display: flex; flex-direction: column; gap: 4px;">
                <label style="font-size: 9px; color: var(--text-dim); text-transform: uppercase; font-weight: 700;">Active Voice</label>
                <select id="voiceSelect" class="btn-mono" style="width: 100%; text-align: left; background: var(--bg-input); border-color: var(--border-subtle); padding: 4px; color: #ffffff;"></select>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; font-size: 11px;">
                <span class="stat-label">Speech Speed</span>
                <span id="rateVal" class="stat-value">200</span>
              </div>
              <input type="range" id="rateSlider" min="120" max="280" value="200" style="width: 100%; accent-color: #ffffff; cursor: pointer;" />
              
              <div style="display: flex; align-items: center; justify-content: space-between; font-size: 11px;">
                <span class="stat-label">Volume</span>
                <span id="volumeVal" class="stat-value">1.0</span>
              </div>
              <input type="range" id="volumeSlider" min="0.0" max="1.0" step="0.1" value="1.0" style="width: 100%; accent-color: #ffffff; cursor: pointer;" />
            </div>
          </div>

          <!-- Audio History Player Card -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>AUDIO HISTORY PLAYER</span>
            </div>
            <div id="audioHistoryContainer" style="display: flex; flex-direction: column; gap: 8px; max-height: 140px; overflow-y: auto;">
              <span style="color: var(--text-dim); font-size: 11px;">No voice recordings captured yet.</span>
            </div>
          </div>

          <!-- Current Turn Retrieved RAG Context -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>RAG RETRIEVED (CURRENT TURN)</span>
            </div>
            <div id="ragContainer" style="display: flex; flex-direction: column; gap: 6px;">
              <span style="color: var(--text-dim); font-size: 11px;">No RAG context fetched for this query yet.</span>
            </div>
          </div>

          <!-- Active Tools Registry -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>AVAILABLE AGENT TOOLS</span>
            </div>
            <div class="tool-chip-group">
              <span class="tool-chip">calculator</span>
              <span class="tool-chip">system_info</span>
              <span class="tool-chip">read_file</span>
              <span class="tool-chip">write_file</span>
              <span class="tool-chip">edit_file</span>
              <span class="tool-chip">delete_file</span>
              <span class="tool-chip">execute_command</span>
              <span class="tool-chip">web_search</span>
              <span class="tool-chip">list_directory</span>
            </div>
          </div>

          <!-- Hardware & System Specs -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>SYSTEM PROFILE</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <div class="stat-row">
                <span class="stat-label">Model Runtime</span>
                <select id="modelRouterSelect" class="btn-mono" style="background: var(--bg-input); border-color: var(--border-subtle); font-size: 10px; font-family: var(--font-mono); padding: 2px 4px; color: #ffffff; cursor: pointer; max-width: 180px;"></select>
              </div>
              <div class="stat-row"><span class="stat-label">Inference Latency</span><span class="stat-value" id="statLatency">0.00s</span></div>
              <div class="stat-row"><span class="stat-label">ReAct Step Bound</span><span class="stat-value">5 Steps Max</span></div>
              <div class="stat-row"><span class="stat-label">Memory Backend</span><span class="stat-value">SQLite + Vector</span></div>
              <div class="stat-row"><span class="stat-label">Creator Auth</span><span class="stat-value" id="statAuth">Unverified</span></div>
              
              <!-- Real-time Latency Chart -->
              <div style="margin-top: 8px; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
                <div style="font-size: 10px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px; font-weight: 700;">Latency Trend (last 8 queries)</div>
                <svg id="latencySvg" width="100%" height="45" style="background: #000; border-radius: 3px; border: 1px solid var(--border-subtle);"></svg>
              </div>
            </div>
          </div>

          <!-- Recent SQLite Memory Store -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>SQLITE MEMORY VAULT</span>
            </div>
            <div id="sqliteContainer" style="display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto;">
              <span style="color: var(--text-dim); font-size: 11px;">Loading SQLite memory...</span>
            </div>
          </div>

        </div>
      </aside>
    </div>

    <!-- RAG Memory Studio & Knowledge Vault (Phase 4) -->
    <div id="memoryStudioContainer" class="workspace-content" style="display: none; flex-direction: column; overflow: hidden; background: var(--bg-workspace);">
      
      <!-- Studio Sub-Navigation Bar -->
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: var(--bg-card); border-bottom: 1px solid var(--border-subtle); flex-shrink: 0;">
        <div style="display: flex; gap: 8px;">
          <button class="btn-mono active" id="tabGraphBtn" style="font-weight: 700;">🕸 MEMORY GRAPH</button>
          <button class="btn-mono" id="tabPlaygroundBtn">🔍 VECTOR PLAYGROUND</button>
          <button class="btn-mono" id="tabVaultBtn">🗄 KNOWLEDGE VAULT</button>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <span id="memoryStudioStats" style="font-size: 11px; color: var(--text-dim); font-family: var(--font-mono);">Nodes: 0 | Links: 0</span>
          <button class="btn-mono primary" id="addMemoryModalBtn">+ ADD FACT</button>
        </div>
      </div>

      <!-- Studio Sub-Views Container -->
      <div style="flex: 1; position: relative; overflow: hidden; display: flex; flex-direction: column;">
        
        <!-- Sub-View 1: Interactive Memory Graph -->
        <div id="viewMemoryGraph" style="flex: 1; display: flex; flex-direction: column; position: relative; background: #060608; overflow: hidden;">
          <div style="position: absolute; top: 12px; left: 16px; z-index: 10; display: flex; align-items: center; gap: 12px; background: rgba(12,12,16,0.9); backdrop-filter: blur(8px); padding: 6px 14px; border-radius: 4px; border: 1px solid var(--border-subtle);">
            <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
              <span style="color: var(--text-dim);">Similarity Link Threshold:</span>
              <input type="range" id="graphThreshSlider" min="0.1" max="0.8" step="0.05" value="0.35" style="width: 90px; accent-color: #4ade80;" />
              <span id="graphThreshVal" style="color: #4ade80; font-family: var(--font-mono); font-weight: 700;">0.35</span>
            </div>
            <button class="btn-mono" id="graphRefreshBtn" style="padding: 2px 8px; font-size: 10px;">RELOAD</button>
            <button class="btn-mono" id="graphRecenterBtn" style="padding: 2px 8px; font-size: 10px;">RECENTER</button>
          </div>
          <div style="position: absolute; bottom: 12px; left: 16px; z-index: 10; display: flex; gap: 14px; font-size: 10px; color: var(--text-dim); background: rgba(12,12,16,0.9); padding: 6px 10px; border-radius: 4px; border: 1px solid var(--border-subtle);">
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #4ade80; display: inline-block; box-shadow: 0 0 6px #4ade80;"></span> Semantic Fact (Vector)</span>
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #60a5fa; display: inline-block; box-shadow: 0 0 6px #60a5fa;"></span> User Prompt</span>
            <span style="display: flex; align-items: center; gap: 5px;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #a78bfa; display: inline-block; box-shadow: 0 0 6px #a78bfa;"></span> Assistant Turn</span>
          </div>
          <canvas id="memoryGraphCanvas" style="width: 100%; height: 100%; cursor: grab;"></canvas>
          <div id="graphTooltip" style="display: none; position: absolute; z-index: 20; background: rgba(14,14,18,0.95); border: 1px solid #4ade80; border-radius: 4px; padding: 8px 12px; max-width: 300px; font-size: 11px; color: #fff; pointer-events: none; box-shadow: 0 4px 20px rgba(0,0,0,0.6);"></div>
        </div>

        <!-- Sub-View 2: Vector Search Playground -->
        <div id="viewVectorPlayground" style="flex: 1; display: none; flex-direction: column; padding: 20px; overflow-y: auto; background: var(--bg-workspace); gap: 16px;">
          <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 16px; display: flex; flex-direction: column; gap: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #fff; letter-spacing: 0.5px;">VECTOR SEARCH TEST &amp; RAG INSPECTION</div>
            <div style="display: flex; gap: 10px;">
              <input id="playgroundQueryInput" placeholder="Enter test query (e.g. 'GitHub repositories', 'Roshan personal projects', 'tools available')..." style="flex: 1; background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 8px 12px; font-family: var(--font-mono); font-size: 12px; border-radius: 4px;" />
              <button class="btn-mono primary" id="playgroundSearchBtn" style="padding: 8px 16px;">RUN COMPARISON</button>
            </div>
            <div style="display: flex; gap: 24px; font-size: 11px; color: var(--text-dim);">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span>Top-K Results:</span>
                <input type="range" id="playgroundKSlider" min="1" max="10" value="5" style="width: 80px; accent-color: #60a5fa;" />
                <span id="playgroundKVal" style="color: #60a5fa; font-weight: 700;">5</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span>Min Similarity:</span>
                <input type="range" id="playgroundSimSlider" min="0.0" max="0.9" step="0.05" value="0.25" style="width: 80px; accent-color: #4ade80;" />
                <span id="playgroundSimVal" style="color: #4ade80; font-weight: 700;">0.25</span>
              </div>
            </div>
          </div>

          <!-- Comparison Columns -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; flex: 1;">
            
            <!-- Semantic Vector Matches -->
            <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 16px; display: flex; flex-direction: column;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 700; color: #4ade80;">TIER-3 // SEMANTIC VECTOR EMBEDDINGS</span>
                <span id="playgroundSemanticCount" style="font-size: 10px; color: var(--text-dim);">0 matches</span>
              </div>
              <div id="playgroundSemanticList" style="display: flex; flex-direction: column; gap: 8px; overflow-y: auto; flex: 1; max-height: 280px;">
                <span style="color: var(--text-dim); font-size: 11px;">Run a search to inspect cosine similarity scores.</span>
              </div>
            </div>

            <!-- Episodic Fuzzy Matches -->
            <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 16px; display: flex; flex-direction: column;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 700; color: #60a5fa;">TIER-2 // EPISODIC FUZZY &amp; RECENCY</span>
                <span id="playgroundEpisodicCount" style="font-size: 10px; color: var(--text-dim);">0 matches</span>
              </div>
              <div id="playgroundEpisodicList" style="display: flex; flex-direction: column; gap: 8px; overflow-y: auto; flex: 1; max-height: 280px;">
                <span style="color: var(--text-dim); font-size: 11px;">Run a search to inspect token ratio matches.</span>
              </div>
            </div>

          </div>

          <!-- Synthesized Context Injection Preview -->
          <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 14px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--text-dim); margin-bottom: 6px;">SYNTHESIZED RAG CONTEXT INJECTION PREVIEW</div>
            <pre id="playgroundRagPreview" style="margin: 0; padding: 10px; background: #050507; border-radius: 4px; color: #e4e4e7; font-family: var(--font-mono); font-size: 11px; white-space: pre-wrap; max-height: 120px; overflow-y: auto;">(No search executed yet)</pre>
          </div>
        </div>

        <!-- Sub-View 3: CRUD Knowledge Vault -->
        <div id="viewKnowledgeVault" style="flex: 1; display: none; flex-direction: column; padding: 16px; overflow-y: auto; background: var(--bg-workspace); gap: 12px;">
          
          <!-- Toolbar -->
          <div style="display: flex; gap: 10px; align-items: center; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 14px;">
            <input id="vaultSearchInput" placeholder="Filter memory records..." style="flex: 1; background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 6px 10px; font-family: var(--font-mono); font-size: 11px; border-radius: 4px;" />
            <select id="vaultTypeSelect" class="btn-mono" style="background: var(--bg-input); border-color: var(--border-subtle); font-size: 11px; color: #fff; padding: 6px 8px;">
              <option value="all">All Types</option>
              <option value="semantic">Semantic Facts (Vector)</option>
              <option value="episodic">Episodic Messages (SQLite)</option>
            </select>
            <button class="btn-mono" id="vaultRefreshBtn">REFRESH</button>
          </div>

          <!-- Memory Records Table / List -->
          <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 6px; overflow: hidden; flex: 1; display: flex; flex-direction: column;">
            <div style="display: grid; grid-template-columns: 60px 110px 130px 1fr 140px; padding: 10px 16px; background: #0c0c10; border-bottom: 1px solid var(--border-subtle); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase;">
              <span>ID</span>
              <span>Type</span>
              <span>Category / Role</span>
              <span>Memory Content</span>
              <span style="text-align: right;">Actions</span>
            </div>
            <div id="vaultTableBody" style="overflow-y: auto; flex: 1; max-height: 480px; display: flex; flex-direction: column;">
              <div style="padding: 20px; text-align: center; color: var(--text-dim); font-size: 11px;">Loading knowledge records...</div>
            </div>
          </div>

        </div>

      </div>
    </div>
  </main>

  <!-- Add Memory Modal -->
  <div id="addMemoryModal" class="gate-overlay" style="display: none;">
    <div class="gate-card" style="max-width: 460px;">
      <div class="gate-header">
        <span>NEW MEMORY FACT // VECTOR VAULT</span>
        <button class="btn-mono" id="addMemoryCloseBtn" style="padding: 2px 6px;">✕</button>
      </div>
      <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; color: var(--text-dim); font-weight: 700;">STORE TYPE</label>
          <select id="addMemoryType" class="btn-mono" style="width: 100%; text-align: left; background: var(--bg-input); border-color: var(--border-subtle); padding: 6px; color: #fff;">
            <option value="semantic">Tier-3 Semantic Vector Memory</option>
            <option value="episodic">Tier-2 Episodic Message</option>
          </select>
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; color: var(--text-dim); font-weight: 700;">CATEGORY / TAG</label>
          <input id="addMemoryCategory" placeholder="e.g. personal, preferences, credentials, project" style="background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 6px 10px; font-family: var(--font-mono); font-size: 12px; border-radius: 4px;" value="general" />
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; color: var(--text-dim); font-weight: 700;">FACT / MEMORY CONTENT</label>
          <textarea id="addMemoryContent" rows="4" placeholder="Enter the exact fact or information to remember..." style="background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 8px 10px; font-family: var(--font-mono); font-size: 12px; border-radius: 4px; resize: vertical;"></textarea>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button class="btn-mono" id="addMemoryCancelBtn">CANCEL</button>
          <button class="btn-mono primary" id="addMemorySubmitBtn">SAVE FACT</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Edit Memory Modal -->
  <div id="editMemoryModal" class="gate-overlay" style="display: none;">
    <div class="gate-card" style="max-width: 460px;">
      <div class="gate-header">
        <span>EDIT MEMORY RECORD</span>
        <button class="btn-mono" id="editMemoryCloseBtn" style="padding: 2px 6px;">✕</button>
      </div>
      <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
        <input type="hidden" id="editMemoryId" />
        <input type="hidden" id="editMemoryType" />
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; color: var(--text-dim); font-weight: 700;">CATEGORY / ROLE</label>
          <input id="editMemoryCategory" style="background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 6px 10px; font-family: var(--font-mono); font-size: 12px; border-radius: 4px;" />
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; color: var(--text-dim); font-weight: 700;">CONTENT</label>
          <textarea id="editMemoryContent" rows="4" style="background: var(--bg-input); border: 1px solid var(--border-subtle); color: #fff; padding: 8px 10px; font-family: var(--font-mono); font-size: 12px; border-radius: 4px; resize: vertical;"></textarea>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button class="btn-mono" id="editMemoryCancelBtn">CANCEL</button>
          <button class="btn-mono primary" id="editMemorySubmitBtn">UPDATE RECORD</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    // DOM Elements - Chat & Header
    const chatFeed = document.getElementById('chatFeed');
    const promptInput = document.getElementById('promptInput');
    const composerForm = document.getElementById('composerForm');
    const headerModel = document.getElementById('headerModel');
    const headerLatency = document.getElementById('headerLatency');
    const headerState = document.getElementById('headerState');
    const headerAuth = document.getElementById('headerAuth');
    const headerBackend = document.getElementById('headerBackend');
    const statLatency = document.getElementById('statLatency');
    const statAuth = document.getElementById('statAuth');
    const ttsToggleBtn = document.getElementById('ttsToggleBtn');
    const clearBtn = document.getElementById('clearBtn');
    const micToggleBtn = document.getElementById('micToggleBtn');
    const gateOverlay = document.getElementById('gateOverlay');
    const gateForm = document.getElementById('gateForm');
    const gatePinInput = document.getElementById('gatePinInput');
    const gateCloseBtn = document.getElementById('gateCloseBtn');
    const gateLockBtn = document.getElementById('gateLockBtn');
    const gateGuestBtn = document.getElementById('gateGuestBtn');
    const gateDescription = document.getElementById('gateDescription');
    const ragContainer = document.getElementById('ragContainer');
    const sqliteContainer = document.getElementById('sqliteContainer');
    const navSecurity = document.getElementById('navSecurity');
    const navTools = document.getElementById('navTools');
    const navCookbook = document.getElementById('navCookbook');
    const modelRouterSelect = document.getElementById('modelRouterSelect');
    const rateSlider = document.getElementById('rateSlider');
    const rateVal = document.getElementById('rateVal');
    const volumeSlider = document.getElementById('volumeSlider');
    const volumeVal = document.getElementById('volumeVal');
    const voiceSelect = document.getElementById('voiceSelect');
    const audioHistoryContainer = document.getElementById('audioHistoryContainer');
    const executionStepsContainer = document.getElementById('executionStepsContainer');
    const waveformCanvas = document.getElementById('waveformCanvas');

    // DOM Elements - Phase 4 Memory Studio
    const navChat = document.getElementById('navChat');
    const navMemory = document.getElementById('navMemory');
    const chatViewContainer = document.getElementById('chatViewContainer');
    const memoryStudioContainer = document.getElementById('memoryStudioContainer');
    const tabGraphBtn = document.getElementById('tabGraphBtn');
    const tabPlaygroundBtn = document.getElementById('tabPlaygroundBtn');
    const tabVaultBtn = document.getElementById('tabVaultBtn');
    const viewMemoryGraph = document.getElementById('viewMemoryGraph');
    const viewVectorPlayground = document.getElementById('viewVectorPlayground');
    const viewKnowledgeVault = document.getElementById('viewKnowledgeVault');
    const memoryStudioStats = document.getElementById('memoryStudioStats');
    const graphCanvas = document.getElementById('memoryGraphCanvas');
    const graphTooltip = document.getElementById('graphTooltip');
    const graphThreshSlider = document.getElementById('graphThreshSlider');
    const graphThreshVal = document.getElementById('graphThreshVal');
    const graphRefreshBtn = document.getElementById('graphRefreshBtn');
    const graphRecenterBtn = document.getElementById('graphRecenterBtn');

    // DOM Elements - Vector Playground
    const playgroundQueryInput = document.getElementById('playgroundQueryInput');
    const playgroundSearchBtn = document.getElementById('playgroundSearchBtn');
    const playgroundKSlider = document.getElementById('playgroundKSlider');
    const playgroundKVal = document.getElementById('playgroundKVal');
    const playgroundSimSlider = document.getElementById('playgroundSimSlider');
    const playgroundSimVal = document.getElementById('playgroundSimVal');
    const playgroundSemanticList = document.getElementById('playgroundSemanticList');
    const playgroundSemanticCount = document.getElementById('playgroundSemanticCount');
    const playgroundEpisodicList = document.getElementById('playgroundEpisodicList');
    const playgroundEpisodicCount = document.getElementById('playgroundEpisodicCount');
    const playgroundRagPreview = document.getElementById('playgroundRagPreview');

    // DOM Elements - Knowledge Vault & Modals
    const vaultSearchInput = document.getElementById('vaultSearchInput');
    const vaultTypeSelect = document.getElementById('vaultTypeSelect');
    const vaultRefreshBtn = document.getElementById('vaultRefreshBtn');
    const vaultTableBody = document.getElementById('vaultTableBody');
    const addMemoryModalBtn = document.getElementById('addMemoryModalBtn');
    const addMemoryModal = document.getElementById('addMemoryModal');
    const addMemoryCloseBtn = document.getElementById('addMemoryCloseBtn');
    const addMemoryCancelBtn = document.getElementById('addMemoryCancelBtn');
    const addMemorySubmitBtn = document.getElementById('addMemorySubmitBtn');
    const addMemoryType = document.getElementById('addMemoryType');
    const addMemoryCategory = document.getElementById('addMemoryCategory');
    const addMemoryContent = document.getElementById('addMemoryContent');

    const editMemoryModal = document.getElementById('editMemoryModal');
    const editMemoryCloseBtn = document.getElementById('editMemoryCloseBtn');
    const editMemoryCancelBtn = document.getElementById('editMemoryCancelBtn');
    const editMemorySubmitBtn = document.getElementById('editMemorySubmitBtn');
    const editMemoryId = document.getElementById('editMemoryId');
    const editMemoryType = document.getElementById('editMemoryType');
    const editMemoryCategory = document.getElementById('editMemoryCategory');
    const editMemoryContent = document.getElementById('editMemoryContent');

    // State Variables
    let recording = false;
    let mediaRecorder = null;
    let audioChunks = [];
    let latencyHistory = [0.12, 0.25, 0.18, 0.45, 0.30];
    let audioContext = null;
    let analyser = null;
    let dataArray = null;
    let source = null;
    let animationFrameId = null;
    let isPolling = false;
    let currentIsVerified = false;
    let lastRenderedMessagesJson = '';
    let ttsEnabled = localStorage.getItem('roha_tts_enabled') !== 'false';

    // Graph Simulation State
    let graphNodes = [];
    let graphLinks = [];
    let graphTransform = { x: 0, y: 0, k: 1 };
    let isDragging = false;
    let draggedNode = null;
    let dragStart = { x: 0, y: 0 };
    let animFrameId = null;

    // Helper: Unified API Fetch
    async function api(path, payload, method = 'POST') {
      const opts = {
        method: payload ? method : 'GET',
        headers: { 'Content-Type': 'application/json' },
      };
      if (payload) opts.body = JSON.stringify(payload);
      const res = await fetch(path, opts);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    }

    // TTS Toggle Helper
    function updateTtsButton() {
      if (!ttsToggleBtn) return;
      if (ttsEnabled) {
        ttsToggleBtn.textContent = 'SPEECH: ON 🔊';
        ttsToggleBtn.style.color = '#ffffff';
        ttsToggleBtn.style.borderColor = '#ffffff';
      } else {
        ttsToggleBtn.textContent = 'SPEECH: OFF 🔇';
        ttsToggleBtn.style.color = 'var(--text-dim)';
        ttsToggleBtn.style.borderColor = 'var(--border-subtle)';
      }
    }
    if (ttsToggleBtn) {
      ttsToggleBtn.addEventListener('click', () => {
        ttsEnabled = !ttsEnabled;
        localStorage.setItem('roha_tts_enabled', ttsEnabled ? 'true' : 'false');
        updateTtsButton();
      });
      updateTtsButton();
    }

    // Gate Authentication Modal
    function openGate() {
      gateOverlay.classList.remove('hidden');
      gatePinInput.value = '';
      if (currentIsVerified) {
        gateDescription.innerHTML = 'Status: <strong>VERIFIED CREATOR (Roshan Kumar)</strong>.<br>Full file inspection and execution tools are active.';
        gateLockBtn.style.display = 'inline-block';
      } else {
        gateDescription.innerHTML = 'Enter owner passphrase / PIN (default: <strong>1430</strong>) to unlock creator privileges and full tools.';
        gateLockBtn.style.display = 'none';
      }
      setTimeout(() => gatePinInput.focus(), 60);
    }
    function closeGate() {
      gateOverlay.classList.add('hidden');
    }
    headerAuth.addEventListener('click', openGate);
    navSecurity.addEventListener('click', openGate);
    gateCloseBtn.addEventListener('click', closeGate);
    gateGuestBtn.addEventListener('click', closeGate);
    gateLockBtn.addEventListener('click', async () => {
      try {
        await api('/api/lock', {});
        await refreshState();
        closeGate();
      } catch (err) {
        alert('Failed to lock session.');
      }
    });
    gateForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pin = gatePinInput.value.trim();
      if (!pin) return;
      try {
        const res = await api('/api/auth', { pin });
        if (res.ok && res.is_verified) {
          closeGate();
          await refreshState();
          addMessage('system-note', 'Access unlocked: Creator privileges active.');
        } else {
          alert('Invalid PIN.');
        }
      } catch (err) {
        alert('Authentication error: ' + err.message);
      }
    });

    // Chat Message Rendering
    function addMessage(role, text, toolTraces = []) {
      const card = document.createElement('div');
      card.className = `message-card ${role}`;

      const header = document.createElement('div');
      header.className = 'message-header';
      header.textContent = role === 'user' ? 'USER' : (role === 'assistant' ? 'ROHA' : 'SYSTEM');

      if (toolTraces && toolTraces.length > 0) {
        toolTraces.forEach(toolName => {
          const badge = document.createElement('span');
          badge.className = 'tool-badge-item';
          badge.textContent = `TOOL: ${toolName}`;
          header.appendChild(badge);
        });
      }

      const body = document.createElement('div');
      body.className = 'message-body';
      body.textContent = text;

      card.appendChild(header);
      card.appendChild(body);
      chatFeed.appendChild(card);
      chatFeed.scrollTop = chatFeed.scrollHeight;
      return card;
    }

    function renderFeed(messages) {
      const currentJson = JSON.stringify(messages || []);
      if (currentJson === lastRenderedMessagesJson) return;
      lastRenderedMessagesJson = currentJson;

      chatFeed.innerHTML = '';
      const initCard = document.createElement('div');
      initCard.className = 'message-card system-note';
      initCard.innerHTML = '<div class="message-header">SYSTEM // INITIALIZATION</div><div class="message-body">Roha AI Agent online. Type your instruction or command below. Local RAG memory active.</div>';
      chatFeed.appendChild(initCard);

      messages.forEach(m => {
        if (m.role === 'system') return;
        addMessage(m.role, m.content || '');
      });
    }

    function renderRagSnippets(snippets) {
      ragContainer.innerHTML = '';
      if (!snippets || snippets.length === 0) {
        ragContainer.innerHTML = '<span style="color: var(--text-dim); font-size: 11px;">No RAG context fetched for this query yet.</span>';
        return;
      }
      snippets.forEach(s => {
        const item = document.createElement('div');
        item.className = 'rag-snippet';
        item.style.marginBottom = '6px';
        item.textContent = s;
        ragContainer.appendChild(item);
      });
    }

    function renderSqliteMemories(memories) {
      sqliteContainer.innerHTML = '';
      if (!memories || memories.length === 0) {
        sqliteContainer.innerHTML = '<span style="color: var(--text-dim); font-size: 11px;">SQLite memory empty.</span>';
        return;
      }
      memories.slice().reverse().forEach(rec => {
        const item = document.createElement('div');
        item.style.fontSize = '11px';
        item.style.color = 'var(--text-muted)';
        item.style.padding = '4px 0';
        item.style.borderBottom = '1px solid rgba(255,255,255,0.04)';
        item.textContent = typeof rec === 'string' ? rec : (rec.content || JSON.stringify(rec));
        sqliteContainer.appendChild(item);
      });
    }

    // Real-time ReAct Step Visualizer & HITL Interrupter
    function renderSteps(steps, hasPendingTools, pendingTools) {
      if (!executionStepsContainer) return;
      const hasToolActivity = steps && steps.some(st => 
        (st.tool_calls && st.tool_calls.length > 0) || 
        (st.observations && st.observations.length > 0) ||
        st.status === 'pending_approval'
      );
      if (!hasToolActivity) {
        executionStepsContainer.style.display = 'none';
        executionStepsContainer.innerHTML = '';
        return;
      }
      executionStepsContainer.style.display = 'flex';
      executionStepsContainer.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 10px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px;">AUTONOMOUS EXECUTION TIMELINE (${steps.length} STEPS)</span>
          <span style="font-size: 9px; color: var(--text-dim); font-family: var(--font-mono);">${hasPendingTools ? 'PAUSED (AWAITING APPROVAL)' : 'ACTIVE'}</span>
        </div>
      `;

      steps.forEach((st) => {
        const stepCard = document.createElement('div');
        stepCard.style.cssText = 'background: #0d0d10; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 8px 10px; margin-bottom: 6px; font-size: 11px;';
        
        let toolsBadges = '';
        if (st.tool_calls && st.tool_calls.length > 0) {
          st.tool_calls.forEach(tc => {
            const name = tc.function ? tc.function.name : 'tool';
            toolsBadges += `<span style="background: rgba(255,255,255,0.08); border: 1px solid var(--border-subtle); color: #fff; padding: 1px 4px; border-radius: 3px; font-size: 9px; margin-left: 4px;">${name}</span>`;
          });
        }

        stepCard.innerHTML = `
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 700; color: var(--text-dim);">STEP ${st.step} // ${st.status.toUpperCase()}</span>
            <div>${toolsBadges}</div>
          </div>
          <div style="color: var(--text-muted); font-size: 11px; line-height: 1.4; margin-bottom: 4px;">${st.thought}</div>
        `;

        if (st.observations && st.observations.length > 0) {
          const obsBlock = document.createElement('pre');
          obsBlock.style.cssText = 'margin: 4px 0 0 0; padding: 4px 6px; background: #050507; border-radius: 3px; color: #a1a1aa; font-family: var(--font-mono); font-size: 10px; white-space: pre-wrap; max-height: 70px; overflow-y: auto;';
          obsBlock.textContent = st.observations.join(String.fromCharCode(10));
          stepCard.appendChild(obsBlock);
        }

        if (st.status === 'pending_approval' && hasPendingTools) {
          const hitlBox = document.createElement('div');
          hitlBox.style.cssText = 'margin-top: 8px; padding: 8px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 4px; display: flex; flex-direction: column; gap: 6px;';
          hitlBox.innerHTML = `
            <div style="font-weight: 700; color: #f87171; font-size: 10px;">⚠️ HIGH IMPACT ACTIONS DETECTED</div>
            <div style="font-size: 11px; color: #fca5a5;">The agent has proposed actions that require creator authorization.</div>
            <div style="display: flex; gap: 8px; margin-top: 4px;">
              <button class="btn-mono primary" id="approveToolBtn" style="padding: 4px 10px; font-size: 10px; background: #22c55e; color: #000; border-color: #22c55e;">APPROVE &amp; RUN</button>
              <button class="btn-mono" id="rejectToolBtn" style="padding: 4px 10px; font-size: 10px; background: #ef4444; color: #fff; border-color: #ef4444;">REJECT</button>
            </div>
          `;
          stepCard.appendChild(hitlBox);
        }

        executionStepsContainer.appendChild(stepCard);
      });

      const approveBtn = document.getElementById('approveToolBtn');
      const rejectBtn = document.getElementById('rejectToolBtn');
      if (approveBtn) approveBtn.addEventListener('click', approveStep);
      if (rejectBtn) rejectBtn.addEventListener('click', rejectStep);
    }

    async function approveStep() {
      headerState.textContent = 'EXECUTING...';
      try {
        const res = await api('/api/chat/approve', {});
        drawLatencyChart(res.reply === '__AWAITING_APPROVAL__' ? undefined : res.latency);
        renderRagSnippets(res.rag_snippets || []);
        await refreshState();
      } catch (err) {
        alert('Failed to approve tool execution: ' + err.message);
      }
    }

    async function rejectStep() {
      headerState.textContent = 'REJECTING...';
      try {
        const res = await api('/api/chat/reject', {});
        drawLatencyChart(res.reply === '__AWAITING_APPROVAL__' ? undefined : res.latency);
        renderRagSnippets(res.rag_snippets || []);
        await refreshState();
      } catch (err) {
        alert('Failed to reject tool execution: ' + err.message);
      }
    }

    // Latency Chart
    function drawLatencyChart(newLatency) {
      const svg = document.getElementById('latencySvg');
      if (!svg) return;
      if (newLatency !== undefined && newLatency > 0) {
        latencyHistory.push(newLatency);
        if (latencyHistory.length > 8) latencyHistory.shift();
      }
      if (latencyHistory.length === 0) return;

      const w = svg.clientWidth || 200;
      const h = svg.clientHeight || 45;
      const maxVal = Math.max(...latencyHistory, 0.6);
      const points = latencyHistory.map((val, idx) => {
        const x = (idx / (latencyHistory.length - 1 || 1)) * (w - 16) + 8;
        const y = h - ((val / maxVal) * (h - 14) + 6);
        return `${x},${y}`;
      }).join(' ');

      svg.innerHTML = `
        <polyline fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="1" stroke-dasharray="2" points="0,${h/2} ${w},${h/2}" />
        <polyline fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${points}" />
        ${latencyHistory.map((val, idx) => {
          const x = (idx / (latencyHistory.length - 1 || 1)) * (w - 16) + 8;
          const y = h - ((val / maxVal) * (h - 14) + 6);
          return `<circle cx="${x}" cy="${y}" r="2.5" fill="#ffffff" />`;
        }).join('')}
      `;
    }

    // Audio Waveform
    function startWaveform(stream) {
      if (!waveformCanvas) return;
      try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyser.fftSize = 64;
        const bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
        waveformCanvas.style.display = 'inline-block';
        const ctx = waveformCanvas.getContext('2d');
        function draw() {
          animationFrameId = requestAnimationFrame(draw);
          analyser.getByteFrequencyData(dataArray);
          ctx.fillStyle = '#000000';
          ctx.fillRect(0, 0, waveformCanvas.width, waveformCanvas.height);
          const barWidth = (waveformCanvas.width / bufferLength) * 1.5;
          let x = 0;
          for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255) * waveformCanvas.height;
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(x, waveformCanvas.height - barHeight, barWidth - 1, barHeight);
            x += barWidth;
          }
        }
        draw();
      } catch (err) {
        console.warn('Web Audio waveform initialization failed', err);
      }
    }
    function stopWaveform() {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      if (audioContext) audioContext.close();
      if (waveformCanvas) waveformCanvas.style.display = 'none';
    }

    // Audio History Player Card
    function addAudioHistory(text, audioBlobUrl) {
      if (!audioHistoryContainer) return;
      if (audioHistoryContainer.innerText.includes('No voice recordings')) {
        audioHistoryContainer.innerHTML = '';
      }
      const item = document.createElement('div');
      item.style.cssText = 'background: #09090c; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 6px 8px; display: flex; flex-direction: column; gap: 4px;';
      const cleanSnippet = text.length > 35 ? text.substring(0, 32) + '...' : text;
      item.innerHTML = `
        <div style="font-size: 10px; color: var(--text-dim); display: flex; justify-content: space-between;">
          <span>AUDIO CAPTURE</span>
          <span style="color: #fff; font-weight: 700;">${new Date().toLocaleTimeString()}</span>
        </div>
        <div style="font-size: 11px; color: #fff;">"${cleanSnippet}"</div>
        <audio controls src="${audioBlobUrl}" style="width: 100%; height: 24px; margin-top: 2px; filter: invert(1);"></audio>
      `;
      audioHistoryContainer.prepend(item);
    }

    // Model Router & Voice Config
    async function loadModels() {
      try {
        const res = await api('/api/models');
        modelRouterSelect.innerHTML = '';
        const models = (res.models && res.models.length > 0) ? res.models : ['qwen2.5:3b-instruct', 'qwen3:4b', 'gemma3:4b'];
        models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          modelRouterSelect.appendChild(opt);
        });
      } catch (err) {
        console.warn('Failed to load models list', err);
        modelRouterSelect.innerHTML = '<option value="qwen2.5:3b-instruct">qwen2.5:3b-instruct</option>';
      }
    }
    modelRouterSelect.addEventListener('change', async () => {
      const selected = modelRouterSelect.value;
      if (!selected) return;
      headerState.textContent = 'CHANGING MODEL...';
      try {
        await api('/api/models', { model: selected });
        await refreshState();
      } catch (err) {
        alert('Failed to switch model: ' + err.message);
      }
    });

    async function loadVoices() {
      try {
        const res = await api('/api/voices');
        voiceSelect.innerHTML = '';
        if (res.voices && res.voices.length > 0) {
          res.voices.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = v.name;
            voiceSelect.appendChild(opt);
          });
        } else {
          voiceSelect.innerHTML = '<option value="">Default System Voice</option>';
        }
      } catch (err) {
        console.warn('Failed to load system voices', err);
        voiceSelect.innerHTML = '<option value="">Default System Voice</option>';
      }
    }
    async function saveVoiceSettings() {
      try {
        await api('/api/voice/settings', {
          rate: parseInt(rateSlider.value, 10),
          volume: parseFloat(volumeSlider.value),
          voice_id: voiceSelect.value || undefined,
        });
      } catch (err) {
        console.warn('Failed to update voice settings', err);
      }
    }
    rateSlider.addEventListener('input', () => { rateVal.textContent = rateSlider.value; });
    rateSlider.addEventListener('change', saveVoiceSettings);
    volumeSlider.addEventListener('input', () => { volumeVal.textContent = volumeSlider.value; });
    volumeSlider.addEventListener('change', saveVoiceSettings);

    // Backend toggle click handler
    headerBackend.addEventListener('click', async () => {
      const current = headerBackend.textContent.includes('LOCAL') ? 'local' : 'cloud';
      const next = current === 'local' ? 'cloud' : 'local';
      try {
        const res = await api('/api/backend', { provider: next });
        if (res.ok) {
          await refreshState();
          addMessage('system', next === 'cloud'
            ? `☁️ Switched to CLOUD mode — ${res.provider_name} (${res.model})`
            : `🏠 Switched to LOCAL mode — ${res.provider_name} (${res.model})`
          );
        } else {
          addMessage('system', `❌ ${res.error || 'Failed to switch backend'}`);
        }
      } catch (err) {
        addMessage('system', `❌ Backend switch failed: ${err.message}`);
      }
    });
    voiceSelect.addEventListener('change', saveVoiceSettings);

    // Periodic State Poller
    async function refreshState() {
      try {
        const state = await api('/api/state');
        currentIsVerified = !!state.is_verified;
        headerModel.textContent = state.model || 'qwen2.5:3b-instruct';

        // Update backend badge
        const prov = state.provider || 'local';
        if (prov === 'cloud') {
          headerBackend.textContent = '☁️ CLOUD';
          headerBackend.className = 'header-badge backend-cloud';
        } else {
          headerBackend.textContent = '🏠 LOCAL';
          headerBackend.className = 'header-badge backend-local';
        }
        if (state.model && modelRouterSelect.value !== state.model) {
          modelRouterSelect.value = state.model;
        }
        headerLatency.textContent = `${state.last_latency || 0.00}s`;
        statLatency.textContent = `${state.last_latency || 0.00}s`;

        if (state.voice_id && voiceSelect.value !== state.voice_id) {
          voiceSelect.value = state.voice_id;
        }
        if (state.voice_rate && document.activeElement !== rateSlider) {
          rateSlider.value = state.voice_rate;
          rateVal.textContent = state.voice_rate;
        }
        if (state.voice_volume !== undefined && document.activeElement !== volumeSlider) {
          volumeSlider.value = state.voice_volume;
          volumeVal.textContent = state.voice_volume;
        }

        if (state.status_text === 'thinking' || state.status_text === 'Thinking') {
          headerState.textContent = 'THINKING...';
        } else if (state.has_pending_tools) {
          headerState.textContent = 'AWAITING APPROVAL...';
        } else {
          headerState.textContent = state.status_text ? state.status_text.toUpperCase() : 'IDLE';
        }

        if (state.is_verified) {
          headerAuth.textContent = 'VERIFIED CREATOR';
          headerAuth.style.borderColor = '#ffffff';
          statAuth.textContent = 'Roshan (Verified)';
        } else {
          headerAuth.textContent = 'GUEST MODE';
          headerAuth.style.borderColor = 'var(--border-subtle)';
          statAuth.textContent = 'Guest (Restricted)';
        }

        renderRagSnippets(state.last_rag_snippets || []);
        renderSqliteMemories(state.sqlite_memories || []);
        renderSteps(state.execution_steps || [], state.has_pending_tools, state.pending_tools);

        if ((state.status_text && state.status_text.toLowerCase().includes('thinking')) || state.has_pending_tools) {
          if (!isPolling) {
            isPolling = true;
            setTimeout(async () => {
              isPolling = false;
              await refreshState();
            }, 800);
          }
        }
      } catch (err) {
        console.warn('Polling error', err);
      }
    }

    // Chat Composer Form Submit
    composerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = promptInput.value.trim();
      if (!msg) return;

      promptInput.value = '';
      addMessage('user', msg);
      headerState.textContent = 'THINKING...';
      const tempLoading = addMessage('assistant', 'Analyzing request & executing ReAct steps...');
      tempLoading.style.opacity = '0.5';

      try {
        const res = await api('/api/chat', { message: msg, speak: ttsEnabled });
        tempLoading.remove();
        if (res.reply && res.reply !== '__AWAITING_APPROVAL__') {
          addMessage('assistant', res.reply, res.tools_executed || []);
        }
        drawLatencyChart(res.reply === '__AWAITING_APPROVAL__' ? undefined : res.latency);
        renderRagSnippets(res.rag_snippets || []);
        await refreshState();
      } catch (err) {
        tempLoading.remove();
        addMessage('system-note', 'Error connecting to Roha local server: ' + (err.message || 'Request failed'));
        headerState.textContent = 'ERROR';
      }
    });

    clearBtn.addEventListener('click', async () => {
      try {
        await api('/api/reset', {});
        chatFeed.innerHTML = `
          <div class="message-card system-note">
            <div class="message-header">SYSTEM // INITIALIZATION</div>
            <div class="message-body">Roha AI Agent online. Type your instruction or command below. Local RAG memory active.</div>
          </div>
        `;
        if (ragContainer) ragContainer.innerHTML = '<span style="color: var(--text-dim); font-size: 11px;">No RAG context fetched for this query yet.</span>';
        if (executionStepsContainer) {
          executionStepsContainer.style.display = 'none';
          executionStepsContainer.innerHTML = '';
        }
        await refreshState();
      } catch (err) {
        console.warn('Clear session error', err);
      }
    });

    // Microphone Recording Handler
    micToggleBtn.addEventListener('click', async () => {
      if (!recording) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          audioChunks = [];
          mediaRecorder = new MediaRecorder(stream);
          mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
          mediaRecorder.onstop = async () => {
            stopWaveform();
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            const audioUrl = URL.createObjectURL(blob);
            headerState.textContent = 'TRANSCRIBING...';
            const tempLoading = addMessage('assistant', 'Transcribing & processing audio...');
            tempLoading.style.opacity = '0.5';
            try {
              const res = await fetch('/api/voice/chat', {
                method: 'POST',
                headers: { 
                  'Content-Type': 'audio/webm',
                  'X-Speak': ttsEnabled ? '1' : '0'
                },
                body: blob,
              });
              const data = await res.json();
              tempLoading.remove();
              if (data.reply && data.reply !== '__AWAITING_APPROVAL__') {
                addMessage('assistant', data.reply, data.tools_executed || []);
              }
              addAudioHistory(data.transcript || "Voice input", audioUrl);
              drawLatencyChart(data.reply === '__AWAITING_APPROVAL__' ? undefined : data.latency);
              renderRagSnippets(data.rag_snippets || []);
              await refreshState();
            } catch (err) {
              tempLoading.remove();
              addMessage('system-note', 'Voice transcription failed.');
              headerState.textContent = 'ERROR';
            }
          };
          mediaRecorder.start();
          recording = true;
          micToggleBtn.textContent = 'STOP';
          micToggleBtn.style.background = '#ffffff';
          micToggleBtn.style.color = '#000000';
          headerState.textContent = 'RECORDING...';
          startWaveform(stream);
        } catch (err) {
          alert('Microphone access unsupported or denied.');
        }
      } else {
        mediaRecorder.stop();
        recording = false;
        micToggleBtn.textContent = 'MIC';
        micToggleBtn.style.background = '';
        micToggleBtn.style.color = '';
      }
    });

    // ==========================================
    // Phase 4: RAG Memory Studio & Graph Logic
    // ==========================================

    navChat.addEventListener('click', () => {
      navChat.classList.add('active');
      navMemory.classList.remove('active');
      chatViewContainer.style.display = 'grid';
      memoryStudioContainer.style.display = 'none';
    });

    if (navTools) {
      navTools.addEventListener('click', () => {
        navChat.classList.add('active');
        navMemory.classList.remove('active');
        chatViewContainer.style.display = 'grid';
        memoryStudioContainer.style.display = 'none';
        const toolsCard = document.querySelector('.tool-chip-group');
        if (toolsCard) toolsCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }

    if (navCookbook) {
      navCookbook.addEventListener('click', () => {
        navChat.classList.add('active');
        navMemory.classList.remove('active');
        chatViewContainer.style.display = 'grid';
        memoryStudioContainer.style.display = 'none';
        const profileCard = document.getElementById('statLatency');
        if (profileCard) profileCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }

    navMemory.addEventListener('click', () => {
      navMemory.classList.add('active');
      navChat.classList.remove('active');
      chatViewContainer.style.display = 'none';
      memoryStudioContainer.style.display = 'flex';
      loadMemoryGraph();
      loadVaultRecords();
    });

    tabGraphBtn.addEventListener('click', () => {
      tabGraphBtn.classList.add('active');
      tabPlaygroundBtn.classList.remove('active');
      tabVaultBtn.classList.remove('active');
      viewMemoryGraph.style.display = 'flex';
      viewVectorPlayground.style.display = 'none';
      viewKnowledgeVault.style.display = 'none';
      resizeGraphCanvas();
    });

    tabPlaygroundBtn.addEventListener('click', () => {
      tabPlaygroundBtn.classList.add('active');
      tabGraphBtn.classList.remove('active');
      tabVaultBtn.classList.remove('active');
      viewVectorPlayground.style.display = 'flex';
      viewMemoryGraph.style.display = 'none';
      viewKnowledgeVault.style.display = 'none';
    });

    tabVaultBtn.addEventListener('click', () => {
      tabVaultBtn.classList.add('active');
      tabGraphBtn.classList.remove('active');
      tabPlaygroundBtn.classList.remove('active');
      viewKnowledgeVault.style.display = 'flex';
      viewMemoryGraph.style.display = 'none';
      viewVectorPlayground.style.display = 'none';
      loadVaultRecords();
    });

    function resizeGraphCanvas() {
      if (!graphCanvas || !viewMemoryGraph) return;
      const rect = viewMemoryGraph.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        graphCanvas.width = rect.width;
        graphCanvas.height = rect.height;
        if (graphTransform.x === 0 && graphTransform.y === 0) {
          graphTransform.x = rect.width / 2;
          graphTransform.y = rect.height / 2;
        }
      }
    }
    window.addEventListener('resize', resizeGraphCanvas);

    async function loadMemoryGraph() {
      try {
        const thresh = graphThreshSlider.value || 0.35;
        const res = await api(`/api/memories/graph?limit=50&threshold=${thresh}`);
        const nodes = res.nodes || [];
        const links = res.links || [];

        memoryStudioStats.textContent = `Nodes: ${nodes.length} | Links: ${links.length}`;

        resizeGraphCanvas();
        const width = graphCanvas.width || 600;
        const height = graphCanvas.height || 400;

        graphNodes = nodes.map((n, idx) => {
          const angle = (idx / (nodes.length || 1)) * 2 * Math.PI;
          const radius = 100 + (idx % 3) * 50;
          return {
            ...n,
            x: (width / 2) + Math.cos(angle) * radius + (Math.random() - 0.5) * 30,
            y: (height / 2) + Math.sin(angle) * radius + (Math.random() - 0.5) * 30,
            vx: 0,
            vy: 0,
            radius: n.type === 'semantic' ? 12 : 9,
          };
        });

        const nodeMap = new Map(graphNodes.map(n => [n.id, n]));
        graphLinks = links.map(l => ({
          ...l,
          sourceNode: nodeMap.get(l.source),
          targetNode: nodeMap.get(l.target),
        })).filter(l => l.sourceNode && l.targetNode);

        if (!animFrameId) runGraphSimulation();
      } catch (err) {
        console.warn('Failed to load memory graph', err);
      }
    }

    graphThreshSlider.addEventListener('input', () => { graphThreshVal.textContent = graphThreshSlider.value; });
    graphThreshSlider.addEventListener('change', loadMemoryGraph);
    graphRefreshBtn.addEventListener('click', loadMemoryGraph);
    graphRecenterBtn.addEventListener('click', () => {
      const rect = graphCanvas.getBoundingClientRect();
      graphTransform = { x: rect.width / 2, y: rect.height / 2, k: 1 };
    });

    function runGraphSimulation() {
      const ctx = graphCanvas.getContext('2d');
      const width = graphCanvas.width;
      const height = graphCanvas.height;

      const repulsion = 1200;
      const springLength = 80;
      const springStrength = 0.04;
      const centerGravity = 0.015;
      const friction = 0.88;

      for (let i = 0; i < graphNodes.length; i++) {
        const n1 = graphNodes[i];
        if (n1 === draggedNode) continue;

        for (let j = i + 1; j < graphNodes.length; j++) {
          const n2 = graphNodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = repulsion / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          n1.vx -= fx;
          n1.vy -= fy;
          n2.vx += fx;
          n2.vy += fy;
        }

        n1.vx += ((width / 2) - n1.x) * centerGravity;
        n1.vy += ((height / 2) - n1.y) * centerGravity;
      }

      for (const link of graphLinks) {
        const n1 = link.sourceNode;
        const n2 = link.targetNode;
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const delta = dist - springLength;
        const force = delta * springStrength * (link.similarity || 0.5);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (n1 !== draggedNode) { n1.vx += fx; n1.vy += fy; }
        if (n2 !== draggedNode) { n2.vx -= fx; n2.vy -= fy; }
      }

      for (const n of graphNodes) {
        if (n === draggedNode) continue;
        n.vx *= friction;
        n.vy *= friction;
        n.x += n.vx;
        n.y += n.vy;
      }

      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(graphTransform.x, graphTransform.y);
      ctx.scale(graphTransform.k, graphTransform.k);
      ctx.translate(-width / 2, -height / 2);

      for (const link of graphLinks) {
        ctx.beginPath();
        ctx.moveTo(link.sourceNode.x, link.sourceNode.y);
        ctx.lineTo(link.targetNode.x, link.targetNode.y);
        const alpha = Math.min(0.8, Math.max(0.15, (link.similarity || 0.4) * 0.9));
        ctx.strokeStyle = `rgba(74, 222, 128, ${alpha})`;
        ctx.lineWidth = Math.max(1, (link.similarity || 0.5) * 3);
        ctx.stroke();
      }

      for (const n of graphNodes) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
        let fill = '#4ade80';
        let stroke = 'rgba(74, 222, 128, 0.4)';
        if (n.type === 'episodic') {
          if (n.category === 'assistant') { fill = '#a78bfa'; stroke = 'rgba(167, 139, 250, 0.4)'; }
          else { fill = '#60a5fa'; stroke = 'rgba(96, 165, 250, 0.4)'; }
        }
        ctx.fillStyle = fill;
        ctx.shadowColor = fill;
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.lineWidth = 3;
        ctx.strokeStyle = stroke;
        ctx.stroke();

        ctx.font = '10px monospace';
        ctx.fillStyle = '#e4e4e7';
        ctx.textAlign = 'center';
        ctx.fillText(n.label || '', n.x, n.y + n.radius + 12);
      }

      ctx.restore();
      animFrameId = requestAnimationFrame(runGraphSimulation);
    }

    function getCanvasCoords(evt) {
      const rect = graphCanvas.getBoundingClientRect();
      const clientX = evt.clientX - rect.left;
      const clientY = evt.clientY - rect.top;
      const width = graphCanvas.width;
      const height = graphCanvas.height;
      const worldX = (clientX - graphTransform.x) / graphTransform.k + width / 2;
      const worldY = (clientY - graphTransform.y) / graphTransform.k + height / 2;
      return { clientX, clientY, worldX, worldY };
    }

    graphCanvas.addEventListener('mousedown', (e) => {
      const { worldX, worldY, clientX, clientY } = getCanvasCoords(e);
      draggedNode = graphNodes.find(n => {
        const dx = n.x - worldX;
        const dy = n.y - worldY;
        return Math.sqrt(dx * dx + dy * dy) <= n.radius + 4;
      });
      isDragging = true;
      dragStart = { x: clientX, y: clientY, tx: graphTransform.x, ty: graphTransform.y };
      graphCanvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging) {
        if (viewMemoryGraph.style.display !== 'none') {
          const { worldX, worldY, clientX, clientY } = getCanvasCoords(e);
          const hovered = graphNodes.find(n => {
            const dx = n.x - worldX;
            const dy = n.y - worldY;
            return Math.sqrt(dx * dx + dy * dy) <= n.radius + 4;
          });
          if (hovered) {
            graphTooltip.style.display = 'block';
            graphTooltip.style.left = `${clientX + 16}px`;
            graphTooltip.style.top = `${clientY + 16}px`;
            graphTooltip.innerHTML = `<div style="font-weight: 700; color: #4ade80; margin-bottom: 4px;">${hovered.type.toUpperCase()} [${hovered.category}]</div><div style="color: #e4e4e7;">${hovered.full_text}</div>`;
          } else {
            graphTooltip.style.display = 'none';
          }
        }
        return;
      }
      const rect = graphCanvas.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;

      if (draggedNode) {
        const width = graphCanvas.width;
        const height = graphCanvas.height;
        draggedNode.x = (clientX - graphTransform.x) / graphTransform.k + width / 2;
        draggedNode.y = (clientY - graphTransform.y) / graphTransform.k + height / 2;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
      } else {
        graphTransform.x = dragStart.tx + (clientX - dragStart.x);
        graphTransform.y = dragStart.ty + (clientY - dragStart.y);
      }
    });

    window.addEventListener('mouseup', () => {
      isDragging = false;
      draggedNode = null;
      if (graphCanvas) graphCanvas.style.cursor = 'grab';
    });

    graphCanvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      graphTransform.k = Math.min(3, Math.max(0.3, graphTransform.k * zoomFactor));
    });

    playgroundKSlider.addEventListener('input', () => { playgroundKVal.textContent = playgroundKSlider.value; });
    playgroundSimSlider.addEventListener('input', () => { playgroundSimVal.textContent = playgroundSimSlider.value; });

    playgroundSearchBtn.addEventListener('click', async () => {
      const query = playgroundQueryInput.value.trim();
      if (!query) return;

      playgroundSearchBtn.textContent = 'SEARCHING...';
      try {
        const res = await api('/api/memories/playground', {
          query: query,
          k: parseInt(playgroundKSlider.value, 10),
          min_similarity: parseFloat(playgroundSimSlider.value),
        });

        playgroundSemanticList.innerHTML = '';
        playgroundSemanticCount.textContent = `${(res.semantic_matches || []).length} matches`;
        if ((res.semantic_matches || []).length === 0) {
          playgroundSemanticList.innerHTML = '<span style="color: var(--text-dim); font-size: 11px;">No semantic vector matches above threshold.</span>';
        } else {
          res.semantic_matches.forEach(m => {
            const card = document.createElement('div');
            card.style.cssText = 'background: #09090c; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 10px; display: flex; flex-direction: column; gap: 4px;';
            const pct = Math.round(m.score * 100);
            card.innerHTML = `
              <div style="display: flex; justify-content: space-between; font-size: 11px;">
                <span style="color: #4ade80; font-weight: 700;">Cosine Similarity: ${m.score}</span>
                <span style="color: var(--text-dim);">${pct}% Match</span>
              </div>
              <div style="width: 100%; height: 4px; background: #18181b; border-radius: 2px; overflow: hidden; margin: 2px 0;">
                <div style="width: ${pct}%; height: 100%; background: #4ade80;"></div>
              </div>
              <div style="font-size: 11px; color: #f4f4f5; line-height: 1.4;">${m.text}</div>
            `;
            playgroundSemanticList.appendChild(card);
          });
        }

        playgroundEpisodicList.innerHTML = '';
        playgroundEpisodicCount.textContent = `${(res.episodic_matches || []).length} matches`;
        if ((res.episodic_matches || []).length === 0) {
          playgroundEpisodicList.innerHTML = '<span style="color: var(--text-dim); font-size: 11px;">No episodic messages matched.</span>';
        } else {
          res.episodic_matches.forEach(m => {
            const card = document.createElement('div');
            card.style.cssText = 'background: #09090c; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 10px; display: flex; flex-direction: column; gap: 4px;';
            card.innerHTML = `
              <div style="display: flex; justify-content: space-between; font-size: 11px;">
                <span style="color: #60a5fa; font-weight: 700;">${(m.role || 'USER').toUpperCase()} // Score: ${m.score}</span>
                <span style="color: var(--text-dim);">${m.match_type}</span>
              </div>
              <div style="font-size: 11px; color: #f4f4f5; line-height: 1.4;">${m.content}</div>
            `;
            playgroundEpisodicList.appendChild(card);
          });
        }

        if ((res.rag_context_preview || []).length > 0) {
          playgroundRagPreview.textContent = '[Relevant Memories Retrieved]:' + String.fromCharCode(10) + res.rag_context_preview.join(String.fromCharCode(10));
        } else {
          playgroundRagPreview.textContent = '(No memories retrieved for injection into system prompt)';
        }

      } catch (err) {
        alert('Vector playground search failed: ' + err.message);
      } finally {
        playgroundSearchBtn.textContent = 'RUN COMPARISON';
      }
    });

    async function loadVaultRecords() {
      try {
        const search = vaultSearchInput.value.trim();
        const type = vaultTypeSelect.value || 'all';
        vaultTableBody.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim); font-size: 11px;">Loading records...</div>';

        const res = await api(`/api/memories?type=${type}&search=${encodeURIComponent(search)}&limit=100`);
        const memories = res.memories || [];
        vaultTableBody.innerHTML = '';

        if (memories.length === 0) {
          vaultTableBody.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim); font-size: 11px;">No memory records found.</div>';
          return;
        }

        memories.forEach(m => {
          const row = document.createElement('div');
          row.style.cssText = 'display: grid; grid-template-columns: 60px 110px 130px 1fr 140px; padding: 10px 16px; border-bottom: 1px solid var(--border-subtle); align-items: center; font-size: 11px;';
          const isSem = m.type === 'semantic';
          const typeBadge = `<span style="padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; background: ${isSem ? 'rgba(74, 222, 128, 0.15)' : 'rgba(96, 165, 250, 0.15)'}; color: ${isSem ? '#4ade80' : '#60a5fa'}; border: 1px solid ${isSem ? '#4ade80' : '#60a5fa'};">${isSem ? 'SEMANTIC' : 'EPISODIC'}</span>`;

          row.innerHTML = `
            <span style="color: var(--text-dim); font-family: var(--font-mono);">${m.id}</span>
            <div>${typeBadge}</div>
            <span style="color: #e4e4e7; font-family: var(--font-mono); font-weight: 700;">${m.category || 'general'}</span>
            <span style="color: #f4f4f5; line-height: 1.4; padding-right: 12px; word-break: break-word;">${m.content}</span>
            <div style="display: flex; gap: 6px; justify-content: flex-end;">
              <button class="btn-mono edit-btn" style="padding: 2px 8px; font-size: 10px;">EDIT</button>
              <button class="btn-mono delete-btn" style="padding: 2px 8px; font-size: 10px; color: #ef4444; border-color: rgba(239, 68, 68, 0.3);">DEL</button>
            </div>
          `;

          row.querySelector('.edit-btn').addEventListener('click', () => {
            editMemoryId.value = m.id;
            editMemoryType.value = m.type;
            editMemoryCategory.value = m.category || '';
            editMemoryContent.value = m.content || '';
            editMemoryModal.style.display = 'flex';
          });

          row.querySelector('.delete-btn').addEventListener('click', async () => {
            if (!confirm(`Delete ${m.type} memory record #${m.id}?`)) return;
            try {
              await api('/api/memories/delete', { id: m.id, type: m.type });
              await loadVaultRecords();
              loadMemoryGraph();
            } catch (err) {
              alert('Failed to delete memory: ' + err.message);
            }
          });

          vaultTableBody.appendChild(row);
        });

      } catch (err) {
        vaultTableBody.innerHTML = `<div style="padding: 20px; text-align: center; color: #ef4444; font-size: 11px;">Error loading memories: ${err.message}</div>`;
      }
    }

    vaultRefreshBtn.addEventListener('click', loadVaultRecords);
    vaultSearchInput.addEventListener('input', () => {
      clearTimeout(window._searchTimer);
      window._searchTimer = setTimeout(loadVaultRecords, 300);
    });
    vaultTypeSelect.addEventListener('change', loadVaultRecords);

    addMemoryModalBtn.addEventListener('click', () => {
      addMemoryContent.value = '';
      addMemoryCategory.value = 'general';
      addMemoryModal.style.display = 'flex';
    });
    addMemoryCloseBtn.addEventListener('click', () => { addMemoryModal.style.display = 'none'; });
    addMemoryCancelBtn.addEventListener('click', () => { addMemoryModal.style.display = 'none'; });
    addMemorySubmitBtn.addEventListener('click', async () => {
      const content = addMemoryContent.value.trim();
      const category = addMemoryCategory.value.trim();
      const type = addMemoryType.value;
      if (!content) return alert('Please enter fact content.');
      addMemorySubmitBtn.textContent = 'SAVING...';
      try {
        await api('/api/memories', { type, content, category });
        addMemoryModal.style.display = 'none';
        await loadVaultRecords();
        loadMemoryGraph();
      } catch (err) {
        alert('Failed to save memory: ' + err.message);
      } finally {
        addMemorySubmitBtn.textContent = 'SAVE FACT';
      }
    });

    editMemoryCloseBtn.addEventListener('click', () => { editMemoryModal.style.display = 'none'; });
    editMemoryCancelBtn.addEventListener('click', () => { editMemoryModal.style.display = 'none'; });
        editMemorySubmitBtn.addEventListener('click', async () => {
      const id = editMemoryId.value;
      const type = editMemoryType.value;
      const category = editMemoryCategory.value.trim();
      const content = editMemoryContent.value.trim();
      if (!content) return alert('Please enter memory content.');

      editMemorySubmitBtn.textContent = 'UPDATING...';
      try {
        await api('/api/memories/update', { id, type, content, category });
        editMemoryModal.style.display = 'none';
        await loadVaultRecords();
        loadMemoryGraph();
      } catch (err) {
        alert('Failed to update memory: ' + err.message);
      } finally {
        editMemorySubmitBtn.textContent = 'UPDATE RECORD';
      }
    });

    // Initialize all components on load
    async function init() {
      await loadVoices();
      await loadModels();
      try {
        const state = await api('/api/state');
        if (state.messages) renderFeed(state.messages);
      } catch (err) {}
      await refreshState();
      drawLatencyChart();
      setInterval(refreshState, 3000);
    }

    init();
  </script>
</body>
</html>
"""


@dataclass
class WebState:
    session: RohaSession
    status_text: str = "Idle"
    last_heard: str = ""
    last_assistant: str = ""
    last_error: str = ""
    wake_thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class RohaHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, state: WebState):
        self.state = state
        super().__init__(server_address, RequestHandlerClass)

def _resolve_secure_workspace_path(rel_path: str) -> str:
    workspace_root = os.path.abspath(os.getcwd())
    clean_rel = (rel_path or "").strip().lstrip("/\\")
    target = os.path.abspath(os.path.join(workspace_root, clean_rel))
    if not target.startswith(workspace_root):
        raise PermissionError("Access denied: Target path is outside workspace root.")
    return target


def _build_workspace_tree(base_path: str, max_depth: int = 5, current_depth: int = 0) -> list:
    if current_depth > max_depth or not os.path.exists(base_path):
        return []
    workspace_root = os.path.abspath(os.getcwd())
    ignore_names = {".git", "__pycache__", ".venv", ".pytest_cache", ".vscode", "node_modules", "data", "logs", "recordings"}
    items = []
    try:
        entries = sorted(os.listdir(base_path), key=lambda x: (not os.path.isdir(os.path.join(base_path, x)), x.lower()))
        for entry in entries:
            if entry in ignore_names or entry.endswith(".pyc"):
                continue
            full_path = os.path.join(base_path, entry)
            rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")
            is_dir = os.path.isdir(full_path)
            node = {
                "name": entry,
                "path": rel_path,
                "is_dir": is_dir,
            }
            if is_dir:
                node["children"] = _build_workspace_tree(full_path, max_depth, current_depth + 1)
            else:
                try:
                    node["size"] = os.path.getsize(full_path)
                except Exception:
                    node["size"] = 0
            items.append(node)
    except Exception:
        pass
    return items


class RohaWebHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _state(self) -> WebState:
        return self.server.state  # type: ignore[attr-defined]

    def _send_json(self, payload, status: int = 200):
        self.close_connection = True
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def address_string(self):
        # Override to avoid slow reverse DNS lookups on Windows
        return self.client_address[0]

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        self.close_connection = True
        state = self._state()
        parsed = urlparse(self.path)
        logging.info("do_GET: path=%s, parsed.path=%s", self.path, parsed.path)

        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            logging.info("do_GET: served root index page successfully")
            return

        if parsed.path == "/api/state":
            logging.info("do_GET /api/state: start")
            sqlite_memories = []
            try:
                logging.info("do_GET /api/state: fetching memories")
                sqlite_memories = state.session.memory_manager.get_memories(limit=25)
                logging.info("do_GET /api/state: memories fetched count=%d", len(sqlite_memories))
            except Exception as e:
                logging.exception("do_GET /api/state: failed to get memories")

            try:
                logging.info("do_GET /api/state: fetching snapshot messages")
                msgs = state.session.snapshot_messages()
                logging.info("do_GET /api/state: snapshot messages fetched count=%d", len(msgs))
            except Exception as e:
                logging.exception("do_GET /api/state: failed to snapshot messages")
                msgs = []

            payload = {
                "status_text": state.status_text,
                "last_heard": state.last_heard,
                "last_assistant": state.last_assistant,
                "last_error": state.last_error,
                "is_verified": state.session.is_verified,
                "model": state.session.model,
                "last_latency": state.session.last_latency,
                "last_rag_snippets": state.session.last_rag_snippets,
                "last_tools_executed": state.session.last_tools_executed,
                "sqlite_memories": sqlite_memories,
                "messages": msgs,
                "execution_steps": state.session.current_execution_steps,
                "has_pending_tools": bool(state.session.pending_tool_calls),
                "pending_tools": state.session.pending_tool_calls,
                "voice_id": state.session.tts.voice_id if state.session.tts else "",
                "voice_rate": state.session.tts.rate if state.session.tts else 200,
                "voice_volume": state.session.tts.volume if state.session.tts else 1.0,
                "provider": state.session.active_provider,
                "provider_name": state.session.provider_config.get("name", state.session.active_provider),
            }
            logging.info("do_GET /api/state: sending json")
            self._send_json(payload)
            logging.info("do_GET /api/state: completed successfully")
            return

        if parsed.path == "/api/models":
            logging.info("do_GET /api/models: start")
            models_list = []
            try:
                import ollama
                res = ollama.list()
                models_list = [m.model for m in res.models]
            except Exception:
                try:
                    import urllib.request
                    import json
                    req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
                    with urllib.request.urlopen(req, timeout=3) as r:
                        data = json.loads(r.read().decode("utf-8"))
                        models_list = [m["name"] for m in data.get("models", [])]
                except Exception:
                    models_list = ["qwen2.5:3b-instruct", "llama3.1", "phi3"]
            logging.info("do_GET /api/models: sending models count=%d", len(models_list))
            self._send_json({"models": models_list})
            logging.info("do_GET /api/models: completed successfully")
            return

        if parsed.path == "/api/voices":
            logging.info("do_GET /api/voices: start")
            from app.tts import list_available_voices
            self._send_json({"voices": list_available_voices()})
            logging.info("do_GET /api/voices: completed successfully")
            return

        if parsed.path == "/api/memories":
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            mem_type = query_params.get("type", ["all"])[0]
            search_str = query_params.get("search", [""])[0]
            limit_val = int(query_params.get("limit", ["50"])[0])

            records = []
            if mem_type in ("all", "semantic"):
                try:
                    sem_items = state.session.memory_manager.vector_store.get_all_memories(limit=limit_val)
                    if search_str:
                        s_lower = search_str.lower()
                        sem_items = [item for item in sem_items if s_lower in item.get("text", "").lower() or s_lower in item.get("category", "").lower()]
                    for item in sem_items:
                        records.append({
                            "id": item["id"],
                            "type": "semantic",
                            "category": item.get("category", "general"),
                            "content": item["text"],
                            "created_at": item.get("created_at", ""),
                        })
                except Exception:
                    logging.exception("Failed to retrieve semantic memories in API")

            if mem_type in ("all", "episodic"):
                try:
                    ep_items = state.session.memory_manager.get_detailed_messages(limit=limit_val, search=search_str)
                    for item in ep_items:
                        records.append({
                            "id": item["id"],
                            "type": "episodic",
                            "category": item.get("role", "user"),
                            "content": item["content"],
                            "created_at": item.get("timestamp", ""),
                        })
                except Exception:
                    logging.exception("Failed to retrieve episodic memories in API")

            self._send_json({"memories": records, "count": len(records)})
            return

        if parsed.path == "/api/memories/graph":
            from urllib.parse import parse_qs
            query_params = parse_qs(parsed.query)
            limit_val = int(query_params.get("limit", ["50"])[0])
            thresh_val = float(query_params.get("threshold", ["0.35"])[0])

            graph_data = state.session.memory_manager.vector_store.get_memory_graph(
                limit=limit_val, similarity_threshold=thresh_val
            )
            self._send_json(graph_data)
            return

        if parsed.path == "/api/workspace/tree":
            tree = _build_workspace_tree(os.getcwd())
            self._send_json({"ok": True, "tree": tree})
            return

        if parsed.path == "/api/workspace/file":
            from urllib.parse import parse_qs, unquote
            query_params = parse_qs(parsed.query)
            rel_path = unquote(query_params.get("path", [""])[0])
            if not rel_path:
                self._send_json({"ok": False, "error": "File path parameter required."}, status=400)
                return
            try:
                target_file = _resolve_secure_workspace_path(rel_path)
                if not os.path.isfile(target_file):
                    self._send_json({"ok": False, "error": f"File '{rel_path}' not found."}, status=404)
                    return
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._send_json({
                    "ok": True,
                    "path": rel_path,
                    "content": content,
                    "size": len(content.encode("utf-8")),
                    "lines": len(content.splitlines()),
                })
                return
            except PermissionError as pe:
                self._send_json({"ok": False, "error": str(pe)}, status=403)
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
                return

        logging.info("do_GET: path not found: %s", parsed.path)
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        state = self._state()

        if self.path == "/api/chat":
            payload = self._read_json()
            message = str(payload.get("message") or "")
            speak = bool(payload.get("speak", False)) and bool(state.session.tts)
            reply = state.session.process_user_input(message, speak=speak, suspend_for_hitl=True)
            with state.lock:
                state.last_heard = message
                state.last_assistant = reply
                state.status_text = "Idle"
                state.last_error = ""
            self._send_json({
                "reply": reply,
                "latency": state.session.last_latency,
                "rag_snippets": state.session.last_rag_snippets,
                "tools_executed": state.session.last_tools_executed,
                "is_verified": state.session.is_verified,
            })
            return

        if self.path == "/api/chat/approve":
            reply = state.session.resume_react_loop_with_approval()
            with state.lock:
                state.last_assistant = reply
                state.status_text = "Idle"
                state.last_error = ""
            self._send_json({
                "reply": reply,
                "latency": state.session.last_latency,
                "rag_snippets": state.session.last_rag_snippets,
                "tools_executed": state.session.last_tools_executed,
                "is_verified": state.session.is_verified,
            })
            return

        if self.path == "/api/chat/reject":
            reply = state.session.resume_react_loop_with_rejection()
            with state.lock:
                state.last_assistant = reply
                state.status_text = "Idle"
                state.last_error = ""
            self._send_json({
                "reply": reply,
                "latency": state.session.last_latency,
                "rag_snippets": state.session.last_rag_snippets,
                "tools_executed": state.session.last_tools_executed,
                "is_verified": state.session.is_verified,
            })
            return

        if self.path == "/api/models":
            payload = self._read_json()
            model_name = str(payload.get("model") or "").strip()
            if model_name:
                state.session.model = model_name
                self._send_json({"ok": True, "model": model_name})
            else:
                self._send_json({"error": "Model name required"}, status=400)
            return

        if self.path == "/api/voice/settings":
            payload = self._read_json()
            rate = payload.get("rate")
            volume = payload.get("volume")
            voice_id = payload.get("voice_id")
            
            if rate is not None:
                rate = int(rate)
            if volume is not None:
                volume = float(volume)
            if voice_id is not None:
                voice_id = str(voice_id)
                
            state.session.update_tts_settings(rate=rate, volume=volume, voice_id=voice_id)
            self._send_json({"ok": True})
            return

        if self.path == "/api/auth":
            payload = self._read_json()
            pin = str(payload.get("pin") or "")
            ok = state.session.authenticate(pin)
            self._send_json({"ok": ok, "is_verified": state.session.is_verified})
            return

        if self.path == "/api/lock":
            state.session.lock_session()
            self._send_json({"ok": True, "is_verified": state.session.is_verified})
            return

        if self.path == "/api/backend":
            payload = self._read_json()
            provider_key = str(payload.get("provider") or "").strip().lower()
            if not provider_key:
                self._send_json({"error": "Provider key required ('local' or 'cloud')"}, status=400)
                return
            result = state.session.switch_provider(provider_key)
            if result.get("ok"):
                self._send_json(result)
            else:
                self._send_json(result, status=400)
            return

        if self.path == "/api/voice/chat":
            length = int(self.headers.get("Content-Length") or 0)
            audio_bytes = self.rfile.read(length) if length > 0 else b""
            transcript = ""
            reply = ""
            audio_path = None
            try:
                content_type = (self.headers.get("Content-Type") or "").lower()
                suffix = ".webm" if "webm" in content_type else ".wav"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(audio_bytes)
                    audio_path = temp_file.name

                transcript = transcribe_audio(audio_path).strip()
                speak_opt = (self.headers.get("X-Speak") or "1").lower() in ("1", "true", "yes") and bool(state.session.tts)
                reply = state.session.process_user_input(transcript, speak=speak_opt, suspend_for_hitl=True) if transcript else ""

            finally:
                if audio_path:
                    try:
                        os.unlink(audio_path)
                    except Exception:
                        logging.debug("Failed to clean up temporary voice file", exc_info=True)

            with state.lock:
                state.last_heard = transcript
                state.last_assistant = reply if transcript else ""
                state.status_text = "Idle"
                state.last_error = ""
            self._send_json({
                "transcript": transcript,
                "reply": reply,
                "latency": state.session.last_latency,
                "rag_snippets": state.session.last_rag_snippets,
                "tools_executed": state.session.last_tools_executed,
            })
            return

        if self.path == "/api/reset":
            state.session.reset()
            with state.lock:
                state.status_text = "Idle"
                state.last_heard = ""
                state.last_assistant = ""
                state.last_error = ""
            self._send_json({"ok": True})
            return

        if self.path == "/api/wake/start":
            start_wake_listener(state)
            self._send_json({"ok": True})
            return

        if self.path == "/api/wake/stop":
            stop_wake_listener(state)
            self._send_json({"ok": True})
            return

        if self.path == "/api/memories":
            payload = self._read_json()
            m_type = str(payload.get("type") or "semantic").lower()
            content = str(payload.get("content") or "").strip()
            category = str(payload.get("category") or "general").strip()
            role = str(payload.get("role") or "user").strip()

            if not content:
                self._send_json({"error": "Content is required"}, status=400)
                return

            if m_type == "semantic":
                ok = state.session.memory_manager.vector_store.add_memory(content, category=category)
            else:
                try:
                    state.session.memory_manager.add_message(role, content)
                    ok = True
                except Exception:
                    ok = False
            self._send_json({"ok": ok})
            return

        if self.path == "/api/memories/update":
            payload = self._read_json()
            mem_id = int(payload.get("id") or 0)
            m_type = str(payload.get("type") or "semantic").lower()
            content = str(payload.get("content") or "").strip()
            category = str(payload.get("category") or "general").strip()

            if not mem_id or not content:
                self._send_json({"error": "ID and content are required"}, status=400)
                return

            if m_type == "semantic":
                ok = state.session.memory_manager.vector_store.update_memory(mem_id, content, category=category)
            else:
                ok = state.session.memory_manager.update_message(mem_id, content)
            self._send_json({"ok": ok})
            return

        if self.path == "/api/memories/delete":
            payload = self._read_json()
            mem_id = int(payload.get("id") or 0)
            m_type = str(payload.get("type") or "semantic").lower()

            if not mem_id:
                self._send_json({"error": "ID is required"}, status=400)
                return

            if m_type == "semantic":
                ok = state.session.memory_manager.vector_store.delete_memory(mem_id)
            else:
                ok = state.session.memory_manager.delete_message(mem_id)
            self._send_json({"ok": ok})
            return

        if self.path == "/api/memories/playground":
            payload = self._read_json()
            query = str(payload.get("query") or "").strip()
            k_val = int(payload.get("k") or 5)
            sim_val = float(payload.get("min_similarity") or 0.25)

            result = state.session.memory_manager.search_playground(query, k=k_val, min_similarity=sim_val)
            self._send_json(result)
            return

        if self.path == "/api/workspace/file/save":
            if not state.session.is_verified:
                self._send_json({"ok": False, "error": "Verification PIN required for file save operations."}, status=403)
                return
            data = self._read_json()
            rel_path = str(data.get("path") or "").strip()
            content = str(data.get("content") if "content" in data else "")
            if not rel_path:
                self._send_json({"ok": False, "error": "File path parameter required."}, status=400)
                return
            try:
                target_file = _resolve_secure_workspace_path(rel_path)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(content)
                self._send_json({"ok": True, "path": rel_path, "bytes_written": len(content.encode("utf-8"))})
                return
            except PermissionError as pe:
                self._send_json({"ok": False, "error": str(pe)}, status=403)
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
                return

        if self.path == "/api/workspace/file/delete":
            if not state.session.is_verified:
                self._send_json({"ok": False, "error": "Verification PIN required for file deletion."}, status=403)
                return
            data = self._read_json()
            rel_path = str(data.get("path") or "").strip()
            if not rel_path:
                self._send_json({"ok": False, "error": "File path parameter required."}, status=400)
                return
            try:
                target_file = _resolve_secure_workspace_path(rel_path)
                if not os.path.exists(target_file):
                    self._send_json({"ok": False, "error": "File not found."}, status=404)
                    return
                if os.path.isdir(target_file):
                    self._send_json({"ok": False, "error": "Direct directory deletion not allowed."}, status=400)
                    return
                os.remove(target_file)
                self._send_json({"ok": True, "path": rel_path})
                return
            except PermissionError as pe:
                self._send_json({"ok": False, "error": str(pe)}, status=403)
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
                return

        self._send_json({"error": "Not found"}, status=404)


def _wake_loop(state: WebState):
    session = state.session
    while not state.stop_event.is_set():
        with state.lock:
            state.status_text = "Listening for wake word"
            state.last_error = ""

        heard = wait_for_wake_word(state.stop_event)
        if heard is None:
            break

        with state.lock:
            state.last_heard = heard
            state.status_text = "Wake word detected"

        if session.tts:
            try:
                session.tts.speak("Yes?")
            except Exception:
                logging.exception("TTS wake acknowledgement failed")

        with state.lock:
            state.status_text = "Recording response"

        audio_path = record_wake_audio()
        if state.stop_event.is_set():
            break

        try:
            raw_text = transcribe_audio(audio_path)
        except Exception:
            logging.exception("Transcription failed in web wake loop")
            with state.lock:
                state.last_error = "Transcription failed"
                state.status_text = "Listening for wake word"
            continue

        user_input = (raw_text or "").strip()
        if not user_input:
            with state.lock:
                state.status_text = "Listening for wake word"
            continue

        if user_input.lower() == "exit":
            with state.lock:
                state.status_text = "Stopped"
            break

        with state.lock:
            state.status_text = "Thinking"

        reply = session.process_user_input(user_input, speak=bool(session.tts))
        with state.lock:
            state.last_heard = user_input
            state.last_assistant = reply
            state.status_text = "Listening for wake word"
            state.last_error = ""

    with state.lock:
        state.status_text = "Stopped"


def start_wake_listener(state: WebState):
    with state.lock:
        if state.wake_thread and state.wake_thread.is_alive():
            state.status_text = "Wake listener already running"
            return
        state.stop_event.clear()
        state.status_text = "Starting wake listener"
        state.wake_thread = threading.Thread(target=_wake_loop, args=(state,), daemon=True)
        state.wake_thread.start()


def stop_wake_listener(state: WebState):
    with state.lock:
        state.stop_event.set()
        state.status_text = "Stopping wake listener"
        thread = state.wake_thread
    if thread and thread.is_alive():
        thread.join(timeout=2)
    with state.lock:
        state.status_text = "Stopped"


def run_web_app(session: Optional[RohaSession] = None, host: str = "0.0.0.0", port: Optional[int] = None):
    import subprocess
    session = session or RohaSession()
    state = WebState(session=session)
    
    ports_to_try = [port] if port else [int(os.getenv("ROHA_WEB_PORT", "8000")), 8080, 5000, 7000]
    server = None
    selected_port = None

    for p in ports_to_try:
        if not p:
            continue
        try:
            server = RohaHTTPServer((host, p), RohaWebHandler, state)
            selected_port = p
            break
        except OSError:
            continue

    if server is None:
        server = RohaHTTPServer((host, 0), RohaWebHandler, state)
        selected_port = server.server_address[1]

    url = f"http://127.0.0.1:{selected_port}"
    logging.info("Starting Roha web app at %s", url)
    
    # Reliably launch default browser on Windows and other OSes
    try:
        if hasattr(os, "startfile"):
            os.startfile(url)
        elif os.name == "nt":
            subprocess.Popen(f'cmd /c start "" "{url}"', shell=True)
        else:
            webbrowser.open(url)
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            logging.warning("Failed to open browser automatically")


    try:
        print("=" * 60)
        print(f" ROHA ODYSSEUS-STYLE WORKSPACE READY")
        print(f" Running on: {url}")
        print(f" Also accessible at: http://localhost:{selected_port}")
        print(" Opening in your default web browser...")
        print(" Press Ctrl+C in terminal to stop the web server.")
        print("=" * 60)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
    except Exception as e:
        import traceback
        logging.error("Exception in serve_forever:")
        traceback.print_exc()
    finally:
        stop_wake_listener(state)
        # Avoid deadlock by not calling shutdown from the same thread running the loop
        try:
            server.server_close()
        except Exception:
            pass
        session.close()

