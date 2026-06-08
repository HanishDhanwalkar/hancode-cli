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

De