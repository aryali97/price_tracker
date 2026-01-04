import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
import json
import re
from urllib.parse import urlparse


def extract_apollo_state(html: str) -> dict:
    """
    Extract Apollo GraphQL state from page HTML.

    Returns the full APOLLO_STATE object or None if not found.
    """
    # Find the start of the Apollo state assignment
    start_pattern = r"window\['APOLLO_STATE__product-mfe-web-service-ProductPageFrontend-config'\]\s*=\s*"
    start_match = re.search(start_pattern, html)

    if not start_match:
        return None

    # Find the starting position of the JSON
    start_pos = start_match.end()

    # Manually parse balanced braces to find the complete JSON object
    brace_count = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(html[start_pos:], start=start_pos):
        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found the end of the JSON object
                    apollo_json = html[start_pos:i+1]
                    try:
                        return json.loads(apollo_json)
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                        return None

    return None


def extract_colorways_from_apollo(apollo_data: dict, base_url: str) -> list:
    """
    Extract colorway information from Apollo state.

    Args:
        apollo_data: The parsed Apollo state object
        base_url: Base product URL

    Returns:
        List of colorway dicts: [
            {
                'colorway_name': 'white',
                'seq': '02',
                'url': 'https://...?seq=02',
                'kic_id': 'KIC_...',
                'image_url': 'https://...',
                'discount_price': '$48',
                'original_price': '$60'
            },
            ...
        ]
    """
    colorways = []

    # Navigate to ROOT_QUERY
    cache = apollo_data.get('CACHE', {})
    root_query = cache.get('ROOT_QUERY', {})

    # Find collection keys (they match pattern "collection(...)")
    for key, value in root_query.items():
        if key.startswith('collection('):
            # Access the collection and products
            if isinstance(value, dict) and 'collection' in value:
                collection = value['collection']
                products = collection.get('products', [])

                # Extract each product
                for product in products:
                    if not isinstance(product, dict):
                        continue

                    swatch_name = product.get('swatchName')
                    seq = product.get('defaultSwatchSequence')
                    kic_id = product.get('kicId')
                    image_url = product.get('swatchImageUrl')

                    # Extract prices
                    prices = product.get('prices', {})
                    price_list = prices.get('list', {})
                    discount_price = price_list.get('discountPrice')
                    original_price = price_list.get('originalPrice')

                    # Build the URL with seq parameter
                    parsed = urlparse(base_url)
                    # Remove any existing query params and add seq
                    colorway_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?seq={seq}"

                    if swatch_name and seq:
                        colorways.append({
                            'colorway_name': swatch_name,
                            'seq': seq,
                            'url': colorway_url,
                            'kic_id': kic_id,
                            'image_url': image_url,
                            'discount_price': discount_price,
                            'original_price': original_price
                        })

    # Sort by seq for consistent ordering
    colorways.sort(key=lambda x: x['seq'])

    return colorways


async def discover_colorways_test(url: str):
    """
    Test Apollo state extraction for colorway discovery.
    """
    browser_config = BrowserConfig(
        headless=True,  # Can be headless since no interaction needed
        user_agent_mode="random"
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        print(f"Fetching product page: {url}\n")

        config = CrawlerRunConfig(
            delay_before_return_html=3.0,  # Let JS execute and load Apollo state
            cache_mode="disabled"  # Ensure fresh data
        )

        result = await crawler.arun(url=url, config=config)

        # Extract Apollo state
        apollo_data = extract_apollo_state(result.html)

        if not apollo_data:
            print("ERROR: Could not find Apollo state in page")
            return {}

        # Extract colorways
        colorways = extract_colorways_from_apollo(apollo_data, url)

        print(f"Found {len(colorways)} colorways:\n")

        # Build mapping
        mapping = {}
        for cw in colorways:
            mapping[cw['colorway_name']] = {
                'seq': cw['seq'],
                'url': cw['url'],
                'kic_id': cw['kic_id'],
                'discount_price': cw['discount_price'],
                'original_price': cw['original_price']
            }
            price_str = f"{cw['discount_price']} (was {cw['original_price']})" if cw['discount_price'] else cw['original_price']
            print(f"  • {cw['colorway_name']:20s} → seq={cw['seq']:3s}  {price_str}")

        return mapping


async def main():
    test_url = "https://www.abercrombie.com/shop/us/p/essential-popover-hoodie-61791319"

    print("APOLLO STATE COLORWAY DISCOVERY TEST")
    print("="*60)

    mapping = await discover_colorways_test(test_url)

    if mapping:
        print(f"\n✓ Successfully extracted {len(mapping)} colorways")
    else:
        print("\n✗ No colorways discovered")


if __name__ == "__main__":
    asyncio.run(main())
