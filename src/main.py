from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

from src.audits.seo_audit import (
    generate_catalog_summary,
    write_summary_csv,
    write_summary_markdown,
)
from src.audits.title_audit import audit_titles
from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient
from src.shopify.products import fetch_all_products, save_product_snapshot

RAW_PRODUCTS_PATH = Path("data/raw/products.json")
REPORTS_DIR = Path("data/reports")
SUMMARY_CSV_PATH = REPORTS_DIR / "catalog_summary.csv"
SUMMARY_MD_PATH = REPORTS_DIR / "catalog_summary.md"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> int:
    configure_logging()
    load_dotenv()

    try:
        config = ShopifyConfig.from_env()
        client = ShopifyGraphQLClient(config)
        products = fetch_all_products(client)

        save_product_snapshot(products, RAW_PRODUCTS_PATH)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        summary = generate_catalog_summary(products)
        write_summary_csv(summary, str(SUMMARY_CSV_PATH))
        write_summary_markdown(summary, str(SUMMARY_MD_PATH))
        title_findings = audit_titles(products)
    except Exception as exc:
        logging.getLogger(__name__).exception("Catalog audit failed")
        print(f"Catalog audit failed: {exc}")
        return 1

    print("Catalog audit complete")
    print(f"Products audited: {summary.total_products}")
    print(f"Missing product type: {summary.products_missing_product_type}")
    print(f"Missing SEO title: {summary.products_missing_seo_title}")
    print(f"Missing meta description: {summary.products_missing_meta_description}")
    print(f"Missing images: {summary.products_missing_images}")
    print(f"Title audit findings: {len(title_findings)}")
    print(f"Raw snapshot: {RAW_PRODUCTS_PATH}")
    print(f"Summary CSV: {SUMMARY_CSV_PATH}")
    print(f"Summary Markdown: {SUMMARY_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
