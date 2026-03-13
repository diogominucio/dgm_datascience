"""Price classification, trend analysis, and historical data management."""

import csv
import json
import logging
import os
from datetime import datetime, timedelta

import pandas as pd

from config import DATA_DIR, PRICE_TIERS

logger = logging.getLogger(__name__)


def classify_price_tier(price: float | None) -> str:
    """Classify a price into its tier.

    Tiers:
        Tier 1: $0-$70
        Tier 2: $70-$100
        Tier 3: $100-$150
        Tier 4: $150-$200
        Tier 5: $200-$300
        Tier 6: $300+
    """
    if price is None:
        return "Unknown"

    for threshold, label in PRICE_TIERS:
        if price <= threshold:
            return label

    return "Tier 6: $300+"


def enrich_products(products: list[dict]) -> list[dict]:
    """Add price tier classifications and discount calculations to products."""
    for product in products:
        price = product.get("price")
        msrp = product.get("msrp")

        # Classify price tiers
        product["price_tier"] = classify_price_tier(price)
        product["msrp_tier"] = classify_price_tier(msrp)

        # Calculate discount
        if price is not None and msrp is not None and msrp > 0:
            product["discount_amount"] = round(msrp - price, 2)
            product["discount_pct"] = round((1 - price / msrp) * 100, 1)
        else:
            product["discount_amount"] = None
            product["discount_pct"] = None

    return products


def save_daily_snapshot(all_results: dict[str, list[dict]]) -> str:
    """Save today's scrape results as a daily snapshot."""
    os.makedirs(DATA_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_file = os.path.join(DATA_DIR, f"snapshot_{today}.json")

    # Enrich all products with tier classifications
    enriched = {}
    for cat_key, products in all_results.items():
        enriched[cat_key] = enrich_products(products)

    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Saved daily snapshot: {snapshot_file}")

    # Also append to master CSV for easy trend analysis
    _append_to_master_csv(enriched)

    return snapshot_file


def _append_to_master_csv(all_results: dict[str, list[dict]]):
    """Append current results to the master CSV file for historical tracking."""
    csv_file = os.path.join(DATA_DIR, "price_history.csv")

    fieldnames = [
        "scrape_date", "scrape_timestamp", "category", "category_key",
        "name", "brand", "sku", "url",
        "price", "msrp", "high_price",
        "price_tier", "msrp_tier",
        "discount_amount", "discount_pct",
        "promotion", "rating", "source",
    ]

    file_exists = os.path.exists(csv_file)

    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()

        for products in all_results.values():
            for product in products:
                writer.writerow(product)

    logger.info(f"Appended data to master CSV: {csv_file}")


def load_history(days: int = 90) -> pd.DataFrame:
    """Load historical price data from master CSV."""
    csv_file = os.path.join(DATA_DIR, "price_history.csv")

    if not os.path.exists(csv_file):
        logger.warning("No historical data found")
        return pd.DataFrame()

    df = pd.read_csv(csv_file, parse_dates=["scrape_date"])

    # Filter to requested time range
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df["scrape_date"] >= cutoff]

    return df


def analyze_trends(df: pd.DataFrame) -> dict:
    """Analyze price trends and promotion patterns from historical data."""
    if df.empty:
        return {"error": "No historical data available for analysis"}

    analysis = {}

    # --- Overall Summary ---
    analysis["total_products_tracked"] = df["name"].nunique()
    analysis["total_snapshots"] = df["scrape_date"].nunique()
    analysis["date_range"] = {
        "start": df["scrape_date"].min().strftime("%Y-%m-%d"),
        "end": df["scrape_date"].max().strftime("%Y-%m-%d"),
    }

    # --- Price Changes by Category ---
    category_stats = {}
    for cat in df["category"].unique():
        cat_df = df[df["category"] == cat]
        latest_date = cat_df["scrape_date"].max()
        latest = cat_df[cat_df["scrape_date"] == latest_date]

        # Price distribution today
        prices = latest["price"].dropna()
        msrps = latest["msrp"].dropna()

        category_stats[cat] = {
            "product_count": latest["name"].nunique(),
            "avg_price": round(prices.mean(), 2) if not prices.empty else None,
            "min_price": round(prices.min(), 2) if not prices.empty else None,
            "max_price": round(prices.max(), 2) if not prices.empty else None,
            "avg_msrp": round(msrps.mean(), 2) if not msrps.empty else None,
            "avg_discount_pct": round(
                latest["discount_pct"].dropna().mean(), 1
            ) if not latest["discount_pct"].dropna().empty else None,
            "price_tier_distribution": (
                latest["price_tier"].value_counts().to_dict()
            ),
        }

    analysis["categories"] = category_stats

    # --- Price Movement Detection ---
    price_changes = _detect_price_changes(df)
    analysis["price_changes"] = price_changes

    # --- Promotion Patterns ---
    promo_analysis = _analyze_promotions(df)
    analysis["promotions"] = promo_analysis

    # --- Weekly Patterns ---
    weekly = _analyze_weekly_patterns(df)
    analysis["weekly_patterns"] = weekly

    # --- Monthly Trends ---
    monthly = _analyze_monthly_trends(df)
    analysis["monthly_trends"] = monthly

    return analysis


def _detect_price_changes(df: pd.DataFrame) -> list[dict]:
    """Detect products with price changes between snapshots."""
    changes = []

    if df["scrape_date"].nunique() < 2:
        return changes

    dates = sorted(df["scrape_date"].unique())
    latest_date = dates[-1]
    previous_date = dates[-2]

    latest = df[df["scrape_date"] == latest_date].set_index("name")
    previous = df[df["scrape_date"] == previous_date].set_index("name")

    common_products = latest.index.intersection(previous.index)

    for product_name in common_products:
        current_price = latest.loc[product_name, "price"]
        prev_price = previous.loc[product_name, "price"]

        # Handle cases where there are multiple rows per product
        if isinstance(current_price, pd.Series):
            current_price = current_price.iloc[0]
        if isinstance(prev_price, pd.Series):
            prev_price = prev_price.iloc[0]

        if pd.isna(current_price) or pd.isna(prev_price):
            continue

        if current_price != prev_price:
            pct_change = round((current_price - prev_price) / prev_price * 100, 1)
            changes.append({
                "product": product_name,
                "category": latest.loc[product_name, "category"]
                if isinstance(latest.loc[product_name, "category"], str)
                else latest.loc[product_name, "category"].iloc[0],
                "previous_price": prev_price,
                "current_price": current_price,
                "change_amount": round(current_price - prev_price, 2),
                "change_pct": pct_change,
                "direction": "increase" if pct_change > 0 else "decrease",
                "previous_date": str(previous_date.date())
                if hasattr(previous_date, "date") else str(previous_date),
                "current_date": str(latest_date.date())
                if hasattr(latest_date, "date") else str(latest_date),
            })

    # Sort by absolute change percentage
    changes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return changes


def _analyze_promotions(df: pd.DataFrame) -> dict:
    """Analyze promotion patterns across time."""
    promo_df = df[df["promotion"].notna() & (df["promotion"] != "")]

    if promo_df.empty:
        return {"active_promotions": [], "promotion_frequency": {}}

    # Current active promotions
    latest_date = df["scrape_date"].max()
    active = promo_df[promo_df["scrape_date"] == latest_date]

    active_promos = []
    for _, row in active.iterrows():
        active_promos.append({
            "product": row["name"],
            "category": row["category"],
            "promotion": row["promotion"],
            "price": row["price"],
            "msrp": row["msrp"],
            "discount_pct": row["discount_pct"],
        })

    # Promotion frequency by category
    promo_freq = (
        promo_df.groupby(["category", "scrape_date"])
        .size()
        .reset_index(name="promo_count")
        .groupby("category")["promo_count"]
        .mean()
        .to_dict()
    )

    return {
        "active_promotions": active_promos,
        "promotion_frequency": promo_freq,
        "total_promo_products_today": len(active_promos),
    }


def _analyze_weekly_patterns(df: pd.DataFrame) -> dict:
    """Identify weekly price/promotion patterns."""
    if df.empty:
        return {}

    df = df.copy()
    df["day_of_week"] = pd.to_datetime(df["scrape_date"]).dt.day_name()
    df["week_number"] = pd.to_datetime(df["scrape_date"]).dt.isocalendar().week

    # Average discount by day of week
    daily_discounts = (
        df.groupby("day_of_week")["discount_pct"]
        .mean()
        .round(1)
        .to_dict()
    )

    return {
        "avg_discount_by_day": daily_discounts,
    }


def _analyze_monthly_trends(df: pd.DataFrame) -> dict:
    """Analyze monthly price trends."""
    if df.empty:
        return {}

    df = df.copy()
    df["month"] = pd.to_datetime(df["scrape_date"]).dt.to_period("M").astype(str)

    monthly_avg = (
        df.groupby(["month", "category"])["price"]
        .mean()
        .round(2)
        .reset_index()
    )

    monthly_discount = (
        df.groupby(["month", "category"])["discount_pct"]
        .mean()
        .round(1)
        .reset_index()
    )

    return {
        "avg_price_by_month": monthly_avg.to_dict("records"),
        "avg_discount_by_month": monthly_discount.to_dict("records"),
    }
