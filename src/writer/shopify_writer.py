from __future__ import annotations

from typing import Any

from src.shopify.client import ShopifyApiError, ShopifyGraphQLClient
from src.writer.write_models import (
    OneProductUpdate,
    ShopifyMediaSnapshot,
    ShopifyProductSnapshot,
)

PRODUCT_BY_ID_QUERY = """
query ProductById($id: ID!) {
  node(id: $id) {
    ... on Product {
      id
      title
      handle
      status
      descriptionHtml
      tags
      seo {
        title
        description
      }
      variants(first: 100) {
        edges {
          node {
            inventoryQuantity
          }
        }
      }
      media(first: 1) {
        edges {
          node {
            id
            alt
            ... on MediaImage {
              image {
                altText
                url
              }
            }
          }
        }
      }
    }
  }
}
"""

PRODUCT_UPDATE_MUTATION = """
mutation UpdateOneProduct($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      id
      title
      handle
      status
      descriptionHtml
      tags
      seo {
        title
        description
      }
      variants(first: 100) {
        edges {
          node {
            inventoryQuantity
          }
        }
      }
      media(first: 1) {
        edges {
          node {
            id
            alt
            ... on MediaImage {
              image {
                altText
                url
              }
            }
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_UPDATE_MEDIA_MUTATION = """
mutation UpdateOneProductMedia($productId: ID!, $media: [UpdateMediaInput!]!) {
  productUpdateMedia(productId: $productId, media: $media) {
    media {
      id
      alt
      ... on MediaImage {
        image {
          altText
          url
        }
      }
    }
    mediaUserErrors {
      field
      message
      code
    }
  }
}
"""


def fetch_product_snapshot(
    client: ShopifyGraphQLClient,
    product_id: str,
) -> ShopifyProductSnapshot:
    data = client.execute(PRODUCT_BY_ID_QUERY, {"id": product_id})
    node = data.get("node")
    if not isinstance(node, dict):
        raise ShopifyApiError(f"Product not found: {product_id}")
    return ShopifyProductSnapshot.from_node(node)


def apply_product_update(
    client: ShopifyGraphQLClient,
    update: OneProductUpdate,
) -> ShopifyProductSnapshot:
    product_fields = [
        field for field in update.written_fields if field != "image_alt"
    ]
    snapshot: ShopifyProductSnapshot | None = None
    if product_fields:
        snapshot = _update_product(client, update)
    if update.first_image_alt is not None:
        before = snapshot or fetch_product_snapshot(client, update.product_id)
        if not before.media:
            raise ShopifyApiError("Cannot update first image alt; product has no media")
        _update_first_media_alt(
            client,
            product_id=update.product_id,
            media_id=before.media[0].id,
            alt_text=update.first_image_alt,
        )
    return fetch_product_snapshot(client, update.product_id)


def _update_product(
    client: ShopifyGraphQLClient,
    update: OneProductUpdate,
) -> ShopifyProductSnapshot:
    data = client.execute(
        PRODUCT_UPDATE_MUTATION,
        variables={"product": update.to_product_input()},
    )
    payload = data.get("productUpdate")
    if not isinstance(payload, dict):
        raise ShopifyApiError("Shopify response missing productUpdate payload")
    user_errors = payload.get("userErrors") or []
    if user_errors:
        raise ShopifyApiError(
            "Shopify productUpdate returned user errors: "
            + "; ".join(_format_user_error(error) for error in user_errors if isinstance(error, dict))
        )
    product = payload.get("product")
    if not isinstance(product, dict):
        raise ShopifyApiError("Shopify productUpdate did not return a product")
    return ShopifyProductSnapshot.from_node(product)


def _update_first_media_alt(
    client: ShopifyGraphQLClient,
    product_id: str,
    media_id: str,
    alt_text: str,
) -> ShopifyMediaSnapshot:
    data = client.execute(
        PRODUCT_UPDATE_MEDIA_MUTATION,
        variables={"productId": product_id, "media": [{"id": media_id, "alt": alt_text}]},
    )
    payload = data.get("productUpdateMedia")
    if not isinstance(payload, dict):
        raise ShopifyApiError("Shopify response missing productUpdateMedia payload")
    user_errors = payload.get("mediaUserErrors") or []
    if user_errors:
        raise ShopifyApiError(
            "Shopify productUpdateMedia returned user errors: "
            + "; ".join(_format_user_error(error) for error in user_errors if isinstance(error, dict))
        )
    media = payload.get("media") or []
    if not media or not isinstance(media[0], dict):
        raise ShopifyApiError("Shopify productUpdateMedia did not return media")
    return ShopifyMediaSnapshot.from_node(media[0])


def _format_user_error(error: dict[str, Any]) -> str:
    field = error.get("field")
    message = error.get("message", "Unknown error")
    if field:
        return f"{'.'.join(str(part) for part in field)}: {message}"
    return str(message)
