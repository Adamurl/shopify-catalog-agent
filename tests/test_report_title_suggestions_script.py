from scripts.report_title_suggestions import (
    _filter_active_products,
    _filter_products_by_categories,
)
from src.models.product import Product


def make_product(
    title: str,
    collections: list[str],
    product_type: str | None = None,
    status: str = "ACTIVE",
) -> Product:
    return Product(
        id=title,
        title=title,
        handle=title.lower().replace(" ", "-"),
        vendor="Vendor",
        product_type=product_type,
        category=None,
        tags=[],
        status=status,
        seo_title=None,
        seo_description=None,
        description_html=None,
        collections=collections,
        variants=[],
        options=[],
        media=[],
    )


def test_filter_products_by_category_matches_collection() -> None:
    products = [
        make_product("Top - Tochtli - Black", ["Men", "Clothing"]),
        make_product("Feather wing Earrings 8", ["Jewelry"]),
    ]

    filtered = _filter_products_by_categories(products, ["Clothing"])

    assert [product.title for product in filtered] == ["Top - Tochtli - Black"]


def test_filter_active_products_excludes_inactive_statuses() -> None:
    products = [
        make_product("Active Top", ["Clothing"], status="ACTIVE"),
        make_product("Draft Top", ["Clothing"], status="DRAFT"),
        make_product("Archived Top", ["Clothing"], status="ARCHIVED"),
    ]

    filtered = _filter_active_products(products)

    assert [product.title for product in filtered] == ["Active Top"]
