import asyncio
import os
import subprocess
from playwright.async_api import async_playwright
import sqlite3
import time
import logging
from bs4 import BeautifulSoup
import csv
import random
import json
from datetime import datetime
import socket
from contextlib import closing
import shutil

# ── Configuration ─────────────────────────────────────────────────────────────
DB_FILE = "./data/hm_products.db"
BOOKMARK_FILE = "./product_id/last_accessed_product.txt"
STYLES_LIST_IN_DB = ["fit", "neckline", "length", "sleeve_length"]
# SEPARATOR_CHAR=","
# csv_file_name = "./data/hm_products_detail.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

class DetailedScraper:
    def __init__(self):
        self.continuous_failed_attempts = 0
        self.conn = sqlite3.connect(DB_FILE)
        self.total_product_count = self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        self.last_timeout_product_count = 0

    def still_have_products_to_process(self):
        count = self.conn.execute("SELECT COUNT(*) FROM products WHERE pattern_scraped_at IS NULL").fetchone()[0] 
        return count > 0
    
    def __del__(self):
        if self.conn:
            self.conn.close()            

    # ── Database helpers ──────────────────────────────────────────────────────────
    def get_unprocessed_products(self) -> list[tuple]:
        """Return (product_id, product_url) for every row in products."""
        sql_rows = None
        sql_rows = self.conn.execute(
            "SELECT product_id, product_url FROM products WHERE pattern_scraped_at IS NULL ORDER BY product_id ASC"
        ).fetchall()
        log.info(f"Found {len(sql_rows)} products remaining to be scraped.")

        return sql_rows

    def update_product_details(self, product_id, description_text, style_attributes, material_text):
        extra_attributes_json = json.dumps(style_attributes, ensure_ascii=False)
        pattern_scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "UPDATE products SET description = ?, extra_attributes = ?, material = ?, pattern_scraped_at = ? WHERE product_id = ?",
            (description_text, extra_attributes_json, material_text, pattern_scraped_at, product_id)
        )

    async def extract_fields(self, page):
            # debugging --------------
            self.continuous_failed_attempts += 1
            log.info("Starting detail scrape for remaining products...")    

            unprocessed_products_ids = self.get_unprocessed_products()
            unprocessed_product_count = len(unprocessed_products_ids)
            processed_product_count = self.total_product_count - unprocessed_product_count
            # csv_file = open(csv_file_name, "w", encoding="utf-8")

            # extract style dictionary and material list        
            try:
                for i, (product_id, product_url) in enumerate(unprocessed_products_ids, 1):
                    log.info("[%d/%d] Processing ID: %s -> %s", i + processed_product_count, self.total_product_count, product_id, product_url)
                    # Direct navigation simulating normal window operations
                    await page.goto(product_url, wait_until="domcontentloaded", timeout=5000)

                    # -------- 1. find description accordion -------------
                    # await page.locator("#toggle-descriptionAccordion").click()
                    
                    product_card_locator = page.locator("#section-descriptionAccordion")
                    #html_text = await product_card_locator.inner_html()
                    #print("Description html_ext:", html_text)

                    description_text = None  # Default value
                    try:
                        description_locator = product_card_locator.locator("p").first
                        description_text = await description_locator.text_content() 
                        log.info(f"Extracted description for product: {description_text}")
                    except Exception as e:
                        log.warning(f"No description found for product {product_id}")
                        raise e

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
                            self.conn.execute(f'UPDATE products SET "{clean_key}" = ? WHERE product_id = ?', (value_data['text'], product_id))
                            log.info(f"Extracted {clean_key}: {value_data['text']}")
                        else:
                            # testid_attribute = value_data['testId']                    
                            style_attributes[clean_key] = value_data['text']
                        #csv_file.write(f'{SEPARATOR_CHAR}"{clean_key}"')
                    log.info("Found style attributes: %s", style_attributes)
                    # csv_file.write("\n")


                    # -------- 2. find material accordion -------------
                    # await page.locator("#toggle-materialsAndSuppliersAccordion").click()
                    material_card_locator = page.locator("#section-materialsAndSuppliersAccordion")
                    # html_text = await material_card_locator.inner_html()
                    # print("Materials html_text:", html_text)

                    material_text = None  # Default value
                    try:
                        material_text = await material_card_locator.locator("dd").first.text_content()
                        log.info(f"Extracted material for product: {material_text}\n")
                    except Exception as e:
                        log.warning(f"No material found for product {product_id}\n")
                        raise e
                    # print("Material text:", material_text)                

                    # await page.wait_for_timeout(3000)   # structural delay ensuring JS hydration finishes
                    # html = await page.content()
                    # debug dump
                    # open(f"htmls/debug_{product_id}.html", "w", encoding="utf-8").write(html) 

                    self.update_product_details(product_id, description_text, style_attributes, material_text)
                    
                    # Commit periodically to secure data safety thresholds
                    if i % 3 == 0:
                        self.conn.commit()
                        log.info("  ✔ Committed %d products so far", i)
                    self.last_timeout_product_count = i
                    self.continuous_failed_attempts = 0  # Reset on successful processing
                    await page.wait_for_timeout(random.randint(3500, 5000))   # polite anti-scraping cadence cooldown 

            except Exception as e:
                log.warning("  ✗ Fetch failed for item %s: %s", product_id, e)   
            
            finally:
                self.conn.commit()
                log.info("  ✔ Committed products so far")                   

# main logic ─────────────────────────────────────────────────────────────
    async def run_detail_scrape(self, cdp_port=9223):
        async with async_playwright() as p:
            # Connect to an existing browser instance over CDP to avoid cookie issues
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
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
            await self.extract_fields(page)

            await browser.close()
 
     #browser create
    def start_browser_instance(self, cdp_port=9222):
        """
        Starts a browser instance with remote debugging, ensuring it's ready by checking the CDP port.
        """

        browser_path = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
        uuid_suffix = random.randint(0, 99999)
        user_data_dir = os.path.abspath(f"./browser_data_dir/user_data_{cdp_port}_{uuid_suffix}")
        os.makedirs(user_data_dir, exist_ok=True)
        
        if os.path.exists("./browser_data_dir/template"):
            shutil.copytree("./browser_data_dir/template", user_data_dir, dirs_exist_ok=True)

        command = [
            browser_path,
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            #"--headless",       # Consider adding "--headless" if you don't need to see the browser UI
        ]

        log.info(f"Starting browser for port {cdp_port}...")
        
        # Use Popen for non-blocking process creation and capture output
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW # For Windows, to avoid a console window
        )

        # --- Health Check: Wait for the browser's CDP port to be open ---
        max_wait_seconds = 30
        start_time = time.time()
        log.info(f"Waiting for browser to be ready on port {cdp_port}...")

        while time.time() - start_time < max_wait_seconds:
            # Check if the process terminated unexpectedly
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                log.error(f"Browser process failed to start. Exit code: {process.returncode}")
                log.error(f"STDERR: {stderr.strip()}")
                log.error(f"STDOUT: {stdout.strip()}")
                return None, user_data_dir # Indicate failure

            # Try to connect to the port
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                sock.settimeout(1) # Timeout for the connection attempt itself
                if sock.connect_ex(('127.0.0.1', cdp_port)) == 0:
                    log.info(f"Browser is ready and listening on port {cdp_port}!")
                    return process, user_data_dir # Success!

            time.sleep(0.5) # Wait before next poll

        # If the loop completes, it means we timed out
        log.error(f"Timeout: Browser on port {cdp_port} did not become ready in {max_wait_seconds}s.")
        process.terminate() # Clean up the zombie process
        stdout, stderr = process.communicate()
        log.error(f"Final STDERR from timed-out process: {stderr.strip()}")
        return None, user_data_dir      

    def browser_cleanup(self, browser_process, user_data_dir):
        if browser_process:
            log.info("Closing browser process...")
            browser_process.terminate()  # Request graceful shutdown
            try:
                # Wait for a few seconds for the process to terminate
                browser_process.wait(timeout=5)
                log.info("Browser process terminated gracefully.")
            except subprocess.TimeoutExpired:
                log.warning("Browser process did not terminate gracefully, forcing kill.")
                browser_process.kill()  # Force kill if it doesn't close
                log.info("Browser process killed.")
        shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == "__main__":
    scraper = DetailedScraper()
    #scraper.reload_accessed_productIDs(BOOKMARK_FILE) // No need to reload since we are now tracking accessed_product_ids in memory and storing them periodically
    browser_process = None
    user_data_dir = None
    cdp_port = 9223

    try:
        while scraper.still_have_products_to_process():
            browser_process, user_data_dir = scraper.start_browser_instance(cdp_port)            
            if browser_process:                
                log.info("Successfully started a browser instance.")
                try:
                    asyncio.run(scraper.run_detail_scrape(cdp_port=cdp_port))
                except KeyboardInterrupt:
                    log.warning("KeyboardInterrupt received during scraping. Shutting down.")
                    break  # Exit the while loop to proceed to finally block
                finally:
                    # This inner finally ensures cleanup for the current instance
                    if browser_process:
                        log.info("Cleaning up browser instance for port %d.", cdp_port)
                        scraper.browser_cleanup(browser_process, user_data_dir)

            else:
                log.error("Failed to start browser instance for port %d.", cdp_port)

            cdp_port = cdp_port + 1 if cdp_port == 9223 else cdp_port - 1
            
            # cdp_port += 1
            # Reset for the next loop iteration
            browser_process = None
            user_data_dir = None
           
            if scraper.last_timeout_product_count <= 10:
                waiting_time = 700
            else:
                waiting_time = 210*(scraper.continuous_failed_attempts+1)*2
            log.info("Waiting %d seconds before starting the next browser instance...", waiting_time)
            time.sleep(waiting_time)  # Short delay before starting the next browser instance.unit second.
            
    finally:
        log.info("Main loop finished or interrupted. Performing final cleanup.")
        # The last running instance might not have been cleaned up if interrupted
        if browser_process and browser_process.poll() is None:
            log.info("Final cleanup of lingering browser instance.")
            scraper.browser_cleanup(browser_process, user_data_dir)
        
        # Always save progress on exit
        log.info("Scraping process finished.")