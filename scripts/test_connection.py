from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shopify.client import ShopifyApiError, ShopifyConfig, ShopifyGraphQLClient

SHOP_QUERY = """
query ShopConnectionTest {
  shop {
    name
    myshopifyDomain
  }
}
"""

PRODUCT_READ_QUERY = """
query ProductReadTest {
  products(first: 1) {
    edges {
      node {
        id
        title
        handle
      }
    }
  }
}
"""


def main() -> int:
    logging.basicConfig(level=logging.CRITICAL)
    load_dotenv()

    try:
        config = ShopifyConfig.from_env()
        client = ShopifyGraphQLClient(config)
        shop_data = client.execute(SHOP_QUERY)
    except Exception as exc:
        print(f"Connection test failed: {exc}")
        return 1

    print("Connection test passed")
    shop = shop_data.get("shop") or {}
    print(f"Shop: {shop.get('name', 'Unknown')}")
    print(f"Domain: {shop.get('myshopifyDomain', config.store_domain)}")

    try:
        product_data = client.execute(PRODUCT_READ_QUERY)
    except ShopifyApiError as exc:
        print(f"Product read access: no ({exc})")
        return 2

    product_edges = (product_data.get("products") or {}).get("edges") or []
    first_product = product_edges[0]["node"] if product_edges else None
    if first_product:
        print(f"Product read access: yes ({first_product.get('title')})")
    else:
        print("Product read access: yes (no products returned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
