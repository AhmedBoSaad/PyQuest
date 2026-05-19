"""LM Studio client.

LM Studio exposes an OpenAI-compatible REST server at http://localhost:1234/v1
once the user clicks 'Start Server' inside LM Studio. We just hit:
  - GET  /v1/models       -> health check
  - POST /v1/chat/completions  with stream=true  -> SSE stream of token deltas

No API key is required (LM Studio ignores Authorization headers by default).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_MODEL = "local-model"  # LM Studio uses whatever's loaded; this name is ignored


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


def list_models(base_url: str, timeout: float = 5.0) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]


def stream_chat(
    base_url: str,
    model: str,
    messages: list[ChatMessage],
    *,
    temperature: float = 0.4,
    max_tokens: int = 600,
    timeout: float = 120.0,
) -> Iterator[str]:
    """Yield content deltas from the assistant. Raises on HTTP errors."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    with requests.post(url, json=payload, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        # SSE is always UTF-8 per the spec. LM Studio sends Content-Type
        # 'text/event-stream' with no charset, which makes requests default to
        # ISO-8859-1 — that mangles curly quotes, em dashes, etc. Force UTF-8.
        resp.encoding = "utf-8"
        for raw_bytes in resp.iter_lines(decode_unicode=False):
            if not raw_bytes:
                continue
            try:
                raw = raw_bytes.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            chunk = delta.get("content")
            if chunk:
                yield chunk


def complete_chat(
    base_url: str,
    model: str,
    messages: list[ChatMessage],
    **kwargs,
) -> str:
    """Non-streaming convenience: collect the full reply."""
    return "".join(stream_chat(base_url, model, messages, **kwargs))
