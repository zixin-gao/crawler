"""
H&M Hong Kong Product Scraper
Scrapes men's t-shirts & tanks from the H&M listing API.
Saves products, color variants, and a raw JSON sample to SQLite.
"""

import requests
import sqlite3
import json
import time
import logging
from datetime import datetime
import random

# ── Configuration ────────────────────────────────────────────────────────────
# https://www2.hm.com/en_hk/men/shop-by-product/t-shirts-and-tanks.html
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
            product_id              TEXT PRIMARY KEY,
            name                    TEXT,
            gender                  TEXT,
            category                TEXT,
            current_price           REAL,
            max_price               REAL,
            min_price               REAL,
            on_sale                 INTEGER,
            stock_status            TEXT,
            main_image_url          TEXT,
            model_image_url         TEXT,
            description             TEXT,    -- pattern start here
            fit                     TEXT,
            neckline                TEXT,
            length                  TEXT,
            sleeve_length           TEXT,
            extra_attributes        TEXT,    -- pattern ends here
            tags                    TEXT,
            new_arrival             INTEGER,
            external                INTEGER,     
            product_url             TEXT,
            raw_json                TEXT,
            pattern_scraped_at      TEXT     -- update later 
        );

        CREATE TABLE IF NOT EXISTS color_variants (
            product_id                TEXT NOT NULL,
            color_code                TEXT NOT NULL,
            color_name                TEXT,
            color_hex                 TEXT,
            color_product_image       TEXT,
            color_in_stock            INTEGER,
            color_scraped_at          TEXT NOT NULL,
            PRIMARY KEY (product_id, color_code, color_scraped_at)
        );
    """)
    conn.commit()

# ── API helpers ───────────────────────────────────────────────────────────────

def fetch_page(base_url: str, page: int, headers: dict, session: requests.Session, page_id: str, page_size: int, category_id: str) -> dict:
    """Fetch one page of products from the H&M listing API."""
    params = {
        "pageSource":    "PLP",
        "page":          page,
        "sort":          "RELEVANCE",
        "pageId":        page_id,
        "page-size":     page_size,
        "categoryId":    category_id,
        "filters":       "sale:false||oldSale:false",
        "touchPoint":    "DESKTOP",
        "skipStockCheck":"false",
    }
    resp = session.get(base_url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()

# ── Parsing helpers ───────────────────────────────────────────────────────────

# def extract_fit(product_name: str) -> str:
#     """Pull fit type from the product name string."""
#     for fit in ["Slim Fit", "Loose Fit", "Regular Fit", "Relaxed Fit",
#                 "Oversized Fit", "Muscle Fit", "Compression Fit"]:
#         if fit.lower() in product_name.lower():
#             return fit
#     return ""

def parse_product(item: dict) -> dict:
    """Map one raw API product dict to our schema."""
    prices   = item.get("prices", [{}])
    price    = prices[0].get("price") if prices else None
    max_price = prices[0].get("maxPrice") if prices else None
    min_price = prices[0].get("minPrice") if prices else None
    on_sale  = any(p.get("priceType") == "redPrice" for p in prices)

    markers  = [m.get("text", "") for m in item.get("productMarkers", []).lower()]
    tags_str = ", ".join(markers) if markers else None
    product_name = item.get("productName", "").lower()
    main_category = item.get("mainCatCode", "").lower()

    gender = ""
    if "men" in main_category:
        gender = "men"
    elif "ladies" in main_category:
        gender = "women"
    elif "kids" in main_category:
        gender = "kids"

    return {
        "product_id":      item.get("id"),
        "name":            product_name,
        "gender":          gender, 
        "category":        main_category,
        "current_price":   price,
        "max_price":       max_price,
        "min_price":       min_price,
        "on_sale":         on_sale,
        "stock_status":    item.get("availability", {}).get("stockState"),
        "main_image_url":  item.get("productImage"),
        "model_image_url": item.get("modelImage"),
        "description":     None,  # update patterns using level 2 scraper through html
        "fit":             None, # extract_fit(product_name),
        "neckline":        None,
        "length":          None,
        "sleeve_length":   None,
        "extra_attributes": None,
        "tags":            tags_str,
        "new_arrival":     item.get("newArrival", False),
        "external":        item.get("external", False),
        "product_url":     "https://www2.hm.com" + item.get("url", ""),
        "pattern_scraped_at":      None,
        "raw_json":        json.dumps(item),
    }

def parse_colors(item: dict) -> list[dict]:
    """Extract color variant rows from a product item."""
    rows = []
    product_id = item.get("id")
    main_stock = item.get("availability", {}).get("stockState") == "Available"
    color_scraped_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")

    for swatch in item.get("swatches", []):
        rows.append({
            "product_id":          product_id,
            "color_code":          swatch.get("articleId"),   # unique per color
            "color_name":          swatch.get("colorName"),
            "color_hex":           swatch.get("colorCode"),   # hex without #
            "color_product_image": swatch.get("productImage"),
            "color_in_stock":      int(main_stock),           # best available signal
            "color_scraped_at":    color_scraped_at,
        })
    return rows

# ── Database inserts ──────────────────────────────────────────────────────────

def upsert_product(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO products
        (product_id, name, gender, category, current_price, max_price, min_price,
         on_sale, stock_status, main_image_url, model_image_url, description,
         fit, neckline, length, sleeve_length, extra_attributes, tags, new_arrival, external, product_url, pattern_scraped_at, raw_json)
        VALUES
        (:product_id, :name, :gender, :category, :current_price, :max_price, :min_price,
         :on_sale, :stock_status, :main_image_url, :model_image_url, :description,
         :fit, :neckline, :length, :sleeve_length, :extra_attributes, :tags, :new_arrival, :external, :product_url, :pattern_scraped_at, :raw_json)
    """, row)

def upsert_colors(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany("""
        INSERT OR REPLACE INTO color_variants
        (product_id, color_code, color_name, color_hex,
         color_product_image, color_in_stock, color_scraped_at)
        VALUES
        (:product_id, :color_code, :color_name, :color_hex,
         :color_product_image, :color_in_stock, :color_scraped_at)
    """, rows)

# ── Main scrape loop ──────────────────────────────────────────────────────────

def run_level1_scrape() -> None:
    conn    = sqlite3.connect(DB_FILE)
    session = requests.Session()
    init_db(conn)

    # --- Page 1: get total pages and save raw sample ---
    log.info("Fetching page 1 to discover total pages...")
    try:
        data = fetch_page(BASE_URL, 1, HEADERS, session, PAGE_ID, PAGE_SIZE, CATEGORY_ID)
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
                data = fetch_page(BASE_URL, page, HEADERS, session, PAGE_ID, PAGE_SIZE, CATEGORY_ID)
            except Exception as e:
                log.warning("Page %d failed (%s) — skipping", page, e)
                time.sleep(3)
                continue

        items = data.get("plpList", {}).get("productList", [])
        log.info("  Page %d: %d products", page, len(items))

        for item in items:
            product_row  = parse_product(item)
            color_rows   = parse_colors(item)

            upsert_product(conn, product_row)
            upsert_colors(conn, color_rows)
            product_count += 1
            color_count   += len(color_rows)

        conn.commit()
        time.sleep(random.uniform(4.5, 7.2))   # polite delay between pages
        if page == 1:
            break

    log.info("Done. Inserted/updated %d products, %d color variants.", product_count, color_count)
    log.info("Database saved to: %s", DB_FILE)
    conn.close()

# if __name__ == "__main__":
#     run_level1_scrape()