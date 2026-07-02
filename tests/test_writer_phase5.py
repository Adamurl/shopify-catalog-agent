import csv
from pathlib import Path

import pytest

from src.writer.approved_row_loader import load_preview_row, require_approved
from src.writer.safety_checks import build_update_from_row, validate_row_for_apply
from src.writer.shopify_writer import apply_product_update, fetch_product_snapshot
from src.writer.verification import verify_snapshot
from src.writer.write_models import OneProductUpdate, VerificationResult
from src.writer.writer_reports import write_verification_reports


class FakeClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        query: str,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append({"query": query, "variables": variables or {}})
        return self.responses.pop(0)


def write_preview(path: Path, rows: list[dict[str, object]]) -> None:
    columns = [
        "approval",
        "product_id",
        "status",
        "inventory",
        "current_title",
        "suggested_title",
        "current_handle",
        "suggested_handle",
        "current_seo_title",
        "suggested_seo_title",
        "current_seo_description",
        "suggested_seo_description",
        "current_description",
        "suggested_description",
        "current_first_image_alt",
        "suggested_first_image_alt",
        "current_tags",
        "suggested_tags",
        "tags_to_append",
        "detected_family",
        "detected_subgroup",
        "detected_attributes",
        "confidence",
        "warnings",
        "blocked_fields",
        "rule_id",
        "rule_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def preview_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "approval": "APPROVED",
        "product_id": "gid://shopify/Product/1",
        "status": "ACTIVE",
        "inventory": "1",
        "current_title": "Old Title",
        "suggested_title": "New Title",
        "current_handle": "old-title",
        "suggested_handle": "new-title",
        "current_seo_title": "Old SEO",
        "suggested_seo_title": "New Title",
        "current_seo_description": "Old description",
        "suggested_seo_description": "New deterministic SEO description.",
        "current_description": "<p>Old</p>",
        "suggested_description": "<p>New</p>",
        "current_first_image_alt": "Old alt",
        "suggested_first_image_alt": "New alt",
        "current_tags": "Macuahuitl; Mexica",
        "suggested_tags": "Macuahuitl; Mexica; Aztec",
        "tags_to_append": "Aztec",
        "detected_family": "Macuahuitl",
        "detected_subgroup": "Macuahuitl 27 inch",
        "detected_attributes": '{"family":"Macuahuitl"}',
        "confidence": "0.91",
        "warnings": "",
        "blocked_fields": '["handle", "description", "image_alt"]',
        "rule_id": "macuahuitl_27_inch_v1",
        "rule_status": "approved",
    }
    row.update(overrides)
    return row


def product_node(
    title: str = "New Title",
    seo_title: str = "New Title",
    seo_description: str = "New deterministic SEO description.",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": "gid://shopify/Product/1",
        "title": title,
        "handle": "old-title",
        "status": "ACTIVE",
        "descriptionHtml": "<p>Old</p>",
        "tags": tags or ["Macuahuitl", "Mexica", "Aztec"],
        "seo": {"title": seo_title, "description": seo_description},
        "variants": {"edges": [{"node": {"inventoryQuantity": 1}}]},
        "media": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/MediaImage/1",
                        "alt": "Old alt",
                        "image": {"altText": "Old alt", "url": "https://example.com/a.jpg"},
                    }
                }
            ]
        },
    }


def test_loader_requires_approved_preview_rows(tmp_path: Path) -> None:
    preview = tmp_path / "preview.csv"
    write_preview(preview, [preview_row(approval="PENDING")])

    row = load_preview_row(preview, product_id="gid://shopify/Product/1")

    with pytest.raises(ValueError, match="APPROVED"):
        require_approved(row)


def test_loader_rejects_row_index_when_product_id_is_duplicated(tmp_path: Path) -> None:
    preview = tmp_path / "preview.csv"
    write_preview(preview, [preview_row(), preview_row(current_title="Duplicate")])

    with pytest.raises(ValueError, match="exactly once"):
        load_preview_row(preview, row_index=1)


def test_safety_builds_safe_update_and_leaves_blocked_fields_unwritten(tmp_path: Path) -> None:
    preview = tmp_path / "preview.csv"
    write_preview(preview, [preview_row()])
    row = load_preview_row(preview, row_index=1)

    warnings = validate_row_for_apply(row)
    update = build_update_from_row(row)

    assert warnings == [
        "handle blocked and will not be written",
        "description blocked and will not be written",
        "image_alt blocked and will not be written",
    ]
    assert update.written_fields == ["title", "seo", "tags"]
    assert update.to_product_input() == {
        "id": "gid://shopify/Product/1",
        "title": "New Title",
        "seo": {"title": "New Title", "description": "New deterministic SEO description."},
        "tags": ["Macuahuitl", "Mexica", "Aztec"],
    }


def test_safety_rejects_non_append_tags(tmp_path: Path) -> None:
    preview = tmp_path / "preview.csv"
    write_preview(preview, [preview_row(suggested_tags="Macuahuitl; Aztec")])
    row = load_preview_row(preview, product_id="gid://shopify/Product/1")

    with pytest.raises(ValueError, match="append only"):
        validate_row_for_apply(row)


def test_shopify_writer_updates_product_and_refetches() -> None:
    client = FakeClient(
        [
            {
                "productUpdate": {
                    "product": product_node(),
                    "userErrors": [],
                }
            },
            {"node": product_node()},
        ]
    )
    update = OneProductUpdate(
        product_id="gid://shopify/Product/1",
        written_fields=["title", "seo", "tags"],
        title="New Title",
        seo_title="New Title",
        seo_description="New deterministic SEO description.",
        tags=["Macuahuitl", "Mexica", "Aztec"],
    )

    after = apply_product_update(client, update)  # type: ignore[arg-type]

    assert after.title == "New Title"
    assert client.calls[0]["variables"] == {"product": update.to_product_input()}
    assert client.calls[1]["variables"] == {"id": "gid://shopify/Product/1"}


def test_verification_detects_mismatches(tmp_path: Path) -> None:
    preview = tmp_path / "preview.csv"
    write_preview(preview, [preview_row()])
    row = load_preview_row(preview, product_id="gid://shopify/Product/1")
    update = build_update_from_row(row)
    after = fetch_product_snapshot(  # type: ignore[arg-type]
        FakeClient([{"node": product_node(title="Wrong Title")}]),
        "gid://shopify/Product/1",
    )

    mismatches = verify_snapshot(row, update, after)

    assert [mismatch.field for mismatch in mismatches] == ["title"]


def test_writer_reports_create_markdown_and_json(tmp_path: Path) -> None:
    result = VerificationResult(
        mode="ONE_PRODUCT_TEST",
        product_id="gid://shopify/Product/1",
        preview_file="preview.csv",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
        write_attempted=True,
        verification_passed=True,
        written_fields=["title", "seo", "tags"],
        blocked_fields=["handle"],
        before={},
        expected={"title": "New Title"},
        after={"title": "New Title"},
        mismatches=[],
        warnings=[],
    )

    paths = write_verification_reports(result, tmp_path, "20260101_000000")

    assert paths["verification_md"].exists()
    assert paths["verification_json"].exists()
    assert "ONE_PRODUCT_TEST" in paths["verification_md"].read_text()
