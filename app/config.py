import os
from pathlib import Path

try:
    # pyrefly: ignore [missing-import]
    from dotenv import load_dotenv
    # Load .env if present (developer can create a .env file)
    load_dotenv()
except Exception:
    # dotenv is optional in some environments (e.g., CI/test)
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# Core directories (can be overridden via env)
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(BASE_DIR / "logs")))
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(BASE_DIR / "prompts")))

# ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

# Model selection via environment variable for safety and flexibility
MODEL = os.getenv("MODEL", "qwen2.5:3b-instruct")

# ---------------------------------------------------------------------------
# Hybrid Backend Provider Registry
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

PROVIDERS = {
    "local": {
        "name": "Local Ollama",
        "base_url": os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1"),
        "model": os.getenv("LOCAL_MODEL", MODEL),
        "api_key": "ollama",  # Ollama ignores the key but openai client requires one
        "timeout": int(os.getenv("LOCAL_TIMEOUT", "120")),
    },
    "cloud": {
        "name": "Groq Cloud",
        "base_url": os.getenv("CLOUD_BASE_URL", "https://api.groq.com/openai/v1"),
        "model": os.getenv("CLOUD_MODEL", "qwen/qwen3.8-27b"),
        "api_key": GROQ_API_KEY,
        "timeout": int(os.getenv("CLOUD_TIMEOUT", "30")),
    },
}

DEFAULT_PROVIDER = os.getenv("ROHA_PROVIDER", "local")

# Paths
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "roha.db"))
LOG_PATH = os.getenv("LOG_PATH", str(LOGS_DIR / "roha.log"))
PROMPT_PATH = os.getenv("PROMPT_PATH", str(PROMPTS_DIR / "system_prompt.txt"))

# Conversation / memory settings
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "12"))

# Speech / audio settings
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "false").lower() in ("1", "true", "yes")
VOICE_STYLE = os.getenv("VOICE_STYLE", "casual").strip()

# Owner Security & Creator Verification Settings
OWNER_NAME = os.getenv("ROHA_OWNER_NAME", "Roshan")
OWNER_PIN = os.getenv("ROHA_OWNER_PIN", "1430")
AUTO_VERIFY_LOCAL_OS = os.getenv("ROHA_AUTO_VERIFY_OS", "true").lower() in ("1", "true", "yes")

# Model execution timeout (seconds)
MODEL_TIMEOUT = int(os.getenv("MODEL_TIMEOUT", "90"))

