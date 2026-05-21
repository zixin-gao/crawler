"""
Code that runs through the loop and continues after bot behavior detected
"""
from level1_scraper import run_level1_scrape
from level2_html_scraper import run_detail_scrape

# IDs that needs to be looped
CATEGORY_ID_LIST = ["men_tshirtstanks"]
PAGE_ID_LIST = ["/men/shop-by-product/t-shirts-and-tanks"]

if __name__ == "__main__":
    run_level1_scrape()
    run_detail_scrape()