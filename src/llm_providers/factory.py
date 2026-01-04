"""
Factory for creating LLM provider instances.
"""

import os
from .base import LLMProvider
from .groq_provider import GroqProvider
from .ollama_provider import OllamaProvider


class LLMProviderFactory:
    """Factory for creating LLM providers based on configuration."""

    @staticmethod
    def create_provider(provider_type: str = None) -> LLMProvider:
        """
        Create LLM provider based on configuration.

        Args:
            provider_type: Provider type override (groq, local, auto).
                          If None, reads from LLM_PROVIDER env var.
                          Default: groq (for backward compatibility)

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider cannot be created or configuration is invalid
        """
        # Get provider type from parameter or environment
        provider_type = provider_type or os.getenv('LLM_PROVIDER', 'groq')
        provider_type = provider_type.lower()

        # Get configuration from environment
        groq_key = os.getenv('GROQ_API_KEY')
        ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2:8b')
        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

        if provider_type == 'groq':
            # Always use Groq
            if not groq_key:
                raise ValueError("GROQ_API_KEY not found in environment variables")
            return GroqProvider(api_key=groq_key)

        elif provider_type == 'local':
            # Always use Ollama - fail if not available (no fallback)
            provider = OllamaProvider(model=ollama_model, base_url=ollama_url)
            if not provider.is_available():
                raise ValueError(
                    f"Ollama not available. Ensure:\n"
                    f"1. Ollama is running: ollama serve\n"
                    f"2. Model is downloaded: ollama pull {ollama_model}"
                )
            return provider

        elif provider_type == 'auto':
            # Try Ollama first
            ollama_provider = OllamaProvider(model=ollama_model, base_url=ollama_url)
            if ollama_provider.is_available():
                print(f"✓ Using local LLM: {ollama_provider.get_name()}")
                return ollama_provider

            # Explicit failure if Groq not available
            if not groq_key:
                raise ValueError(
                    f"Ollama unavailable and no Groq API key found.\n"
                    f"Either:\n"
                    f"1. Start Ollama: ollama serve\n"
                    f"2. Set GROQ_API_KEY in .env"
                )

            # Warn loudly before falling back to Groq
            print("⚠️  WARNING: Ollama not available!")
            print(f"⚠️  Falling back to Groq API (will use API quota)")
            print(f"⚠️  To use local LLM:")
            print(f"    1. Run: ollama serve")
            print(f"    2. Ensure model exists: ollama pull {ollama_model}")
            return GroqProvider(api_key=groq_key)

        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: {provider_type}. "
                f"Valid options: 'groq', 'local', 'auto'"
            )
