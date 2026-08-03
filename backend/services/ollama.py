"""Async Ollama API client."""
import httpx
import json
from typing import AsyncIterator, List, Dict

OLLAMA_BASE = "http://localhost:11434"
_TIMEOUT = httpx.Timeout(5.0, read=None)   # no read timeout for streams


async def is_online() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(OLLAMA_BASE)
            return r.status_code == 200
    except Exception:
        return False


async def list_models() -> List[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


async def stream_chat(
    model: str,
    messages: List[Dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }
    if max_tokens > 0:
        payload["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            async with c.stream(
                "POST", f"{OLLAMA_BASE}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    yield f"[Error {resp.status_code}]"
                    return
                async for raw in resp.aiter_lines():
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            return
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        yield f"\n\n[Ollama error: {exc}]"
