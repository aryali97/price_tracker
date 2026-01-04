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

    def get_learn_mode_prompt(self) -> str:
        """
        Get the LLM prompt for learn mode - extracts data AND selectors.

        Returns:
            Prompt string that asks LLM to return both data and CSS selectors
        """
        return """You are analyzing an e-commerce product page to extract BOTH product data AND the CSS selectors used to find that data.

Your task:
1. Extract the product information (name, price, sizes, etc.)
2. Identify the CSS selectors that would reliably find each piece of data

Return a JSON object with TWO sections:

{
  "data": {
    "name": "Product name",
    "brand": "Brand name",
    "category": "Category (e.g., Hoodies, Jackets)",
    "listed_price": 70.00,
    "sale_price": 56.00,
    "colorway_name": "Color name or null",
    "sizes_available": ["XS", "S", "M", "L"]
  },
  "selectors": {
    "name": {
      "primary": "h1.product-title",
      "fallbacks": [".product-name", "h1[data-testid='product-title']"],
      "extraction": "text",
      "required": true
    },
    "brand": {
      "primary": ".product-brand",
      "fallbacks": ["meta[property='og:brand']"],
      "attribute": "content",
      "extraction": "text",
      "required": false
    },
    "category": {
      "primary": ".breadcrumb-item:last-child",
      "fallbacks": [".product-category"],
      "extraction": "text",
      "required": false
    },
    "listed_price": {
      "primary": ".price-was",
      "fallbacks": [".original-price", ".price-list"],
      "extraction": "price",
      "required": true
    },
    "sale_price": {
      "primary": ".price-now",
      "fallbacks": [".current-price", ".price-sale"],
      "extraction": "price",
      "required": true
    },
    "colorway_name": {
      "primary": ".color-selected",
      "fallbacks": ["button[aria-pressed='true'][data-testid^='swatch-']"],
      "attribute": "aria-label",
      "extraction": "text",
      "required": false
    },
    "sizes_available": {
      "primary": "button.size-button:not([disabled])",
      "fallbacks": [".size-selector option:not([disabled])", "button[data-testid^='size-']:not([disabled])"],
      "extraction": "list_text",
      "required": true
    }
  }
}

CRITICAL RULES FOR SELECTORS:
- Use CSS selectors ONLY (not XPath)
- "primary" selector should be the MOST RELIABLE selector you found in the HTML
- "fallbacks" should be alternative selectors that could also work
- Be specific enough to avoid false matches, but generic enough to work across similar pages
- For prices: always use extraction type "price"
- For lists (like sizes): use extraction type "list_text"
- For single text values: use extraction type "text"
- If extracting from HTML attribute (like meta tags): specify "attribute" field

SELECTOR QUALITY GUIDELINES:
- PREFER: Class names, data attributes, semantic HTML tags
- AVOID: Generic tags without qualifiers, positional selectors (nth-child)
- Example GOOD: "button.size-button:not([disabled])"
- Example BAD: "div > div > span:nth-child(3)"

ABERCROMBIE-SPECIFIC PRICE SELECTORS:
- Listed/original price: use .product-price-text[data-variant="original"]
- Sale/discount price: use .product-price-text[data-variant="discount"]
- Both prices have the same class but different data-variant attributes

For "required" field:
- true for critical fields (name, prices, sizes)
- false for optional fields (brand, category, color)

Return ONLY the JSON object with no explanatory text before or after."""

    def get_colorway_selectors(self) -> List[str]:
        """
        Get CSS selectors for Abercrombie color swatches.

        Note: Abercrombie uses <a> tags inside swatch tile groups for colors.
        Color names are typically in nested img alt attributes or hrefs.

        Returns:
            List of CSS selectors to try
        """
        return [
            '[data-testid="swatch-tile-group"] a',
            '.swatch-tile-group a',
            '[class*="swatch"] a',
            'button[aria-label*="color"]'
        ]
