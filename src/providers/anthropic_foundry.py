"""Anthropic Foundry Provider"""

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

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-4-6")


class AnthropicFoundryProvider(ModelProvider):
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client = None  # lazy load to avoid importing anthropic package unnecessarily

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            from anthropic import AnthropicFoundry

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            resource_id = os.environ.get("ANTHROPIC_RESOURCE_ID")
            if not api_key or not resource_id:
                raise ValueError(
                    "ANTHROPIC_API_KEY or ANTHROPIC_RESOURCE_ID environment variable is not set")

            self._client = AnthropicFoundry(
                api_key=api_key,
                resource_id=resource_id
            )

        return self._client

    def chat(
        self,
        messages: list[ProviderMessage],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        on_token: Callable[[str], None] | None = None
    ) -> ProviderResponse:
        client = self._get_client()
        api_msgs = [
            {
                "role": m.role,
                "content": m.content,
            }
            for m in messages
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,  # TODO: make this configurable
            "messages": api_msgs,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        if on_token:
            text_parts: list[str] = []
            tool_calls: list[ToolCallRequest] = []

            with client.beta.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            text_parts.append(delta.text)
                            on_token(delta.text)
                    elif event.type == "content_block_start":
                        block = event.content_block
                        if getattr(block, "type", "") == "tool_use":
                            tool_calls.append(
                                ToolCallRequest(
                                    id=block.id,
                                    tool_name=block.name,
                                    input={},
                                )
                            )
                    elif event.type == "content_block_stop":
                        pass

                final = stream.get_final_message()
                for block in final.content:
                    if block.type == "tool_use":
                        for tc in tool_calls:
                            if tc.id == block.id:
                                tc.input = block.input if isinstance(
                                    block.input, dict) else {}

            return ProviderResponse(
                content="".join(text_parts),
                tool_calls=tool_calls,
                stop_reason=getattr(final, "stop_reason", None)
            )

        res = client.beta.messages.create(**kwargs)
        content_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []

        for block in res.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        tool_name=block.name,
                        input=block.input if isinstance(
                            block.input, dict) else {},
                    )
                )

        return ProviderResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            stop_reason=getattr(res, "stop_reason", None)
        )
