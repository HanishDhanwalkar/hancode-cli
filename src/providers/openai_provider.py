"""Openai Provider"""

from __future__ import annotations

import os
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

DEFAULT_MODEL = ""

class OpenAIProvider(ModelProvider):
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client = None  # lazy load to avoid importing anthropic package unnecessarily

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        pass

    def chat(
        self,
        messages: list[ProviderMessage],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        on_token: Callable[[str], None] | None = None
    ) -> ProviderResponse:
        pass