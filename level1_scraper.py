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
from playwright.async_api import async_playwright
import asyncio

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

### https://api.hm.com/search-services/v1/en_hk/listing/resultpage?pageSource=PLP&page=2&sort=RELEVANCE&pageId=/men/shop-by-product/t-shirts-and-tanks&page-size=36&categoryId=men_tshirtstanks&filters=sale:false||oldSale:false&touchPoint=DESKTOP&skipStockCheck=false

# ── API helpers ───────────────────────────────────────────────────────────────
async def fetch_page(base_url: str, page_num: int, page_id: str, category_id: str) -> dict:
    """Fetch one page of products from the H&M listing API."""
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()

        params = {
            "pageSource":    "PLP",
            "page":          page_num,
            "sort":          "RELEVANCE",
            "pageId":        page_id,
            "page-size":     PAGE_SIZE,
            "categoryId":    category_id,
            "filters":       "sale:false||oldSale:false",
            "touchPoint":    "DESKTOP",
            "skipStockCheck":"false",
        }

        # 这段 JavaScript 代码将在浏览器的页面中执行
        js_script = """
        async (args) => {
            const { baseUrl, params } = args;
            
            // 使用浏览器内置的 URLSearchParams 来构建查询字符串，比手动拼接更安全
            const queryString = new URLSearchParams(params).toString();
            const url = `${baseUrl}?${queryString}`;
            
            // 使用 Fetch API 发送 GET 请求
            const response = await fetch(url);
            
            // 检查请求是否成功
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 假设 API 返回的是 JSON 格式的数据，并将其返回
            return await response.json();
        }
        """

        # 定义要传递给 JavaScript 函数的参数
        args = {
            "baseUrl": base_url,
            "params": params
        }

        # 执行 JavaScript 并获取返回的数据
        content = await page.evaluate(js_script, args)
    
        # 打印获取到的内容（用于调试）
        print(f"content: {content}")
        
        # 返回获取到的数据，以便其他部分的代码可以使用
        return content

# method that uses cdp to open another browser to get info from the API
# async def query_products_baseinfo(page):
#     page_num=1
#     params = {
#             "pageSource":    "PLP",
#             "page":          page_num,
#             "sort":          "RELEVANCE",
#             "pageId":        PAGE_ID,
#             "page-size":     PAGE_SIZE,
#             "categoryId":    CATEGORY_ID,
#             "filters":       "sale:false||oldSale:false",
#             "touchPoint":    "DESKTOP",
#             "skipStockCheck":"false",
#         }
#     # 导入 Python 内置的 urllib.parse 库，它专门用来处理 URL
#     import urllib.parse
    
#     # 1. 使用 urlencode 函数将 params 字典转换成 URL 查询字符串
#     # 例如: "pageSource=PLP&page=1&sort=RELEVANCE&..."
#     query_string = urllib.parse.urlencode(params)
    
#     # 2. 将 BASE_URL 和查询字符串拼接成一个完整的 URL
#     full_url = f"{BASE_URL}?{query_string}"
    
#     # 3. 让 Playwright 导航到这个构建好的、包含所有参数的完整 URL
#     # 这就等同于向服务器发送了一个带有这些参数的 GET 请求
#     await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
#     content = await page.content()
#     print(f"content:{content}")

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

    markers  = [m.get("text", "") for m in item.get("productMarkers", [])]
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
    color_scraped_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

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

async def run_level1_scrape():
    conn    = sqlite3.connect(DB_FILE)
    session = requests.Session()
    init_db(conn)

    # --- Page 1: get total pages and save raw sample ---
    log.info("Fetching page 1 to discover total pages...")
    try:
        data = await fetch_page(BASE_URL, 1, PAGE_ID, CATEGORY_ID)
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
                data = await fetch_page(BASE_URL, 1, PAGE_ID, CATEGORY_ID)
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

if __name__ == "__main__":
    asyncio.run(run_level1_scrape())