from pathlib import Path

from src.rules.rule_proposer import (
    filter_classified_products,
    propose_rules,
)
from src.rules.rule_reports import write_rule_reports
from src.rules.rule_validator import validate_rule
from src.rules.template_inferer import infer_title_pattern, render_template


def classified_product(
    product_id: str,
    title: str,
    *,
    family: str = "Macuahuitl",
    subgroup: str = "Macuahuitl 27 inch",
    confidence: float = 0.9,
    design: str = "Eagle Warrior",
    size: str = "27 inch",
    size_number: int = 27,
    material: str = "wood",
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": product_id,
        "title": title,
        "handle": title.casefold().replace(" ", "-").replace('"', ""),
        "status": "ACTIVE",
        "vendor": "Vendor A",
        "product_type": "Macuahuitls",
        "collections": ["Macuahuitls"],
        "tags": tags or ["Macuahuitl", "Mexica"],
        "classification": {
            "family": family,
            "subgroup": subgroup,
            "category_intent": "ceremonial wood macuahuitl",
            "is_accessory": False,
            "is_variant_like": False,
            "confidence": confidence,
            "matched_signals": ["product_type:Macuahuitl", f"size:{size}"],
            "warnings": [],
            "conflicting_signals": [],
        },
        "attributes": {
            "family": family,
            "style": design,
            "design": design,
            "size": size,
            "size_number": size_number,
            "color": [],
            "material": material,
            "audience": None,
            "gender": None,
            "age_group": None,
            "number_index": None,
            "set_quantity": None,
            "variant_type": None,
            "use_case": "Danza Azteca",
            "cultural_terms": ["Mexica", "Aztec"],
            "accessory_type": None,
        },
        "source_product": {
            "id": product_id,
            "title": title,
            "handle": title.casefold(),
        },
    }


def test_infer_title_pattern_prefers_common_design_and_size() -> None:
    products = [
        classified_product("1", 'Macuahuitl - Eagle Warrior - 27"'),
        classified_product("2", 'Macuahuitl - Jaguar - 27"', design="Jaguar"),
        classified_product("3", 'Macuahuitl - Sun - 27"', design="Sun"),
    ]

    assert infer_title_pattern(products) == "Macuahuitl - {design} - {size}"
    assert render_template(
        "{family} - {design} - {size}",
        products[0]["attributes"],  # type: ignore[arg-type]
    ) == "Macuahuitl - Eagle Warrior - 27 inch"


def test_propose_rules_writes_proposed_json_with_safe_defaults(tmp_path: Path) -> None:
    products = [
        classified_product("1", 'Macuahuitl - Eagle Warrior - 27"'),
        classified_product("2", 'Macuahuitl - Jaguar - 27"', design="Jaguar"),
        classified_product("3", 'Macuahuitl - Sun - 27"', design="Sun"),
    ]

    result = propose_rules(products, tmp_path, "20260101_000000")

    assert len(result.rules) == 1
    rule = result.rules[0]
    assert rule.status == "proposed"
    assert rule.match.required_attributes == {"size": "27 inch", "material": "wood"}
    assert rule.fields.update == ["title", "seo", "tags"]
    assert rule.fields.leave_alone == ["handle", "description", "image_alt"]
    assert rule.constraints.allow_handle_updates is False
    assert rule.constraints.allow_description_updates is False
    assert rule.constraints.allow_image_alt_updates is False
    assert rule.tags.replace_existing is False
    assert rule.tags.remove == []
    assert "Macuahuitl" in rule.tags.append
    assert result.rule_paths[rule.rule_id].exists()
    assert '"status": "proposed"' in result.rule_paths[rule.rule_id].read_text()


def test_rule_validation_flags_unsafe_or_small_group_rules(tmp_path: Path) -> None:
    result = propose_rules(
        [classified_product("1", 'Macuahuitl - Eagle Warrior - 27"')],
        tmp_path,
        "20260101_000000",
    )

    rule = result.rules[0]

    assert "small_group" in rule.confidence.warnings
    assert "handle_update_not_disabled" not in validate_rule(rule)


def test_rule_reports_include_manual_review_and_paths(tmp_path: Path) -> None:
    result = propose_rules(
        [classified_product("1", 'Macuahuitl - Eagle Warrior - 27"')],
        tmp_path / "rules",
        "20260101_000000",
    )

    paths = write_rule_reports(
        result.rules,
        result.rule_paths,
        tmp_path / "reports",
        "20260101_000000",
        "test scope",
    )

    assert "READ ONLY MODE" in paths["rule_proposal_summary"].read_text()
    assert "rule_id,group,family" in paths["proposed_rules"].read_text()
    assert "small_group" in paths["rule_manual_review"].read_text()


def test_filter_classified_products_supports_phase3_filters() -> None:
    products = [
        classified_product("1", "First"),
        classified_product("2", "Second", subgroup="Macuahuitl 40 inch", size="40 inch", size_number=40),
    ]

    filtered = filter_classified_products(
        products,
        family="Macuahuitl",
        subgroup="Macuahuitl 40 inch",
        product_type="Macuahuitls",
        collection="Macuahuitls",
        tag="Mexica",
        vendor="Vendor A",
        min_confidence=0.8,
    )

    assert [product["id"] for product in filtered] == ["2"]
