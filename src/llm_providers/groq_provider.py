"""
Groq LLM provider implementation.
"""

from groq import AsyncGroq
from .base import LLMProvider


class GroqProvider(LLMProvider):
    """LLM provider using Groq API."""

    def __init__(self, api_key: str):
        """
        Initialize Groq provider.

        Args:
            api_key: Groq API key
        """
        self.api_key = api_key
        self.client = AsyncGroq(api_key=api_key)

    async def extract(self, markdown: str, prompt: str) -> str:
        """
        Extract structured data using Groq LLM.

        Args:
            markdown: Page content in markdown format
            prompt: Extraction prompt

        Returns:
            LLM response (JSON string)
        """
        # Build the full prompt
        full_prompt = f"{prompt}\n\nPage content:\n\n{markdown}"

        # Call Groq API
        try:
            chat_completion = await self.client.chat.completions.create(
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
                model="llama-3.3-70b-versatile",
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000,
            )

            response = chat_completion.choices[0].message.content
            return response.strip()

        except Exception as e:
            raise Exception(f"Groq API extraction failed: {e}")

    def is_available(self) -> bool:
        """
        Check if Groq provider is available.

        Returns:
            True if API key is set
        """
        return bool(self.api_key)

    def get_name(self) -> str:
        """
        Get provider name.

        Returns:
            Provider name with model
        """
        return "Groq (llama-3.3-70b-versatile)"
