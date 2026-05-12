"""
Intershop Customer Reference Scraper
=====================================
Scrapes https://www.intershop.com/en/customers and saves each company
as an individual LangChain-compatible JSON document.

Install:
    pip install requests beautifulsoup4

Run:
    python scraper.py

Output:
    ./references/<customer_slug>.json  (one file per company)
    ./references/_all.json             (combined list for convenience)
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.intershop.com"
CUSTOMERS_URL = f"{BASE_URL}/en/customers"
OUTPUT_DIR = Path("references")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Turn 'Merck Millipore' → 'merck_millipore'"""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name


def extract_customer_name(img_alt: str, fallback: str) -> str:
    """
    Logo <img> alt text is usually the customer name.
    Cleans up suffixes like 'logo', 'Logo BME Black', etc.
    """
    name = img_alt or fallback
    name = re.sub(r"\s+(logo|Logo|BME|Black|white|White|RGB|svg).*", "", name, flags=re.IGNORECASE)
    return name.strip()


def clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


# ── Main scraper ─────────────────────────────────────────────────────────────

def scrape_customers() -> list[dict]:
    print(f"Fetching {CUSTOMERS_URL} ...")
    resp = requests.get(CUSTOMERS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    documents = []

    # Each customer is an <a> tag containing:
    #   - an <img> (logo)
    #   - headline + description text
    #   - a CTA that is one of:
    #       "Read more"  → href = /en/customers-details/<slug>   (internal)
    #       "Visit shop" → href = https://external-domain.com    (external)
    #       "Visit page" → href = https://external-domain.com    (external)
    #
    # Strategy: grab ALL <a> tags that contain an <img> AND enough text
    # (>30 chars), regardless of where the href points.
    # This catches both internal "Read more" and external "Visit shop/page" cards.

    customer_links = [
        a for a in soup.find_all("a", href=True)
        if a.find("img") and len(a.get_text(strip=True)) > 30
    ]

    print(f"  Found {len(customer_links)} candidate entries.")

    seen_slugs = set()

    for a_tag in customer_links:
        href = a_tag.get("href", "")
        full_href = href if href.startswith("http") else BASE_URL + href

        # ── Logo ──────────────────────────────────────────────────────────
        img = a_tag.find("img")
        logo_url = ""
        raw_alt = ""
        if img:
            src = img.get("src") or img.get("data-src") or ""
            logo_url = src if src.startswith("http") else BASE_URL + src
            raw_alt = img.get("alt", "")

        # ── Customer name ─────────────────────────────────────────────────
        # Try <img alt>, then title attribute on the <a>, then first heading inside
        customer_name = ""
        title_attr = a_tag.get("title", "")

        if raw_alt:
            customer_name = extract_customer_name(raw_alt, "")

        if not customer_name and title_attr:
            # title is usually the headline, not the company name — skip as name source
            pass

        # If still empty, try to find a heading tag inside
        if not customer_name:
            for tag in ["h2", "h3", "h4", "strong", "b"]:
                heading = a_tag.find(tag)
                if heading:
                    customer_name = clean_text(heading.get_text())
                    break

        if not customer_name:
            customer_name = "Unknown"

        # ── Page content (headline + description) ─────────────────────────
        # Remove the img from a clone so we only get text nodes
        a_clone = BeautifulSoup(str(a_tag), "html.parser").find("a")
        for img_tag in a_clone.find_all("img"):
            img_tag.decompose()

        # Collect all text blocks, filter noise
        # Strip all known CTA button texts
        CTA_TEXTS = {"read more", "visit shop", "visit page", "mehr erfahren", "zur website"}
        text_blocks = []
        for elem in a_clone.find_all(["p", "h2", "h3", "h4", "span", "strong", "div"]):
            t = clean_text(elem.get_text())
            if t and t.lower() not in CTA_TEXTS and len(t) > 10:
                # avoid duplicates from nested tags
                if not any(t in existing for existing in text_blocks):
                    text_blocks.append(t)

        # If no structured tags, fall back to raw text of the <a>
        if not text_blocks:
            raw = clean_text(a_clone.get_text())
            # strip all CTA variants at the end
            raw = re.sub(r"\s*(Read more|Visit shop|Visit page|Mehr erfahren|Zur Website)\s*$", "", raw, flags=re.IGNORECASE).strip()
            if raw:
                text_blocks = [raw]

        page_content = "\n".join(text_blocks)
        # Final safety net: strip any CTA that bled into the last line
        page_content = re.sub(
            r"\s*(Read more|Visit shop|Visit page|Mehr erfahren|Zur Website)\s*$",
            "",
            page_content,
            flags=re.IGNORECASE,
        ).strip()

        # ── Deduplicate ───────────────────────────────────────────────────
        slug = slugify(customer_name)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # ── Assemble document ─────────────────────────────────────────────
        metadata: dict = {
            "customer": customer_name,
            "logo_url": logo_url,
            "challenges": [],           # to be filled later
        }

        # Distinguish internal detail pages from external "Visit shop/page" links
        if "/customers-details/" in full_href:
            metadata["read_more"] = full_href
        elif full_href.startswith("http"):
            # External link — only save if it's clearly a company site, not intershop.com itself
            if "intershop.com" not in full_href:
                metadata["visit_shop"] = full_href

        doc = {
            "page_content": page_content,
            "metadata": metadata,
        }

        documents.append((slug, doc))
        print(f"  ✓ {customer_name}")

    return documents


def save_documents(documents: list[tuple[str, dict]]) -> None:
    all_docs = []

    for slug, doc in documents:
        # Individual file
        out_path = OUTPUT_DIR / f"{slug}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        all_docs.append(doc)

    # Combined file (useful for loading all at once into LangChain)
    combined_path = OUTPUT_DIR / "_all.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(all_docs)} documents to ./{OUTPUT_DIR}/")
    print(f"Combined: ./{OUTPUT_DIR}/_all.json")

# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    documents = scrape_customers()

    if not documents:
        print("\nNo documents found. The page structure may have changed.")
        print("Check the HTML manually and adjust the selectors in scrape_customers().")
    else:
        save_documents(documents)