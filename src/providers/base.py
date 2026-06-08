"""Model provider abstraction"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable
from dataclasses import dataclass, field


class ModelProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def chat(
        self,
        messages: list[ProviderMessage],
        system: str = "",
        tools: list[ToolDefinition] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderResponse: ...


@dataclass
class ProviderMessage:
    role: str
    content: str


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    stop_reason: str | None = None


@dataclass
class ToolCallRequest:
    id: str
    name: str
    input: dict[str, Any]
