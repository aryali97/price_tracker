# Price Tracker - Project Context

## Project Overview
A clothing price tracker that crawls e-commerce websites (Abercrombie, Adidas, etc.) to monitor inventory and price changes over time. Uses AI-assisted crawling to handle varying site structures and dynamic content.

## Tech Stack
- **Python 3.x** - Core language
- **Crawl4AI** - Web crawling with AI extraction
- **SQLite** - Price history database (simple, file-based, no server needed)
- **Groq (Llama 3.1 70B)** - LLM for parsing HTML/extracting data
- **Conda** - Environment management
- **Cron** - Daily scheduled scraping

## Key Constraints & Considerations

1. **Anti-scraping measures**: Sites use throttling/spam prevention → Will use VPN/proxy rotation in future
2. **Variable site structures**: Different sites serve content differently → Using LLM + Crawl4AI for adaptive parsing
3. **Colorway complexity**: Some items (e.g., Abercrombie) show different prices for different colors at same URL → **SOLVED: Extract from Apollo GraphQL state**
4. **Deal detection**: Ongoing sales complicate pricing → Track both listed and sale prices

## Abercrombie Colorway Discovery Breakthrough

**Key Discovery**: Abercrombie embeds all colorway data in a JavaScript object on the page:
- **Apollo GraphQL state**: `window['APOLLO_STATE__product-mfe-web-service-ProductPageFrontend-config']`
- **Contains**: All colorways, seq IDs, prices, images in a single page load
- **No clicking needed**: Pure JSON extraction from HTML
- **Fast**: Single page load vs 20+ clicks through swatches

### Apollo State Structure
```json
{
  "CACHE": {
    "ROOT_QUERY": {
      "collection({\"collectionId\":\"682490\",\"faceout\":\"\",\"productId\":\"61414825\"})": {
        "collection": {
          "products": [
            {
              "swatchName": "white",
              "defaultSwatchSequence": "02",
              "kicId": "KIC_122-5454-00891-100",
              "prices": {
                "list": {
                  "discountPrice": "$48",
                  "originalPrice": "$60"
                }
              }
            },
            {
              "swatchName": "light brown",
              "defaultSwatchSequence": "03",
              "kicId": "KIC_122-5631-01161-406",
              "prices": {
                "list": {
                  "discountPrice": "$56",
                  "originalPrice": "$70"
                }
              }
            }
          ]
        }
      }
    }
  }
}
```

**Path**: `CACHE → ROOT_QUERY → collection(...) → collection → products[]`

### Extraction Benefits
✅ **10x faster** - Single page load vs clicking 20 swatches
✅ **Includes prices** - Discount and original prices per colorway
✅ **No JavaScript interaction** - Pure HTML parsing
✅ **Reliable** - No timing issues or anti-bot detection

**Note**: Size availability still requires visiting individual colorway URLs (`?seq=XX`)

## Database Schema (SQLite)

### `items` table
```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    scrape_frequency TEXT DEFAULT 'daily',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `price_history` table
```sql
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    colorway_name TEXT,
    listed_price REAL,
    sale_price REAL,
    sizes_available TEXT,  -- JSON stored as TEXT
    screenshot_url TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX idx_item_date ON price_history(item_id, scraped_at);
```

### `scrape_logs` table
```sql
CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success INTEGER,  -- 0 or 1 (SQLite doesn't have BOOLEAN)
    error_message TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
);
```

### `item_colorways` table (Planned - Milestone 4)
```sql
CREATE TABLE item_colorways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    colorway_name TEXT NOT NULL,
    colorway_url TEXT NOT NULL,
    seq_param TEXT,  -- The ?seq=XX parameter value
    is_tracked INTEGER DEFAULT 1,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scraped_at TIMESTAMP,
    UNIQUE(item_id, colorway_name),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE INDEX idx_item_colorways ON item_colorways(item_id, is_tracked);
```

**Purpose**: Store discovered colorways with their seq URLs for efficient re-scraping

**Workflow**:
1. **Discovery phase**: Extract all colorways from Apollo state → Insert into `item_colorways`
2. **Scraping phase**: Query tracked colorways → Visit each URL → Save sizes to `price_history`

**Notes:**
- `is_in_stock` field removed - determined by `sizes_available` (empty = out of stock)
- SQLite stores JSON as TEXT (automatically converted in Python)
- Database is a single file: `price_tracker.db`

## Project Structure

```
price_tracker/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration loader (YAML parsing)
│   ├── database.py            # MySQL connection & models
│   ├── crawler.py             # Crawl4AI wrapper & core scraping logic
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py           # Base extractor interface
│   │   └── abercrombie.py    # Abercrombie-specific extraction
│   └── utils.py              # Logging, error handling
├── config/
│   └── items.yaml            # URL tracking configuration
├── scripts/
│   ├── init_db.py            # Database initialization script
│   └── daily_scrape.py       # Cron job entry point
├── test.py                   # Existing test file (keep for experiments)
├── requirements.txt          # Conda dependencies
├── .env                      # API keys (GROQ_API_KEY, DB credentials)
├── CLAUDE.md                 # This file - project context
└── README.md                 # Setup instructions
```

## Milestones

### Milestone 1: MySQL Database Setup
- Create database schema and connection layer
- Files: `scripts/init_db.py`, `src/database.py`, `.env.example`

### Milestone 2: URL Configuration & Basic Scraping
- Allow users to configure URLs in YAML
- Scrape single items with LLM extraction
- Files: `config/items.yaml`, `src/config.py`, `src/crawler.py`, `src/extractors/`

### Milestone 3: Cron Job for Daily Scraping
- Automate daily price tracking
- Files: `scripts/daily_scrape.py`, `src/utils.py`

### Milestone 4: Multi-Colorway Support (In Progress)
- **Discovery**: Extract all colorways from Apollo GraphQL state (single page load)
- **Database**: Store colorways in `item_colorways` table with seq URLs
- **Scraping**: Visit each colorway URL to get size availability
- **No clicking needed**: Pure JSON extraction from embedded JavaScript object

**Current Status**: Building `test_apollo_extraction.py` to validate extraction approach

**Files**:
- `test_apollo_extraction.py` - Validation script
- `src/extractors/abercrombie.py` - Apollo state extraction methods
- `src/database.py` - Add `item_colorways` table and CRUD methods

### Milestone 5: Category Crawling
- Crawl entire category (e.g., all "Men's Polos")
- Auto-discover product URLs

### Milestone 6: Full Website Crawling
- Recursively crawl entire Abercrombie website
- Map site structure

### Milestone 7: Multi-Site Support
- Extend to Adidas, Nike, etc.
- Site-specific extractors

## Crawl4AI Integration

### Basic Setup
```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig

# Configure Groq LLM
llm_config = LLMConfig(
    provider="groq/llama-3.1-70b-versatile",
    api_token="env:GROQ_API_KEY"
)

browser_config = BrowserConfig(
    headless=True,
    enable_stealth=True,
    user_agent_mode="random"
)

run_config = CrawlerRunConfig(
    word_count_threshold=10,
    cache_mode="disabled"  # Always fresh data
)

async with AsyncWebCrawler(config=browser_config) as crawler:
    result = await crawler.arun(url=item_url, config=run_config)
```

### Apollo State Extraction (Abercrombie)
```python
import re
import json

# Extract Apollo state from HTML using balanced brace parsing
start_pattern = r"window\['APOLLO_STATE__product-mfe-web-service-ProductPageFrontend-config'\]\s*=\s*"
start_match = re.search(start_pattern, html)
start_pos = start_match.end()

# Parse balanced braces to get complete JSON
brace_count = 0
for i, char in enumerate(html[start_pos:], start=start_pos):
    if char == '{':
        brace_count += 1
    elif char == '}':
        brace_count -= 1
        if brace_count == 0:
            apollo_data = json.loads(html[start_pos:i+1])
            break

# Navigate to products: CACHE → ROOT_QUERY → collection(...) → collection → products[]
cache = apollo_data.get('CACHE', {})
root_query = cache.get('ROOT_QUERY', {})

colorways = []
for key, value in root_query.items():
    if key.startswith('collection('):
        products = value.get('collection', {}).get('products', [])

        for product in products:
            colorways.append({
                'name': product['swatchName'],
                'seq': product['defaultSwatchSequence'],
                'url': f"{base_url}?seq={product['defaultSwatchSequence']}",
                'discount_price': product.get('prices', {}).get('list', {}).get('discountPrice'),
                'original_price': product.get('prices', {}).get('list', {}).get('originalPrice')
            })
```

**Benefits**:
- Single page load gets all ~20 colorways
- No clicking, no timing issues
- Prices included in extraction
- Proper brace balancing handles complex JSON

## Configuration Format (YAML)

```yaml
items:
  - url: "https://www.abercrombie.com/shop/us/p/item-123"
    name: "Classic Polo Shirt"
    brand: "Abercrombie"
    category: "Tops"
    scrape_frequency: "daily"
```

## Environment Variables (.env)

```bash
# Database (SQLite)
DB_PATH=price_tracker.db

# Groq API
GROQ_API_KEY=your_groq_api_key

# Optional: Future proxy support
PROXY_ENABLED=false
PROXY_URL=
PROXY_USERNAME=
PROXY_PASSWORD=
```

## Dependencies

```
Crawl4AI==0.4.247
python-dotenv==1.0.1
pydantic==2.10.6
PyYAML==6.0.1
groq>=0.13.0
```

Note: SQLite is built into Python, no additional database driver needed!

## Key Technical Decisions

### VPN/Proxy (Future)
- Design for extensibility now
- Crawl4AI supports proxy in BrowserConfig
- Implement when rate limiting becomes an issue

### Error Handling
- 3 retry attempts with exponential backoff
- Graceful degradation (LLM fails → regex fallback)
- All errors logged to database + file

### LLM Cost Management
- Use Groq free tier (cheap/free)
- Cache site structure prompts
- Fallback to cached selectors if LLM fails
- Use cleaned HTML for smaller context

### Data Retention
- Keep daily data for 6 months
- Weekly snapshots for 6-12 months
- Monthly snapshots after 1 year

### Test Script Best Practices
- **Clean output only**: Print essential information to console
- **No file persistence**: Avoid saving test data to JSON/files unless specifically needed for debugging
- **Minimal dependencies**: Keep test scripts focused on validation, not production features
- **Remove debug code**: Clean up debugging statements before finalizing test scripts

## Current Status

### Completed Milestones

✅ **Milestone 1: Database setup (SQLite)**
  - Database auto-initializes on first use
  - No server configuration needed
  - Simple file-based storage

✅ **Milestone 2: URL configuration & basic scraping**
  - YAML configuration for tracking URLs
  - Crawl4AI integration with Groq LLM (llama-3.3-70b-versatile)
  - Smart product section extraction (finds prices/content automatically)
  - Abercrombie extractor with robust price parsing
  - Successfully extracts: name, prices, colors, sizes
  - Saves to database with full history tracking

### In Progress

🚧 **Milestone 4: Multi-Colorway Support**
  - **Breakthrough**: Discovered Apollo GraphQL state embedded in Abercrombie pages
  - **Current Task**: Building `test_apollo_extraction.py` to validate extraction
  - **What it does**:
    - Extracts all 20 colorways from single page load
    - Gets seq IDs for building colorway URLs (`?seq=02`, `?seq=24`, etc.)
    - Includes prices (discount and original) per colorway
    - No JavaScript clicking required - pure JSON parsing
  - **Next**:
    - Validate test script works
    - Add `item_colorways` table to database
    - Integrate into main crawler

### Deferred

⏸️ **Milestone 3: Cron job** - Will implement after colorway support is complete
