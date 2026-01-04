"""
Base class for LLM providers.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def extract(self, markdown: str, prompt: str) -> str:
        """
        Extract structured data using LLM.

        Args:
            markdown: Page content in markdown format
            prompt: Extraction prompt

        Returns:
            LLM response (should be JSON string)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is configured and available.

        Returns:
            True if provider is ready to use, False otherwise
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get provider name for logging.

        Returns:
            Human-readable provider name
        """
        pass
