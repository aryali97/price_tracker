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

    def __init__(self):
        """Initialize the crawler."""
        self.groq_api_key = os.getenv('GROQ_API_KEY')

        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")

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
        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )
        self._browser = AsyncWebCrawler(config=browser_config)
        await self._browser.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser when exiting context."""
        if self._browser:
            await self._browser.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None

    async def scrape_item(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single product URL and extract pricing data.

        Args:
            url: Product URL to scrape

        Returns:
            Dictionary with extracted product data

        Raises:
            Exception: If scraping or extraction fails
        """
        print(f"Scraping: {url}")

        # Get the appropriate extractor
        extractor = self.get_extractor(url)
        print(f"Using extractor: {extractor.__class__.__name__}")

        # Configure crawler
        run_config = CrawlerRunConfig(
            word_count_threshold=5,
            cache_mode="bypass",  # Always fetch fresh data
            wait_until="networkidle",  # Wait for network to be idle
            page_timeout=60000,  # 60 second timeout
            delay_before_return_html=3.0,  # Wait 3 seconds after page load
        )

        # Scrape the page using existing browser or create new one
        if self._browser:
            # Use existing browser instance from context manager
            result = await self._browser.arun(url=url, config=run_config)
        else:
            # Fallback: create temporary browser for standalone use
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
            )
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            raise Exception(f"Failed to crawl URL: {url}")

        # Get the markdown content - use fit_markdown for reduced token usage
        markdown_content = (
            result.markdown_v2.fit_markdown
            if result.markdown_v2 and result.markdown_v2.fit_markdown
            else result.markdown_v2.raw_markdown if result.markdown_v2
            else result.markdown
        )

        # Use LLM to extract product data
        print("Extracting product data with LLM...")
        extracted_data = await self._extract_with_llm(
            markdown_content,
            extractor.get_extraction_prompt()
        )

        # Parse and normalize the data
        product_data = extractor.parse_llm_response(extracted_data)

        print(f"✓ Extracted: {product_data.get('name', 'Unknown')}")
        print(f"  Brand: {product_data.get('brand', 'Unknown')}")
        print(f"  Category: {product_data.get('category', 'Unknown')}")
        print(f"  Price: ${product_data.get('sale_price', 'N/A')}")
        print(f"  Sizes: {product_data.get('sizes_available', [])}")

        return product_data

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

    async def _extract_with_llm(self, markdown: str, prompt: str) -> str:
        """
        Extract structured data using Groq LLM.

        Args:
            markdown: Page content in markdown format
            prompt: Extraction prompt

        Returns:
            LLM response (should be JSON)
        """
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self.groq_api_key)

        # Extract the most relevant product section
        focused_markdown = self._extract_product_section(markdown, max_chars=20000)

        # Build the full prompt
        full_prompt = f"{prompt}\n\nPage content:\n\n{focused_markdown}"

        # Call Groq API
        try:
            chat_completion = await client.chat.completions.create(
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
                model="llama-3.3-70b-versatile",  # Updated model (llama-3.1 was decommissioned)
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000,
            )

            response = chat_completion.choices[0].message.content
            return response.strip()

        except Exception as e:
            raise Exception(f"LLM extraction failed: {e}")

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
