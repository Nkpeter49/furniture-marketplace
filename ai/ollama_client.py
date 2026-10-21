"""Small HTTP client for Ollama on this computer; no cloud provider is used."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MODEL_NAME = "qwen3:0.6b"


class LocalAIError(Exception):
    """Raised when the local Ollama service cannot provide usable text."""


def get_model_status() -> dict[str, str]:
    try:
        with urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {"ready": "false", "message": "Local AI is not running. Start Ollama to generate text."}

    installed = {item.get("name") for item in data.get("models", [])}
    if MODEL_NAME not in installed:
        return {"ready": "false", "message": "Ollama is running, but qwen3:0.6b is not installed yet."}
    return {"ready": "true", "message": "Local AI is ready. Your text stays on this computer."}


def generate_text(prompt: str) -> str:
    body = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    req = Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise LocalAIError("Local Ollama request failed") from exc

    result = data.get("message", {}).get("content", "").strip()
    if not result:
        raise LocalAIError("Ollama returned an empty response")
    return result
