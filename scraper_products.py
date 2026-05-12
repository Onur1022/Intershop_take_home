"""
Intershop Product Scraper
=========================
Scrapes Intershop solution pages and populates products.txt.
Uses requests and beautifulsoup4 to maintain consistency with your reference scraper.

Install:
    pip install requests beautifulsoup4

Run:
    python scraper_products.py
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

URLS = [
    "https://www.intershop.com/en/b2b-ecommerce",
    "https://www.intershop.com/en/b2x-ecommerce",
    "https://www.intershop.com/en/b2c-ecommerce",
    "https://www.intershop.com/en/e-commerce-for-manufacturing",
    "https://www.intershop.com/en/e-commerce-wholesale",
    "https://www.intershop.com/en/retail"
]

OUTPUT_FILE = Path("products.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def clean_text(text: str) -> str:
    """Collapse whitespace, remove tabs/newlines."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def scrape_products():
    all_content = []
    
    print(f"Starting crawl of {len(URLS)} pages...")
    
    for url in URLS:
        print(f"Fetching {url} ...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # 1. Identify the main content area 
            # On Intershop pages, the core info is usually inside <main> 
            # or divs with classes like 'content-section' or 'container'
            main_content = soup.find("main") or soup.find("body")
            
            # 2. Extract meaningful blocks (Headings and Paragraphs)
            # We skip nav, footer, and scripts to avoid noise
            if main_content:
                # Remove noise elements
                for noise in main_content.find_all(['nav', 'footer', 'script', 'style', 'header']):
                    noise.decompose()
                
                blocks = []
                for tag in main_content.find_all(['h1', 'h2', 'h3', 'p', 'li']):
                    txt = clean_text(tag.get_text())
                    if len(txt) > 20: # Filter out short UI snippets
                        blocks.append(txt)
                
                page_text = "\n".join(blocks)
                
                entry = f"SOURCE: {url}\n"
                entry += "-" * len(url) + "\n"
                entry += page_text + "\n"
                entry += "=" * 50 + "\n"
                
                all_content.append(entry)
                print(f"  ✓ Extracted {len(blocks)} sections.")
            
            # Polite delay
            time.sleep(1)
            
        except Exception as e:
            print(f"  × Failed to scrape {url}: {e}")

    # Write to file
    if all_content:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("INTERSHOP PRODUCT KNOWLEDGE BASE\n")
            f.write("Generated via scrape script\n")
            f.write("=" * 30 + "\n\n")
            f.write("\n".join(all_content))
        print(f"\nSuccess! Knowledge base saved to {OUTPUT_FILE}")
    else:
        print("\nNo content was extracted. Check your connection or URL access.")

if __name__ == "__main__":
    scrape_products()