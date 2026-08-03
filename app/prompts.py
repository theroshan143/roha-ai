from pathlib import Path
from app.config import PROMPT_PATH


def load_system_prompt() -> str:
    path = Path(PROMPT_PATH)
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    with open(path, "r", encoding="utf-8") as file:
        return file.read()