from src.audits.catalog_analysis import analyze_catalog_titles
from src.models.product import Product


def make_product(
    title: str,
    handle: str,
    product_type: str | None = "Huaraches",
    tags: list[str] | None = None,
    product_id: str = "gid://shopify/Product/1",
) -> Product:
    return Product(
        id=product_id,
        title=title,
        handle=handle,
        vendor="Vendor",
        product_type=product_type,
        category=None,
        tags=tags if tags is not None else ["tag"],
        status="ACTIVE",
        seo_title=None,
        seo_description=None,
        description_html=None,
        collections=[],
        variants=[],
        options=[],
        media=[],
    )


def test_analyze_catalog_titles_counts_patterns_and_missing_data() -> None:
    products = [
        make_product(
            "Huaraches - Aztec Calendar - Brown",
            "huaraches-aztec-calendar-brown",
            product_id="1",
        ),
        make_product(
            "Huaraches - Aztec Calendar - Brown",
            "huaraches-aztec-calendar-brown",
            product_type=None,
            tags=[],
            product_id="2",
        ),
        make_product("Macuahuitl - 27\"", "macuahuitl-27", product_id="3"),
    ]

    analysis = analyze_catalog_titles(products)

    assert analysis.total_products == 3
    assert analysis.title_segment_patterns == {"3 segments": 2, "2 segments": 1}
    assert analysis.common_title_prefixes["Huaraches"] == 2
    assert analysis.common_title_suffixes["Brown"] == 2
    assert analysis.duplicate_titles == ["Huaraches - Aztec Calendar - Brown"]
    assert analysis.duplicate_handles == ["huaraches-aztec-calendar-brown"]
    assert analysis.missing_product_types == 1
    assert analysis.missing_tags == 1
