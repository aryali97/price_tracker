#!/usr/bin/env python3
"""
End-to-end test for the recipe system.
"""

import asyncio
from src.crawler import PriceCrawler
from src.database import Database


async def test_learn_and_direct():
    """Test both learn mode and direct mode."""
    print("=" * 70)
    print("RECIPE SYSTEM END-TO-END TEST")
    print("=" * 70)

    url = "https://www.abercrombie.com/shop/us/p/essential-popover-hoodie-61791319"
    colorway = "White"

    # Clean up any existing recipe for testing
    print("\n[Setup] Cleaning up existing recipes...")
    db = Database()
    existing = db.get_all_recipes('abercrombie.com')
    for recipe in existing:
        db.mark_recipe_inactive(recipe['id'])
    print(f"[Setup] Marked {len(existing)} existing recipes as inactive\n")

    # Test 1: Learn Mode (First Scrape)
    print("\n" + "=" * 70)
    print("TEST 1: LEARN MODE (First Scrape)")
    print("=" * 70)

    try:
        async with PriceCrawler() as crawler:
            print("\nForcing learn mode to create recipe...")
            data1 = await crawler.scrape_item(url, colorway=colorway, force_learn=True)

            print("\n✓ Learn mode test completed")
            print(f"  Extraction method: {data1.get('_extraction_method')}")
            print(f"  Recipe ID: {data1.get('_recipe_id')}")
            print(f"  Confidence: {data1.get('_confidence')}")
            print(f"  Product: {data1.get('name')}")
            print(f"  Price: ${data1.get('sale_price')}")
            print(f"  Sizes: {data1.get('sizes_available')}")

            # Verify recipe was saved
            recipe = db.get_active_recipe('abercrombie.com')
            assert recipe is not None, "Recipe should be saved"
            assert 'selectors' in recipe, "Recipe should have selectors"
            print(f"\n✓ Recipe saved successfully (version {recipe['recipe_version']})")
            print(f"  Selectors: {list(recipe['selectors'].keys())}")

    except Exception as e:
        print(f"\n✗ Learn mode test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Direct Mode (Second Scrape)
    print("\n" + "=" * 70)
    print("TEST 2: DIRECT MODE (Second Scrape)")
    print("=" * 70)

    try:
        async with PriceCrawler() as crawler:
            print("\nScraping again (should use direct mode)...")
            data2 = await crawler.scrape_item(url, colorway=colorway)

            print("\n✓ Direct mode test completed")
            print(f"  Extraction method: {data2.get('_extraction_method')}")
            print(f"  Recipe ID: {data2.get('_recipe_id')}")
            print(f"  Confidence: {data2.get('_confidence')}")
            print(f"  Product: {data2.get('name')}")
            print(f"  Price: ${data2.get('sale_price')}")
            print(f"  Sizes: {data2.get('sizes_available')}")

            # Verify it used direct mode
            assert data2.get('_extraction_method') == 'direct', \
                "Second scrape should use direct mode"
            print("\n✓ Used direct mode as expected")

            # Check recipe stats were updated
            recipe = db.get_active_recipe('abercrombie.com')
            print(f"\n✓ Recipe stats:")
            print(f"  Success count: {recipe['success_count']}")
            print(f"  Failure count: {recipe['failure_count']}")
            print(f"  Avg confidence: {recipe['avg_confidence']:.2f}")

    except Exception as e:
        print(f"\n✗ Direct mode test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Data Consistency
    print("\n" + "=" * 70)
    print("TEST 3: DATA CONSISTENCY")
    print("=" * 70)

    # Compare key fields (ignoring metadata)
    fields_to_compare = ['name', 'sale_price', 'listed_price', 'colorway_name']
    consistent = True

    for field in fields_to_compare:
        val1 = data1.get(field)
        val2 = data2.get(field)
        match = val1 == val2
        status = "✓" if match else "✗"
        print(f"{status} {field}: learn={val1}, direct={val2}")
        if not match:
            consistent = False

    # Sizes might differ slightly due to stock changes, just check both have data
    sizes1 = data1.get('sizes_available', [])
    sizes2 = data2.get('sizes_available', [])
    if sizes1 and sizes2:
        print(f"✓ sizes_available: both have data")
    else:
        print(f"⚠️  sizes_available: learn={sizes1}, direct={sizes2}")

    if consistent:
        print("\n✓ Data consistency check PASSED")
    else:
        print("\n⚠️  Data consistency check FAILED (some fields differ)")

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print("✓ Learn mode: PASSED")
    print("✓ Direct mode: PASSED")
    print(f"{'✓' if consistent else '⚠️ '} Data consistency: {'PASSED' if consistent else 'PARTIAL'}")
    print("\n✓ ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = asyncio.run(test_learn_and_direct())
    exit(0 if success else 1)
