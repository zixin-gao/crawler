import asyncio
from playwright.async_api import async_playwright
import sqlite3
import time
import logging
from bs4 import BeautifulSoup
import csv
import random
import json
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
DB_FILE = "./data/20260521_124811hm_products.db"
BOOKMARK_FILE = "./product_id/last_accessed_product.txt"
STYLES_LIST_IN_DB = ["fit", "neckline", "length", "sleeve_length"]
last_product_id = None

def store_last_accessed_productID(last_accessed_filename):
    global last_product_id
    if last_product_id is not None:
        with open(last_accessed_filename, "w") as f:
            f.write(str(last_product_id))
            log.info("Stored last accessed product ID: %s", last_product_id)

def reload_last_accessed_productID(last_accessed_filename):
    global last_product_id
    try:
        with open(last_accessed_filename, "r") as f:
            last_product_id = f.read().strip()
            log.info("Reloaded last accessed product ID: %s", last_product_id)
    except FileNotFoundError:
        log.info("No bookmark file found. Starting from the beginning.")
        last_product_id = None

# SEPARATOR_CHAR=","
# csv_file_name = "./data/hm_products_detail.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)
 
# ── Database helpers ──────────────────────────────────────────────────────────
def get_all_products(conn: sqlite3.Connection) -> list[tuple]:
    """Return (product_id, product_url) for every row in products."""
    rows = None
    if last_product_id is None:
        rows = conn.execute(
            "SELECT product_id, product_url FROM products ORDER BY product_id ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT product_id, product_url FROM products WHERE product_id >= ? ORDER BY product_id ASC",
            (last_product_id,)
        ).fetchall()

    return rows

def update_product_details(conn:sqlite3.Connection, product_id, description_text, style_attributes, material_text):
    extra_attributes_json = json.dumps(style_attributes, ensure_ascii=False)
    pattern_scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE products SET description = ?, extra_attributes = ?, material = ?, pattern_scraped_at = ? WHERE product_id = ?",
        (description_text, extra_attributes_json, material_text, pattern_scraped_at, product_id)
    )

async def extract_fields(page):
        global last_product_id
        # debugging --------------
        conn = sqlite3.connect(DB_FILE)
        
        products = get_all_products(conn)
        total    = len(products)
        log.info(f"Starting from productID <{last_product_id if last_product_id else 'begin'}>")
        log.info("Starting detail scrape for %d products...", total)        

        # csv_file = open(csv_file_name, "w", encoding="utf-8")

        # extract style dictionary and material list        
        try:
            for i, (product_id, product_url) in enumerate(products, 1):
                log.info("[%d/%d] Processing ID: %s -> %s", i, total, product_id, product_url)
                # Direct navigation simulating normal window operations
                await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)

                # -------- 1. find description accordion -------------
                # await page.locator("#toggle-descriptionAccordion").click()
                
                product_card_locator = page.locator("#section-descriptionAccordion")
                #html_text = await product_card_locator.inner_html()
                #print("Description html_ext:", html_text)

                description_text = None  # Default value
                try:
                    description_locator = product_card_locator.locator("p").first
                    description_text = await description_locator.text_content() 
                except Exception:
                    log.warning(f"No description found for product {product_id}")

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
                #csv_file.write(f'"{product_id}"{SEPARATOR_CHAR}"{description_text}"')
                for key_text, value_data in zip(all_keys_text, all_values_data):
                    clean_key = key_text.strip().replace(':', '').replace(" ", "_").lower()
                    if clean_key in STYLES_LIST_IN_DB:
                        # print(f"clean_key: {clean_key}, value_data['text']: {value_data['text']}")
                        conn.execute(f'UPDATE products SET "{clean_key}" = ? WHERE product_id = ?', (value_data['text'], product_id))
                        # log.info(f"Commited {clean_key}: {value_data['text']} to productID: {product_id}")
                    else:
                        # testid_attribute = value_data['testId']                    
                        style_attributes[clean_key] = value_data['text']
                    #csv_file.write(f'{SEPARATOR_CHAR}"{clean_key}"')
                # print("DEBUG: Found style attributes:", style_attributes)
                # csv_file.write("\n")


                # -------- 2. find material accordion -------------
                # await page.locator("#toggle-materialsAndSuppliersAccordion").click()
                material_card_locator = page.locator("#section-materialsAndSuppliersAccordion")
                # html_text = await material_card_locator.inner_html()
                # print("Materials html_text:", html_text)

                material_text = None  # Default value
                try:
                    material_text = await material_card_locator.locator("dd").first.text_content()
                except Exception:
                    log.warning(f"No material found for product {product_id}")
                # print("Material text:", material_text)                

                await page.wait_for_timeout(3000)   # structural delay ensuring JS hydration finishes
                html = await page.content()
                last_product_id = product_id
                
                # debug dump
                # open(f"htmls/debug_{product_id}.html", "w", encoding="utf-8").write(html) 
                # if i == 1:
                #     break

                update_product_details(conn, product_id, description_text, style_attributes, material_text)
                
                # Commit periodically to secure data safety thresholds
                if i % 2 == 0:
                    conn.commit()
                    log.info("  ✔ Committed %d products so far", i)
                    break

                await page.wait_for_timeout(random.randint(4500, 6000))   # polite anti-scraping cadence cooldown

        except Exception as e:
            log.warning("  ✗ Fetch failed for item %s: %s", product_id, e)
            conn.commit()  # commit progress before exiting due to error
        
        finally:
            store_last_accessed_productID(BOOKMARK_FILE)
            conn.commit()
            conn.close()

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
        await extract_fields(page)

        await browser.close()
 


if __name__ == "__main__":
    reload_last_accessed_productID(BOOKMARK_FILE) 
    asyncio.run(run_detail_scrape())