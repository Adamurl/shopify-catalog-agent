from pathlib import Path

from src.catalog.utils import write_json
from src.preview.preview_builder import build_previews, find_rule_paths
from src.preview.preview_reports import write_preview_outputs
from src.preview.rule_renderer import product_matches_rule, render_preview_row


def classified_product(
    product_id: str,
    title: str,
    *,
    design: str = "Eagle Warrior",
    handle: str | None = None,
    image_id: str = "m1",
    confidence: float = 0.91,
) -> dict[str, object]:
    return {
        "id": product_id,
        "title": title,
        "handle": handle or title.casefold().replace(" ", "-").replace('"', ""),
        "status": "ACTIVE",
        "vendor": "Vendor A",
        "product_type": "Macuahuitls",
        "collections": ["Macuahuitls"],
        "tags": ["Macuahuitl", "Mexica"],
        "seo_title": "",
        "seo_description": "",
        "description_html": "<p>Current description.</p>",
        "images": [{"id": image_id, "url": "https://example.com/image.jpg", "alt": ""}],
        "first_image_alt": "",
        "variants": [{"id": "v1", "title": "Default", "sku": "SKU", "inventory_quantity": 1}],
        "total_inventory": 1,
        "classification": {
            "family": "Macuahuitl",
            "subgroup": "Macuahuitl 27 inch",
            "category_intent": "ceremonial wood macuahuitl",
            "is_accessory": False,
            "is_variant_like": False,
            "confidence": confidence,
            "matched_signals": ["product_type:Macuahuitl", "size:27 inch"],
            "warnings": [],
            "conflicting_signals": [],
        },
        "attributes": {
            "family": "Macuahuitl",
            "design": design,
            "style": design,
            "size": "27 inch",
            "size_number": 27,
            "color": [],
            "material": "wood",
            "use_case": "Danza Azteca",
            "cultural_terms": ["Mexica", "Aztec"],
            "accessory_type": None,
        },
    }


def proposed_rule() -> dict[str, object]:
    return {
        "rule_id": "macuahuitl_27_inch_v1",
        "version": 1,
        "status": "proposed",
        "group": "Macuahuitl 27 inch",
        "family": "Macuahuitl",
        "subgroup": "Macuahuitl 27 inch",
        "created_at": "2026-01-01T00:00:00Z",
        "match": {
            "family": "Macuahuitl",
            "subgroup": "Macuahuitl 27 inch",
            "required_attributes": {"size": "27 inch"},
            "exclude_if": {"is_accessory": True},
            "min_product_confidence": 0.8,
        },
        "templates": {
            "title_pattern": "Macuahuitl - {design} - {size}",
            "handle_pattern": "macuahuitl-{design_slug}-{size_number}",
            "meta_title_pattern": "{title}",
            "meta_description_pattern": "{title} made with wood for Macuahuitl inspired by Danza Azteca.",
            "description_template": "<p>This Macuahuitl uses details detected from the existing catalog data.</p>",
            "image_alt_template": "{title} with {design} design.",
        },
        "tags": {"append": ["Macuahuitl", "Aztec", "wood"], "remove": [], "replace_existing": False},
        "fields": {"update": ["title", "seo", "tags"], "leave_alone": ["handle", "description", "image_alt"]},
        "constraints": {
            "max_seo_title_length": 60,
            "min_meta_description_length": 80,
            "max_meta_description_length": 160,
            "allow_handle_updates": False,
            "allow_description_updates": False,
            "allow_image_alt_updates": False,
        },
        "manual_review_conditions": [],
        "examples": [],
        "confidence": {"score": 0.9, "reasons": [], "warnings": []},
    }


def test_render_preview_row_preserves_tags_and_blocks_risky_fields() -> None:
    product = classified_product("1", 'Old Macuahuitl 27"', design="Eagle Warrior")
    rule = proposed_rule()

    assert product_matches_rule(product, rule) is True
    row = render_preview_row(product, rule)

    assert row.approval == "PENDING"
    assert row.suggested.title == "Macuahuitl - Eagle Warrior - 27 inch"
    assert row.suggested.seo_title == row.suggested.title
    assert row.tags_to_append == ["Aztec", "wood"]
    assert row.suggested.tags == ["Macuahuitl", "Mexica", "Aztec", "wood"]
    assert row.blocked_fields == ["handle", "description", "image_alt"]


def test_build_previews_adds_duplicate_handle_and_shared_media_warnings(tmp_path: Path) -> None:
    products = [
        classified_product("1", "First", design="Same", image_id="shared"),
        classified_product("2", "Second", design="Same", image_id="shared"),
    ]
    rule_path = tmp_path / "rule.json"
    write_json(rule_path, proposed_rule())

    previews = build_previews(products, [rule_path], "20260101_000000")

    assert len(previews) == 1
    warnings = {warning for row in previews[0].rows for warning in row.warnings}
    assert "duplicate_suggested_handle" in warnings
    assert "shared_media_image_id_across_multiple_products" in warnings
    assert "rule_status_is_proposed_not_approved" in warnings
    assert "handle_updates_disabled" in warnings


def test_write_preview_outputs_creates_csv_json_summary_and_warnings(tmp_path: Path) -> None:
    rule_path = tmp_path / "rule.json"
    write_json(rule_path, proposed_rule())
    previews = build_previews(
        [classified_product("1", "First", design="Eagle")],
        [rule_path],
        "20260101_000000",
    )

    paths = write_preview_outputs(
        previews,
        tmp_path / "previews",
        tmp_path / "reports",
        "20260101_000000",
    )

    assert any(path.name.endswith(".csv") for path in paths.values())
    assert any(path.name.endswith(".json") for path in paths.values())
    assert any("preview_summary" in path.name for path in paths.values())
    csv_text = next(path.read_text() for path in paths.values() if path.suffix == ".csv" and "preview_" in path.name)
    assert "approval,product_id,status" in csv_text
    assert "PENDING" in csv_text


def test_find_rule_paths_respects_approved_only_and_explicit_rule(tmp_path: Path) -> None:
    proposed = tmp_path / "proposed"
    approved = tmp_path / "approved"
    proposed.mkdir()
    approved.mkdir()
    proposed_rule_path = proposed / "proposed.json"
    approved_rule_path = approved / "approved.json"
    proposed_rule_path.write_text("{}")
    approved_rule_path.write_text("{}")

    assert find_rule_paths(proposed, approved, approved_rules_only=True) == [approved_rule_path]
    assert find_rule_paths(proposed, approved, explicit_rule=proposed_rule_path) == [proposed_rule_path]
