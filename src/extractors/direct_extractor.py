"""
Direct HTML extraction using selector recipes.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from bs4 import BeautifulSoup


class DirectExtractor:
    """Extract product data directly from HTML using selector recipes."""

    def __init__(self, recipe: Dict[str, Any]):
        """
        Initialize with a recipe.

        Args:
            recipe: Recipe dictionary with selectors
        """
        self.recipe = recipe
        self.selectors = recipe.get('selectors', {})

    def extract(self, html: str) -> Dict[str, Any]:
        """
        Extract product data from HTML using recipe selectors.

        Args:
            html: Raw HTML content

        Returns:
            Extracted product data with _extraction_confidence

        Raises:
            ExtractionError: If required fields cannot be extracted
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = {}
        confidence_scores = []

        for field_name, selector_config in self.selectors.items():
            value, confidence = self._extract_field(soup, field_name, selector_config)
            result[field_name] = value
            confidence_scores.append(confidence)

        # Calculate overall confidence
        result['_extraction_confidence'] = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )

        return result

    def _extract_field(
        self, soup: BeautifulSoup, field_name: str, config: Dict[str, Any]
    ) -> Tuple[Any, float]:
        """
        Extract a single field using selector config.

        Args:
            soup: BeautifulSoup object
            field_name: Name of field being extracted
            config: Field configuration with selectors

        Returns:
            (value, confidence_score)

        Raises:
            ExtractionError: If required field cannot be extracted
        """
        # Try primary selector first, then fallbacks
        selectors_to_try = [config['primary']] + config.get('fallbacks', [])
        extraction_type = config.get('extraction', 'text')
        required = config.get('required', False)

        # Special cases for optional fields:
        # - listed_price might not exist if item is at regular price
        # - sizes_available might be in JSON data rather than DOM (can't use CSS selectors)
        if field_name in ('listed_price', 'sizes_available'):
            required = False

        for i, selector in enumerate(selectors_to_try):
            try:
                # Handle list extraction differently
                if extraction_type == 'list_text':
                    elements = soup.select(selector)
                    if elements:
                        values = [self._extract_text(el, config) for el in elements]
                        values = [v for v in values if v]  # Filter empty
                        if values:
                            # Confidence decreases with fallback usage
                            confidence = 1.0 - (i * 0.1)
                            return values, confidence
                else:
                    element = soup.select_one(selector)
                    if element:
                        value = self._extract_value(element, config, extraction_type)
                        if value is not None:
                            confidence = 1.0 - (i * 0.1)
                            return value, confidence
            except Exception as e:
                # Log but continue to next selector
                print(f"[DirectExtractor] Error with selector '{selector}' for field '{field_name}': {e}")
                continue

        # No selector worked
        if required:
            raise ExtractionError(f"Required field '{field_name}' could not be extracted")

        return None, 0.0

    def _extract_value(
        self, element, config: Dict[str, Any], extraction_type: str
    ) -> Optional[Any]:
        """
        Extract value from element based on extraction type.

        Args:
            element: BeautifulSoup element
            config: Field configuration
            extraction_type: Type of extraction (text, price, html, attribute)

        Returns:
            Extracted value
        """
        # Check if should extract from attribute
        if config.get('attribute'):
            raw_value = element.get(config['attribute'], '')
        else:
            raw_value = element.get_text(strip=True)

        # Apply extraction type transformation
        if extraction_type == 'price':
            return self._parse_price(raw_value)
        elif extraction_type == 'text':
            return raw_value.strip() if raw_value else None
        elif extraction_type == 'html':
            return str(element)
        else:
            return raw_value

    def _extract_text(self, element, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract text from element.

        Args:
            element: BeautifulSoup element
            config: Field configuration

        Returns:
            Extracted text or None
        """
        if config.get('attribute'):
            return element.get(config['attribute'], '').strip()
        return element.get_text(strip=True)

    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Parse price string to float.

        Args:
            price_str: Price string (e.g., "$70.00", "€49.99")

        Returns:
            Float price or None if parsing fails
        """
        if not price_str:
            return None
        # Remove currency symbols, whitespace, commas
        cleaned = re.sub(r'[$€£¥,\s]', '', str(price_str))
        try:
            return float(cleaned)
        except ValueError:
            return None

    def validate_extraction(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate extracted data quality.

        Args:
            data: Extracted product data

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields exist
        # Note: sizes_available is optional because it may be in JSON data rather than DOM
        required_fields = ['name', 'sale_price']
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")

        # If listed_price is missing but sale_price exists, use sale_price as listed_price
        # (This handles cases where there's no separate "was" price shown)
        if not data.get('listed_price') and data.get('sale_price'):
            data['listed_price'] = data['sale_price']

        # Validate prices are reasonable
        if data.get('sale_price'):
            if not (0 < data['sale_price'] < 10000):
                errors.append(f"Suspicious sale price: {data['sale_price']}")

        if data.get('listed_price') and data.get('sale_price'):
            if data['sale_price'] > data['listed_price']:
                errors.append(
                    f"Sale price ({data['sale_price']}) higher than "
                    f"listed price ({data['listed_price']})"
                )

        # Validate sizes format
        if data.get('sizes_available'):
            if not isinstance(data['sizes_available'], list):
                errors.append("sizes_available must be a list")
            elif len(data['sizes_available']) == 0:
                errors.append("sizes_available is empty (product may be out of stock)")

        return (len(errors) == 0, errors)


class ExtractionError(Exception):
    """Raised when direct extraction fails."""
    pass
