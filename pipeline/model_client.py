"""LLM Model Client - Unified interface for multiple LLM providers.

This module provides a consistent interface for calling various LLM providers
including DeepSeek, Qwen, MiniMax, and OpenAI through their OpenAI-compatible APIs.
"""

import os
import logging
from dotenv import load_dotenv
load_dotenv()
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LLMProviderType = str 
PROVIDER_DEEPSEEK: LLMProviderType = "deepseek"
PROVIDER_QWEN: LLMProviderType = "qwen"
PROVIDER_MINIMAX: LLMProviderType = "minimax"
PROVIDER_OPENAI: LLMProviderType = "openai"

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", PROVIDER_MINIMAX).lower()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

PROVIDER_BASE_URLS = {
    PROVIDER_DEEPSEEK: "https://api.deepseek.com/v1",
    PROVIDER_QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    PROVIDER_MINIMAX: "https://api.minimaxi.com/v1",
    PROVIDER_OPENAI: "https://api.openai.com/v1",
}

PROVIDER_MODELS = {
    PROVIDER_DEEPSEEK: "deepseek-chat",
    PROVIDER_QWEN: "qwen-plus",
    PROVIDER_MINIMAX: "MiniMax-M2.7",
    PROVIDER_OPENAI: "gpt-4o-mini",
}

TOKEN_PRICES_PER_MILLION = {
    PROVIDER_DEEPSEEK: {"input": 0.27, "output": 1.1},
    PROVIDER_QWEN: {"input": 0.6, "output": 1.2},
    PROVIDER_MINIMAX: {"input": 0.1, "output": 0.1},
    PROVIDER_OPENAI: {"input": 0.15, "output": 0.6},
}


@dataclass
class Usage:
    """Token usage statistics for an LLM response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Unified response from LLM providers."""

    content: str
    usage: Usage = field(default_factory=Usage)
    provider: LLMProviderType = ""
    model: str = ""
    cost_usd: float = 0.0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse with content and usage information.
        """
        pass

    @abstractmethod
    def get_model(self) -> str:
        """Get the model name for this provider."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible LLM provider implementation."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: LLMProviderType,
    ):
        """Initialize the OpenAI-compatible provider.

        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API endpoint.
            model: Model name to use.
            provider_name: Name identifier for the provider.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider_name = provider_name
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    def chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Additional parameters like temperature, max_tokens.

        Returns:
            LLMResponse with content and usage information.
        """
        client = self._get_client()
        payload = {
            "model": self.model,
            "messages": messages,
        }
        if kwargs:
            payload.update(kwargs)

        response = client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage", {})

        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        cost = calculate_cost(
            usage.prompt_tokens,
            usage.completion_tokens,
            self.provider_name,
        )

        return LLMResponse(
            content=content,
            usage=usage,
            provider=self.provider_name,
            model=self.model,
            cost_usd=cost,
        )

    def get_model(self) -> str:
        """Get the model name for this provider."""
        return self.model

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


def get_provider(provider_type: Optional[LLMProviderType] = None) -> LLMProvider:
    """Factory function to get an LLM provider instance.

    Args:
        provider_type: Type of provider to create. Defaults to LLM_PROVIDER env var.

    Returns:
        An LLMProvider instance.

    Raises:
        ValueError: If provider type is unknown or API key is missing.
    """
    provider = (provider_type or DEFAULT_PROVIDER).lower()

    if provider not in PROVIDER_BASE_URLS:
        raise ValueError(f"Unknown provider: {provider}")

    api_keys = {
        PROVIDER_DEEPSEEK: DEEPSEEK_API_KEY,
        PROVIDER_QWEN: QWEN_API_KEY,
        PROVIDER_MINIMAX: MINIMAX_API_KEY,
        PROVIDER_OPENAI: OPENAI_API_KEY,
    }

    api_key = api_keys.get(provider, "")
    if not api_key:
        raise ValueError(f"API key not found for provider: {provider}")

    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=PROVIDER_BASE_URLS[provider],
        model=PROVIDER_MODELS[provider],
        provider_name=provider,
    )


def estimate_tokens(text: str, model: Optional[str] = None) -> int:
    """Estimate token count for text using approximation.

    Args:
        text: Input text to estimate tokens for.
        model: Model to use for estimation (affects encoding).

    Returns:
        Estimated token count.
    """
    return math.ceil(len(text) / 4)


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    provider: LLMProviderType,
) -> float:
    """Calculate the cost in USD for token usage.

    Args:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        provider: Provider type for pricing.

    Returns:
        Cost in USD.
    """
    prices = TOKEN_PRICES_PER_MILLION.get(provider, {"input": 0, "output": 0})
    input_cost = (prompt_tokens / 1_000_000) * prices["input"]
    output_cost = (completion_tokens / 1_000_000) * prices["output"]
    return round(input_cost + output_cost, 6)


def chat_with_retry(
    messages: list[dict[str, str]],
    provider_type: Optional[LLMProviderType] = None,
    max_retries: int = 3,
    **kwargs,
) -> LLMResponse:
    """Send a chat request with automatic retry on failure.

    Uses exponential backoff for retries.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        provider_type: Type of provider to use.
        max_retries: Maximum number of retry attempts.
        **kwargs: Additional parameters passed to the chat method.

    Returns:
        LLMResponse with content and usage information.

    Raises:
        httpx.HTTPStatusError: After all retries are exhausted.
    """
    provider = get_provider(provider_type)
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            return provider.chat(messages, **kwargs)
        except httpx.HTTPStatusError as e:
            if attempt == max_retries - 1:
                logger.error("All retry attempts exhausted: %s", e)
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                e,
            )
        except httpx.RequestError as e:
            if attempt == max_retries - 1:
                logger.error("Request error after all retries: %s", e)
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Request error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                e,
            )
        except Exception as e:
            logger.error("Unexpected error during chat: %s", e)
            raise


def quick_chat(
    prompt: str,
    system_message: Optional[str] = None,
    provider_type: Optional[LLMProviderType] = None,
    **kwargs,
) -> LLMResponse:
    """Convenience function for a single LLM chat interaction.

    Args:
        prompt: User message to send.
        system_message: Optional system message to prepend.
        provider_type: Type of provider to use.
        **kwargs: Additional parameters passed to the chat method.

    Returns:
        LLMResponse with content and usage information.
    """
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    return chat_with_retry(messages, provider_type, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_system = "You are a helpful assistant."
    test_prompt = "What is 2+2? Answer in one sentence."

    print(f"Testing LLM client with default provider ({DEFAULT_PROVIDER})")
    print(f"Model: {PROVIDER_MODELS.get(DEFAULT_PROVIDER, 'unknown')}")
    print("-" * 50)

    try:
        response = quick_chat(
            prompt=test_prompt,
            system_message=test_system,
        )

        print(f"Provider: {response.provider}")
        print(f"Model: {response.model}")
        print(f"Response: {response.content}")
        print(f"Usage: {response.usage}")
        print(f"Cost: ${response.cost_usd:.6f}")

        print("-" * 50)
        prompt_tokens_est = estimate_tokens(test_prompt + test_system)
        print(f"Estimated prompt tokens: {prompt_tokens_est}")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please set the appropriate API key environment variable.")
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e}")
    except Exception as e:
        print(f"Error: {e}")
