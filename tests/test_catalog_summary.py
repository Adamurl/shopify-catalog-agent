from src.audits.seo_audit import generate_catalog_summary
from src.models.product import Product, ProductMedia, ProductVariant


def test_generate_catalog_summary_counts_missing_fields_and_duplicates() -> None:
    products = [
        Product(
            id="1",
            title="Huaraches - Aztec Calendar - Brown",
            handle="huaraches-aztec-calendar-brown",
            vendor="Vendor A",
            product_type="Huaraches",
            category=None,
            tags=["footwear"],
            status="ACTIVE",
            seo_title=None,
            seo_description="Meta",
            description_html="",
            collections=[],
            variants=[
                ProductVariant(
                    id="v1",
                    title="Default",
                    sku=None,
                    barcode=None,
                    inventory_quantity=3,
                )
            ],
            options=[],
            media=[ProductMedia(id="m1", url="https://example.com/image.jpg", alt_text=None)],
        ),
        Product(
            id="2",
            title="Huaraches - Aztec Calendar - Brown",
            handle="huaraches-aztec-calendar-brown",
            vendor="Vendor A",
            product_type=None,
            category=None,
            tags=[],
            status="ACTIVE",
            seo_title="SEO",
            seo_description=None,
            description_html="<p>Body</p>",
            collections=["Shoes"],
            variants=[],
            options=[],
            media=[],
        ),
    ]

    summary = generate_catalog_summary(products)

    assert summary.total_products == 2
    assert summary.products_by_vendor == {"Vendor A": 2}
    assert summary.products_missing_product_type == 1
    assert summary.products_missing_tags == 1
    assert summary.products_missing_seo_title == 1
    assert summary.products_missing_meta_description == 1
    assert summary.products_missing_descriptions == 1
    assert summary.products_missing_images == 1
    assert summary.products_missing_image_alt_text == 1
    assert summary.products_missing_collections == 1
    assert summary.products_missing_sku == 2
    assert summary.duplicate_titles == ["Huaraches - Aztec Calendar - Brown"]
    assert summary.duplicate_handles == ["huaraches-aztec-calendar-brown"]
