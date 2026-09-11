"""Ollama API client for communicating with local Ollama instances."""

from __future__ import annotations

import httpx


class OllamaClient:
    """Thin wrapper around the Ollama HTTP API."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.ConnectError:
            return False

    async def list_models(self) -> list[dict]:
        """List locally available Ollama models."""
        resp = await self._client.get("/api/tags")
        resp.raise_for_status()
        return resp.json().get("models", [])

    async def get_model_names(self) -> list[str]:
        """Return just the model name strings."""
        models = await self.list_models()
        return [m["name"] for m in models]

    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        stream: bool = False,
    ) -> dict:
        """Send a chat completion request to Ollama.

        When stream=False, returns the full response as a dict.
        When stream=True, returns an async generator of response chunks.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
            },
        }

        if stream:
            return self._stream_chat(payload)
        else:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def _stream_chat(self, payload: dict):
        """Stream chat response chunks from Ollama."""
        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    import json
                    yield json.loads(line)
