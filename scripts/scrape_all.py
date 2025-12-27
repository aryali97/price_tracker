#!/usr/bin/env python3
"""Scrape all URLs from config."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.crawler import PriceCrawler
from src.database import Database


async def main():
    # Load config
    config = load_config("config/items.yaml")

    # Initialize
    crawler = PriceCrawler()
    db = Database()

    print(f"Found {len(config.items)} URLs to scrape\n")

    for i, item_config in enumerate(config.items, 1):
        url = item_config.url
        print(f"[{i}/{len(config.items)}] Scraping: {url[:60]}...")

        try:
            # Scrape
            data = await crawler.scrape_item(url)

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

        except Exception as e:
            print(f"✗ Error: {e}\n")
            db.log_error(None, str(e))

    print("=" * 60)
    print("✓ Scraping complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
