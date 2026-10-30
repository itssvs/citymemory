"""Small LLM client for any OpenAI-compatible chat API.

Default: Ollama on this machine (no key, works offline).
  LLM_BASE_URL  http://localhost:11434/v1
  LLM_MODEL     llama3.2:3b
  LLM_API_KEY   ollama            (any string for Ollama; a real key for cloud providers)
  LLM_ENABLED   auto | off

Cloud example (Groq, OpenRouter, Gemini's OpenAI-compatible endpoint, ...): set LLM_BASE_URL,
LLM_MODEL and LLM_API_KEY to that provider's values.

Every call returns None on any failure, so callers always have a non-AI fallback.
"""
import json
import os
import re
import time

import httpx

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "llama3.2:3b")
API_KEY = os.environ.get("LLM_API_KEY", "ollama")
ENABLED = os.environ.get("LLM_ENABLED", "auto").lower() != "off"
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "60"))

_status = {"checked": 0.0, "ok": False, "error": "not checked yet"}


def _headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def available(force: bool = False) -> bool:
    """Cheap reachability check, cached for 30 seconds."""
    if not ENABLED:
        _status.update(ok=False, error="disabled (LLM_ENABLED=off)")
        return False
    if not force and time.time() - _status["checked"] < 30:
        return _status["ok"]
    _status["checked"] = time.time()
    try:
        r = httpx.get(f"{BASE_URL}/models", headers=_headers(), timeout=3)
        ok = r.status_code == 200
        if ok and ("localhost" in BASE_URL or "127.0.0.1" in BASE_URL):
            names = [m.get("id", "") for m in r.json().get("data", [])]
            if names and not any(n == MODEL or n.split(":")[0] == MODEL.split(":")[0] for n in names):
                _status.update(ok=False, error=f"model '{MODEL}' not pulled; run: ollama pull {MODEL}")
                return False
        _status.update(ok=ok, error=None if ok else f"HTTP {r.status_code}")
    except Exception as exc:
        _status.update(ok=False, error=f"{type(exc).__name__}: cannot reach {BASE_URL}")
    return _status["ok"]


def info() -> dict:
    available()
    host = re.sub(r"^https?://", "", BASE_URL).split("/")[0]
    return {"available": _status["ok"], "model": MODEL, "host": host, "error": _status["error"]}


def _parse_json(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def chat(system: str, user: str, as_json: bool = False, max_tokens: int = 300, timeout: float = None):
    """Return the model's reply (dict when as_json, else str), or None on any failure."""
    if not available():
        return None
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    if as_json:
        payload["response_format"] = {"type": "json_object"}
    for attempt in range(2):
        try:
            r = httpx.post(f"{BASE_URL}/chat/completions", json=payload, headers=_headers(), timeout=timeout or TIMEOUT)
            if r.status_code == 400 and "response_format" in payload:
                payload.pop("response_format")  # some providers reject it; the prompt still asks for JSON
                continue
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            return _parse_json(text) if as_json else text
        except Exception as exc:
            _status.update(error=f"{type(exc).__name__} during chat")
            return None
    return None
