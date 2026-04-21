from .base import Adapter, AgentResponse, Tool, ToolCall

__all__ = ["KNOWN_PROVIDERS", "Adapter", "AgentResponse", "Tool", "ToolCall", "get_adapter"]

KNOWN_PROVIDERS = ("claude", "openai", "gemini", "ollama")


def get_adapter(name: str, model: str) -> Adapter:
    """Lazy-load provider adapters so missing SDKs only break their own provider."""
    if name == "claude":
        from .claude import ClaudeAdapter
        return ClaudeAdapter(model=model)
    if name == "openai":
        from .openai_adapter import OpenAIAdapter
        return OpenAIAdapter(model=model)
    if name == "gemini":
        from .gemini import GeminiAdapter
        return GeminiAdapter(model=model)
    if name == "ollama":
        from .ollama import OllamaAdapter
        return OllamaAdapter(model=model)
    raise ValueError(f"Unknown provider: {name}. Known: {', '.join(KNOWN_PROVIDERS)}")
