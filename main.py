"""
Code that runs through the loop and continues after bot behavior detected
"""
from level1_scraper import run_level1_scrape
from level2_html_scraper import run_detail_scrape

if __name__ == "__main__":
    run_level1_scrape()
    run_detail_scrape()