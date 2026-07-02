from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.shopify.client import ShopifyApiError, ShopifyGraphQLClient


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
mutation UpdateProductSeo($product: ProductUpdateInput!) {
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
    }
    userErrors {
      field
      message
    }
  }
}
"""

PRODUCT_UPDATE_MEDIA_MUTATION = """
mutation UpdateProductMedia($productId: ID!, $media: [UpdateMediaInput!]!) {
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


@dataclass(frozen=True)
class ShopifyProductMediaSnapshot:
    id: str
    alt_text: str | None
    url: str | None

    @classmethod
    def from_node(cls, node: dict[str, Any]) -> "ShopifyProductMediaSnapshot":
        image = node.get("image") or {}
        return cls(
            id=str(node.get("id") or ""),
            alt_text=node.get("alt") or image.get("altText"),
            url=image.get("url"),
        )


@dataclass(frozen=True)
class ShopifyProductSnapshot:
    id: str
    title: str
    handle: str
    status: str | None
    tags: list[str]
    seo_title: str | None
    seo_description: str | None
    description_html: str | None
    inventory_quantity: int | None
    media: list[ShopifyProductMediaSnapshot]

    @classmethod
    def from_node(cls, node: dict[str, Any]) -> "ShopifyProductSnapshot":
        seo = node.get("seo") or {}
        variants = node.get("variants", {}).get("edges", [])
        quantities = [
            edge.get("node", {}).get("inventoryQuantity")
            for edge in variants
            if edge.get("node", {}).get("inventoryQuantity") is not None
        ]
        media = [
            ShopifyProductMediaSnapshot.from_node(edge.get("node", {}))
            for edge in node.get("media", {}).get("edges", [])
        ]
        return cls(
            id=str(node.get("id") or ""),
            title=str(node.get("title") or ""),
            handle=str(node.get("handle") or ""),
            status=node.get("status"),
            tags=list(node.get("tags") or []),
            seo_title=seo.get("title"),
            seo_description=seo.get("description"),
            description_html=node.get("descriptionHtml"),
            inventory_quantity=sum(quantities) if quantities else None,
            media=media,
        )


@dataclass(frozen=True)
class ProductSeoUpdate:
    product_id: str
    seo_title: str
    seo_description: str
    tags: list[str]
    title: str | None = None
    description_html: str | None = None
    handle: str | None = None

    def to_product_input(self) -> dict[str, Any]:
        product_input = {
            "id": self.product_id,
            "seo": {
                "title": self.seo_title,
                "description": self.seo_description,
            },
            "tags": self.tags,
        }
        if self.title:
            product_input["title"] = self.title
        if self.description_html:
            product_input["descriptionHtml"] = self.description_html
        if self.handle:
            product_input["handle"] = self.handle
        return product_input


@dataclass(frozen=True)
class ProductMediaAltUpdate:
    product_id: str
    media_id: str
    alt_text: str


def fetch_product_snapshot(
    client: ShopifyGraphQLClient,
    product_id: str,
) -> ShopifyProductSnapshot:
    data = client.execute(PRODUCT_BY_ID_QUERY, {"id": product_id})
    node = data.get("node")
    if not isinstance(node, dict):
        raise ShopifyApiError(f"Product not found: {product_id}")
    return ShopifyProductSnapshot.from_node(node)


def update_product_seo(
    client: ShopifyGraphQLClient,
    update: ProductSeoUpdate,
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
        messages = [
            _format_user_error(error)
            for error in user_errors
            if isinstance(error, dict)
        ]
        raise ShopifyApiError(
            "Shopify productUpdate returned user errors: "
            + "; ".join(messages)
        )

    product = payload.get("product")
    if not isinstance(product, dict):
        raise ShopifyApiError("Shopify productUpdate did not return a product")
    return ShopifyProductSnapshot.from_node(product)


def update_product_media_alt(
    client: ShopifyGraphQLClient,
    update: ProductMediaAltUpdate,
) -> ShopifyProductMediaSnapshot:
    data = client.execute(
        PRODUCT_UPDATE_MEDIA_MUTATION,
        variables={
            "productId": update.product_id,
            "media": [{"id": update.media_id, "alt": update.alt_text}],
        },
    )
    payload = data.get("productUpdateMedia")
    if not isinstance(payload, dict):
        raise ShopifyApiError("Shopify response missing productUpdateMedia payload")

    user_errors = payload.get("mediaUserErrors") or []
    if user_errors:
        messages = [
            _format_user_error(error)
            for error in user_errors
            if isinstance(error, dict)
        ]
        raise ShopifyApiError(
            "Shopify productUpdateMedia returned user errors: "
            + "; ".join(messages)
        )

    media = payload.get("media") or []
    if not media or not isinstance(media[0], dict):
        raise ShopifyApiError("Shopify productUpdateMedia did not return media")
    return ShopifyProductMediaSnapshot.from_node(media[0])


def append_missing_tags(existing_tags: list[str], new_tags: list[str]) -> list[str]:
    merged = list(existing_tags)
    normalized_existing = {_normalize_tag(tag) for tag in existing_tags}

    for tag in new_tags:
        normalized_tag = _normalize_tag(tag)
        if normalized_tag and normalized_tag not in normalized_existing:
            merged.append(tag)
            normalized_existing.add(normalized_tag)

    return merged


def _format_user_error(error: dict[str, Any]) -> str:
    field = error.get("field")
    message = error.get("message", "Unknown error")
    if field:
        return f"{'.'.join(str(part) for part in field)}: {message}"
    return str(message)


def _normalize_tag(tag: str) -> str:
    return " ".join(tag.casefold().split())
