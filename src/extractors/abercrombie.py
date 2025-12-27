"""
Abercrombie & Fitch specific extractor.
"""

from typing import List
from .base import BaseExtractor


class AbercrombieExtractor(BaseExtractor):
    """Extractor for Abercrombie & Fitch products."""

    PRODUCT_PATTERN = r'abercrombie\.com/shop/[a-z]{2}/p/'

    def get_extraction_prompt(self) -> str:
        """
        Get the LLM prompt for extracting Abercrombie product data.

        Returns:
            Prompt string for LLM
        """
        return """Extract product information from this e-commerce product page.

Look for:
1. Product name/title (usually in headers or near the top)
2. Brand name (often in logo, header, navigation, or product details)
3. Category (from breadcrumbs, URL path, or product type - e.g., "Hoodies", "Jackets", "Shoes")
4. Prices - look for patterns like "Was $X, now $Y" or "$X" or "Price: $X"
   - "Was" price = listed_price (original price)
   - "now" price or current price = sale_price
5. Color/colorway currently selected
6. Available sizes (look for size selectors, buttons, or lists)

Return ONLY a JSON object in this exact format:
{
    "name": "Product name as string",
    "brand": "Brand name as string",
    "category": "Category as string (e.g., Hoodies, Jackets, Shoes)",
    "listed_price": 70.00,
    "sale_price": 56.00,
    "colorway_name": "Color name as string or null",
    "sizes_available": ["XS", "S", "M", "L", "XL"]
}

Rules:
- Prices must be numbers (e.g., 56.00, not "$56" or "56")
- If item is not on sale, listed_price and sale_price are the same
- Only include sizes that are in stock (ignore "Sold Out" or unavailable sizes)
- For brand: look for the company/brand name (not the product line)
- For category: be specific but general (e.g., "Hoodies" not "Men's Essential Hoodies")
- If you cannot find a field, use null (except sizes_available which should be [])

JSON output:"""

    def get_colorway_selectors(self) -> List[str]:
        """
        Get CSS selectors for Abercrombie color swatches.

        Returns:
            List of CSS selectors to try
        """
        return [
            'button[data-testid^="swatch-"]',
            '.product-swatch',
            '[class*="ColorSwatch"]',
            'button[aria-label*="color"]'
        ]
