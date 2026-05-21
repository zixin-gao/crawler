"""
H&M Hong Kong — Product Detail Page Scraper (Async Playwright Edition)
Fetches each product's HTML page using a real headless browser instance to bypass
403 blocks, and extracts design attributes that aren't available in the listing API:
  description_text, fit, length, sleeve_length, neckline,
  material, composition, pattern, style

Designed to be run AFTER hm_scraper.py has already populated
the database with product_ids and product_urls.
"""

import asyncio
import sqlite3
import time
import logging
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────

DB_FILE = "./data/hm_products.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Single-page extraction ────────────────────────────────────────────────────
def extract_detail(html: str) -> dict:
    return {}

def extract_detail2(html: str) -> dict:
    """
    Parse one H&M product page HTML string and return a dict of
    design attributes.

    H&M uses two patterns on the detail page:
      1. A description paragraph  →  <p class="pdp-description-text"> or
                                     first <p> inside the description section
      2. Key-value pairs          →  <dl> with <dt> labels and <dd> values
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Description paragraph ─────────────────────────────────────────────
    # Try the dedicated class first, fall back to any paragraph near the top
    container = soup.find("div", id="section-descriptionAccordion")  # specific to H&M's current structure
    description_paragraph = container.find("p")
    description_text = description_paragraph.get_text(strip=True) if description_paragraph else None
    print("DEBUG: Found description element:", description_text)

    # desc_el = (
    #     soup.find("p", class_="pdp-description-text")
    #     or soup.find("p", class_=lambda c: c and "description" in c.lower())
    #     or soup.select_one(".product-detail-description p")
    # )
    # description_text = desc_el.get_text(strip=True) if desc_el else None


    # # ── 2. Key-value pairs from <dl> lists ───────────────────────────────────
    # # Build a flat dict  { "Fit": "Loose fit", "Length": "Regular length", … }
    # kv = {}
    # for dl in soup.find_all("dl"):
    #     keys   = dl.find_all("dt")
    #     values = dl.find_all("dd")
    #     for dt, dd in zip(keys, values):
    #         key   = dt.get_text(strip=True).rstrip(":").lower()
    #         value = dd.get_text(strip=True)
    #         kv[key] = value

    # # ── 3. Composition / material (may be outside the <dl>) ──────────────────
    # # H&M often puts composition in a separate <ul> or <p> under "MATERIALS"
    # composition = None
    # materials_header = soup.find(
    #     lambda tag: tag.name in ("h2", "h3", "strong", "p")
    #     and "composition" in tag.get_text(strip=True).lower()
    # )
    # if materials_header:
    #     # The composition text is usually the next sibling element
    #     sibling = materials_header.find_next_sibling()
    #     if sibling:
    #         composition = sibling.get_text(separator=", ", strip=True)

    # # Fall back to looking for a <p> or <li> that contains a percentage sign
    # if not composition:
    #     for el in soup.find_all(["p", "li"]):
    #         text = el.get_text(strip=True)
    #         if "%" in text and len(text) < 120:
    #             composition = text
    #             break

    # # ── 4. Pattern — look for "print", "solid", "striped" in description ─────
    # pattern = None
    # search_text = (description_text or "").lower()
    # for candidate in ["print motif", "graphic print", "striped", "solid colour",
    #                   "solid color", "floral", "checked", "tie-dye"]:
    #     if candidate in search_text:
    #         pattern = candidate.title()
    #         break

    # ── 5. Assemble final result ──────────────────────────────────────────────
    return {
        "description_text": description_text,
        # "fit":              kv.get("fit"),
        # "length":           kv.get("length"),
        # "sleeve_length":    kv.get("sleeve length"),
        # "neckline":         kv.get("neckline"),
        # "style":            kv.get("style"),
        # "material":         kv.get("material"),
        # "composition":      composition or kv.get("composition"),
        # "pattern":          pattern or kv.get("pattern"),
    }


# ── Database helpers ──────────────────────────────────────────────────────────

def add_detail_columns(conn: sqlite3.Connection) -> None:
    """
    Safely add new columns to the products table if they don't exist yet.
    SQLite ignores the command if the column is already there (via try/except).
    """
    new_columns = [
        ("description_text", "TEXT"),
        ("length",           "TEXT"),
        ("style",            "TEXT"),
        ("composition",      "TEXT"),
    ]
    for col_name, col_type in new_columns:
        try:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            log.info("Added column: %s", col_name)
        except sqlite3.OperationalError:
            pass   # column already exists — that's fine
    conn.commit()


def get_all_products(conn: sqlite3.Connection) -> list[tuple]:
    """Return (product_id, product_url) for every row in products."""
    rows = conn.execute(
        "SELECT product_id, product_url FROM products"
    ).fetchall()
    return rows


def update_product_details(conn: sqlite3.Connection,
                           product_id: str,
                           details: dict) -> None:
    
        conn.execute("""
        UPDATE products SET
            description_text = :description_text,
        WHERE product_id = :product_id
    """, {**details, "product_id": product_id})

    # conn.execute("""
    #     UPDATE products SET
    #         description_text = :description_text,
    #         fit              = COALESCE(:fit,           fit),
    #         length           = :length,
    #         sleeve_length    = COALESCE(:sleeve_length, sleeve_length),
    #         neckline         = COALESCE(:neckline,      neckline),
    #         style            = :style,
    #         material         = COALESCE(:material,      material),
    #         composition      = :composition,
    #         pattern          = COALESCE(:pattern,       pattern)
    #     WHERE product_id = :product_id
    # """, {**details, "product_id": product_id})


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_detail_scrape() -> None:
    from playwright.async_api import async_playwright

    conn = sqlite3.connect(DB_FILE)
    
    # Make sure the extra columns exist before we try to write to them
    add_detail_columns(conn)
    
    products = get_all_products(conn)
    total    = len(products)
    log.info("Starting detail scrape for %d products...", total)

    async with async_playwright() as p:
        # Launching headless browser environment
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        for i, (product_id, product_url) in enumerate(products, 1):
            log.info("[%d/%d] Processing ID: %s -> %s", i, total, product_id, product_url)
            try:
                # Direct navigation simulating normal window operations
                await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)   # structural delay ensuring JS hydration finishes
                html = await page.content()
            except Exception as e:
                log.warning("  ✗ Fetch failed for item %s: %s", product_id, e)
                continue

            # Run BeautifulSoup parser logic over the loaded HTML page layout
            open(f"htmls/debug_{product_id}.html", "w", encoding="utf-8").write(html)  # debug dump
            if i == 5:
                break

            details = extract_detail(html)
            #update_product_details(conn, product_id, details)

            # Commit periodically to secure data safety thresholds
            if i % 20 == 0:
                conn.commit()
                log.info("  ✔ Committed %d products so far", i)

            await page.wait_for_timeout(3000)   # polite anti-scraping cadence cooldown

        await browser.close()

    conn.commit()
    log.info("Detail scrape complete. %d products updated.", total)
    conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_detail_scrape())