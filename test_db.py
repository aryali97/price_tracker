#!/usr/bin/env python3
"""Quick test to verify database functionality."""

from src.database import Database

def main():
    print("Testing database functionality...")
    print()

    db = Database()

    # Test 1: Add an item
    print("Test 1: Adding item...")
    item_id = db.add_item(
        url="https://www.abercrombie.com/shop/us/p/test-item",
        name="Test Polo Shirt",
        brand="Abercrombie",
        category="Tops"
    )
    print(f"✓ Item added with ID: {item_id}")
    print()

    # Test 2: Get item by URL
    print("Test 2: Retrieving item by URL...")
    item = db.get_item_by_url("https://www.abercrombie.com/shop/us/p/test-item")
    print(f"✓ Found item: {item['name']} (ID: {item['id']})")
    print()

    # Test 3: Insert price record
    print("Test 3: Adding price record...")
    price_id = db.insert_price_record(
        item_id=item_id,
        colorway_name="Navy Blue",
        listed_price=49.99,
        sale_price=29.99,
        sizes_available=["S", "M", "L", "XL"]
    )
    print(f"✓ Price record added with ID: {price_id}")
    print()

    # Test 4: Get item history
    print("Test 4: Retrieving price history...")
    history = db.get_item_history(item_id)
    print(f"✓ Found {len(history)} price record(s)")
    print(f"  Latest: ${history[0]['sale_price']} (was ${history[0]['listed_price']})")
    print(f"  Sizes: {history[0]['sizes_available']}")
    print()

    # Test 5: Log scrape success
    print("Test 5: Logging scrape...")
    db.log_success(item_id)
    print("✓ Scrape logged successfully")
    print()

    # Test 6: Get logs
    print("Test 6: Retrieving logs...")
    logs = db.get_scrape_logs(item_id)
    print(f"✓ Found {len(logs)} log entry(ies)")
    print()

    print("=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
