"""Azure OpenAI Provider"""

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

DEFAULT_MODEL = os.environ.get("AZURE_OPENAI_DEFAULT_MODEL", "gpt-4o")

class AzureOpenAIProvider(ModelProvider):
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client = None  # lazy load to avoid importing anthropic package unnecessarily

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self):
        from openai import AzureOpenAI
        if self._client is None:
            self._client = AzureOpenAI(
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
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
        
        api_messages: list[dict] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": msg.role, "content": msg.content} for msg in messages)
        
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": 4096,  # TODO: make this configurable
        }
        
        if tools:
            kwargs["tools"] = self.build_tools_payload(tools)
            kwargs["tool_choice"] = "auto"
            
        # Streaming --------------
        if on_token:
            text_parts: list[str] = []
            # Accumulate tool-call fragments keyed by idx
            tc_accum: dict = {}
            
            kwargs["stream"] = True
            stream = client.chat.completions.create(**kwargs)
            stop_reason = None
            
            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                
                if choice.finish_reason:
                    stop_reason = choice.finish_reason

                delta = choice.delta
                if delta.content:
                    text_parts.append(delta.content)
                    on_token(delta.content)
                for tc_delta in delta.tool_calls or []:
                    idx = tc_delta.index
                    if idx not in tc_accum:
                        tc_accum[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_delta.id:
                        tc_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_accum[idx]["arguments"] = json.dumps(tc_delta.function.arguments)                    

            tool_calls: list[ToolCallRequest] = []
            for entry in tc_accum.values():
                try:
                    args = json.loads(entry["arguments"]) if entry["arguments"] else {}
                except json.JSONDecodeError:
                    args = {"error": "Invalid JSON in tool arguments", "raw": entry["arguments"]}
                except Exception as e:
                    args = {"error": f"Error parsing tool arguments: {str(e)}", "raw": entry["arguments"]}
                
                tool_calls.append(
                    ToolCallRequest(
                        id=entry["id"],
                        name=entry["name"],
                        arguments=args
                    )
                )
                
            return ProviderResponse(
                content="".join(text_parts),
                tool_calls=tool_calls,
                stop_reason=stop_reason
            )
        
        # Non-streaming --------------
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        tool_calls = self._parse_tool_calls(message.tool_calls)
        
        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason
        )
        
    # ==================== 
    # Internal helpers
    # ==================== 
    
    @staticmethod
    def build_tools_payload(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        payload = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                }
            }
            for tool in tools
        ]
        
        return payload
    
    @staticmethod
    def _parse_tool_calls(raw_calls) -> list[ToolCallRequest]:
        tool_calls: list[ToolCallRequest] = []
        for tc in raw_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {"error": "Invalid JSON in tool arguments", "raw": tc.function.arguments}
            except Exception as e:
                args = {"error": f"Error parsing tool arguments: {str(e)}", "raw": tc.function.arguments}
            
            tool_calls.append(
                ToolCallRequest(
                    id=tc.get.id,
                    name=tc.function.name,
                    input=args
                )
            )
        return tool_calls