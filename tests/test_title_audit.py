from src.audits.title_audit import audit_titles
from src.models.product import Product


def make_product(
    title: str,
    product_type: str | None = "Huaraches",
    product_id: str = "gid://shopify/Product/1",
) -> Product:
    return Product(
        id=product_id,
        title=title,
        handle=title.lower().replace(" ", "-"),
        vendor="Vendor",
        product_type=product_type,
        category=None,
        tags=["tag"],
        status="ACTIVE",
        seo_title="SEO",
        seo_description="Description",
        description_html="<p>Description</p>",
        collections=["Collection"],
        variants=[],
        options=[],
        media=[],
    )


def test_audit_titles_flags_duplicate_and_missing_type() -> None:
    products = [
        make_product("Huaraches - Aztec Calendar - Brown", product_type=None),
        make_product("Huaraches - Aztec Calendar - Brown", product_id="2"),
    ]

    findings = audit_titles(products)

    issues = {(finding.title, finding.issue) for finding in findings}
    assert ("Huaraches - Aztec Calendar - Brown", "Duplicate title") in issues
    assert ("Huaraches - Aztec Calendar - Brown", "Missing product type") in issues


def test_audit_titles_flags_formatting_rules() -> None:
    products = [
        make_product("SHORT"),
        make_product("Snapback Hat - Mexica Eagle - Black - Extra"),
        make_product("Huaraches  - Aztec Calendar - Brown"),
    ]

    findings = audit_titles(products)

    issues = {finding.issue for finding in findings}
    assert "All caps title" in issues
    assert "Title under 10 characters" in issues
    assert "Too many title segments" in issues
    assert "Multiple consecutive spaces" in issues
    assert "Unusual formatting issue" in issues
