import asyncio
from playwright.async_api import async_playwright
import sqlite3
import time
import logging
from bs4 import BeautifulSoup
import csv
import random

# ── Configuration ─────────────────────────────────────────────────────────────
DB_FILE = "./data/hm_products.db"
SEPARATOR_CHAR=","
csv_file_name = "./data/hm_products_detail.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)
 
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

# main logic ─────────────────────────────────────────────────────────────
async def run_detail_scrape():
    async with async_playwright() as p:
        # Connect to an existing browser instance over CDP to avoid cookie issues
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()

        # debug testing whether the browser opens or not
        # await page.goto(
        #     "https://www2.hm.com/en_hk/productpage.1307966001.html",
        #     wait_until="domcontentloaded",
        #     timeout=30000
        # )
 
        # Wait for the page to fully load its products
        await page.wait_for_timeout(3000)

        # debugging --------------
        conn = sqlite3.connect(DB_FILE)
    
        # Make sure the extra columns exist before we try to write to them
        add_detail_columns(conn)
        
        products = get_all_products(conn)
        total    = len(products)
        log.info("Starting detail scrape for %d products...", total)

        csv_file = open(csv_file_name, "w", encoding="utf-8")

        # extract style dictionary and material list
        for i, (product_id, product_url) in enumerate(products, 1):
            log.info("[%d/%d] Processing ID: %s -> %s", i, total, product_id, product_url)
            try:
                # Direct navigation simulating normal window operations
                await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)

                # -------- 1. find description accordion -------------
                # await page.locator("#toggle-descriptionAccordion").click()
                
                product_card_locator = page.locator("#section-descriptionAccordion")
                #html_text = await product_card_locator.inner_html()
                #print("Description html_ext:", html_text)

                description_locator = product_card_locator.locator("p").first
                description_text = await description_locator.text_content()
                #print("Description text:", description_text)              

                # 1. define Locators
                style_category_key = product_card_locator.locator("dt")
                style_category_value = product_card_locator.locator("dd")  

                # 2. find all keys for the styles 
                all_keys_text = await style_category_key.all_text_contents()
                # ---------- NO data-testid --------------
                # all_values_text = await style_category_value.all_text_contents()
                # style_attributes = {}
                # for key, value in zip(all_keys_text, all_values_text):
                #     clean_key = key.strip().replace(':', "").lower()
                #     style_attributes[clean_key] = value.strip()

                # --------- NEED data-testid --------------
                # 3. evaluate_all() get all dd attribute and data-testid
                # only need one await
                all_values_data = await style_category_value.evaluate_all(
                    """(elements) => 
                        elements.map(el => ({
                            text: el.textContent.trim(),
                            testId: el.getAttribute('data-testid')
                        }))
                    """
                )

                # 4. make attribute dictionary
                style_attributes = {}
                csv_file.write(f'"{product_id}"{SEPARATOR_CHAR}"{description_text}"')
                for key_text, value_data in zip(all_keys_text, all_values_data):
                    clean_key = key_text.strip().replace(':', '').lower()
                    testid_attribute = value_data['testId']                    
                    style_attributes[testid_attribute] = (clean_key, value_data['text'])
                    csv_file.write(f'{SEPARATOR_CHAR}"{clean_key}"')
                # print("DEBUG: Found style attributes:", style_attributes)
                csv_file.write("\n")


                # -------- 2. find material accordion -------------
                # await page.locator("#toggle-materialsAndSuppliersAccordion").click()
                material_card_locator = page.locator("#section-materialsAndSuppliersAccordion")
                # html_text = await material_card_locator.inner_html()
                # print("Materials html_text:", html_text)
                material_text = await material_card_locator.locator("dd").first.text_content()
                # print("Material text:", material_text)                

                await page.wait_for_timeout(3000)   # structural delay ensuring JS hydration finishes
                html = await page.content()
    
            except Exception as e:
                log.warning("  ✗ Fetch failed for item %s: %s", product_id, e)
                continue

            # debug dump
            # open(f"htmls/debug_{product_id}.html", "w", encoding="utf-8").write(html) 
            # if i == 1:
            #     break

            # update_product_details(conn, product_id, details)
            
            # Commit periodically to secure data safety thresholds
            if i % 20 == 0:
                # conn.commit()
                log.info("  ✔ Committed %d products so far", i)

            await page.wait_for_timeout(random.randint(4500, 6000))   # polite anti-scraping cadence cooldown

        await browser.close()
 


if __name__ == "__main__":
    asyncio.run(run_detail_scrape())