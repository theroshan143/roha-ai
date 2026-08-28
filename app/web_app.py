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

    /* Left App Sidebar (Odysseus Workspace Nav) */
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
      border-color: var(--border-strong);
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

    /* Passphrase Gate Modal Overlay (Black & White) */
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
  <div class="gate-overlay" id="gateOverlay">
    <div class="gate-modal">
      <h2>ROHA // AUTHENTICATION GATE</h2>
      <p>Enter owner passphrase / PIN (default: <strong>1430</strong>) to unlock creator privileges, workspace file tools, and full RAG memory.</p>
      <form id="gateForm" style="display: flex; flex-direction: column; gap: 12px;">
        <input type="password" id="gatePinInput" placeholder="ENTER PASSPHRASE / PIN..." autofocus />
        <div class="gate-btn-group">
          <button type="submit" class="btn-mono primary" style="flex: 1; padding: 10px;">UNLOCK CREATOR ACCESS</button>
          <button type="button" class="btn-mono" id="gateGuestBtn" style="padding: 10px;">GUEST MODE</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Left Sidebar (Odysseus Style) -->
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
        <span class="header-badge" id="headerModel">qwen2.5:3b-instruct</span>
        <span class="header-badge" id="headerLatency">0.00s</span>
        <span class="header-badge" id="headerState">IDLE</span>
      </div>
      <div class="header-right">
        <span class="header-badge highlight" id="headerAuth" style="cursor: pointer;" title="Click to open Passphrase Gate">GUEST MODE</span>
        <button class="btn-mono" id="clearBtn">CLEAR</button>
        <button class="btn-mono" id="micToggleBtn">MIC</button>
      </div>
    </header>

    <!-- Workspace Content (Chat + Inspector) -->
    <div class="workspace-content">
      
      <!-- Chat Feed & Composer -->
      <section class="chat-section">
        <div class="chat-feed" id="chatFeed">
          <div class="message-card system-note">
            <div class="message-header">SYSTEM // INITIALIZATION</div>
            <div class="message-body">Roha AI Agent online. Type your instruction or command below. Local RAG memory active.</div>
          </div>
        </div>

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
              <span class="tool-chip">list_directory</span>
            </div>
          </div>

          <!-- Hardware & System Specs (Odysseus Style) -->
          <div class="inspector-card">
            <div class="inspector-card-title">
              <span>SYSTEM PROFILE</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <div class="stat-row"><span class="stat-label">Model Runtime</span><span class="stat-value" id="statModel">qwen2.5:3b</span></div>
              <div class="stat-row"><span class="stat-label">Inference Latency</span><span class="stat-value" id="statLatency">0.00s</span></div>
              <div class="stat-row"><span class="stat-label">ReAct Step Bound</span><span class="stat-value">5 Steps Max</span></div>
              <div class="stat-row"><span class="stat-label">Memory Backend</span><span class="stat-value">SQLite + Vector</span></div>
              <div class="stat-row"><span class="stat-label">Creator Auth</span><span class="stat-value" id="statAuth">Unverified</span></div>
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
  </main>

  <script>
    const chatFeed = document.getElementById('chatFeed');
    const promptInput = document.getElementById('promptInput');
    const composerForm = document.getElementById('composerForm');
    const headerModel = document.getElementById('headerModel');
    const headerLatency = document.getElementById('headerLatency');
    const headerState = document.getElementById('headerState');
    const headerAuth = document.getElementById('headerAuth');
    const statModel = document.getElementById('statModel');
    const statLatency = document.getElementById('statLatency');
    const statAuth = document.getElementById('statAuth');
    const clearBtn = document.getElementById('clearBtn');
    const micToggleBtn = document.getElementById('micToggleBtn');
    const gateOverlay = document.getElementById('gateOverlay');
    const gateForm = document.getElementById('gateForm');
    const gatePinInput = document.getElementById('gatePinInput');
    const gateGuestBtn = document.getElementById('gateGuestBtn');
    const ragContainer = document.getElementById('ragContainer');
    const sqliteContainer = document.getElementById('sqliteContainer');
    const navSecurity = document.getElementById('navSecurity');

    let recording = false;
    let mediaRecorder = null;
    let audioChunks = [];

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
    }

    function renderFeed(messages) {
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
      snippets.forEach(snip => {
        const d = document.createElement('div');
        d.className = 'rag-snippet';
        d.textContent = snip;
        ragContainer.appendChild(d);
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

    async function api(path, body) {
      const res = await fetch(path, {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      return await res.json();
    }

    async function refreshState() {
      try {
        const state = await api('/api/state');
        headerModel.textContent = state.model || 'qwen2.5:3b-instruct';
        statModel.textContent = state.model || 'qwen2.5:3b-instruct';
        headerLatency.textContent = `${state.last_latency || 0.00}s`;
        statLatency.textContent = `${state.last_latency || 0.00}s`;
        headerState.textContent = state.status_text ? state.status_text.toUpperCase() : 'IDLE';

        if (state.is_verified) {
          headerAuth.textContent = 'VERIFIED CREATOR';
          headerAuth.style.borderColor = '#ffffff';
          statAuth.textContent = 'Roshan (Verified)';
          gateOverlay.classList.add('hidden');
        } else {
          headerAuth.textContent = 'GUEST MODE';
          headerAuth.style.borderColor = 'var(--border-subtle)';
          statAuth.textContent = 'Guest (Restricted)';
        }

        renderRagSnippets(state.last_rag_snippets || []);
        renderSqliteMemories(state.sqlite_memories || []);
        renderFeed(state.messages || []);
      } catch (err) {
        console.warn('Refresh state error', err);
      }
    }

    composerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = promptInput.value.trim();
      if (!msg) return;
      promptInput.value = '';
      addMessage('user', msg);
      headerState.textContent = 'THINKING...';

      try {
        const res = await api('/api/chat', { message: msg });
        addMessage('assistant', res.reply || '', res.tools_executed || []);
        headerLatency.textContent = `${res.latency || 0.00}s`;
        statLatency.textContent = `${res.latency || 0.00}s`;
        renderRagSnippets(res.rag_snippets || []);
        await refreshState();
      } catch (err) {
        addMessage('system-note', 'Error connecting to Roha local server.');
      }
    });

    gateForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pin = gatePinInput.value.trim();
      if (!pin) return;
      const res = await api('/api/auth', { pin });
      if (res.ok) {
        gateOverlay.classList.add('hidden');
        addMessage('system-note', '🔓 Creator passphrase verified. Workspace tools and RAG memory unlocked.');
      } else {
        alert('❌ Invalid Passphrase / PIN.');
      }
      await refreshState();
    });

    gateGuestBtn.addEventListener('click', () => {
      gateOverlay.classList.add('hidden');
      addMessage('system-note', '🔒 Operating in Guest mode. File inspection tools restricted.');
    });

    headerAuth.addEventListener('click', () => {
      gateOverlay.classList.remove('hidden');
    });

    navSecurity.addEventListener('click', () => {
      gateOverlay.classList.remove('hidden');
    });

    clearBtn.addEventListener('click', async () => {
      await api('/api/reset', {});
      await refreshState();
    });

    micToggleBtn.addEventListener('click', async () => {
      if (!recording) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          audioChunks = [];
          mediaRecorder = new MediaRecorder(stream);
          mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
          mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            headerState.textContent = 'TRANSCRIBING...';
            try {
              const res = await fetch('/api/voice/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'audio/webm' },
                body: blob,
              });
              const data = await res.json();
              if (data.transcript) addMessage('user', data.transcript);
              if (data.reply) addMessage('assistant', data.reply, data.tools_executed || []);
              await refreshState();
            } catch (err) {
              addMessage('system-note', 'Voice transcription failed.');
            }
          };
          mediaRecorder.start();
          recording = true;
          micToggleBtn.textContent = 'STOP';
          micToggleBtn.style.background = '#ffffff';
          micToggleBtn.style.color = '#000000';
          headerState.textContent = 'RECORDING...';
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

    // Check verification status on load
    refreshState().then(() => {
      api('/api/state').then(st => {
        if (!st.is_verified) {
          gateOverlay.classList.remove('hidden');
        }
      });
    });

    setInterval(refreshState, 4000);
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

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        self.close_connection = True
        parsed = urlparse(self.path)

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
            return



        if parsed.path == "/api/state":
            state = self._state()
            sqlite_memories = []
            try:
                sqlite_memories = state.session.memory_manager.get_memories(limit=25)
            except Exception:
                pass

            payload = {
                "status_text": state.status_text,
                "last_heard": state.last_heard,
                "last_assistant": state.last_assistant,
                "last_error": state.last_error,
                "is_verified": state.session.is_verified,
                "model": os.getenv("MODEL", "qwen2.5:3b-instruct"),
                "last_latency": state.session.last_latency,
                "last_rag_snippets": state.session.last_rag_snippets,
                "last_tools_executed": state.session.last_tools_executed,
                "sqlite_memories": sqlite_memories,
                "messages": state.session.snapshot_messages(),
            }
            self._send_json(payload)
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        state = self._state()

        if self.path == "/api/chat":
            payload = self._read_json()
            message = str(payload.get("message") or "")
            speak = bool(payload.get("speak", False)) and bool(state.session.tts)
            reply = state.session.process_user_input(message, speak=speak)
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

        if self.path == "/api/auth":
            payload = self._read_json()
            pin = str(payload.get("pin") or "")
            ok = state.session.authenticate(pin)
            self._send_json({"ok": ok, "is_verified": state.session.is_verified})
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
                reply = state.session.process_user_input(transcript, speak=False) if transcript else ""
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
        print(f" 🚀 ROHA ODYSSEUS-STYLE WORKSPACE READY")
        print(f" 🌐 Running on: {url}")
        print(f" 🌐 Also accessible at: http://localhost:{selected_port}")
        print(" Opening in your default web browser...")
        print(" Press Ctrl+C in terminal to stop the web server.")
        print("=" * 60)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
    finally:
        stop_wake_listener(state)
        server.shutdown()
        server.server_close()
        session.close()

