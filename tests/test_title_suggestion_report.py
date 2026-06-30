import csv

from src.reports.title_suggestion_report import (
    TITLE_SUGGESTION_COLUMNS,
    build_title_suggestion_report,
    write_title_suggestions_csv,
)
from src.models.product import Product


def make_product(title: str, product_id: str = "1") -> Product:
    return Product(
        id=product_id,
        title=title,
        handle=f"handle-{product_id}",
        vendor="Vendor",
        product_type="Huaraches",
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


def test_title_suggestion_report_includes_changed_and_unchanged_products(tmp_path) -> None:
    report = build_title_suggestion_report(
        [
            make_product("Huaraches  -Aztec Calendar-  Brown", product_id="1"),
            make_product("Huaraches - Aztec Calendar - Brown", product_id="2"),
        ]
    )
    output_path = tmp_path / "title_suggestions.csv"

    write_title_suggestions_csv(report.rows, output_path)

    rows = list(csv.DictReader(output_path.open(encoding="utf-8")))
    assert rows[0].keys() == set(TITLE_SUGGESTION_COLUMNS)
    assert len(rows) == 2
    assert rows[0]["Suggested Title"] == "Huaraches - Aztec Calendar - Brown"
    assert "Menu Title Identifier" in rows[0]
    assert "Menu Path" in rows[0]
    assert rows[0]["Approve"] == ""
    assert rows[0]["Notes"] == ""
    assert rows[1]["Reason For Change"] == "No change needed"
    assert report.total_products_reviewed == 2
    assert report.total_suggestions_generated == 1
