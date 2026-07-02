from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.catalog.normalize import normalize_products
from src.catalog.utils import write_json
from src.shopify.client import ShopifyGraphQLClient

LOGGER = logging.getLogger(__name__)

PRODUCTS_PAGE_SIZE = 100
VARIANTS_PAGE_SIZE = 100
COLLECTIONS_PAGE_SIZE = 100
MEDIA_PAGE_SIZE = 100
IMAGES_PAGE_SIZE = 100

PRODUCTS_QUERY = """
query PhaseOneProducts($first: Int!, $after: String) {
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
        status
        vendor
        productType
        category {
          name
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
        tags
        seo {
          title
          description
        }
        descriptionHtml
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
        images(first: %d) {
          edges {
            node {
              id
              url
              altText
            }
          }
        }
        variants(first: %d) {
          edges {
            node {
              id
              title
              sku
              inventoryQuantity
            }
          }
        }
        createdAt
        updatedAt
      }
    }
  }
}
""" % (
    COLLECTIONS_PAGE_SIZE,
    MEDIA_PAGE_SIZE,
    IMAGES_PAGE_SIZE,
    VARIANTS_PAGE_SIZE,
)


def fetch_raw_product_nodes(client: ShopifyGraphQLClient) -> list[dict[str, Any]]:
    """Fetch Shopify products with cursor pagination using read-only queries."""
    products: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = client.execute(
            PRODUCTS_QUERY,
            variables={"first": PRODUCTS_PAGE_SIZE, "after": cursor},
        )
        connection = data.get("products")
        if not isinstance(connection, dict):
            raise ValueError("Shopify response missing products connection")

        edges = connection.get("edges") or []
        products.extend(edge.get("node") or {} for edge in edges)

        page_info = connection.get("pageInfo") or {}
        LOGGER.info("READ ONLY MODE: fetched %s products so far", len(products))
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            raise ValueError("Shopify pagination indicated a next page without cursor")

    return products


def fetch_and_save_snapshots(
    client: ShopifyGraphQLClient,
    raw_path: Path,
    normalized_path: Path,
) -> tuple[Path, Path]:
    """Fetch products and save raw plus canonical normalized JSON snapshots."""
    raw_products = fetch_raw_product_nodes(client)
    normalized = normalize_products(raw_products)
    write_json(raw_path, raw_products)
    write_json(normalized_path, [product.to_dict() for product in normalized])
    return raw_path, normalized_path
