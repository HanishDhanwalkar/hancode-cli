"""Ollama provider implementation"""

from __future__ import annotations

import os
import json
from typing import Any, Callable

from dotenv import load_dotenv

from src.providers.base import (
    ModelProvider,
    ProviderMessage,
    ProviderResponse,
    ToolCallRequest,
    ToolDefinition,
)

load_dotenv()

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL_ID", "qwen3:8b")


class OllamaProvider(ModelProvider):
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client = None  # lazy load to avoid importing ollama package unnecessarily

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[ProviderMessage],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        on_token: Callable[[str], None] | None = None
    ) -> ProviderResponse:
        import ollama

        tool_calls = []
        text_parts = []

        def handle_tool_call(tool_name: str, tool_input: dict[str, Any]):
            tool_calls.append(ToolCallRequest(tool_name=tool_name, tool_input=tool_input))

        for chunk in ollama.chat(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            system=system,
            tools=[{"name": t.name, "description": t.description} for t in tools] if tools else None,
            stream=True,
            on_tool_call=handle_tool_call
        ):
            if "content" in chunk:
                text_parts.append(chunk["content"])
                if on_token:
                    on_token(chunk["content"])