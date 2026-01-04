# Price Tracker

A clothing price tracker that crawls e-commerce websites (Abercrombie, Adidas, etc.) to monitor inventory and price changes over time. Uses AI-assisted crawling with a "learn once, reuse selectors" architecture for fast, cost-effective scraping.

## Features

- **Smart Extraction**: First scrape uses LLM to learn CSS selectors, subsequent scrapes use direct HTML parsing (99%+ cost reduction)
- **Multi-Site Support**: Extensible architecture for tracking multiple e-commerce sites
- **Price History**: SQLite database tracks price changes over time
- **Colorway Support**: Handles products with multiple color variations
- **Automated Scraping**: Cron job support for daily price monitoring

## Tech Stack

- **Python 3.12** - Core language
- **Crawl4AI** - Web crawling with AI extraction
- **SQLite** - Price history database
- **Groq (Llama 3.3 70B)** - LLM for learning CSS selectors
- **BeautifulSoup** - Fast direct HTML parsing
- **Playwright** - Headless browser automation

## Setup Instructions (Mac M3)

### 1. Install Conda (if not already installed)

```bash
# Download Miniconda for Apple Silicon
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh
# Follow the prompts, then restart your terminal
```

### 2. Create and Activate Conda Environment

```bash
# Create a new conda environment with Python 3.12
conda create -n price_tracker python=3.12 -y

# Activate the environment
conda activate price_tracker
```

### 3. Install Python Dependencies

```bash
# Navigate to the project directory
cd /path/to/price_tracker

# Install required packages
pip install -r requirements.txt

# Install Playwright browser drivers
python -m playwright install
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Database (SQLite - no configuration needed, uses local file)
DB_PATH=price_tracker.db

# Groq API (get free API key from https://console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# Optional: Ollama (for local LLM support)
OLLAMA_ENABLED=false
OLLAMA_MODEL=llama3.2

# Optional: Future proxy support
PROXY_ENABLED=false
```

### 5. Initialize Database

The database initializes automatically on first use, but you can verify it works:

```bash
python -c "from src.database import Database; db = Database(); print('✓ Database initialized')"
```

### 6. Test the Setup

```bash
# Test the recipe system
python test_recipe_system.py

# Or run a single item scrape
python scripts/scrape_all.py
```

## Project Structure

```
price_tracker/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration loader (YAML parsing)
│   ├── database.py            # SQLite connection & models
│   ├── crawler.py             # Crawl4AI wrapper & scraping logic
│   ├── recipe_manager.py      # Learn/direct mode orchestration
│   ├── llm_providers/         # LLM provider abstraction (Groq, Ollama)
│   ├── extractors/
│   │   ├── base.py           # Base extractor interface
│   │   ├── direct_extractor.py # BeautifulSoup-based extraction
│   │   └── abercrombie.py    # Abercrombie-specific extraction
│   └── utils.py              # Logging, error handling
├── config/
│   └── items.yaml            # URL tracking configuration
├── scripts/
│   ├── init_db.py            # Database initialization
│   └── scrape_all.py         # Scrape all configured items
├── tests/
│   └── test_recipe_system.py # End-to-end tests
├── requirements.txt          # Python dependencies
├── .env                      # API keys (create this)
├── CLAUDE.md                 # Project context for Claude
└── README.md                 # This file
```

## Database Schema

### `items` table
Tracks which product URLs to monitor.

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
Records price snapshots for each scrape.

```sql
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    colorway_name TEXT,
    listed_price REAL,
    sale_price REAL,
    sizes_available TEXT,  -- JSON stored as TEXT
    extraction_method TEXT DEFAULT 'llm',  -- 'llm' or 'direct'
    recipe_id INTEGER,     -- FK to extraction_recipes
    extraction_confidence REAL,
    screenshot_url TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);
```

### `extraction_recipes` table
Stores learned CSS selectors for fast direct extraction.

```sql
CREATE TABLE extraction_recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_domain TEXT NOT NULL,
    recipe_version INTEGER DEFAULT 1,
    selectors TEXT NOT NULL,  -- JSON with CSS selectors
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_successful_use TIMESTAMP,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    avg_confidence REAL,
    UNIQUE(site_domain, recipe_version)
);
```

### `scrape_logs` table
Tracks scraping success/failure for debugging.

```sql
CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success INTEGER,  -- 0 or 1
    error_message TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
);
```

## How It Works

### Learn Once, Reuse Selectors Architecture

**First Scrape (Learn Mode)**:
1. Crawl4AI fetches the page HTML
2. Focused HTML section sent to LLM (Groq Llama 3.3 70B)
3. LLM extracts product data AND learns CSS selectors
4. Selectors saved as "recipe" in database (versioned)
5. Cost: ~$0.001, Time: 5-15s

**Subsequent Scrapes (Direct Mode)**:
1. Crawl4AI fetches the page HTML
2. BeautifulSoup + saved CSS selectors extract data directly
3. No LLM needed!
4. Cost: $0, Time: ~2s (2-7x faster)

**Automatic Fallback**:
- If direct mode fails (>30% failure rate), automatically re-learns
- Creates new recipe version, marks old as inactive
- Handles site changes gracefully

### Cost Savings

- **Before**: Every scrape uses LLM (~$0.001/scrape)
- **After**: Only first scrape per site uses LLM
- **Savings**: 99.7% cost reduction for daily tracking

Example: 100 items/day × 365 days = 36,500 scrapes/year
- Before: $36.50/year
- After: $0.10/year

## Configuration

### Adding Items to Track

Edit `config/items.yaml`:

```yaml
items:
  - url: "https://www.abercrombie.com/shop/us/p/essential-popover-hoodie-61791319"
    name: "Essential Popover Hoodie"
    brand: "Abercrombie"
    category: "Hoodies"
    scrape_frequency: "daily"
```

### Running Daily Scrapes

Set up a cron job:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/price_tracker && /path/to/conda/envs/price_tracker/bin/python scripts/scrape_all.py
```

## Troubleshooting

### Playwright Browser Not Found

If you see `FileNotFoundError: [Errno 2] No such file or directory: '.../playwright/driver/node'`:

```bash
conda activate price_tracker
python -m playwright install
```

### Groq API Rate Limits

Free tier: 30 requests/minute. For heavy usage:
- Add delays between scrapes
- Use Ollama for local LLM (see CLAUDE.md)

### Database Locked

SQLite can have locking issues with concurrent access:
- Run scrapes sequentially, not in parallel
- Or consider upgrading to PostgreSQL for production

## Development

### Running Tests

```bash
# End-to-end recipe system test
python test_recipe_system.py

# Test database operations
python -c "from src.database import Database; db = Database(); print(db.get_all_items())"
```

### Adding a New Site Extractor

1. Create `src/extractors/yoursite.py` extending `BaseExtractor`
2. Implement `get_learn_mode_prompt()` with site-specific instructions
3. Register in `crawler.py`'s `get_extractor()` method

See `src/extractors/abercrombie.py` as example.

## License

MIT License

## Contributing

Pull requests welcome! Please ensure tests pass before submitting.

## Support

For issues or questions, check `CLAUDE.md` for detailed project context.
