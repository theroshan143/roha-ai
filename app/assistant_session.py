import concurrent.futures
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from app.chat import chat_with_roha, check_provider_health
from app.config import DB_PATH, HISTORY_LIMIT, OWNER_NAME, OWNER_PIN, AUTO_VERIFY_LOCAL_OS, MODEL_TIMEOUT, PROVIDERS, DEFAULT_PROVIDER
from app.memory import MemoryManager
from app.prompts import load_system_prompt
from app.tts import create_default_tts
from app.types import Message
from tools.builtin import (
    CalculatorTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    DeleteFileTool,
    ExecuteCommandTool,
    WebSearchTool,
    FetchUrlTool,
    GitHubTool,
    SystemInfoTool,
    ListDirectoryTool,
)
from tools.registry import ToolRegistry

# Shared persistent thread pool for model execution timeouts
_MODEL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def trimmed_messages(messages: List[Message], history_limit: int = HISTORY_LIMIT) -> List[Message]:
    """Return a trimmed copy of messages keeping the system prompt and last N messages."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]
    trimmed: List[Message] = (system[:1] if system else []) + other[-history_limit:]
    return trimmed


def _call_model_with_timeout(messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, timeout: int = MODEL_TIMEOUT, model: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
    """Call the chat model with timeout using a persistent thread pool."""
    fut = _MODEL_EXECUTOR.submit(chat_with_roha, messages, tools, model, provider)

    try:
        res = fut.result(timeout=timeout)
        if isinstance(res, str):
            return {"content": res, "tool_calls": []}
        return res
    except concurrent.futures.TimeoutError:
        fut.cancel()
        raise TimeoutError("Model request timed out")


class RohaSession:
    """Shared assistant agent runtime for terminal and web UI entrypoints."""

    def __init__(self):
        self.system_prompt = load_system_prompt()
        self.memory_manager = MemoryManager(DB_PATH)
        
        # Authentication state
        self.is_verified: bool = AUTO_VERIFY_LOCAL_OS

        # --- Hybrid Backend Provider State ---
        self.active_provider: str = DEFAULT_PROVIDER
        provider_cfg = PROVIDERS.get(self.active_provider, PROVIDERS["local"])
        self.model: str = provider_cfg.get("model", os.getenv("MODEL", "qwen2.5:3b-instruct"))

        # Diagnostics & RAG metrics
        self.last_latency: float = 0.0
        self.last_rag_snippets: List[str] = []
        self.last_tools_executed: List[str] = []

        # ReAct loop state & step visualizer
        self.current_execution_steps: List[Dict[str, Any]] = []
        self.pending_tool_calls: List[Dict[str, Any]] = []
        self.scratchpad: List[Message] = []
        self.step_index: int = 0
        self.max_steps: int = 5
        self.speak: bool = False
        self.suspend_for_hitl: bool = False
        self.t_start: float = 0.0

        # Hydrate session context from DB
        recent_history = self.memory_manager.load_recent_history(limit=HISTORY_LIMIT)
        self.messages: List[Message] = [{"role": "system", "content": self.system_prompt}] + recent_history

        # Initialize Tool Registry with Phase 3 Action & Research Tools
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(CalculatorTool())
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WriteFileTool())
        self.tool_registry.register(EditFileTool())
        self.tool_registry.register(DeleteFileTool())
        self.tool_registry.register(ExecuteCommandTool())
        self.tool_registry.register(WebSearchTool())
        self.tool_registry.register(FetchUrlTool())
        self.tool_registry.register(GitHubTool())
        self.tool_registry.register(SystemInfoTool())
        self.tool_registry.register(ListDirectoryTool())

        from app.circuit_breaker import CircuitBreaker
        self.cb = CircuitBreaker()
        self.tts = create_default_tts()
        self._lock = threading.Lock()
        self.execution_lock = threading.Lock()

    def authenticate(self, pin: str) -> bool:
        """Authenticate creator with PIN."""
        with self._lock:
            if (pin or "").strip() == str(OWNER_PIN).strip():
                self.is_verified = True
                return True
            return False

    def lock_session(self) -> None:
        """Lock session into guest mode."""
        with self._lock:
            self.is_verified = False

    # --- Hybrid Backend Provider Switching ---
    @property
    def provider_config(self) -> Dict[str, Any]:
        """Return the config dict for the currently active provider."""
        return PROVIDERS.get(self.active_provider, PROVIDERS["local"])

    def switch_provider(self, provider_key: str) -> Dict[str, Any]:
        """Switch the active LLM backend provider.

        Args:
            provider_key: 'local' or 'cloud'.

        Returns:
            Dict with status, provider name, and active model.
        """
        if provider_key not in PROVIDERS:
            return {"ok": False, "error": f"Unknown provider '{provider_key}'. Valid: {list(PROVIDERS.keys())}"}

        cfg = PROVIDERS[provider_key]

        # Validate cloud API key before switching
        if provider_key == "cloud" and not cfg.get("api_key"):
            return {"ok": False, "error": "GROQ_API_KEY is not set. Add it to your .env file."}

        with self._lock:
            self.active_provider = provider_key
            self.model = cfg["model"]

        logging.info("Switched provider to '%s' (model: %s)", provider_key, self.model)
        return {
            "ok": True,
            "provider": provider_key,
            "provider_name": cfg["name"],
            "model": self.model,
        }

    def get_backend_status(self) -> Dict[str, Any]:
        """Return current backend status info."""
        cfg = self.provider_config
        return {
            "provider": self.active_provider,
            "provider_name": cfg.get("name", self.active_provider),
            "model": self.model,
            "base_url": cfg.get("base_url", ""),
        }

    def reset(self) -> None:
        with self._lock:
            self.messages = [{"role": "system", "content": self.system_prompt}]

    def snapshot_messages(self) -> List[Message]:
        with self._lock:
            return list(self.messages)

    def _assistant_count(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "assistant")

    def update_tts_settings(self, rate: Optional[int] = None, volume: Optional[float] = None, voice_id: Optional[str] = None):
        """Update voice settings on active TTS manager if enabled."""
        if self.tts:
            self.tts.update_settings(rate=rate, volume=volume, voice_id=voice_id)

    def _is_critical_tool(self, name: str) -> bool:
        """Define which tools require human-in-the-loop (HITL) approval when verified."""
        return name in ("write_file", "edit_file", "delete_file", "execute_command")

    def _any_critical(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """Check if any tool call requires verification."""
        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "")
            if self._is_critical_tool(name):
                return True
        return False

    def _handle_backend_command(self, normalized: str) -> Optional[str]:
        """Intercept /online, /offline, /backend commands. Returns response or None."""
        lower = normalized.lower()

        if lower == "/online":
            result = self.switch_provider("cloud")
            if result["ok"]:
                return f"☁️  Switched to CLOUD mode — {result['provider_name']} ({result['model']})"
            return f"❌ {result['error']}"

        if lower == "/offline":
            result = self.switch_provider("local")
            if result["ok"]:
                return f"🏠 Switched to LOCAL mode — {result['provider_name']} ({result['model']})"
            return f"❌ {result['error']}"

        if lower == "/backend":
            status = self.get_backend_status()
            mode_emoji = "☁️" if status["provider"] == "cloud" else "🏠"
            return (
                f"{mode_emoji} Backend: {status['provider_name']}\n"
                f"   Model: {status['model']}\n"
                f"   Endpoint: {status['base_url']}"
            )

        return None

    def process_user_input(self, user_input: str, speak: bool = False, suspend_for_hitl: bool = False) -> str:
        import time
        normalized = (user_input or "").strip()
        if not normalized:
            return ""

        if normalized.lower() == "exit":
            return "Goodbye!"

        # Intercept backend switching commands before model call
        backend_response = self._handle_backend_command(normalized)
        if backend_response is not None:
            return backend_response

        self.t_start = time.time()
        self.speak = speak
        self.suspend_for_hitl = suspend_for_hitl

        with self.execution_lock:
            with self._lock:
                self.messages.append({"role": "user", "content": normalized})
                try:
                    self.memory_manager.add_message("user", normalized)
                except Exception:
                    logging.exception("Failed to persist user message")

                # RAG Memory context retrieval
                relevant_snippets = self.memory_manager.get_relevant_memories(normalized, k=3)
                self.last_rag_snippets = list(relevant_snippets)
                
                # Assemble model context
                to_send = trimmed_messages(self.messages, history_limit=HISTORY_LIMIT)
                
                # Inject Authentication Status System Note
                auth_status = f"[AUTHENTICATION STATUS]: VERIFIED CREATOR ({OWNER_NAME}). Full permissions unlocked." if self.is_verified else "[AUTHENTICATION STATUS]: UNVERIFIED GUEST USER. Restrict personal files and personal information."
                to_send.insert(1, {"role": "system", "content": auth_status})

                # Inject Backend Mode System Note
                backend_cfg = self.provider_config
                backend_label = "CLOUD (Groq)" if self.active_provider == "cloud" else "LOCAL"
                backend_note = f"[BACKEND: {backend_label}] Active model: {self.model} via {backend_cfg.get('name', self.active_provider)}"
                to_send.insert(2, {"role": "system", "content": backend_note})

                if relevant_snippets and self.is_verified:
                    memory_context = "\n".join(relevant_snippets)
                    rag_note: Message = {
                        "role": "system",
                        "content": f"[Relevant Memories Retrieved]:\n{memory_context}",
                    }
                    to_send.insert(3, rag_note)

                self.scratchpad = list(to_send)
                self.step_index = 0
                self.max_steps = int(os.getenv("ROHA_MAX_STEPS", "5"))
                self.current_execution_steps = []
                self.pending_tool_calls = []
                self.last_tools_executed = []

            return self.run_react_loop_segment()

    def run_react_loop_segment(self) -> str:
        import time
        timeout_val = int(os.getenv("MODEL_TIMEOUT", str(MODEL_TIMEOUT)))
        if self.is_verified:
            tools_schema = self.tool_registry.get_schemas()
        else:
            # Restrict file editing, reading & terminal execution for guest users
            from tools.builtin import CalculatorTool, SystemInfoTool, WebSearchTool, GitHubTool
            guest_tools = [CalculatorTool(), SystemInfoTool(), WebSearchTool(), GitHubTool()]
            tools_schema = [t.to_ollama_schema() for t in guest_tools]

        is_error = False
        assistant_reply = ""

        try:
            if not self.cb.call_allowed():
                wait_seconds = self.cb.time_until_reset()
                logging.warning("Circuit breaker open; skipping call for %d seconds", wait_seconds)
                assistant_reply = "The model is temporarily unavailable due to repeated errors. Please try again later."
            else:
                while True:
                    with self._lock:
                        current_step = self.step_index
                    if current_step >= self.max_steps:
                        break

                    with self._lock:
                        self.step_index += 1
                        step_num = self.step_index
                        scratchpad_copy = list(self.scratchpad)
                        active_model = self.model
                        active_provider = self.active_provider

                    logging.info("ReAct Loop Step %d/%d [%s]", step_num, self.max_steps, active_provider)
                    response_dict = _call_model_with_timeout(scratchpad_copy, tools=tools_schema, timeout=timeout_val, model=active_model, provider=active_provider)
                    self.cb.record_success()

                    tool_calls = response_dict.get("tool_calls", [])
                    content = response_dict.get("content", "")

                    if tool_calls:
                        thought_text = content or "Analyzing next actions..."
                    else:
                        thought_text = "Generated direct response." if step_num == 1 else "Synthesized final answer."

                    step_record = {
                        "step": step_num,
                        "thought": thought_text,
                        "tool_calls": tool_calls,
                        "status": "completed",
                        "observations": []
                    }

                    if tool_calls:
                        if self.suspend_for_hitl and self._any_critical(tool_calls):
                            step_record["status"] = "pending_approval"
                            with self._lock:
                                self.current_execution_steps.append(step_record)
                                self.pending_tool_calls = tool_calls
                                if content:
                                    self.scratchpad.append({"role": "assistant", "content": content})
                            return "__AWAITING_APPROVAL__"
                        else:
                            step_record["status"] = "executing"

                    with self._lock:
                        self.current_execution_steps.append(step_record)

                    if not tool_calls:
                        assistant_reply = content
                        break

                    if content:
                        with self._lock:
                            self.scratchpad.append({"role": "assistant", "content": content})

                    observations = []
                    for tool_call in tool_calls:
                        fn = tool_call.get("function", {})
                        name = fn.get("name", "")
                        args = fn.get("arguments", {})

                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}

                        result_str = self.tool_registry.execute(name, args)
                        with self._lock:
                            self.last_tools_executed.append(name)
                        observations.append(f"Observation from tool '{name}':\n{result_str}")

                    step_record["observations"] = observations
                    obs_text = "\n\n".join(observations)
                    with self._lock:
                        self.scratchpad.append({
                            "role": "user",
                            "content": f"[Tool Observations]:\n{obs_text}\n\nIf you have sufficient information to answer, provide your final response. Otherwise, call the next tool.",
                        })

                # Fallback synthesis if max_steps reached without final text
                with self._lock:
                    needs_fallback = not assistant_reply and self.step_index >= self.max_steps
                    scratchpad_copy = list(self.scratchpad)
                    active_model = self.model
                    active_provider = self.active_provider

                if needs_fallback:
                    logging.info("ReAct loop completed tool turns; requesting final synthesis.")
                    scratchpad_copy.append({
                        "role": "user",
                        "content": "Please synthesize all observations and findings above to provide your final, complete answer to the user. Do not include execution placeholder markers.",
                    })
                    final_resp = _call_model_with_timeout(scratchpad_copy, tools=None, timeout=timeout_val, model=active_model, provider=active_provider)
                    assistant_reply = final_resp.get("content", "I have completed the operations.")

                if not assistant_reply:
                    assistant_reply = "I completed the requested operations."

        except Exception:
            logging.exception("Model call failed during ReAct loop")
            self.cb.record_failure()
            assistant_reply = "I'm having trouble connecting to the model right now. Please try again later."
            is_error = True

        self.last_latency = round(time.time() - self.t_start, 3)

        with self._lock:
            if not is_error and assistant_reply:
                self.messages.append({"role": "assistant", "content": assistant_reply})
                try:
                    self.memory_manager.add_message("assistant", assistant_reply)
                except Exception:
                    logging.exception("Failed to persist assistant message")
            elif is_error:
                # Rollback user message from in-memory session if model generation failed
                if self.messages and self.messages[-1].get("role") == "user":
                    self.messages.pop()

        try:
            if self._assistant_count() % 20 == 0:
                self.memory_manager.summarize_memory(keep_last=200)
        except Exception:
            logging.exception("Memory summarization failed")

        if self.speak and self.tts:
            try:
                # Prepare concise voice summary for TTS so long markdown isn't read aloud
                import re
                clean = (assistant_reply or "").strip()
                if len(clean) > 250:
                    sentences = re.split(r"(?<=[.!?])\s+", clean)
                    speech = ""
                    for s in sentences:
                        if len(speech) + len(s) + 1 <= 250:
                            speech += (" " + s if speech else s)
                        else:
                            break
                    speech_text = (speech.rstrip() + ". Here is the detailed response on screen.") if speech else clean[:250]
                else:
                    speech_text = clean

                self.tts.speak(speech_text, wait=False)
            except Exception:
                logging.exception("TTS speak failed")

        return assistant_reply

    def resume_react_loop_with_approval(self) -> str:
        """Execute pending critical tools, add observation, and run loop segment."""
        with self.execution_lock:
            with self._lock:
                if not self.pending_tool_calls:
                    return "No pending tools to approve."

                # Update step record from pending_approval to executing
                if self.current_execution_steps:
                    last_step = self.current_execution_steps[-1]
                    if last_step.get("status") == "pending_approval":
                        last_step["status"] = "executing"
                
                pending_calls = list(self.pending_tool_calls)

            observations = []
            for tool_call in pending_calls:
                fn = tool_call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})

                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}

                result_str = self.tool_registry.execute(name, args)
                with self._lock:
                    self.last_tools_executed.append(name)
                observations.append(f"Observation from tool '{name}':\n{result_str}")

            with self._lock:
                if self.current_execution_steps:
                    self.current_execution_steps[-1]["observations"] = observations
                    self.current_execution_steps[-1]["status"] = "completed"

                self.pending_tool_calls = []

                obs_text = "\n\n".join(observations)
                self.scratchpad.append({
                    "role": "user",
                    "content": f"[Tool Observations]:\n{obs_text}\n\nIf you have sufficient information to answer, provide your final response. Otherwise, call the next tool.",
                })

            return self.run_react_loop_segment()

    def resume_react_loop_with_rejection(self) -> str:
        """Reject pending tools and continue running the ReAct loop segment."""
        with self.execution_lock:
            with self._lock:
                if not self.pending_tool_calls:
                    return "No pending tools to reject."

                pending_calls = list(self.pending_tool_calls)

            observations = []
            for tool_call in pending_calls:
                fn = tool_call.get("function", {})
                name = fn.get("name", "")
                observations.append(f"Observation from tool '{name}':\nExecution denied/rejected by the user.")

            with self._lock:
                if self.current_execution_steps:
                    self.current_execution_steps[-1]["observations"] = observations
                    self.current_execution_steps[-1]["status"] = "rejected"

                self.pending_tool_calls = []

                obs_text = "\n\n".join(observations)
                self.scratchpad.append({
                    "role": "user",
                    "content": f"[Tool Observations]:\n{obs_text}\n\nIf you have sufficient information to answer, provide your final response. Otherwise, call the next tool.",
                })

            return self.run_react_loop_segment()

    def close(self) -> None:
        try:
            self.memory_manager.close()
        except Exception:
            logging.exception("Error closing memory manager")
        try:
            if self.tts:
                self.tts.shutdown()
                logging.info("TTS shut down")
        except Exception:
            logging.exception("Error shutting down TTS")

