#!/usr/bin/env python3
"""Test script for the price scraper."""

import asyncio
from src.crawler import PriceCrawler
from src.database import Database


async def main():
    print("=" * 60)
    print("Testing Price Scraper")
    print("=" * 60)
    print()

    # Initialize
    crawler = PriceCrawler()
    db = Database()

    # Test URL
    url = "https://www.abercrombie.com/shop/us/p/essential-popover-hoodie-61791319?categoryId=12202&faceout=life&seq=48&pagefm=navigation-grid&prodvm=navigation-grid"

    try:
        # Scrape the item
        print(f"Scraping: {url[:80]}...")
        print()
        data = await crawler.scrape_item(url)

        print("\n" + "=" * 60)
        print("Extraction Successful!")
        print("=" * 60)
        print(f"Product Name: {data.get('name')}")
        print(f"Listed Price: ${data.get('listed_price')}")
        print(f"Sale Price: ${data.get('sale_price')}")
        print(f"Color: {data.get('colorway_name', 'N/A')}")
        print(f"Sizes Available: {data.get('sizes_available', [])}")
        print("=" * 60)
        print()

        # Save to database
        print("Saving to database...")

        # First, add the item if it doesn't exist (using scraped data!)
        item_id = db.add_item_if_new(
            url=url,
            name=data.get('name', 'Unknown Item'),
            brand=data.get('brand', 'Unknown'),
            category=data.get('category', 'General')
        )

        # Then save the price record
        price_id = db.insert_price_record(
            item_id=item_id,
            colorway_name=data.get('colorway_name'),
            listed_price=data.get('listed_price'),
            sale_price=data.get('sale_price'),
            sizes_available=data.get('sizes_available')
        )

        # Log success
        db.log_success(item_id)

        print(f"✓ Saved to database (Item ID: {item_id}, Price ID: {price_id})")
        print()

        # Show history
        print("Price History:")
        history = db.get_item_history(item_id, limit=5)
        for i, record in enumerate(history, 1):
            print(f"  {i}. {record['scraped_at']} - ${record['sale_price']} ({len(record.get('sizes_available', []))} sizes)")

        print()
        print("=" * 60)
        print("✓ Test Complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
