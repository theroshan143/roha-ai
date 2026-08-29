import concurrent.futures
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from app.chat import chat_with_roha
from app.config import DB_PATH, HISTORY_LIMIT, OWNER_NAME, OWNER_PIN, AUTO_VERIFY_LOCAL_OS, MODEL_TIMEOUT
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


def _call_model_with_timeout(messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None, timeout: int = MODEL_TIMEOUT) -> Dict[str, Any]:
    """Call the chat model with timeout using a persistent thread pool."""
    fut = _MODEL_EXECUTOR.submit(chat_with_roha, messages, tools)

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

        # Diagnostics & RAG metrics
        self.last_latency: float = 0.0
        self.last_rag_snippets: List[str] = []
        self.last_tools_executed: List[str] = []

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

    def reset(self) -> None:
        with self._lock:
            self.messages = [{"role": "system", "content": self.system_prompt}]

    def snapshot_messages(self) -> List[Message]:
        with self._lock:
            return list(self.messages)

    def _assistant_count(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "assistant")

    def process_user_input(self, user_input: str, speak: bool = False) -> str:
        import time
        normalized = (user_input or "").strip()
        if not normalized:
            return ""

        if normalized.lower() == "exit":
            return "Goodbye!"

        t_start = time.time()
        executed_tools: List[str] = []
        is_error: bool = False

        with self._lock:

            self.messages.append({"role": "user", "content": normalized})
            self.memory_manager.add_message("user", normalized)

            # RAG Memory context retrieval
            relevant_snippets = self.memory_manager.get_relevant_memories(normalized, k=3)
            self.last_rag_snippets = list(relevant_snippets)
            
            # Assemble model context
            to_send = trimmed_messages(self.messages, history_limit=HISTORY_LIMIT)
            
            # Inject Authentication Status System Note
            auth_status = f"[AUTHENTICATION STATUS]: VERIFIED CREATOR ({OWNER_NAME}). Full permissions unlocked." if self.is_verified else "[AUTHENTICATION STATUS]: UNVERIFIED GUEST USER. Restrict personal files and personal information."
            to_send.insert(1, {"role": "system", "content": auth_status})

            if relevant_snippets and self.is_verified:
                memory_context = "\n".join(relevant_snippets)
                rag_note: Message = {
                    "role": "system",
                    "content": f"[Relevant Memories Retrieved]:\n{memory_context}",
                }
                to_send.insert(2, rag_note)

            # Tool Gating: Guests get public tools only, Verified Creator gets all tools
            if self.is_verified:
                tools_schema = self.tool_registry.get_schemas()
            else:
                # Restrict file editing, reading & terminal execution for guest users
                guest_tools = [CalculatorTool(), SystemInfoTool(), WebSearchTool(), GitHubTool()]
                tools_schema = [t.to_ollama_schema() for t in guest_tools]


            timeout_val = int(os.getenv("MODEL_TIMEOUT", str(MODEL_TIMEOUT)))
            max_steps = int(os.getenv("ROHA_MAX_STEPS", "5"))


            try:
                if not self.cb.call_allowed():
                    wait_seconds = self.cb.time_until_reset()
                    logging.warning("Circuit breaker open; skipping call for %d seconds", wait_seconds)
                    assistant_reply = "The model is temporarily unavailable due to repeated errors. Please try again later."
                else:
                    try:
                        step = 0
                        assistant_reply = ""
                        scratchpad = list(to_send)

                        while step < max_steps:
                            step += 1
                            logging.info("ReAct Loop Step %d/%d", step, max_steps)
                            response_dict = _call_model_with_timeout(scratchpad, tools=tools_schema, timeout=timeout_val)
                            self.cb.record_success()

                            tool_calls = response_dict.get("tool_calls", [])
                            content = response_dict.get("content", "")

                            if not tool_calls:
                                # Model produced final response without requesting further tools
                                assistant_reply = content
                                break

                            # Model requested tool execution
                            logging.info("[Step %d/%d] Executing %d tool calls requested by model", step, max_steps, len(tool_calls))
                            if content:
                                scratchpad.append({
                                    "role": "assistant",
                                    "content": content,
                                })

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
                                executed_tools.append(name)
                                observations.append(f"Observation from tool '{name}':\n{result_str}")

                            obs_text = "\n\n".join(observations)
                            scratchpad.append({
                                "role": "user",
                                "content": f"[Tool Observations]:\n{obs_text}\n\nIf you have sufficient information to answer, provide your final response. Otherwise, call the next tool.",
                            })

                        # Fallback synthesis if max_steps reached without final text
                        if not assistant_reply:
                            logging.info("ReAct loop completed tool turns; requesting final synthesis.")
                            scratchpad.append({
                                "role": "user",
                                "content": "Please synthesize all observations and findings above to provide your final, complete answer to the user. Do not include execution placeholder markers.",
                            })
                            final_resp = _call_model_with_timeout(scratchpad, tools=None, timeout=timeout_val)
                            assistant_reply = final_resp.get("content", "I have completed the operations.")

                        if not assistant_reply:
                            assistant_reply = "I completed the requested operations."


                    except Exception:
                        logging.exception("Model call failed during ReAct loop")
                        self.cb.record_failure()
                        assistant_reply = "I'm having trouble connecting to the model right now. Please try again later."
                        is_error = True
            except Exception:
                logging.exception("Unexpected model error")
                assistant_reply = "Sorry, something went wrong while generating a response."
                is_error = True

            self.last_latency = round(time.time() - t_start, 3)
            self.last_tools_executed = list(executed_tools)

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

        if speak and self.tts:
            try:
                self.tts.speak(assistant_reply)
                logging.info("TTS status after enqueue: %s", self.tts.status())
            except Exception:
                logging.exception("TTS speak failed")

        return assistant_reply

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

