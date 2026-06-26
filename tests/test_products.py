from typing import Any

from src.shopify.products import fetch_all_products


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(variables or {})
        if len(self.calls) == 1:
            return {
                "products": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    "edges": [{"node": make_node("1", "First Product")}],
                }
            }
        return {
            "products": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [{"node": make_node("2", "Second Product")}],
            }
        }


def test_fetch_all_products_handles_pagination() -> None:
    client = FakeClient()

    products = fetch_all_products(client)  # type: ignore[arg-type]

    assert [product.title for product in products] == ["First Product", "Second Product"]
    assert client.calls[0]["after"] is None
    assert client.calls[1]["after"] == "cursor-1"


def make_node(product_id: str, title: str) -> dict[str, Any]:
    return {
        "id": product_id,
        "title": title,
        "handle": title.lower().replace(" ", "-"),
        "vendor": "Vendor",
        "productType": "Type",
        "category": {"name": "Category"},
        "tags": ["tag"],
        "status": "ACTIVE",
        "seo": {"title": title, "description": "Description"},
        "descriptionHtml": "<p>Description</p>",
        "options": [],
        "collections": {"edges": []},
        "variants": {"edges": []},
        "media": {"edges": []},
    }
