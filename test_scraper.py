"""
H&M Hong Kong Product Scraper
Scrapes men's t-shirts & tanks from the H&M listing API.
Saves products, color variants, and a raw JSON sample to SQLite.

Phase 1: One-time full snapshot.
Designed to be re-run safely (idempotent via INSERT OR REPLACE).
"""

import requests
import sqlite3
import json
import time
import logging
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────

CATEGORY_ID   = "men_tshirtstanks"
PAGE_ID       = "/men/shop-by-product/t-shirts-and-tanks"
BASE_URL      = "https://api.hm.com/search-services/v1/en_hk/listing/resultpage"
PAGE_SIZE     = 36
DB_FILE       = "./data/hm_products.db"
RAW_JSON_FILE = "./data/hm_raw_sample.json"   # saves the first page response as a sample

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Database setup ────────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id      TEXT PRIMARY KEY,
            name            TEXT,
            gender          TEXT,
            category        TEXT,
            current_price   REAL,
            origin_price    REAL,
            on_sale         INTEGER,
            stock_status    TEXT,
            main_image_url  TEXT,
            model_image_url TEXT,
            fit             TEXT,
            pattern         TEXT,
            neckline        TEXT,
            sleeve_length   TEXT,
            material        TEXT,
            tags            TEXT,
            new_arrival     INTEGER,
            product_url     TEXT,
            scraped_at      TEXT,
            raw_json        TEXT
        );

        CREATE TABLE IF NOT EXISTS color_variants (
            product_id          TEXT NOT NULL,
            color_code          TEXT NOT NULL,
            color_name          TEXT,
            color_hex           TEXT,
            color_product_image TEXT,
            color_in_stock      INTEGER,
            scraped_at          TEXT NOT NULL,
            PRIMARY KEY (product_id, color_code, scraped_at)
        );
    """)
    conn.commit()

# ── API helpers ───────────────────────────────────────────────────────────────

def fetch_page(page: int, session: requests.Session) -> dict:
    """Fetch one page of products from the H&M listing API."""
    params = {
        "pageSource":    "PLP",
        "page":          page,
        "sort":          "RELEVANCE",
        "pageId":        PAGE_ID,
        "page-size":     PAGE_SIZE,
        "categoryId":    CATEGORY_ID,
        "filters":       "sale:false||oldSale:false",
        "touchPoint":    "DESKTOP",
        "skipStockCheck":"false",
    }
    resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()

# ── Parsing helpers ───────────────────────────────────────────────────────────

def extract_fit(product_name: str) -> str:
    """Pull fit type from the product name string."""
    for fit in ["Slim Fit", "Loose Fit", "Regular Fit", "Relaxed Fit",
                "Oversized Fit", "Muscle Fit", "Compression Fit"]:
        if fit.lower() in product_name.lower():
            return fit
    return ""

def parse_product(item: dict, scraped_at: str) -> dict:
    """Map one raw API product dict to our schema."""
    prices   = item.get("prices", [{}])
    price    = prices[0].get("price") if prices else None
    on_sale  = any(p.get("priceType") == "redPrice" for p in prices)

    markers  = [m.get("text", "") for m in item.get("productMarkers", [])]
    tags_str = ", ".join(markers) if markers else ""

    product_name = item.get("productName", "")

    return {
        "product_id":      item.get("id"),
        "name":            product_name,
        "gender":          "Men",
        "category":        item.get("mainCatCode"),
        "current_price":   price,
        "origin_price":    price,          # H&M API doesn't separate these
        "on_sale":         int(on_sale),
        "stock_status":    item.get("availability", {}).get("stockState"),
        "main_image_url":  item.get("productImage"),
        "model_image_url": item.get("modelImage"),
        "fit":             extract_fit(product_name),
        "pattern":         "",             # available in facets, not per-product
        "neckline":        "",             # same — facet-level only
        "sleeve_length":   "",             # same
        "material":        "",             # same
        "tags":            tags_str,
        "new_arrival":     int(item.get("newArrival", False)),
        "product_url":     "https://www2.hm.com" + item.get("url", ""),
        "scraped_at":      scraped_at,
        "raw_json":        json.dumps(item),
    }

def parse_colors(item: dict, scraped_at: str) -> list[dict]:
    """Extract color variant rows from a product item."""
    rows = []
    product_id = item.get("id")
    main_stock = item.get("availability", {}).get("stockState") == "Available"

    for swatch in item.get("swatches", []):
        rows.append({
            "product_id":          product_id,
            "color_code":          swatch.get("articleId"),   # unique per color
            "color_name":          swatch.get("colorName"),
            "color_hex":           swatch.get("colorCode"),   # hex without #
            "color_product_image": swatch.get("productImage"),
            "color_in_stock":      int(main_stock),           # best available signal
            "scraped_at":          scraped_at,
        })
    return rows

# ── Database inserts ──────────────────────────────────────────────────────────

def upsert_product(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO products
        (product_id, name, gender, category, current_price, origin_price,
         on_sale, stock_status, main_image_url, model_image_url,
         fit, pattern, neckline, sleeve_length, material,
         tags, new_arrival, product_url, scraped_at, raw_json)
        VALUES
        (:product_id, :name, :gender, :category, :current_price, :origin_price,
         :on_sale, :stock_status, :main_image_url, :model_image_url,
         :fit, :pattern, :neckline, :sleeve_length, :material,
         :tags, :new_arrival, :product_url, :scraped_at, :raw_json)
    """, row)

def upsert_colors(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany("""
        INSERT OR REPLACE INTO color_variants
        (product_id, color_code, color_name, color_hex,
         color_product_image, color_in_stock, scraped_at)
        VALUES
        (:product_id, :color_code, :color_name, :color_hex,
         :color_product_image, :color_in_stock, :scraped_at)
    """, rows)

# ── Main scrape loop ──────────────────────────────────────────────────────────

def run_scrape() -> None:
    scraped_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Scrape started at %s (UTC)", scraped_at)

    conn    = sqlite3.connect(DB_FILE)
    session = requests.Session()
    init_db(conn)

    # --- Page 1: get total pages and save raw sample ---
    log.info("Fetching page 1 to discover total pages...")
    try:
        data = fetch_page(1, session)
    except Exception as e:
        log.error("Failed to fetch page 1: %s", e)
        conn.close()
        return

    # Save raw JSON sample (first page only, for documentation)
    with open(RAW_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Raw JSON sample saved to %s", RAW_JSON_FILE)

    pagination   = data.get("pagination", {})
    total_pages  = pagination.get("totalPages", 1)
    total_hits   = data.get("numberOfHits", "?")
    log.info("Total products: %s across %s pages", total_hits, total_pages)

    product_count = 0
    color_count   = 0

    # Process pages 1 … total_pages
    for page in range(1, total_pages + 1):
        if page > 1:
            log.info("Fetching page %d / %d ...", page, total_pages)
            try:
                data = fetch_page(page, session)
            except Exception as e:
                log.warning("Page %d failed (%s) — skipping", page, e)
                time.sleep(3)
                continue

        items = data.get("plpList", {}).get("productList", [])
        log.info("  Page %d: %d products", page, len(items))

        for item in items:
            product_row  = parse_product(item, scraped_at)
            color_rows   = parse_colors(item, scraped_at)

            upsert_product(conn, product_row)
            upsert_colors(conn, color_rows)
            product_count += 1
            color_count   += len(color_rows)

        conn.commit()
        time.sleep(0.5)   # polite delay between pages

    log.info("Done. Inserted/updated %d products, %d color variants.",
             product_count, color_count)
    log.info("Database saved to: %s", DB_FILE)
    conn.close()

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_scrape()