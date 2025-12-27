#!/usr/bin/env python3
"""Scrape all URLs from config."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.crawler import PriceCrawler
from src.database import Database


async def scrape_with_error_handling(crawler, db, item_config, index, total):
    """Scrape single item with error handling."""
    url = item_config.url
    colorway = item_config.colorway
    print(f"[{index}/{total}] Scraping: {url[:60]}...")
    if colorway:
        print(f"  Colorway: {colorway}")

    try:
        # Scrape with optional colorway
        data = await crawler.scrape_item(url, colorway=colorway)

        # Save to DB
        item_id = db.add_item_if_new(
            url=url,
            name=data.get('name', 'Unknown'),
            brand=data.get('brand', 'Unknown'),
            category=data.get('category', 'General')
        )

        db.insert_price_record(
            item_id=item_id,
            colorway_name=data.get('colorway_name'),
            listed_price=data.get('listed_price'),
            sale_price=data.get('sale_price'),
            sizes_available=data.get('sizes_available')
        )

        db.log_success(item_id)
        print(f"✓ Saved: {data['name']} - ${data['sale_price']}\n")

        return {"success": True, "url": url, "data": data}

    except Exception as e:
        print(f"✗ Error: {e}\n")
        db.log_error(None, str(e))
        return {"success": False, "url": url, "error": str(e)}


async def main():
    # Load config
    config = load_config("config/items.yaml")
    db = Database()

    print(f"Found {len(config.items)} URLs to scrape")
    print(f"Processing with max 5 concurrent requests\n")

    # Create crawler with context manager for browser reuse
    async with PriceCrawler() as crawler:
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

        async def limited_scrape(item_config, index):
            """Wrap scrape with semaphore to limit concurrency."""
            async with semaphore:
                return await scrape_with_error_handling(
                    crawler, db, item_config, index, len(config.items)
                )

        # Create tasks for all items
        tasks = [
            limited_scrape(item_config, i)
            for i, item_config in enumerate(config.items, 1)
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failures = len(results) - successes

        print("=" * 60)
        print(f"✓ Scraping complete!")
        print(f"  Successful: {successes}/{len(results)}")
        print(f"  Failed: {failures}/{len(results)}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
