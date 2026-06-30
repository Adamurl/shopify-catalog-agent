from src.audits.family_detection import detect_product_family
from src.models.product import Product


def make_product(title: str, product_type: str | None = None) -> Product:
    return Product(
        id="1",
        title=title,
        handle="handle",
        vendor="Vendor",
        product_type=product_type,
        category=None,
        tags=[],
        status="ACTIVE",
        seo_title=None,
        seo_description=None,
        description_html=None,
        collections=[],
        variants=[],
        options=[],
        media=[],
    )


def test_detect_product_family_from_specific_product_type() -> None:
    detection = detect_product_family(
        make_product("Leather Sandals - Brown", product_type="Sandals")
    )

    assert detection.family == "Sandals"
    assert detection.source == "product_type"


def test_detect_product_family_uses_title_prefix_for_generic_product_type() -> None:
    detection = detect_product_family(
        make_product("Leather Sandals - Brown", product_type="Accessories")
    )

    assert detection.family == "Leather Sandals"
    assert detection.source == "title_prefix"


def test_detect_product_family_uses_known_keyword_match() -> None:
    detection = detect_product_family(
        make_product("Ceremonial Ayoyotes with Obsidian - Adult - Teal")
    )

    assert detection.family == "Ayoyotes with Obsidian"
    assert detection.source == "keyword_match"
