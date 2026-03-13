"""Configuration for Blinds.com Price Monitor."""

import os
from dotenv import load_dotenv

load_dotenv()

# Categories to monitor on blinds.com
CATEGORIES = {
    "cellular_shades": {
        "name": "Cellular Shades",
        "url": "https://www.blinds.com/c/cellular-shades/t/all",
        "search_terms": ["cellular shade", "cell shade", "honeycomb shade"],
    },
    "faux_wood_blinds": {
        "name": "Faux Wood Blinds",
        "url": "https://www.blinds.com/c/faux-wood-blinds/t/all",
        "search_terms": ["faux wood blind"],
    },
    "wood_blinds": {
        "name": "Wood Blinds",
        "url": "https://www.blinds.com/c/wood-blinds/t/all",
        "search_terms": ["wood blind"],
    },
    "roman_shades": {
        "name": "Roman Shades",
        "url": "https://www.blinds.com/c/roman-shades/t/all",
        "search_terms": ["roman shade"],
    },
    "roller_shades": {
        "name": "Roller Shades",
        "url": "https://www.blinds.com/c/roller-shades/t/all",
        "search_terms": ["roller shade"],
    },
}

# Default window size for price scraping (standard comparison size)
DEFAULT_WIDTH = 36  # inches
DEFAULT_HEIGHT = 48  # inches

# Price tiers classification
PRICE_TIERS = [
    (70, "Tier 1: $0-$70"),
    (100, "Tier 2: $70-$100"),
    (150, "Tier 3: $100-$150"),
    (200, "Tier 4: $150-$200"),
    (300, "Tier 5: $200-$300"),
    (float("inf"), "Tier 6: $300+"),
]

# Email settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "Diogominucio@gmail.com")

# Data storage
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

# Cloudflare settings
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
