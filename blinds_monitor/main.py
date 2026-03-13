#!/usr/bin/env python3
"""
Blinds.com Price Monitor — Main Orchestrator

Monitors blinds.com daily for price changes, promotions, and trends.
Sends executive competitor analysis reports via email.

Usage:
    python main.py                  # Run once (scrape + analyze + report)
    python main.py --scrape-only    # Only scrape, no report
    python main.py --report-only    # Only generate report from existing data
    python main.py --schedule       # Run on a daily schedule
"""

import argparse
import logging
import sys
from datetime import datetime

import schedule
import time

from scraper import scrape_all_categories
from price_analyzer import save_daily_snapshot, load_history, analyze_trends
from report_generator import render_report, save_report, send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("blinds_monitor.log"),
    ],
)

logger = logging.getLogger(__name__)


def run_scrape():
    """Execute the scraping phase."""
    logger.info("=" * 60)
    logger.info("Starting blinds.com price scraping...")
    logger.info("=" * 60)

    results = scrape_all_categories()

    total = sum(len(v) for v in results.values())
    logger.info(f"Scraping complete: {total} products found across {len(results)} categories")

    for cat, products in results.items():
        logger.info(f"  {cat}: {len(products)} products")

    # Save snapshot
    snapshot_path = save_daily_snapshot(results)
    logger.info(f"Snapshot saved: {snapshot_path}")

    return results


def run_report():
    """Generate and send the analysis report."""
    logger.info("Generating analysis report...")

    # Load historical data
    df = load_history(days=90)

    if df.empty:
        logger.warning("No historical data available. Run scraping first.")
        return None

    # Analyze trends
    analysis = analyze_trends(df)

    # Render HTML report
    html = render_report(analysis)

    # Save report to disk
    report_path = save_report(html)
    logger.info(f"Report saved: {report_path}")

    # Send email
    email_sent = send_email(html)
    if email_sent:
        logger.info("Email report sent successfully!")
    else:
        logger.warning("Email not sent. Check SMTP configuration in .env file.")

    return report_path


def run_full_pipeline():
    """Run the complete pipeline: scrape -> analyze -> report."""
    start_time = datetime.now()
    logger.info(f"Starting full pipeline at {start_time.isoformat()}")

    try:
        # Phase 1: Scrape
        run_scrape()

        # Phase 2: Report
        run_report()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Pipeline completed in {elapsed:.1f} seconds")

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        raise


def run_scheduled():
    """Run the monitor on a daily schedule."""
    logger.info("Starting scheduled execution (daily at 08:00 AM)")

    # Run immediately on first start
    run_full_pipeline()

    # Schedule daily execution
    schedule.every().day.at("08:00").do(run_full_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(
        description="Blinds.com Price Monitor — Competitor Intelligence System"
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only run the scraper, skip report generation",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate report from existing historical data",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a daily schedule (08:00 AM)",
    )

    args = parser.parse_args()

    if args.scrape_only:
        run_scrape()
    elif args.report_only:
        run_report()
    elif args.schedule:
        run_scheduled()
    else:
        run_full_pipeline()


if __name__ == "__main__":
    main()
