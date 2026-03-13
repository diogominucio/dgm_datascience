#!/usr/bin/env python3
"""
Test script to validate Cloudflare API access and blinds.com scraping.

Run locally:
    pip install requests beautifulsoup4 lxml
    python test_cloudflare.py
"""

import json
import os
import sys

import requests
from bs4 import BeautifulSoup

# ===== CONFIGURATION =====
# Set these via environment variables or edit directly for testing
CLOUDFLARE_ACCOUNT_ID = os.getenv(
    "CLOUDFLARE_ACCOUNT_ID", "ddf1c64d26ab3334d00c00b39ee8112d"
)
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}"
CF_HEADERS = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json",
}

CATEGORIES_TO_TEST = {
    "cellular_shades": "https://www.blinds.com/c/cellular-shades/t/all",
    "faux_wood_blinds": "https://www.blinds.com/c/faux-wood-blinds/t/all",
    "wood_blinds": "https://www.blinds.com/c/wood-blinds/t/all",
    "roman_shades": "https://www.blinds.com/c/roman-shades/t/all",
    "roller_shades": "https://www.blinds.com/c/roller-shades/t/all",
}


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(label, success, detail=""):
    icon = "✅" if success else "❌"
    print(f"  {icon} {label}: {detail}")


# ===== TEST 1: Verify Cloudflare Token =====
def test_cf_token():
    print_header("TEST 1: Verificar Token Cloudflare")

    if not CLOUDFLARE_API_TOKEN:
        print("  ⚠️  Token não configurado. Defina CLOUDFLARE_API_TOKEN.")
        print("     export CLOUDFLARE_API_TOKEN='seu-token-aqui'")
        return False

    try:
        resp = requests.get(
            f"{CF_BASE}/tokens/verify",
            headers=CF_HEADERS,
            timeout=10,
        )
        data = resp.json()
        if data.get("success"):
            status = data["result"]["status"]
            print_result("Token válido", status == "active", f"Status: {status}")
            return status == "active"
        else:
            errors = data.get("errors", [])
            print_result("Token inválido", False, str(errors))
            return False
    except Exception as e:
        print_result("Erro de conexão", False, str(e))
        return False


# ===== TEST 2: Check available Cloudflare services =====
def test_cf_services():
    print_header("TEST 2: Verificar Serviços Disponíveis na Conta")

    if not CLOUDFLARE_API_TOKEN:
        print("  ⚠️  Pulando (token não configurado)")
        return

    services = {
        "Workers": f"{CF_BASE}/workers/scripts",
        "KV Namespaces": f"{CF_BASE}/storage/kv/namespaces",
        "Browser Rendering": f"{CF_BASE}/browser-rendering",
        "AI Gateway": f"{CF_BASE}/ai/models",
    }

    for name, url in services.items():
        try:
            resp = requests.get(url, headers=CF_HEADERS, timeout=10)
            data = resp.json()
            success = data.get("success", False)
            if success:
                result_count = len(data.get("result", []))
                print_result(name, True, f"{result_count} items encontrados")
            else:
                errors = data.get("errors", [{}])
                code = errors[0].get("code", "?") if errors else "?"
                msg = errors[0].get("message", "unknown") if errors else "unknown"
                print_result(name, False, f"Code {code}: {msg}")
        except Exception as e:
            print_result(name, False, str(e))


# ===== TEST 3: Direct scraping test =====
def test_direct_scrape():
    print_header("TEST 3: Scraping Direto do blinds.com")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Test just one category first
    test_url = CATEGORIES_TO_TEST["cellular_shades"]
    print(f"\n  Testando: {test_url}")

    try:
        resp = requests.get(test_url, headers=headers, timeout=30)
        print_result("HTTP Status", resp.status_code == 200, f"{resp.status_code}")
        print_result("Content Length", len(resp.text) > 1000, f"{len(resp.text)} chars")

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            title = soup.find("title")
            print_result(
                "Page Title",
                bool(title),
                title.get_text()[:60] if title else "N/A",
            )

            # Check for JSON-LD
            json_ld = soup.find_all("script", type="application/ld+json")
            print_result("JSON-LD Scripts", len(json_ld) > 0, f"{len(json_ld)} found")

            # Try to extract products
            products = _extract_test_products(soup, json_ld)
            print_result(
                "Produtos Extraídos",
                len(products) > 0,
                f"{len(products)} produtos",
            )

            # Show first 3 products
            if products:
                print("\n  📦 Primeiros produtos encontrados:")
                for i, p in enumerate(products[:5], 1):
                    name = p.get("name", "?")[:50]
                    price = p.get("price", "N/A")
                    msrp = p.get("msrp", "N/A")
                    print(f"     {i}. {name}")
                    print(f"        Preço: ${price} | MSRP: ${msrp}")

            return len(products) > 0
        else:
            print(f"\n  ⚠️  Site retornou {resp.status_code}.")
            print("     O blinds.com pode estar bloqueando scraping direto.")
            print("     Alternativas:")
            print("     1. Usar Cloudflare Browser Rendering API")
            print("     2. Usar um proxy rotativo (ScraperAPI, Bright Data)")
            print("     3. Usar Selenium/Playwright com headless browser")
            return False

    except Exception as e:
        print_result("Conexão", False, str(e))
        return False


def _extract_test_products(soup, json_ld_scripts):
    """Extract products for testing."""
    products = []

    # From JSON-LD
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Product", "IndividualProduct"):
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    products.append({
                        "name": item.get("name", "Unknown"),
                        "price": offers.get("price") or offers.get("lowPrice"),
                        "msrp": item.get("msrp"),
                        "source": "json_ld",
                    })
        except (json.JSONDecodeError, TypeError):
            continue

    # From HTML product cards
    card_selectors = [
        ".product-card", ".product-tile", ".product-item",
        "[data-product]", ".plp-product-card",
    ]
    for selector in card_selectors:
        cards = soup.select(selector)
        if cards:
            for card in cards:
                name_el = card.select_one("h2, h3, .product-name, .product-title")
                if name_el:
                    products.append({
                        "name": name_el.get_text(strip=True),
                        "price": "parsing needed",
                        "msrp": "parsing needed",
                        "source": "html_card",
                    })
            break

    # From script data
    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string
        # Look for product data patterns
        if '"products"' in text or '"productName"' in text:
            import re
            matches = re.findall(
                r'"(?:product)?[Nn]ame"\s*:\s*"([^"]{5,80})"', text
            )
            for name in matches[:10]:
                if not any(p["name"] == name for p in products):
                    products.append({
                        "name": name,
                        "price": "in script data",
                        "msrp": "in script data",
                        "source": "script",
                    })

    return products


# ===== TEST 4: Cloudflare Browser Rendering =====
def test_cf_browser_rendering():
    print_header("TEST 4: Cloudflare Browser Rendering API")

    if not CLOUDFLARE_API_TOKEN:
        print("  ⚠️  Pulando (token não configurado)")
        return

    test_url = CATEGORIES_TO_TEST["cellular_shades"]

    # Try the Browser Rendering API
    endpoint = f"{CF_BASE}/browser-rendering/render"
    payload = {
        "url": test_url,
        "wait_until": "networkidle0",
        "viewport": {"width": 1920, "height": 1080},
    }

    try:
        resp = requests.post(
            endpoint,
            headers=CF_HEADERS,
            json=payload,
            timeout=60,
        )
        data = resp.json()

        if data.get("success"):
            html = data.get("result", {}).get("html", "")
            print_result(
                "Browser Rendering",
                len(html) > 1000,
                f"{len(html)} chars de HTML renderizado",
            )

            if html:
                soup = BeautifulSoup(html, "lxml")
                json_ld = soup.find_all("script", type="application/ld+json")
                products = _extract_test_products(soup, json_ld)
                print_result(
                    "Produtos via Browser Rendering",
                    len(products) > 0,
                    f"{len(products)} produtos",
                )

                if products:
                    print("\n  📦 Produtos encontrados via Browser Rendering:")
                    for i, p in enumerate(products[:5], 1):
                        print(f"     {i}. {p['name'][:50]}: ${p.get('price', 'N/A')}")
        else:
            errors = data.get("errors", [])
            print_result("Browser Rendering", False, str(errors))
            print("\n  ℹ️  Se o Browser Rendering não está disponível na sua conta,")
            print("     você pode ativá-lo no dashboard da Cloudflare:")
            print("     Dashboard > Workers & Pages > Browser Rendering")

    except Exception as e:
        print_result("Browser Rendering", False, str(e))


# ===== TEST 5: Test all categories =====
def test_all_categories():
    print_header("TEST 5: Testar Todas as Categorias")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    import time

    total_products = 0

    for cat_key, url in CATEGORIES_TO_TEST.items():
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                json_ld = soup.find_all("script", type="application/ld+json")
                products = _extract_test_products(soup, json_ld)
                total_products += len(products)
                print_result(cat_key, len(products) > 0, f"{len(products)} produtos")
            else:
                print_result(cat_key, False, f"HTTP {resp.status_code}")
        except Exception as e:
            print_result(cat_key, False, str(e))

        time.sleep(2)

    print(f"\n  📊 Total de produtos encontrados: {total_products}")


# ===== MAIN =====
def main():
    print("\n" + "🔍 " * 20)
    print("  BLINDS.COM PRICE MONITOR — TESTE DE VALIDAÇÃO")
    print("🔍 " * 20)

    # Test 1: Cloudflare token
    token_ok = test_cf_token()

    # Test 2: Available services
    test_cf_services()

    # Test 3: Direct scraping
    direct_ok = test_direct_scrape()

    # Test 4: Browser Rendering (only if token works)
    if token_ok:
        test_cf_browser_rendering()

    # Test 5: All categories (only if direct scraping works)
    if direct_ok:
        test_all_categories()

    # Summary
    print_header("RESUMO")
    if direct_ok:
        print("  ✅ Scraping direto funciona! O sistema pode coletar dados.")
        print("     Execute: python main.py")
    elif token_ok:
        print("  ⚠️  Scraping direto bloqueado, mas Cloudflare API disponível.")
        print("     Recomendação: usar Cloudflare Browser Rendering ou Workers.")
    else:
        print("  ❌ Nenhum método funcionou.")
        print("     Opções:")
        print("     1. Configure o token da Cloudflare (CLOUDFLARE_API_TOKEN)")
        print("     2. Use um serviço de proxy (ScraperAPI, Bright Data)")
        print("     3. Use Selenium/Playwright para renderização local")
        print("     4. Cadastre-se no programa de afiliados (Impact.com)")
        print("        para acesso ao product feed da blinds.com")


if __name__ == "__main__":
    main()
