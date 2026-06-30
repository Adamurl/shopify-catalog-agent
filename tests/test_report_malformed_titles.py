import json

from scripts.report_malformed_titles import (
    build_title_report_rows,
    load_products_from_snapshot,
    render_title_report_markdown,
    write_title_report_csv,
)
from src.audits.title_audit import TitleAuditFinding


def test_load_products_from_snapshot_supports_saved_product_shape(tmp_path) -> None:
    snapshot_path = tmp_path / "products.json"
    snapshot_path.write_text(
        json.dumps(
            [
                {
                    "id": "gid://shopify/Product/1",
                    "title": "Huaraches  - Aztec Calendar - Brown",
                    "handle": "huaraches-aztec-calendar-brown",
                    "vendor": "Vendor",
                    "productType": "Huaraches",
                    "category": "Shoes",
                    "tags": ["shoe"],
                    "status": "ACTIVE",
                    "seo": {"title": "SEO", "description": "Meta"},
                    "descriptionHtml": "<p>Body</p>",
                    "collections": ["Shoes"],
                    "variants": [
                        {
                            "id": "gid://shopify/ProductVariant/1",
                            "title": "Default",
                            "sku": "SKU-1",
                            "barcode": None,
                            "inventory_quantity": 5,
                            "selected_options": {"Title": "Default"},
                        }
                    ],
                    "options": [],
                    "media": [{"id": "media-1", "url": "https://example.com/image.jpg", "alt_text": "Alt"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    products = load_products_from_snapshot(snapshot_path)

    assert products[0].title == "Huaraches  - Aztec Calendar - Brown"
    assert products[0].product_type == "Huaraches"
    assert products[0].skus == ["SKU-1"]
    assert products[0].media[0].alt_text == "Alt"


def test_build_title_report_rows_groups_issues_by_product() -> None:
    findings = [
        TitleAuditFinding(product_id="1", title="SHORT", issue="All caps title"),
        TitleAuditFinding(product_id="1", title="SHORT", issue="Title under 10 characters"),
        TitleAuditFinding(product_id="2", title="Bad  Spacing", issue="Multiple consecutive spaces"),
    ]

    rows = build_title_report_rows(findings)

    assert len(rows) == 2
    assert rows[0].title == "Bad  Spacing"
    assert rows[0].issues == ["Multiple consecutive spaces"]
    assert rows[1].title == "SHORT"
    assert rows[1].issues == ["All caps title", "Title under 10 characters"]


def test_report_writers_include_titles_and_issues(tmp_path) -> None:
    rows = build_title_report_rows(
        [
            TitleAuditFinding(
                product_id="1",
                title="Belt|Faja - Large Pink",
                issue="Too few title segments",
            )
        ]
    )
    csv_path = tmp_path / "malformed_titles.csv"

    write_title_report_csv(rows, csv_path)
    markdown = render_title_report_markdown(rows)

    assert "Belt|Faja - Large Pink" in csv_path.read_text(encoding="utf-8")
    assert "Too few title segments" in csv_path.read_text(encoding="utf-8")
    assert "Belt\\|Faja - Large Pink" in markdown
    assert "Products with title findings: 1" in markdown
