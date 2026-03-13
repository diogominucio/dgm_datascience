"""Web scraper for blinds.com product prices and promotions."""

import json
import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import CATEGORIES, DEFAULT_HEIGHT, DEFAULT_WIDTH

logger = logging.getLogger(__name__)

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def scrape_category_page(category_key: str, category_info: dict) -> list[dict]:
    """Scrape all products from a category page on blinds.com."""
    url = category_info["url"]
    logger.info(f"Scraping category: {category_info['name']} -> {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "lxml")
    products = []

    # Try to extract product data from JSON-LD structured data
    json_ld_products = _extract_json_ld(soup)
    if json_ld_products:
        products.extend(json_ld_products)

    # Also parse product cards from HTML
    html_products = _extract_product_cards(soup)
    if html_products:
        products.extend(html_products)

    # Try extracting from Next.js / React hydration data
    script_products = _extract_from_scripts(soup)
    if script_products:
        products.extend(script_products)

    # Deduplicate by product name
    seen = set()
    unique_products = []
    for p in products:
        key = p.get("name", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            p["category"] = category_info["name"]
            p["category_key"] = category_key
            p["scrape_date"] = datetime.now().strftime("%Y-%m-%d")
            p["scrape_timestamp"] = datetime.now().isoformat()
            unique_products.append(p)

    logger.info(
        f"Found {len(unique_products)} products in {category_info['name']}"
    )
    return unique_products


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Extract product data from JSON-LD structured data."""
    products = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    product = _parse_json_ld_item(item)
                    if product:
                        products.append(product)
            elif isinstance(data, dict):
                product = _parse_json_ld_item(data)
                if product:
                    products.append(product)
        except (json.JSONDecodeError, TypeError):
            continue
    return products


def _parse_json_ld_item(item: dict) -> dict | None:
    """Parse a single JSON-LD item into product data."""
    if item.get("@type") not in ("Product", "IndividualProduct"):
        # Check for ItemList containing products
        if item.get("@type") == "ItemList":
            return None  # handled by caller iterating list elements
        return None

    offers = item.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    price = offers.get("price") or offers.get("lowPrice")
    high_price = offers.get("highPrice")
    msrp = item.get("msrp")

    if price is not None:
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = None

    if high_price is not None:
        try:
            high_price = float(high_price)
        except (ValueError, TypeError):
            high_price = None

    if msrp is not None:
        try:
            msrp = float(msrp)
        except (ValueError, TypeError):
            msrp = None

    return {
        "name": item.get("name", "Unknown"),
        "url": item.get("url", ""),
        "image": item.get("image", ""),
        "price": price,
        "high_price": high_price,
        "msrp": msrp,
        "currency": offers.get("priceCurrency", "USD"),
        "availability": offers.get("availability", ""),
        "brand": (item.get("brand", {}) or {}).get("name", ""),
        "description": item.get("description", ""),
        "sku": item.get("sku", ""),
        "source": "json_ld",
    }


def _extract_product_cards(soup: BeautifulSoup) -> list[dict]:
    """Extract product data from HTML product cards."""
    products = []

    # Common product card selectors for e-commerce sites
    card_selectors = [
        "div[data-testid='product-card']",
        ".product-card",
        ".product-tile",
        ".product-item",
        "[data-product]",
        ".plp-product-card",
        "li.product",
        ".grid-item.product",
    ]

    cards = []
    for selector in card_selectors:
        cards = soup.select(selector)
        if cards:
            break

    for card in cards:
        product = _parse_product_card(card)
        if product and product.get("name"):
            products.append(product)

    return products


def _parse_product_card(card) -> dict | None:
    """Parse a single product card HTML element."""
    # Extract product name
    name_el = (
        card.select_one("h2, h3, .product-name, .product-title, [data-testid='product-name']")
    )
    name = name_el.get_text(strip=True) if name_el else ""

    # Extract URL
    link = card.select_one("a[href]")
    url = link.get("href", "") if link else ""
    if url and not url.startswith("http"):
        url = "https://www.blinds.com" + url

    # Extract prices
    price = _extract_price(card, [
        ".product-price", ".sale-price", ".final-price",
        "[data-testid='sale-price']", ".price--sale", ".price-current",
    ])

    msrp = _extract_price(card, [
        ".original-price", ".was-price", ".msrp", ".list-price",
        "[data-testid='original-price']", ".price--original",
        ".price-was", "s", "del", ".strike-through",
    ])

    # Extract discount/promotion info
    promo_el = card.select_one(
        ".promo-badge, .discount-badge, .sale-badge, .promotion, "
        ".savings, [data-testid='promo']"
    )
    promotion = promo_el.get_text(strip=True) if promo_el else ""

    # Extract rating
    rating_el = card.select_one(".rating, .stars, [data-rating]")
    rating = None
    if rating_el:
        rating_text = rating_el.get("data-rating") or rating_el.get_text(strip=True)
        try:
            rating = float(re.search(r"[\d.]+", rating_text).group())
        except (AttributeError, ValueError, TypeError):
            pass

    # Extract image
    img = card.select_one("img")
    image = ""
    if img:
        image = img.get("src") or img.get("data-src") or ""

    if not name:
        return None

    return {
        "name": name,
        "url": url,
        "image": image,
        "price": price,
        "msrp": msrp,
        "high_price": None,
        "currency": "USD",
        "promotion": promotion,
        "rating": rating,
        "brand": "",
        "description": "",
        "sku": "",
        "source": "html_card",
    }


def _extract_price(element, selectors: list[str]) -> float | None:
    """Extract a price value from an element using multiple selectors."""
    for selector in selectors:
        price_el = element.select_one(selector)
        if price_el:
            text = price_el.get_text(strip=True)
            match = re.search(r"\$?([\d,]+\.?\d*)", text)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    continue
    return None


def _extract_from_scripts(soup: BeautifulSoup) -> list[dict]:
    """Extract product data from inline script tags (React/Next.js hydration)."""
    products = []
    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string

        # Look for common patterns in SPAs
        patterns = [
            r'window\.__NEXT_DATA__\s*=\s*({.*?});',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'"products"\s*:\s*(\[.*?\])',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    extracted = _extract_products_from_data(data)
                    products.extend(extracted)
                except (json.JSONDecodeError, TypeError):
                    continue

    return products


def _extract_products_from_data(data, depth=0) -> list[dict]:
    """Recursively extract product-like objects from nested data."""
    if depth > 5:
        return []

    products = []

    if isinstance(data, dict):
        # Check if this dict looks like a product
        if "name" in data and ("price" in data or "msrp" in data or "offers" in data):
            price = data.get("price") or data.get("salePrice") or data.get("finalPrice")
            msrp = data.get("msrp") or data.get("listPrice") or data.get("originalPrice")

            if price is not None:
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    price = None
            if msrp is not None:
                try:
                    msrp = float(msrp)
                except (ValueError, TypeError):
                    msrp = None

            products.append({
                "name": str(data.get("name", "")),
                "url": str(data.get("url", data.get("pdpUrl", ""))),
                "image": str(data.get("image", data.get("imageUrl", ""))),
                "price": price,
                "msrp": msrp,
                "high_price": None,
                "currency": "USD",
                "brand": str(data.get("brand", data.get("brandName", ""))),
                "description": str(data.get("description", "")),
                "sku": str(data.get("sku", data.get("skuId", ""))),
                "promotion": str(data.get("promotion", data.get("promoMessage", ""))),
                "source": "script_data",
            })
        else:
            for value in data.values():
                products.extend(_extract_products_from_data(value, depth + 1))

    elif isinstance(data, list):
        for item in data:
            products.extend(_extract_products_from_data(item, depth + 1))

    return products


def scrape_all_categories() -> dict[str, list[dict]]:
    """Scrape all configured categories and return results."""
    all_results = {}

    for cat_key, cat_info in CATEGORIES.items():
        products = scrape_category_page(cat_key, cat_info)
        all_results[cat_key] = products
        # Be polite - wait between requests
        time.sleep(2)

    total = sum(len(v) for v in all_results.values())
    logger.info(f"Total products scraped: {total}")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scrape_all_categories()
    for cat, prods in results.items():
        print(f"\n{cat}: {len(prods)} products")
        for p in prods[:3]:
            print(f"  - {p['name']}: ${p.get('price', 'N/A')} (MSRP: ${p.get('msrp', 'N/A')})")
