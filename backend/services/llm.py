import json
from typing import AsyncGenerator

import httpx

from backend.config import settings


class LLMClient:
    """Unified chat/embedding client for local Ollama or OpenAI-compatible APIs."""

    def __init__(self):
        self.provider = settings.llm_provider.strip().lower()
        self.timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)

    @property
    def model(self) -> str:
        if self.provider == "openai-compatible":
            return settings.openai_model
        return settings.ollama_model

    async def is_available(self) -> bool:
        if self.provider == "openai-compatible":
            return bool(settings.openai_api_key and settings.openai_base_url and settings.openai_model)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str,
    ) -> AsyncGenerator[str, None]:
        if self.provider == "openai-compatible":
            async for token in self._stream_openai_compatible(messages, system_prompt):
                yield token
            return

        async for token in self._stream_ollama(messages, system_prompt):
            yield token

    async def complete(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages = [{"role": "system", "content": system}] + messages

        if self.provider == "openai-compatible":
            headers = self._openai_headers()
            payload = {
                "model": settings.openai_model,
                "messages": messages,
                "stream": False,
                "temperature": temperature,
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"].get("content", "")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

    async def embed(self, text: str) -> list[float]:
        if settings.embedding_provider.strip().lower() == "openai-compatible":
            if not settings.openai_api_key:
                return []
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/embeddings",
                    headers=self._openai_headers(),
                    json={"model": settings.openai_embed_model, "input": text},
                )
                r.raise_for_status()
                data = r.json()
                return data.get("data", [{}])[0].get("embedding", [])

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

    async def _stream_ollama(self, messages: list[dict], system_prompt: str) -> AsyncGenerator[str, None]:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": full_messages,
                    "stream": True,
                    "think": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1,
                        "num_ctx": 8192,
                        "num_predict": 1024,
                    },
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

    async def _stream_openai_compatible(self, messages: list[dict], system_prompt: str) -> AsyncGenerator[str, None]:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": settings.openai_model,
            "messages": full_messages,
            "stream": True,
            "temperature": 0.7,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers=self._openai_headers(),
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

    def _openai_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.openai_api_key:
            headers["Authorization"] = f"Bearer {settings.openai_api_key}"
        return headers


# Keep the historical import name so existing routers/services do not need churn.
ollama = LLMClient()
