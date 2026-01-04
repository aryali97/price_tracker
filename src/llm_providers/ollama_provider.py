"""
Ollama local LLM provider implementation.
"""

import ollama
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """LLM provider using local Ollama."""

    def __init__(self, model: str = "llama3.2:8b", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (default: llama3.2:8b)
            base_url: Ollama server URL (default: http://localhost:11434)
        """
        self.model = model
        self.base_url = base_url
        self.client = ollama.AsyncClient(host=base_url)

    async def extract(self, markdown: str, prompt: str) -> str:
        """
        Extract structured data using Ollama local LLM.

        Args:
            markdown: Page content in markdown format
            prompt: Extraction prompt

        Returns:
            LLM response (JSON string)
        """
        # Build the full prompt
        full_prompt = f"{prompt}\n\nPage content:\n\n{markdown}"

        print(f"[DEBUG] Calling Ollama with {len(full_prompt)} chars...")
        print(f"[DEBUG] Model: {self.model}")

        try:
            print("[DEBUG] Starting chat request...")
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts structured product information from e-commerce websites. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                options={
                    "temperature": 0.1,  # Low temperature for consistent extraction
                    "num_predict": 1000,  # Max output tokens
                }
            )

            print(f"[DEBUG] Got response: {len(str(response))} chars")
            return response['message']['content'].strip()

        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            raise Exception(f"Ollama extraction failed: {e}")

    def is_available(self) -> bool:
        """
        Check if Ollama is running and model exists.

        Returns:
            True if Ollama server is running and model is available
        """
        try:
            # Use sync client for quick availability check
            response = ollama.list()
            # Check if model name matches (with or without tag)
            # e.g., "llama3.2" matches both "llama3.2:latest" and "llama3.2:8b"
            model_base = self.model.split(':')[0]
            return any(m.model.startswith(model_base) for m in response.models)
        except Exception:
            return False

    def get_name(self) -> str:
        """
        Get provider name.

        Returns:
            Provider name with model
        """
        return f"Ollama ({self.model})"
