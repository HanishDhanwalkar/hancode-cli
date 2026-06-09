import os

from src.providers.base import ModelProvider, ProviderMessage, ToolDefinition
from src.providers.anthropic_foundry import AnthropicFoundryProvider
from src.providers.openai import OpenAIProvider
from src.providers.azure_openai import AzureOpenAIProvider
from src.providers.gemini import GeminiProvider
from src.providers.ollama_provider import OllamaProvider
from src.providers.aws_bedrock import AWSBedrockProvider


__all__ = [
    "ModelProvider",
    "ProviderMessage",
    "ToolDefinition",
    "list_available_models",
    # "AWSBedrockProvider",
    "AnthropicFoundryProvider",
    # "OpenAIProvider",
    # "AzureOpenAIProvider",
    # "GeminiProvider",
    "OllamaProvider",
    # TODO: add providers to __all__
]

def list_available_models() -> list[str]:
    """returns a list of available provider/models pairs"""
    raw = os.getenv("AVAILABLE_MODELS", "").strip()
    if not raw:
        return []
    pairs = [item.strip() for item in raw.split(",") if item.strip()]
    return pairs

def resolve_model(model: str) -> tuple[str, str] | None:
    """
    resolves a model query to a (provider, model) tuple
    supports:
        - provider/model
    """
    available = list_available_models()
    
    for m in available:
        if m.lower() == model.lower():
            if "/" not in m:
                parts = m.split("/")
                return parts[0], parts[1]
            else:
                return "unknown", m  # model without provider, will be resolved later
            
    return None

def get_provider(provider: str, model: str) -> ModelProvider:
    """factory method to get provider instance based on provider name"""
    if provider in ("anthropic_foundry", "anthropic"):
        return AnthropicFoundryProvider(model)
    if provider in ("azure_openai", "azure"):
        return AzureOpenAIProvider(model)
    if provider in ("openai", "oai"):
        return OpenAIProvider(model)
    if provider in ("gemini", "google"):
        return GeminiProvider(model)
    if provider in ("ollama", "ollama_provider"):
        return OllamaProvider(model)
    if provider in ("aws_bedrock", "bedrock"):
        return AWSBedrockProvider(model)
