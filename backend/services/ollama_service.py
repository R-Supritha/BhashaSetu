"""
Clean low-level access to a locally installed Ollama daemon.

Every function here is safe to call at any time:
  - returns None / {"available": False, ...} when the daemon is down, the
    model is missing, or Ollama has been disabled via config;
  - never raises into a route — errors are swallowed and surfaced as labelled
    fallbacks by the higher-level services (llm_service) that decide REAL vs
    FALLBACK.

The exact model name always comes from Config.OLLAMA_MODEL so operators pick
the tag that is actually installed on the machine (no invented names).
"""

import json
import re

import requests

from backend.config import Config

_GENERATE_URL = "/api/generate"
_TAGS_URL = "/api/tags"


def enabled() -> bool:
    """OLLAMA_ENABLED controls whether the local LLM is used, independent of APP_MODE."""
    return bool(Config.OLLAMA_ENABLED)


def is_available() -> dict:
    """Ping the daemon and report which exact model is present. Never raises."""
    try:
        response = requests.get(f"{Config.OLLAMA_BASE_URL}{_TAGS_URL}", timeout=2)
        response.raise_for_status()
        names = [m.get("name") for m in response.json().get("models", []) if m.get("name")]
        present = any(
            Config.OLLAMA_MODEL == name or name.startswith(Config.OLLAMA_MODEL.split(":")[0])
            for name in names
        )
        return {
            "available": True,
            "model": Config.OLLAMA_MODEL,
            "model_present": present,
            "enabled": enabled(),
            "models": names,
        }
    except Exception:
        return {
            "available": False,
            "model": Config.OLLAMA_MODEL,
            "model_present": False,
            "enabled": enabled(),
            "models": [],
        }


def chat(prompt: str, *, temperature: float | None = None,
         max_tokens: int | None = None) -> str | None:
    """
    Run one non-streamed generation against the configured model.

    Returns the raw text, or None when disabled/unreachable/error/empty.
    """
    if not enabled():
        return None
    payload: dict = {
        "model": Config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    if max_tokens is not None:
        payload.setdefault("options", {})["num_predict"] = max_tokens
    try:
        response = requests.post(
            f"{Config.OLLAMA_BASE_URL}{_GENERATE_URL}",
            json=payload,
            timeout=Config.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return (response.json().get("response") or "").strip() or None
    except Exception:
        return None


def _extract_json(text: str) -> dict | None:
    """Pull the first balanced JSON object out of a model response."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        char = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except Exception:
                    return None
    return None


def chat_json(prompt: str, *, temperature: float | None = None,
              max_tokens: int | None = None) -> dict | None:
    """
    Generate and parse a single JSON object. Returns None when the model does
    not produce parseable JSON (caller decides on a labelled fallback).
    """
    raw = chat(prompt, temperature=temperature, max_tokens=max_tokens)
    if raw is None:
        return None
    return _extract_json(raw)