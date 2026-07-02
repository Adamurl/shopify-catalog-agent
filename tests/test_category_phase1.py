from pathlib import Path

from src.catalog.analyzer import analyze_catalog, filter_products, title_pattern
from src.catalog.normalize import normalize_products
from src.catalog.reports import write_reports


def make_raw_product(
    product_id: str,
    title: str,
    *,
    status: str = "ACTIVE",
    product_type: str = "Macuahuitls",
    collections: list[str] | None = None,
    tags: list[str] | None = None,
    seo_title: str | None = None,
    seo_description: str | None = None,
    image_alt: str | None = None,
    inventory: int | None = 1,
) -> dict[str, object]:
    return {
        "id": product_id,
        "title": title,
        "handle": title.casefold().replace(" ", "-").replace('"', ""),
        "status": status,
        "vendor": "Vendor",
        "productType": product_type,
        "category": {"name": "Weapons"},
        "collections": {
            "edges": [
                {"node": {"title": collection, "handle": collection.casefold()}}
                for collection in (collections or ["Featured"])
            ]
        },
        "tags": tags or ["Macuahuitl"],
        "seo": {"title": seo_title, "description": seo_description},
        "descriptionHtml": "<p>short</p>",
        "media": {
            "edges": [
                {
                    "node": {
                        "id": f"media-{product_id}",
                        "alt": image_alt,
                        "image": {"url": "https://example.com/image.jpg"},
                    }
                }
            ]
        },
        "images": {"edges": []},
        "variants": {
            "edges": [
                {
                    "node": {
                        "id": f"variant-{product_id}",
                        "title": "Default",
                        "sku": "SKU",
                        "inventoryQuantity": inventory,
                    }
                }
            ]
        },
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
    }


def test_normalize_products_creates_canonical_shape() -> None:
    products = normalize_products(
        [
            make_raw_product(
                "gid://shopify/Product/1",
                'Macuahuitl - Eagle Warrior - 27"',
                image_alt="Macuahuitl alt",
                inventory=4,
            )
        ]
    )

    product = products[0]

    assert product.id == "gid://shopify/Product/1"
    assert product.product_type == "Macuahuitls"
    assert product.category == "Weapons"
    assert product.collections == ["Featured"]
    assert product.first_image_alt == "Macuahuitl alt"
    assert product.total_inventory == 4
    assert product.is_in_stock is True
    assert product.description_text == "short"


def test_filter_products_defaults_to_active_and_supports_group_filters() -> None:
    products = normalize_products(
        [
            make_raw_product("1", "Active", collections=["Jewelry"], tags=["Huaraches"]),
            make_raw_product(
                "2",
                "Draft",
                status="DRAFT",
                collections=["Jewelry"],
                tags=["Huaraches"],
            ),
            make_raw_product("3", "Other", product_type="Shirts"),
        ]
    )

    filtered = filter_products(
        products,
        product_type="Macuahuitls",
        tag="Huaraches",
        collection="Jewelry",
    )

    assert [product.title for product in filtered] == ["Active"]
    assert len(filter_products(products, include_inactive=True)) == 3


def test_title_pattern_normalizes_sizes_numbers_colors_and_separators() -> None:
    assert title_pattern('Macuahuitl - Eagle Warrior - 27"') == (
        "{text} - {text} - {size}"
    )
    assert title_pattern("Huaraches / Brown / 10") == "{text} - {color} - {number}"


def test_analyze_catalog_and_write_reports(tmp_path: Path) -> None:
    products = normalize_products(
        [
            make_raw_product("1", 'Macuahuitl - Eagle Warrior - 27"', inventory=2),
            make_raw_product("2", 'Macuahuitl - Eagle Warrior - 27"', inventory=0),
            make_raw_product(
                "3",
                "Archived",
                status="ARCHIVED",
                seo_title="SEO",
                seo_description="Meta",
                image_alt="Alt",
            ),
        ]
    )
    active_products = filter_products(products)

    analysis = analyze_catalog(active_products)
    paths = write_reports(analysis, tmp_path, "20260101_000000")

    assert analysis.total_products == 2
    assert len(analysis.missing_seo_title) == 2
    assert len(analysis.missing_first_image_alt) == 2
    assert len(analysis.duplicate_titles) == 2
    assert paths["catalog_summary"].exists()
    assert "READ ONLY MODE" in paths["catalog_summary"].read_text()
    assert paths["missing_seo"].read_text().splitlines()[0].startswith("product_id")
    assert paths["broad_groups"].exists()
