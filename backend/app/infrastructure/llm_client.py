"""LLM client — DeepSeek via LangChain.

Security boundary: this module handles all cloud LLM communication.
"""

from langchain_deepseek import ChatDeepSeek
from app.config import settings

_model = None


def get_model(timeout: int | None = None, max_tokens: int | None = None):
    """Get the ChatDeepSeek model (lazy singleton).

    Args:
        timeout: Override the default HTTP timeout in seconds.
        max_tokens: Override the default max output tokens.
        When either is provided, returns a fresh instance (not cached).
    """
    global _model
    if timeout is not None or max_tokens is not None:
        return ChatDeepSeek(
            model=settings.deepseek.model,
            api_key=settings.deepseek.api_key,
            api_base=settings.deepseek.base_url,
            temperature=0.1,
            timeout=timeout or settings.agent.cloud_timeout_seconds,
            max_tokens=max_tokens or settings.agent.cloud_max_tokens,
        )
    if _model is None:
        _model = ChatDeepSeek(
            model=settings.deepseek.model,
            api_key=settings.deepseek.api_key,
            api_base=settings.deepseek.base_url,
            temperature=0.1,
            timeout=settings.agent.cloud_timeout_seconds,
            max_tokens=settings.agent.cloud_max_tokens,
        )
    return _model
