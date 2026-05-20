import asyncio
from playwright.async_api import async_playwright
 
 
async def main():
    async with async_playwright() as p:
        # Connect to an existing browser instance over CDP
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()

        await page.goto(
            "https://www2.hm.com/en_hk/productpage.1307966001.html",
            wait_until="domcontentloaded",
            timeout=30000
        )
 
        # Wait for the page to fully load its products
        await page.wait_for_timeout(3000)
 
        # # Run JavaScript inside the page to extract product names and prices
        # products = await page.evaluate("""
        #     () => {
        #         const items = document.querySelectorAll(
        #             '[class*="product"], [class*="item"], [class*="card"], ' +
        #             '[class*="tile"], li.product, .ec-item'
        #         );
        #         const seen = new Set();
        #         const results = [];
        #         items.forEach(el => {
        #             const nameEl = el.querySelector(
        #                 '[class*="name"], [class*="title"], ' +
        #                 '[class*="productName"], h3, h4, a'
        #             );
        #             const priceEl = el.querySelector(
        #                 '[class*="price"], [class*="amount"], [class*="productPrice"]'
        #             );
        #             const name = nameEl?.innerText?.trim();
        #             const price = priceEl?.innerText?.trim();
        #             if (!name) return;
        #             const key = name.split(/[\\d]{6,}/)[0].trim();
        #             if (seen.has(key)) return;
        #             seen.add(key);
        #             results.push({ name, price: price || "(no price)" });
        #         });
        #         return results;
        #     }
        # """)
 
        # # Print the scraped data
        # print(f"Found {len(products)} unique products:\n")
        # for i, prod in enumerate(products, 1):
        #     print(f"{i}. {prod['name']}")
        #     print(f"   Price: {prod['price']}")
        #     print()
 
        # input("Press Enter to close the browser...")
        # When connecting to an existing browser, we don't close it
        # await browser.close()
 
 
if __name__ == "__main__":
    asyncio.run(main())