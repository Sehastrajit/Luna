"""
Unified LLM client — supports:
  ollama            Local Ollama (default)
  openai-compatible OpenAI, OpenRouter, Groq, LM Studio, Jan.ai, llama.cpp, etc.
  anthropic         Anthropic Claude (native Messages API)
  google            Google Gemini (native REST API)
  groq              Groq cloud inference (native, fastest)
  cohere            Cohere Command R (native Chat API v2)
  mistral           Mistral AI (native)

All providers stream tokens via the same async generator interface so the
rest of the codebase needs zero changes.
"""
import json
from typing import AsyncGenerator

import httpx

from backend.config import settings

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)


# ── helpers ───────────────────────────────────────────────────────────────────

def _openai_headers(api_key: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _provider() -> str:
    return settings.llm_provider.strip().lower()


# ── per-provider streaming generators ────────────────────────────────────────

async def _stream_ollama(
    messages: list[dict],
    system_prompt: str,
    *,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    options = {
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
        "num_ctx": num_ctx or 8192,
        "num_predict": num_predict or 1024,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": full_messages,
                "stream": True,
                "think": False,
                "options": options,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break


async def _stream_openai_compatible(
    messages: list[dict],
    system_prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "messages": full_messages,
        "stream": True,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/chat/completions",
            headers=_openai_headers(api_key),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content


async def _stream_anthropic(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Anthropic Messages API with server-sent events streaming."""
    # Convert role names: Anthropic uses 'user'/'assistant' (same as OpenAI)
    payload = {
        "model": settings.anthropic_model,
        "system": system_prompt,
        "messages": messages,
        "max_tokens": 1024,
        "stream": True,
        "temperature": temperature,
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                # content_block_delta carries the actual text
                if data.get("type") == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield text
                elif data.get("type") == "message_stop":
                    break


async def _stream_google(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Google Gemini REST API with streaming (newline-delimited JSON)."""
    # Convert messages to Gemini format
    gemini_contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1024,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{settings.google_model}:streamGenerateContent"
        f"?key={settings.google_api_key}&alt=sse"
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                for candidate in data.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text = part.get("text", "")
                        if text:
                            yield text


async def _stream_groq(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Groq uses the OpenAI-compatible protocol at their own endpoint."""
    async for token in _stream_openai_compatible(
        messages,
        system_prompt,
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=temperature,
    ):
        yield token


async def _stream_cohere(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Cohere Chat API v2 with streaming."""
    # Build message list in Cohere v2 format
    cohere_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = "assistant" if m["role"] == "assistant" else "user"
        cohere_messages.append({"role": role, "content": m["content"]})

    payload = {
        "model": settings.cohere_model,
        "messages": cohere_messages,
        "stream": True,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.cohere_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            "https://api.cohere.com/v2/chat",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                event_type = data.get("type", "")
                if event_type == "content-delta":
                    text = data.get("delta", {}).get("message", {}).get("content", {}).get("text", "")
                    if text:
                        yield text
                elif event_type == "message-end":
                    break


async def _stream_mistral(
    messages: list[dict],
    system_prompt: str,
    *,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Mistral AI — OpenAI-compatible endpoint."""
    async for token in _stream_openai_compatible(
        messages,
        system_prompt,
        base_url="https://api.mistral.ai/v1",
        api_key=settings.mistral_api_key,
        model=settings.mistral_model,
        temperature=temperature,
    ):
        yield token


# ── non-streaming complete (used by memory/fact extraction) ───────────────────

async def _complete_ollama(prompt: str, system: str, temperature: float) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": temperature},
            },
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


async def _complete_openai(
    prompt: str, system: str, temperature: float,
    base_url: str, api_key: str, model: str,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=_openai_headers(api_key),
            json={"model": model, "messages": messages, "stream": False, "temperature": temperature},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"].get("content", "")


async def _complete_anthropic(prompt: str, system: str, temperature: float) -> str:
    payload = {
        "model": settings.anthropic_model,
        "system": system or "You are a helpful assistant.",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        content = r.json().get("content", [])
        return content[0].get("text", "") if content else ""


async def _complete_google(prompt: str, system: str, temperature: float) -> str:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 512},
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{settings.google_model}:generateContent?key={settings.google_api_key}"
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        candidates = r.json().get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        return ""


# ── public LLMClient class ────────────────────────────────────────────────────

class LLMClient:
    """Unified streaming + completion client.  Provider is read from settings at call time."""

    def __init__(self):
        self.timeout = _TIMEOUT

    @property
    def provider(self) -> str:
        return _provider()

    @property
    def model(self) -> str:
        p = self.provider
        mapping = {
            "ollama": settings.ollama_model,
            "openai-compatible": settings.openai_model,
            "anthropic": settings.anthropic_model,
            "google": settings.google_model,
            "groq": settings.groq_model,
            "cohere": settings.cohere_model,
            "mistral": settings.mistral_model,
        }
        return mapping.get(p, settings.ollama_model)

    async def is_available(self) -> bool:
        p = self.provider
        if p == "ollama":
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                    r = await client.get(f"{settings.ollama_base_url}/api/tags")
                    return r.status_code == 200
            except Exception:
                return False
        if p == "openai-compatible":
            return bool(settings.openai_api_key and settings.openai_base_url and settings.openai_model)
        if p == "anthropic":
            return bool(settings.anthropic_api_key)
        if p == "google":
            return bool(settings.google_api_key)
        if p == "groq":
            return bool(settings.groq_api_key)
        if p == "cohere":
            return bool(settings.cohere_api_key)
        if p == "mistral":
            return bool(settings.mistral_api_key)
        return False

    async def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        p = self.provider
        if p == "ollama":
            return _stream_ollama(
                messages, system_prompt,
                num_ctx=num_ctx, num_predict=num_predict, temperature=temperature,
            )
        if p == "openai-compatible":
            return _stream_openai_compatible(
                messages, system_prompt,
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=temperature,
            )
        if p == "anthropic":
            return _stream_anthropic(messages, system_prompt, temperature=temperature)
        if p == "google":
            return _stream_google(messages, system_prompt, temperature=temperature)
        if p == "groq":
            return _stream_groq(messages, system_prompt, temperature=temperature)
        if p == "cohere":
            return _stream_cohere(messages, system_prompt, temperature=temperature)
        if p == "mistral":
            return _stream_mistral(messages, system_prompt, temperature=temperature)
        # Fallback to Ollama
        return _stream_ollama(messages, system_prompt, temperature=temperature)

    async def complete(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        p = self.provider
        if p == "ollama":
            return await _complete_ollama(prompt, system, temperature)
        if p == "openai-compatible":
            return await _complete_openai(
                prompt, system, temperature,
                settings.openai_base_url, settings.openai_api_key, settings.openai_model,
            )
        if p == "anthropic":
            return await _complete_anthropic(prompt, system, temperature)
        if p == "google":
            return await _complete_google(prompt, system, temperature)
        if p == "groq":
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.groq.com/openai/v1", settings.groq_api_key, settings.groq_model,
            )
        if p == "cohere":
            # Cohere non-streaming via same endpoint with stream=False
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.cohere.com/v2", settings.cohere_api_key, settings.cohere_model,
            )
        if p == "mistral":
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.mistral.ai/v1", settings.mistral_api_key, settings.mistral_model,
            )
        return await _complete_ollama(prompt, system, temperature)

    async def embed(self, text: str) -> list[float]:
        if settings.embedding_provider.strip().lower() == "openai-compatible":
            if not settings.openai_api_key:
                return []
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/embeddings",
                    headers=_openai_headers(settings.openai_api_key),
                    json={"model": settings.openai_embed_model, "input": text},
                )
                r.raise_for_status()
                data = r.json()
                return data.get("data", [{}])[0].get("embedding", [])

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": text},
            )
            if r.status_code == 200:
                data = r.json()
                if "embeddings" in data:
                    return data["embeddings"][0]
                return data.get("embedding", [])
        return []


# Keep the historical import name so existing routers/services need zero churn.
ollama = LLMClient()
