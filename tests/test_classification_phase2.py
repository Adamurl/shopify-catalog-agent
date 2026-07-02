from pathlib import Path

from src.catalog.classification_config import load_classification_config
from src.catalog.classification_reports import write_classification_outputs
from src.catalog.classifier import classify_product, classify_products, needs_manual_review
from src.catalog.models import CatalogImage, CatalogProduct, CatalogVariant
from src.catalog.analyzer import filter_products


def make_product(
    title: str,
    *,
    product_id: str = "gid://shopify/Product/1",
    product_type: str | None = "Macuahuitls",
    status: str = "ACTIVE",
    tags: list[str] | None = None,
    collections: list[str] | None = None,
    description_text: str = "Traditional wood ceremonial product for Danza Azteca.",
    first_image_alt: str | None = "Wood macuahuitl with obsidian details",
    variants: list[CatalogVariant] | None = None,
) -> CatalogProduct:
    images = (
        [CatalogImage(id="m1", url="https://example.com/image.jpg", alt=first_image_alt)]
        if first_image_alt is not None
        else []
    )
    return CatalogProduct(
        id=product_id,
        title=title,
        handle=title.casefold().replace(" ", "-").replace('"', ""),
        status=status,
        vendor="Vendor A",
        product_type=product_type,
        category="Weapons",
        collections=["Macuahuitls"] if collections is None else collections,
        tags=["Macuahuitl", "Mexica"] if tags is None else tags,
        seo_title=None,
        seo_description=None,
        description_html=f"<p>{description_text}</p>",
        description_text=description_text,
        images=images,
        first_image_alt=first_image_alt,
        variants=variants or [CatalogVariant(id="v1", title="Default", sku="SKU", inventory_quantity=1)],
        total_inventory=1,
        is_in_stock=True,
        created_at=None,
        updated_at=None,
    )


def test_classify_product_extracts_family_subgroup_and_attributes() -> None:
    config = load_classification_config()
    product = make_product('Macuahuitl - Eagle Warrior - 27"')

    classified = classify_product(product, config)

    assert classified.classification.family == "Macuahuitl"
    assert classified.classification.subgroup == "Macuahuitl 27 inch"
    assert classified.attributes.size == "27 inch"
    assert classified.attributes.size_number == 27
    assert classified.attributes.material == "wood"
    assert classified.attributes.design == "Eagle Warrior"
    assert "Mexica" in classified.attributes.cultural_terms
    assert classified.classification.confidence >= 0.65
    assert "product_type:Macuahuitl" in classified.classification.matched_signals


def test_extracts_color_number_index_set_quantity_and_audience() -> None:
    config = load_classification_config()
    product = make_product(
        "Kids Huaraches - Black and Brown - No. 4 - 2 pack",
        product_type="Huaraches",
        tags=["Huaraches", "kids"],
        collections=["Footwear"],
        description_text="Black and brown leather sandals for kids.",
        first_image_alt="Black and brown leather huaraches",
    )

    classified = classify_product(product, config)

    assert classified.classification.family == "Huaraches"
    assert classified.attributes.color == ["black", "brown"]
    assert classified.attributes.material == "leather"
    assert classified.attributes.age_group == "kids"
    assert classified.attributes.audience == "kids"
    assert classified.attributes.number_index == 4
    assert classified.attributes.set_quantity == 2


def test_manual_review_flags_low_information_products() -> None:
    config = load_classification_config()
    product = make_product(
        "Mystery Item",
        product_type=None,
        tags=[],
        collections=[],
        description_text="",
        first_image_alt=None,
        variants=[],
    )

    classified = classify_product(product, config)

    assert needs_manual_review(classified, config) is True
    assert "family_not_detected" in classified.classification.warnings
    assert "product_has_no_image" in classified.classification.warnings
    assert "missing_or_weak_product_type" in classified.classification.warnings
    assert "missing_tags" in classified.classification.warnings


def test_classification_reports_write_expected_outputs(tmp_path: Path) -> None:
    config = load_classification_config()
    products = classify_products(
        [
            make_product('Macuahuitl - Eagle Warrior - 27"', product_id="1"),
            make_product("Mystery Item", product_id="2", product_type=None, tags=[]),
        ],
        config,
    )

    paths = write_classification_outputs(
        products,
        tmp_path / "classified",
        tmp_path / "reports",
        "20260101_000000",
        config,
        "test scope",
    )

    assert paths["classified_json"].exists()
    assert "READ ONLY MODE" in paths["classification_summary"].read_text()
    assert paths["classified_products"].read_text().splitlines()[0].startswith("product_id")
    assert "Mystery Item" in paths["manual_review"].read_text()
    assert "Macuahuitl 27 inch" in paths["subgroup_candidates"].read_text()
    assert "size_number" in paths["extracted_attributes"].read_text()


def test_filter_products_supports_vendor_and_status_for_classify() -> None:
    active = make_product("Active", product_id="1")
    draft = make_product("Draft", product_id="2", status="DRAFT")

    filtered = filter_products([active, draft], vendor="Vendor A", status="DRAFT")

    assert [product.title for product in filtered] == ["Draft"]
