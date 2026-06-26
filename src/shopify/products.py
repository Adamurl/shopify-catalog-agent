from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.models.product import Product
from src.shopify.client import ShopifyGraphQLClient

LOGGER = logging.getLogger(__name__)
PRODUCTS_PAGE_SIZE = 100
VARIANTS_PAGE_SIZE = 100
COLLECTIONS_PAGE_SIZE = 50
MEDIA_PAGE_SIZE = 100

PRODUCTS_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        title
        handle
        vendor
        productType
        category {
          name
        }
        tags
        status
        seo {
          title
          description
        }
        descriptionHtml
        options {
          id
          name
          values
        }
        collections(first: %d) {
          edges {
            node {
              id
              title
              handle
            }
          }
        }
        variants(first: %d) {
          edges {
            node {
              id
              title
              sku
              barcode
              inventoryQuantity
              selectedOptions {
                name
                value
              }
            }
          }
        }
        media(first: %d) {
          edges {
            node {
              ... on MediaImage {
                id
                alt
                image {
                  url
                  altText
                }
              }
            }
          }
        }
      }
    }
  }
}
""" % (
    COLLECTIONS_PAGE_SIZE,
    VARIANTS_PAGE_SIZE,
    MEDIA_PAGE_SIZE,
)


def fetch_all_products(client: ShopifyGraphQLClient) -> list[Product]:
    products: list[Product] = []
    cursor: str | None = None

    while True:
        data = client.execute(
            PRODUCTS_QUERY,
            variables={"first": PRODUCTS_PAGE_SIZE, "after": cursor},
        )
        page = data.get("products")
        if not isinstance(page, dict):
            raise ValueError("Shopify response missing products connection")

        edges = page.get("edges") or []
        products.extend(
            Product.from_shopify_node(edge.get("node", {})) for edge in edges
        )
        page_info = page.get("pageInfo") or {}
        LOGGER.info("Fetched %s products so far", len(products))

        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            raise ValueError("Shopify pagination indicated a next page without cursor")

    return products


def save_product_snapshot(products: list[Product], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot: list[dict[str, Any]] = [product.to_dict() for product in products]
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
