"""
Web crawler using Crawl4AI with LLM-based extraction.
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from dotenv import load_dotenv

from .extractors.base import BaseExtractor
from .extractors.abercrombie import AbercrombieExtractor

# Load environment variables
load_dotenv()


class PriceCrawler:
    """Crawler for extracting product prices using AI."""

    def __init__(self, provider_type: str = None):
        """
        Initialize the crawler.

        Args:
            provider_type: LLM provider type override (groq, local, auto).
                          If None, uses LLM_PROVIDER env var (default: groq)
        """
        # Create LLM provider using factory
        from .llm_providers import LLMProviderFactory
        self.llm_provider = LLMProviderFactory.create_provider(provider_type)
        print(f"LLM: {self.llm_provider.get_name()}")

        # Register extractors
        self.extractors: List[BaseExtractor] = [
            AbercrombieExtractor(),
        ]

        # Browser instance for context manager support
        self._browser = None

    def get_extractor(self, url: str) -> BaseExtractor:
        """
        Get the appropriate extractor for a URL.

        Args:
            url: Product URL

        Returns:
            Matching extractor

        Raises:
            ValueError: If no extractor matches the URL
        """
        for extractor in self.extractors:
            if extractor.matches_site(url):
                return extractor

        raise ValueError(f"No extractor found for URL: {url}")

    async def __aenter__(self):
        """Initialize browser when entering context."""
        # Configure browser with non-headless mode to bypass Abercrombie's bot detection
        # Abercrombie blocks headless browsers from loading color swatches
        browser_config = BrowserConfig(
            headless=False,  # Non-headless required for Abercrombie
            verbose=True,  # Enable to see JavaScript console logs
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        self._browser = AsyncWebCrawler(config=browser_config)
        await self._browser.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser when exiting context."""
        if self._browser:
            await self._browser.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None

    async def scrape_item(self, url: str, colorway: Optional[str] = None,
                          force_learn: bool = False) -> Dict[str, Any]:
        """
        Scrape a single product URL and extract pricing data.

        Strategy:
        1. Try DIRECT mode first (using saved recipe)
        2. Fall back to LEARN mode if no recipe or direct fails

        Args:
            url: Product URL to scrape
            colorway: Optional colorway name to select (e.g., "White", "Black")
            force_learn: Force learn mode even if recipe exists

        Returns:
            Dictionary with extracted product data

        Raises:
            Exception: If scraping or extraction fails
        """
        print(f"Scraping: {url}")
        if colorway:
            print(f"  Selecting colorway: {colorway}")

        # Get the appropriate extractor
        extractor = self.get_extractor(url)
        site_domain = extractor.extract_site_domain(url)
        print(f"Using extractor: {extractor.__class__.__name__}")

        # Import recipe manager
        from .recipe_manager import RecipeManager
        from .database import Database

        db = Database()
        recipe_manager = RecipeManager(db)

        # Determine extraction mode
        use_learn_mode = force_learn or recipe_manager.should_use_learn_mode(site_domain, url)

        if use_learn_mode:
            print("→ Mode: LEARN (will extract data + save recipe)")
            return await self._scrape_learn_mode(url, colorway, extractor, site_domain, recipe_manager)
        else:
            print("→ Mode: DIRECT (using saved recipe)")
            try:
                return await self._scrape_direct_mode(url, colorway, extractor, site_domain, recipe_manager)
            except Exception as e:
                print(f"⚠️  Direct mode failed: {e}")
                print("→ Falling back to LEARN mode")
                return await self._scrape_learn_mode(url, colorway, extractor, site_domain, recipe_manager)

    async def _scrape_direct_mode(self, url: str, colorway: Optional[str],
                                   extractor, site_domain: str,
                                   recipe_manager) -> Dict[str, Any]:
        """Extract using saved recipe (NO LLM)."""
        from .extractors.direct_extractor import DirectExtractor

        # Get recipe
        recipe = recipe_manager.get_active_recipe(site_domain)
        if not recipe:
            raise Exception("No active recipe found")

        # Fetch page (get HTML)
        result = await self._fetch_page(url, colorway, extractor)
        html = result.html

        # Extract using recipe
        direct_extractor = DirectExtractor(recipe)
        product_data = direct_extractor.extract(html)

        # Extract confidence
        confidence = product_data.pop('_extraction_confidence', 0.0)

        # Validate
        is_valid, errors = direct_extractor.validate_extraction(product_data)
        if not is_valid:
            recipe_manager.record_failure(recipe['id'])
            raise Exception(f"Validation failed: {errors}")

        # Record success
        recipe_manager.record_success(recipe['id'], confidence)

        print(f"✓ Direct extraction successful (confidence: {confidence:.2f})")
        print(f"  Product: {product_data.get('name', 'Unknown')}")
        print(f"  Price: ${product_data.get('sale_price', 'N/A')}")
        print(f"  Sizes: {product_data.get('sizes_available', [])}")

        # Add metadata
        product_data['_extraction_method'] = 'direct'
        product_data['_recipe_id'] = recipe['id']
        product_data['_confidence'] = confidence

        return product_data

    async def _scrape_learn_mode(self, url: str, colorway: Optional[str],
                                  extractor, site_domain: str,
                                  recipe_manager) -> Dict[str, Any]:
        """Extract using LLM and save recipe."""

        # Fetch page (need HTML for selector learning)
        result = await self._fetch_page(url, colorway, extractor)

        # Use focused product section - keep it concise to save tokens
        html = result.html
        focused_html = self._extract_product_section_html(html, max_chars=12000)

        # Use learn mode prompt
        prompt = extractor.get_learn_mode_prompt()

        # Extract with LLM
        print("Extracting with LLM (learn mode)...")
        llm_response = await self.llm_provider.extract(focused_html, prompt)

        # Parse response (data + recipe)
        parsed = extractor.parse_learn_mode_response(llm_response)
        product_data = parsed['data']
        recipe_data = parsed['recipe']

        # Save recipe (just the selectors part)
        recipe_id = recipe_manager.save_learned_recipe(site_domain, recipe_data['selectors'])

        print(f"✓ Learn mode successful, recipe saved (ID: {recipe_id})")
        print(f"  Product: {product_data.get('name', 'Unknown')}")
        print(f"  Price: ${product_data.get('sale_price', 'N/A')}")
        print(f"  Sizes: {product_data.get('sizes_available', [])}")

        # Add metadata
        product_data['_extraction_method'] = 'llm'
        product_data['_recipe_id'] = recipe_id
        product_data['_confidence'] = 1.0  # LLM extractions start at full confidence

        return product_data

    async def _fetch_page(self, url: str, colorway: Optional[str], extractor):
        """Fetch page HTML (with optional colorway selection)."""
        # Build JavaScript for colorway selection
        js_code = None
        if colorway:
            selectors = extractor.get_colorway_selectors()
            selectors_js = ', '.join([f"'{s}'" for s in selectors])

            # Build JavaScript that waits for swatches to load, then clicks
            # Updated to check nested img alt attributes (Abercrombie structure)
            js_code = (
                "(async()=>{"
                "const n='%s',s=%s;"
                # Wait longer for swatches to load (anti-bot detection can slow things)
                "await new Promise(r=>setTimeout(r,3000));"
                "console.log('[COLORWAY] Starting search for:',n);"
                "for(const e of s){"
                "const t=document.querySelectorAll(e);"
                "console.log('[COLORWAY] Selector',e,'found',t.length,'elements');"
                "for(let i=0;i<t.length;i++){"
                "const el=t[i];"
                # Check element attributes
                "let txt=(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('title')||'')+' '+"
                "(el.getAttribute('alt')||'')+' '+(el.getAttribute('href')||'')+' '+(el.textContent||'').trim();"
                # Also check nested img alt (Abercrombie uses this)
                "const img=el.querySelector('img');"
                "if(img){txt+=' '+(img.getAttribute('alt')||'')+(img.getAttribute('title')||'');}"
                "txt=txt.toLowerCase();"
                "console.log('[COLORWAY] Element',i,'text:',txt.substring(0,80));"
                "if(txt.includes(n.toLowerCase())){"
                "console.log('[COLORWAY] FOUND! Clicking element',i);"
                "el.scrollIntoView({block:'center'});"
                "await new Promise(r=>setTimeout(r,500));"
                "el.click();"
                "await new Promise(r=>setTimeout(r,5000));"
                "console.log('[COLORWAY] Click complete');"
                "return true"
                "}"
                "}"
                "}"
                "console.log('[COLORWAY] Not found');"
                "return false"
                "})()"
            ) % (colorway, f"[{selectors_js}]")

        # Configure crawler
        run_config_params = {
            "word_count_threshold": 5,
            "cache_mode": "bypass",
            "wait_until": "networkidle",
            "page_timeout": 60000,
            "delay_before_return_html": 3.0,
        }

        if js_code:
            run_config_params["js_code"] = [js_code]
            run_config_params["delay_before_return_html"] = 6.0

        run_config = CrawlerRunConfig(**run_config_params)

        # Scrape
        if self._browser:
            result = await self._browser.arun(url=url, config=run_config)
        else:
            browser_config = BrowserConfig(
                headless=False,  # Non-headless required for Abercrombie
                verbose=False,
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            )
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            raise Exception(f"Failed to crawl URL: {url}")

        return result

    def _extract_product_section(self, markdown: str, max_chars: int = 20000) -> str:
        """
        Extract the most relevant product section from markdown.

        Args:
            markdown: Full markdown content
            max_chars: Maximum characters to return

        Returns:
            Focused markdown section with product info
        """
        import re

        # Look for common price patterns to identify product section
        price_pattern = r'\$\s*\d+(?:\.\d{2})?'
        price_matches = list(re.finditer(price_pattern, markdown))

        if price_matches:
            # Find the densest cluster of prices (likely the product section)
            # Get position of first substantial price occurrence
            for match in price_matches:
                pos = match.start()
                # Extract a window around the price
                # Look back 3000 chars and forward 15000 chars from first price
                start = max(0, pos - 3000)
                end = min(len(markdown), pos + 15000)
                section = markdown[start:end]

                # Make sure we got substantial content
                if len(section) > 5000:
                    return section

        # Fallback: look for h1/h2 headers (often product titles)
        header_pattern = r'^#{1,2}\s+[A-Z].*$'
        header_matches = list(re.finditer(header_pattern, markdown, re.MULTILINE))

        if header_matches:
            pos = header_matches[0].start()
            start = max(0, pos - 1000)
            end = min(len(markdown), start + max_chars)
            return markdown[start:end]

        # Final fallback: skip nav (first 20%) and take middle section
        skip = len(markdown) // 5
        return markdown[skip:skip + max_chars]

    def _extract_product_section_html(self, html: str, max_chars: int = 15000) -> str:
        """
        Extract focused HTML section containing product information.

        Args:
            html: Full HTML content
            max_chars: Maximum characters to return

        Returns:
            Focused HTML section with product info
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')

        # Try to find the main product container
        # Common patterns for product sections
        product_selectors = [
            '[data-testid*="product"]',
            '[class*="product-detail"]',
            '[class*="product-info"]',
            '[class*="ProductDetail"]',
            'main',
            '[role="main"]',
        ]

        product_section = None
        for selector in product_selectors:
            product_section = soup.select_one(selector)
            if product_section:
                break

        if product_section:
            html_str = str(product_section)
        else:
            # Fallback: use body
            body = soup.find('body')
            html_str = str(body) if body else html

        # Trim if too long
        if len(html_str) > max_chars:
            html_str = html_str[:max_chars]

        return html_str

    async def _extract_with_llm(self, markdown: str, prompt: str) -> str:
        """
        Extract structured data using configured LLM provider.

        Args:
            markdown: Page content in markdown format
            prompt: Extraction prompt

        Returns:
            LLM response (should be JSON)
        """
        # Extract the most relevant product section (keep preprocessing)
        focused_markdown = self._extract_product_section(markdown, max_chars=12000)

        # Delegate to provider
        return await self.llm_provider.extract(focused_markdown, prompt)

    async def scrape_multiple(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of product URLs

        Returns:
            Dictionary mapping URLs to extracted data
        """
        results = {}

        for url in urls:
            try:
                data = await self.scrape_item(url)
                results[url] = {"success": True, "data": data}
            except Exception as e:
                results[url] = {"success": False, "error": str(e)}
                print(f"✗ Failed to scrape {url}: {e}")

        return results


async def test_crawler():
    """Test the crawler with a sample URL."""
    crawler = PriceCrawler()

    # Test URL
    url = "https://www.abercrombie.com/shop/us/p/essential-popover-hoodie-61791319"

    try:
        data = await crawler.scrape_item(url)
        print("\n" + "=" * 50)
        print("Extraction successful!")
        print("=" * 50)
        print(f"Product: {data.get('name')}")
        print(f"Listed Price: ${data.get('listed_price')}")
        print(f"Sale Price: ${data.get('sale_price')}")
        print(f"Color: {data.get('colorway_name')}")
        print(f"Sizes: {data.get('sizes_available')}")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_crawler())
