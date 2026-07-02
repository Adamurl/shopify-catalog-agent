import pytest

from src.shopify.client import ShopifyApiError
from proof_of_concept.macuahuitl.product_updates import (
    ProductMediaAltUpdate,
    ProductSeoUpdate,
    append_missing_tags,
    fetch_product_snapshot,
    update_product_media_alt,
    update_product_seo,
)


class FakeClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        query: str,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append({"query": query, "variables": variables or {}})
        return self.responses.pop(0)


def test_append_missing_tags_preserves_existing_tags_and_dedupes() -> None:
    tags = append_missing_tags(
        ["Macuahuitl", "Danza Azteca"],
        ["macuahuitl", "Aztec club", "Danza  Azteca"],
    )

    assert tags == ["Macuahuitl", "Danza Azteca", "Aztec club"]


def test_fetch_product_snapshot_sums_variant_inventory() -> None:
    client = FakeClient(
        [
            {
                "node": {
                    "id": "gid://shopify/Product/1",
                    "title": "Macuahuitl",
                    "handle": "macuahuitl",
                    "status": "ACTIVE",
                    "descriptionHtml": "<p>Description</p>",
                    "tags": ["Macuahuitl"],
                    "seo": {"title": "SEO", "description": "Description"},
                    "variants": {
                        "edges": [
                            {"node": {"inventoryQuantity": 2}},
                            {"node": {"inventoryQuantity": 3}},
                        ]
                    },
                    "media": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/MediaImage/1",
                                    "alt": "Current alt",
                                    "image": {
                                        "altText": "Current alt",
                                        "url": "https://example.com/image.jpg",
                                    },
                                }
                            }
                        ]
                    },
                }
            }
        ]
    )

    snapshot = fetch_product_snapshot(client, "gid://shopify/Product/1")  # type: ignore[arg-type]

    assert snapshot.inventory_quantity == 5
    assert snapshot.status == "ACTIVE"
    assert snapshot.description_html == "<p>Description</p>"
    assert snapshot.media[0].id == "gid://shopify/MediaImage/1"
    assert snapshot.media[0].alt_text == "Current alt"
    assert client.calls[0]["variables"] == {"id": "gid://shopify/Product/1"}


def test_update_product_seo_sends_product_update_input() -> None:
    client = FakeClient(
        [
            {
                "productUpdate": {
                    "product": {
                        "id": "gid://shopify/Product/1",
                        "title": "Macuahuitl",
                        "handle": "macuahuitl",
                        "status": "ACTIVE",
                        "descriptionHtml": "<p>Handmade macuahuitl.</p>",
                        "tags": ["Macuahuitl", "Aztec club"],
                        "seo": {
                            "title": "Macuahuitl - Eagle Jaguar - 27\"",
                            "description": "Handmade macuahuitl product page.",
                        },
                    },
                    "userErrors": [],
                }
            }
        ]
    )
    update = ProductSeoUpdate(
        product_id="gid://shopify/Product/1",
        seo_title='Macuahuitl - Eagle Jaguar - 27"',
        seo_description="Handmade macuahuitl product page.",
        tags=["Macuahuitl", "Aztec club"],
    )

    snapshot = update_product_seo(client, update)  # type: ignore[arg-type]

    assert snapshot.seo_title == 'Macuahuitl - Eagle Jaguar - 27"'
    assert client.calls[0]["variables"] == {
        "product": {
            "id": "gid://shopify/Product/1",
            "seo": {
                "title": 'Macuahuitl - Eagle Jaguar - 27"',
                "description": "Handmade macuahuitl product page.",
            },
            "tags": ["Macuahuitl", "Aztec club"],
        }
    }


def test_product_update_input_can_include_title_and_description_html() -> None:
    update = ProductSeoUpdate(
        product_id="gid://shopify/Product/1",
        seo_title="SEO",
        seo_description="Description",
        tags=["Macuahuitl"],
        title="Macuahuitl - Eagle Jaguar - 27\"",
        description_html="<p>Handmade macuahuitl.</p>",
        handle="macuahuitl-eagle-jaguar-27",
    )

    assert update.to_product_input() == {
        "id": "gid://shopify/Product/1",
        "seo": {"title": "SEO", "description": "Description"},
        "tags": ["Macuahuitl"],
        "title": 'Macuahuitl - Eagle Jaguar - 27"',
        "descriptionHtml": "<p>Handmade macuahuitl.</p>",
        "handle": "macuahuitl-eagle-jaguar-27",
    }


def test_update_product_media_alt_sends_product_update_media_input() -> None:
    client = FakeClient(
        [
            {
                "productUpdateMedia": {
                    "media": [
                        {
                            "id": "gid://shopify/MediaImage/1",
                            "alt": "Updated alt",
                            "image": {
                                "altText": "Updated alt",
                                "url": "https://example.com/image.jpg",
                            },
                        }
                    ],
                    "mediaUserErrors": [],
                }
            }
        ]
    )

    media = update_product_media_alt(
        client,  # type: ignore[arg-type]
        ProductMediaAltUpdate(
            product_id="gid://shopify/Product/1",
            media_id="gid://shopify/MediaImage/1",
            alt_text="Updated alt",
        ),
    )

    assert media.alt_text == "Updated alt"
    assert client.calls[0]["variables"] == {
        "productId": "gid://shopify/Product/1",
        "media": [{"id": "gid://shopify/MediaImage/1", "alt": "Updated alt"}],
    }


def test_update_product_seo_raises_on_shopify_user_errors() -> None:
    client = FakeClient(
        [
            {
                "productUpdate": {
                    "product": None,
                    "userErrors": [
                        {
                            "field": ["product", "seo", "title"],
                            "message": "is too long",
                        }
                    ],
                }
            }
        ]
    )
    update = ProductSeoUpdate(
        product_id="gid://shopify/Product/1",
        seo_title="SEO",
        seo_description="Description",
        tags=[],
    )

    with pytest.raises(ShopifyApiError, match="seo.title: is too long"):
        update_product_seo(client, update)  # type: ignore[arg-type]
