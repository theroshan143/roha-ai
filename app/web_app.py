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
from app.wake_detector import WAKE_WORDS, wait_for_wake_word


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Roha</title>
  <style>
    :root {
      --bg: #f4efe6;
      --panel: rgba(255, 255, 255, 0.78);
      --panel-strong: #fffaf2;
      --ink: #1d1f23;
      --muted: #5f6671;
      --accent: #1f7a6b;
      --accent-2: #c85c3d;
      --border: rgba(29, 31, 35, 0.1);
      --shadow: 0 24px 70px rgba(44, 38, 21, 0.16);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(31, 122, 107, 0.18), transparent 35%),
        radial-gradient(circle at right top, rgba(200, 92, 61, 0.14), transparent 28%),
        linear-gradient(135deg, #f8f2e8 0%, #efe7d8 48%, #e9ded0 100%);
    }

    .shell {
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }

    .hero {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: end;
      padding: 24px 0 18px;
    }

    .brand h1 {
      margin: 0;
      font-size: clamp(2.5rem, 6vw, 4.6rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
      font-family: Georgia, "Times New Roman", serif;
    }

    .brand p {
      max-width: 60ch;
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 1rem;
    }

    .status-pill {
      min-width: 230px;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.65);
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
    }

    .status-pill .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.12em; }
    .status-pill .value { margin-top: 6px; font-size: 1.05rem; font-weight: 700; }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.8fr);
      gap: 20px;
      align-items: start;
    }

    .panel {
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border);
      border-radius: 26px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .chat-panel { min-height: 72vh; display: flex; flex-direction: column; }
    .chat-log {
      flex: 1;
      padding: 18px;
      overflow-y: auto;
      display: grid;
      gap: 14px;
    }

    .bubble {
      max-width: min(82%, 720px);
      padding: 14px 16px;
      border-radius: 18px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
      border: 1px solid rgba(29, 31, 35, 0.08);
      animation: rise 180ms ease-out;
    }

    .bubble.user { margin-left: auto; background: #1d1f23; color: #f7f5ef; border-bottom-right-radius: 6px; }
    .bubble.roha { margin-right: auto; background: #fffaf1; border-bottom-left-radius: 6px; }
    .bubble.meta { margin: 0 auto; background: rgba(31, 122, 107, 0.08); color: var(--accent); font-size: 0.92rem; }

    .composer {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 16px;
      border-top: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.5);
    }

    .composer input {
      width: 100%;
      border: 1px solid rgba(29, 31, 35, 0.12);
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      outline: none;
      background: rgba(255, 255, 255, 0.92);
    }

    .composer button, .controls button {
      border: 0;
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform 140ms ease, opacity 140ms ease, background 140ms ease;
    }

    .composer button { background: var(--accent); color: white; }
    .controls button { width: 100%; margin-top: 10px; }
    .primary { background: var(--accent); color: white; }
    .secondary { background: #f2eadc; color: var(--ink); }
    .danger { background: #b34a37; color: white; }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

    .side {
      display: grid;
      gap: 20px;
    }

    .card {
      padding: 18px;
      border-radius: 26px;
      background: var(--panel-strong);
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
    }

    .card h2 { margin: 0 0 10px; font-family: Georgia, "Times New Roman", serif; font-size: 1.5rem; }
    .kv { display: grid; gap: 12px; }
    .kv .row { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid rgba(29,31,35,0.08); padding-bottom: 10px; }
    .kv .row:last-child { border-bottom: 0; padding-bottom: 0; }
    .key { color: var(--muted); }
    .value { font-weight: 700; text-align: right; }

    .hint {
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.5;
    }

    @keyframes rise {
      from { transform: translateY(8px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    @media (max-width: 920px) {
      .hero, .layout { grid-template-columns: 1fr; display: grid; }
      .status-pill { min-width: 0; }
      .chat-panel { min-height: 62vh; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="brand">
        <h1>Roha</h1>
        <p>A local browser console for chatting with Roha and starting the server-side wake-word listener. Keep the app open and Roha stays within reach.</p>
      </div>
      <div class="status-pill">
        <div class="label">Live State</div>
        <div class="value" id="statusText">Idle</div>
      </div>
    </section>

    <section class="layout">
      <div class="panel chat-panel">
        <div class="chat-log" id="chatLog"></div>
        <form class="composer" id="composer">
          <input id="messageInput" autocomplete="off" placeholder="Ask Roha something or type 'exit'..." />
          <button type="submit">Send</button>
        </form>
      </div>

      <div class="side">
        <div class="card">
          <h2>Controls</h2>
          <div class="controls">
            <button class="primary" id="startWake">Start Wake Listening</button>
            <button class="secondary" id="stopWake">Stop Wake Listening</button>
            <button class="primary" id="startVoice">Start Voice Conversation</button>
            <button class="secondary" id="stopVoice">Stop Voice Conversation</button>
            <button class="secondary" id="resetChat">Reset Chat</button>
            <button class="danger" id="refreshNow">Refresh State</button>
          </div>
          <div class="hint">Wake listening uses the machine microphone. Voice conversation uses the browser microphone and browser speech output for a fuller two-way flow.</div>
        </div>

        <div class="card">
          <h2>Details</h2>
          <div class="kv">
            <div class="row"><div class="key">Wake word</div><div class="value">Roha</div></div>
            <div class="row"><div class="key">Last heard</div><div class="value" id="lastHeard">-</div></div>
            <div class="row"><div class="key">Last reply</div><div class="value" id="lastReply">-</div></div>
            <div class="row"><div class="key">Model</div><div class="value" id="modelState">-</div></div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <script>
    const chatLog = document.getElementById('chatLog');
    const statusText = document.getElementById('statusText');
    const lastHeard = document.getElementById('lastHeard');
    const lastReply = document.getElementById('lastReply');
    const modelState = document.getElementById('modelState');
    const composer = document.getElementById('composer');
    const messageInput = document.getElementById('messageInput');
    const startVoiceButton = document.getElementById('startVoice');
    const stopVoiceButton = document.getElementById('stopVoice');

    let voiceConversationActive = false;
    let currentRecordingStop = null;

    function addBubble(role, text) {
      const bubble = document.createElement('div');
      bubble.className = `bubble ${role}`;
      bubble.textContent = text;
      chatLog.appendChild(bubble);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function renderMessages(messages) {
      chatLog.innerHTML = '';
      messages.forEach((message) => {
        if (message.role === 'system') {
          return;
        }
        addBubble(message.role === 'assistant' ? 'roha' : 'user', message.content || '');
      });
      if (!chatLog.children.length) {
        addBubble('meta', 'Roha is waiting. Start wake listening or type a message.');
      }
    }

    function setStatus(text) {
      statusText.textContent = text;
    }

    function speakInBrowser(text) {
      if (!text || !('speechSynthesis' in window)) {
        return Promise.resolve();
      }
      return new Promise((resolve) => {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      });
    }

    async function recordUtterance(durationMs = 5000) {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone access is not supported in this browser');
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      let stopped = false;

      const cleanup = async () => {
        try { stream.getTracks().forEach((track) => track.stop()); } catch (error) { console.warn(error); }
      };

      const finish = async () => {
        if (stopped) return null;
        stopped = true;
        currentRecordingStop = null;
        await cleanup();
        return new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      };

      currentRecordingStop = async () => {
        try {
          recorder.stop();
        } catch (error) {
          console.warn('Stopping recorder failed', error);
        }
      };

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      const recorded = new Promise((resolve, reject) => {
        recorder.onerror = (event) => reject(event.error || new Error('Recorder error'));
        recorder.onstop = async () => {
          try {
            const blob = await finish();
            resolve(blob);
          } catch (error) {
            reject(error);
          }
        };
      });

      setStatus('Recording');
      recorder.start();
      const timeoutId = window.setTimeout(() => {
        try {
          recorder.stop();
        } catch (error) {
          console.warn('Auto-stop recorder failed', error);
        }
        window.clearTimeout(timeoutId);
      }, durationMs);

      return recorded;
    }

    async function postVoiceAudio(blob) {
      const response = await fetch('/api/voice/chat', {
        method: 'POST',
        headers: { 'Content-Type': blob.type || 'audio/webm' },
        body: blob,
      });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      return await response.json();
    }

    async function sendMessage(message, speak = false) {
      const result = await api('/api/chat', { message, speak });
      addBubble('roha', result.reply);
      lastReply.textContent = result.reply || '-';
      if (speak) {
        speakInBrowser(result.reply);
      }
      return result.reply;
    }

    function stopVoiceConversation() {
      voiceConversationActive = false;
      if (currentRecordingStop) {
        try {
          currentRecordingStop();
        } catch (error) {
          console.warn('Stopping recording failed', error);
        }
      }
      setStatus('Voice conversation stopped');
    }

    function startVoiceConversation() {
      voiceConversationActive = true;
      setStatus('Requesting microphone');
      runVoiceConversation().catch((error) => {
        console.error('Voice conversation failed to start', error);
        setStatus('Voice conversation failed');
      });
    }

    async function runVoiceConversation() {
      while (voiceConversationActive) {
        try {
          setStatus('Listening');
          const blob = await recordUtterance(7000);
          if (!voiceConversationActive) {
            break;
          }

          setStatus('Thinking');
          const result = await postVoiceAudio(blob);
          const transcript = (result.transcript || '').trim();
          const reply = (result.reply || '').trim();

          if (transcript) {
            lastHeard.textContent = transcript;
            addBubble('user', transcript);
          }

          if (reply) {
            lastReply.textContent = reply;
            addBubble('roha', reply);
            await speakInBrowser(reply);
          }

          setStatus('Listening');
        } catch (error) {
          console.error('Voice conversation failed', error);
          setStatus('Voice conversation failed');
          break;
        }
      }

      voiceConversationActive = false;
      setStatus('Voice conversation stopped');
    }

    async function api(path, body) {
      try {
        const response = await fetch(path, {
          method: body ? 'POST' : 'GET',
          headers: body ? { 'Content-Type': 'application/json' } : {},
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        return await response.json();
      } catch (error) {
        setStatus('Backend unavailable');
        throw error;
      }
    }

    async function refreshState() {
      try {
        const state = await api('/api/state');
        if (!voiceConversationActive) {
          setStatus(state.status_text);
        }
        lastHeard.textContent = state.last_heard || '-';
        lastReply.textContent = state.last_assistant || '-';
        modelState.textContent = state.model || '-';
        renderMessages(state.messages || []);
      } catch (error) {
        console.warn('Refresh failed', error);
      }
    }

    composer.addEventListener('submit', async (event) => {
      event.preventDefault();
      const message = messageInput.value.trim();
      if (!message) return;
      messageInput.value = '';
      addBubble('user', message);
      try {
        await sendMessage(message, false);
        await refreshState();
      } catch (error) {
        console.error(error);
      }
    });

    document.getElementById('startWake').addEventListener('click', async () => {
      await api('/api/wake/start', {});
      await refreshState();
    });

    document.getElementById('stopWake').addEventListener('click', async () => {
      await api('/api/wake/stop', {});
      await refreshState();
    });

    startVoiceButton.addEventListener('click', async () => {
      startVoiceConversation();
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      await refreshState();
    });

    stopVoiceButton.addEventListener('click', async () => {
      stopVoiceConversation();
      await refreshState();
    });

    document.getElementById('resetChat').addEventListener('click', async () => {
      await api('/api/reset', {});
      await refreshState();
    });

    document.getElementById('refreshNow').addEventListener('click', refreshState);

    setInterval(refreshState, 2000);
    refreshState();
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
                state.status_text = "Chat replied"
                state.last_error = ""
            self._send_json({"reply": reply})
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
            state.status_text = "Voice replied" if transcript else "Listening for wake word"
            state.last_error = ""
          self._send_json({"transcript": transcript, "reply": reply})
          return

        if self.path == "/api/reset":
            state.session.reset()
            with state.lock:
                state.status_text = "Chat reset"
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
        print(f"Roha web app running at {url}")
        print("Press Ctrl+C to stop the web server.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
    finally:
        stop_wake_listener(state)
        server.shutdown()
        server.server_close()
        session.close()
