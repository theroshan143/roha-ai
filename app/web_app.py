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
  <title>Roha — Personal AI Agent</title>
  <style>
    :root {
      --bg-gradient: radial-gradient(circle at 15% 15%, #1e1b4b 0%, #0f172a 40%, #090d16 100%);
      --panel-bg: rgba(15, 23, 42, 0.72);
      --panel-solid: #0f172a;
      --panel-border: rgba(255, 255, 255, 0.08);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-cyan: #38bdf8;
      --accent-purple: #a855f7;
      --accent-emerald: #10b981;
      --user-bg: #1e293b;
      --roha-bg: #111827;
      --shadow-glow: 0 20px 50px rgba(0, 0, 0, 0.6);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg-gradient);
      overflow-x: hidden;
    }

    .container {
      max-width: 1280px;
      margin: 0 auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 20px;
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 20px;
      margin-bottom: 16px;
      box-shadow: var(--shadow-glow);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .logo-orb {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      box-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 1.2rem;
      color: white;
    }

    .brand-text h1 {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #38bdf8, #c084fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-text p {
      margin: 2px 0 0;
      font-size: 0.82rem;
      color: var(--text-muted);
    }

    .header-badges {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .badge {
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.82rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--panel-border);
    }

    .badge-verified { background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }
    .badge-guest { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border-color: rgba(245, 158, 11, 0.3); }
    .badge-status { background: rgba(56, 189, 248, 0.12); color: var(--accent-cyan); }

    .main-grid {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 16px;
      flex: 1;
      min-height: 0;
    }

    .chat-panel {
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 24px;
      display: flex;
      flex-direction: column;
      box-shadow: var(--shadow-glow);
      overflow: hidden;
    }

    .chat-log {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .bubble {
      max-width: 80%;
      padding: 14px 18px;
      border-radius: 20px;
      line-height: 1.6;
      font-size: 0.95rem;
      white-space: pre-wrap;
      word-break: break-word;
      animation: fadeIn 200ms ease-out;
      border: 1px solid var(--panel-border);
    }

    .bubble.user {
      align-self: flex-end;
      background: var(--user-bg);
      color: #f8fafc;
      border-bottom-right-radius: 4px;
    }

    .bubble.roha {
      align-self: flex-start;
      background: var(--roha-bg);
      color: #f1f5f9;
      border-bottom-left-radius: 4px;
      border-left: 3px solid var(--accent-cyan);
    }

    .bubble.meta {
      align-self: center;
      background: rgba(56, 189, 248, 0.1);
      color: var(--accent-cyan);
      font-size: 0.85rem;
      border: 1px dashed rgba(56, 189, 248, 0.3);
    }

    .composer {
      padding: 16px;
      background: rgba(15, 23, 42, 0.85);
      border-top: 1px solid var(--panel-border);
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .composer input {
      flex: 1;
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      padding: 14px 18px;
      color: white;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 150ms;
    }

    .composer input:focus {
      border-color: var(--accent-cyan);
    }

    .btn {
      padding: 12px 20px;
      border-radius: 16px;
      font-weight: 700;
      font-size: 0.9rem;
      border: none;
      cursor: pointer;
      transition: all 150ms ease;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .btn-primary { background: linear-gradient(135deg, #0284c7, #0369a1); color: white; }
    .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4); }

    .btn-accent { background: linear-gradient(135deg, var(--accent-purple), #7e22ce); color: white; }
    .btn-accent:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(168, 85, 247, 0.4); }

    .btn-secondary { background: #1e293b; color: var(--text-main); border: 1px solid var(--panel-border); }
    .btn-secondary:hover { background: #334155; }

    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
    }

    .card {
      background: var(--panel-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--panel-border);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow-glow);
    }

    .card h3 {
      margin: 0 0 14px;
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--accent-cyan);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .kv-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-size: 0.88rem;
    }

    .kv-row {
      display: flex;
      justify-content: space-between;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .kv-key { color: var(--text-muted); }
    .kv-val { font-weight: 600; }

    .tools-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .tool-chip {
      padding: 8px 10px;
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      font-size: 0.8rem;
      font-weight: 600;
      color: #7dd3fc;
      text-align: center;
    }

    .auth-box {
      display: flex;
      gap: 8px;
      margin-top: 10px;
    }

    .auth-box input {
      flex: 1;
      background: #1e293b;
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 8px 12px;
      color: white;
      font-size: 0.88rem;
      outline: none;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 900px) {
      .main-grid { grid-template-columns: 1fr; }
      .sidebar { display: none; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <div class="logo-orb">R</div>
        <div class="brand-text">
          <h1>Roha Agent</h1>
          <p>Local Autonomous Assistant</p>
        </div>
      </div>
      <div class="header-badges">
        <div class="badge badge-status" id="statusBadge">State: Idle</div>
        <div class="badge badge-guest" id="authBadge">🔒 Guest Mode</div>
      </div>
    </header>

    <div class="main-grid">
      <div class="chat-panel">
        <div class="chat-log" id="chatLog"></div>
        <form class="composer" id="composer">
          <input id="messageInput" autocomplete="off" placeholder="Ask Roha anything or command tools..." />
          <button type="button" class="btn btn-accent" id="micBtn" title="Hold/Click to speak">🎤 Voice</button>
          <button type="submit" class="btn btn-primary">Send</button>
        </form>
      </div>

      <div class="sidebar">
        <div class="card">
          <h3>🔐 Creator Security</h3>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">Security Status</span><span class="kv-val" id="secStatus">Guest</span></div>
            <div class="kv-row"><span class="kv-key">Creator</span><span class="kv-val">Roshan Kumar</span></div>
          </div>
          <div class="auth-box">
            <input type="password" id="pinInput" placeholder="Enter Owner PIN (1430)..." />
            <button class="btn btn-primary" id="authBtn">Unlock</button>
          </div>
        </div>

        <div class="card">
          <h3>🛠️ Active Agent Tools</h3>
          <div class="tools-grid" id="toolsGrid">
            <div class="tool-chip">calculator</div>
            <div class="tool-chip">system_info</div>
            <div class="tool-chip">read_file</div>
            <div class="tool-chip">list_directory</div>
          </div>
        </div>

        <div class="card">
          <h3>⚙️ System Details</h3>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">Model</span><span class="kv-val" id="modelVal">-</span></div>
            <div class="kv-row"><span class="kv-key">ReAct Steps</span><span class="kv-val">Max 5</span></div>
            <div class="kv-row"><span class="kv-key">Memory</span><span class="kv-val">SQLite + RAG</span></div>
          </div>
          <div style="margin-top: 14px; display: flex; gap: 8px;">
            <button class="btn btn-secondary" style="flex:1" id="resetBtn">Reset Session</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const chatLog = document.getElementById('chatLog');
    const statusBadge = document.getElementById('statusBadge');
    const authBadge = document.getElementById('authBadge');
    const secStatus = document.getElementById('secStatus');
    const modelVal = document.getElementById('modelVal');
    const composer = document.getElementById('composer');
    const messageInput = document.getElementById('messageInput');
    const pinInput = document.getElementById('pinInput');
    const authBtn = document.getElementById('authBtn');
    const micBtn = document.getElementById('micBtn');
    const resetBtn = document.getElementById('resetBtn');

    let recording = false;
    let mediaRecorder = null;
    let audioChunks = [];

    function addBubble(role, text) {
      const bubble = document.createElement('div');
      bubble.className = `bubble ${role}`;
      bubble.textContent = text;
      chatLog.appendChild(bubble);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function renderMessages(messages) {
      chatLog.innerHTML = '';
      messages.forEach((msg) => {
        if (msg.role === 'system') return;
        addBubble(msg.role === 'assistant' ? 'roha' : 'user', msg.content || '');
      });
      if (!chatLog.children.length) {
        addBubble('meta', '👋 Welcome to Roha Agent Console! Type a prompt or use Voice to begin.');
      }
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
        statusBadge.textContent = `State: ${state.status_text || 'Idle'}`;
        modelVal.textContent = state.model || 'qwen2.5:3b-instruct';
        
        if (state.is_verified) {
          authBadge.className = 'badge badge-verified';
          authBadge.textContent = '🔓 Verified Creator';
          secStatus.textContent = 'Verified (Roshan Kumar)';
        } else {
          authBadge.className = 'badge badge-guest';
          authBadge.textContent = '🔒 Guest Mode';
          secStatus.textContent = 'Guest / Restricted';
        }

        renderMessages(state.messages || []);
      } catch (err) {
        console.warn('Failed to refresh state', err);
      }
    }

    composer.addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = messageInput.value.trim();
      if (!msg) return;
      messageInput.value = '';
      addBubble('user', msg);
      statusBadge.textContent = 'State: Thinking...';

      try {
        const res = await api('/api/chat', { message: msg });
        addBubble('roha', res.reply || '');
        await refreshState();
      } catch (err) {
        addBubble('meta', 'Error sending message to Roha backend.');
      }
    });

    authBtn.addEventListener('click', async () => {
      const pin = pinInput.value.trim();
      if (!pin) return;
      const res = await api('/api/auth', { pin });
      if (res.ok) {
        pinInput.value = '';
        alert('🔓 Creator Verified successfully!');
      } else {
        alert('❌ Invalid Owner PIN!');
      }
      await refreshState();
    });

    resetBtn.addEventListener('click', async () => {
      await api('/api/reset', {});
      await refreshState();
    });

    micBtn.addEventListener('click', async () => {
      if (!recording) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          audioChunks = [];
          mediaRecorder = new MediaRecorder(stream);
          mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
          mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            statusBadge.textContent = 'State: Transcribing voice...';
            try {
              const res = await fetch('/api/voice/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'audio/webm' },
                body: blob,
              });
              const data = await res.json();
              if (data.transcript) addBubble('user', data.transcript);
              if (data.reply) addBubble('roha', data.reply);
              await refreshState();
            } catch (err) {
              addBubble('meta', 'Voice transcription failed.');
            }
          };
          mediaRecorder.start();
          recording = true;
          micBtn.textContent = '🛑 Stop Mic';
          micBtn.style.background = '#ef4444';
          statusBadge.textContent = 'State: Recording mic...';
        } catch (err) {
          alert('Microphone access denied or unsupported.');
        }
      } else {
        mediaRecorder.stop();
        recording = false;
        micBtn.textContent = '🎤 Voice';
        micBtn.style.background = '';
      }
    });

    refreshState();
    setInterval(refreshState, 3000);
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
    def __init__(self, server_address, RequestHandlerClass, state: WebState):
        super().__init__(server_address, RequestHandlerClass)
        self.state = state


class RohaWebHandler(BaseHTTPRequestHandler):
    def _state(self) -> WebState:
        return self.server.state  # type: ignore[attr-defined]

    def _send_json(self, payload, status: int = 200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/state":
            state = self._state()
            payload = {
                "status_text": state.status_text,
                "last_heard": state.last_heard,
                "last_assistant": state.last_assistant,
                "last_error": state.last_error,
                "is_verified": state.session.is_verified,
                "model": os.getenv("MODEL", "qwen2.5:3b-instruct"),
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
            self._send_json({"reply": reply})
            return

        if self.path == "/api/auth":
            payload = self._read_json()
            pin = str(payload.get("pin") or "")
            ok = state.session.authenticate(pin)
            self._send_json({"ok": ok})
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
            self._send_json({"transcript": transcript, "reply": reply})
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


def run_web_app(session: Optional[RohaSession] = None, host: str = "127.0.0.1", port: Optional[int] = None):
    session = session or RohaSession()
    state = WebState(session=session)
    server = RohaHTTPServer((host, port or int(os.getenv("ROHA_WEB_PORT", "8000"))), RohaWebHandler, state)
    url = f"http://{host}:{server.server_address[1]}"
    logging.info("Starting Roha web app at %s", url)
    try:
        webbrowser.open(url)
    except Exception:
        logging.warning("Failed to open browser automatically")

    try:
        print("=" * 60)
        print(f" 🚀 ROHA AGENT VISUAL CONSOLE READY")
        print(f" 🌐 Running on: {url}")
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
