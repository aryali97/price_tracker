"""
Base extractor interface for product data extraction.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import re


class BaseExtractor(ABC):
    """Base class for site-specific extractors."""

    # Regex pattern to match product URLs for this site
    PRODUCT_PATTERN: str = r""

    def __init__(self):
        """Initialize extractor."""
        pass

    @classmethod
    def matches_site(cls, url: str) -> bool:
        """
        Check if this extractor can handle the given URL.

        Args:
            url: Product URL to check

        Returns:
            True if this extractor can handle this URL
        """
        if not cls.PRODUCT_PATTERN:
            return False
        return bool(re.search(cls.PRODUCT_PATTERN, url))

    @abstractmethod
    def get_extraction_prompt(self) -> str:
        """
        Get the LLM prompt for extracting product data (legacy mode).

        Returns:
            Prompt string for LLM
        """
        pass

    @abstractmethod
    def get_learn_mode_prompt(self) -> str:
        """
        Get the LLM prompt for learn mode - extracts data AND selectors.

        Returns:
            Prompt string that asks LLM to return both data and selectors
        """
        pass

    def parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM JSON response into structured data.

        Args:
            llm_response: Raw LLM response (should be JSON)

        Returns:
            Parsed product data dictionary
        """
        import json

        # Remove markdown code blocks if present
        llm_response = re.sub(r'```json\s*', '', llm_response)
        llm_response = re.sub(r'```\s*$', '', llm_response)
        llm_response = llm_response.strip()

        try:
            # Try to parse as JSON
            data = json.loads(llm_response)
            return self.normalize_data(data)
        except json.JSONDecodeError:
            # If not valid JSON, try to extract JSON from text
            # Look for JSON block in response
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    return self.normalize_data(data)
                except json.JSONDecodeError:
                    pass

            raise ValueError(f"Could not parse LLM response as JSON: {llm_response[:200]}")

    def normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize extracted data to consistent format.

        Args:
            data: Raw extracted data

        Returns:
            Normalized data with standard keys
        """
        # Convert price strings to floats
        if 'listed_price' in data and isinstance(data['listed_price'], str):
            data['listed_price'] = self._parse_price(data['listed_price'])

        if 'sale_price' in data and isinstance(data['sale_price'], str):
            data['sale_price'] = self._parse_price(data['sale_price'])

        # Ensure sizes_available is a list
        if 'sizes_available' in data and not isinstance(data['sizes_available'], list):
            if data['sizes_available']:
                data['sizes_available'] = [data['sizes_available']]
            else:
                data['sizes_available'] = []

        return data

    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Parse price string to float.

        Args:
            price_str: Price string (e.g., "$49.99", "49.99", "$49")

        Returns:
            Price as float, or None if invalid
        """
        if not price_str:
            return None

        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[$€£¥,\s]', '', str(price_str))

        try:
            return float(cleaned)
        except ValueError:
            return None

    def get_colorway_selectors(self) -> List[str]:
        """
        Get CSS selectors for colorway/variant buttons.

        Returns:
            List of CSS selectors to try
        """
        return []

    def extract_colorway_name(self, html: str) -> Optional[str]:
        """
        Extract the currently selected colorway name from HTML.

        Args:
            html: Page HTML

        Returns:
            Colorway name or None
        """
        return None

    def parse_learn_mode_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse learn mode LLM response into data + recipe.

        Expected format:
        {
            "data": {...product data...},
            "selectors": {...selector mappings...}
        }

        Args:
            llm_response: Raw LLM response

        Returns:
            Dictionary with 'data' and 'recipe' keys

        Raises:
            ValueError: If response cannot be parsed or is missing required sections
        """
        import json

        # Remove markdown code blocks
        llm_response = re.sub(r'```json\s*', '', llm_response)
        llm_response = re.sub(r'```\s*$', '', llm_response)
        llm_response = llm_response.strip()

        try:
            parsed = json.loads(llm_response)

            # Validate structure
            if 'data' not in parsed or 'selectors' not in parsed:
                raise ValueError("Learn mode response missing 'data' or 'selectors' sections")

            # Normalize the data section
            normalized_data = self.normalize_data(parsed['data'])

            # Build recipe structure
            recipe = {
                'version': 1,
                'selectors': parsed['selectors']
            }

            return {
                'data': normalized_data,
                'recipe': recipe
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse learn mode response as JSON: {e}")

    def extract_site_domain(self, url: str) -> str:
        """
        Extract site domain from URL.

        Args:
            url: Full URL (e.g., 'https://www.abercrombie.com/shop/us/p/item-123')

        Returns:
            Domain without www (e.g., 'abercrombie.com')
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
