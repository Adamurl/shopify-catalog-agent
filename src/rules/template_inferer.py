from __future__ import annotations

import re
from collections import Counter

from src.rules.rule_models import RuleTemplates
from src.rules.rule_utils import ratio

AttributeDict = dict[str, object]
ClassifiedDict = dict[str, object]


def infer_templates(products: list[ClassifiedDict]) -> RuleTemplates:
    """Infer editable templates from common extracted attributes."""
    title_pattern = infer_title_pattern(products)
    handle_pattern = _handle_pattern(title_pattern)
    meta_description = infer_meta_description_pattern(products)
    description_template = infer_description_template(products)
    image_alt_template = infer_image_alt_template(products)
    return RuleTemplates(
        title_pattern=title_pattern,
        handle_pattern=handle_pattern,
        meta_title_pattern="{title}",
        meta_description_pattern=meta_description,
        description_template=description_template,
        image_alt_template=image_alt_template,
    )


def infer_title_pattern(products: list[ClassifiedDict]) -> str:
    total = len(products)
    family = _common_attr(products, "family") or _common_classification(products, "family") or "{family}"
    parts = [str(family)]

    if _attr_presence(products, "accessory_type") >= 0.60:
        parts.append("{accessory_type}")
    else:
        if _attr_presence(products, "design") >= 0.60:
            parts.append("{design}")
        elif _attr_presence(products, "color") >= 0.60:
            parts.append("{color}")
        elif _attr_presence(products, "audience") >= 0.60:
            parts.append("{audience}")
        if _attr_presence(products, "size") >= 0.60:
            parts.append("{size}")
        elif _attr_presence(products, "material") >= 0.75 and total > 0:
            parts.append("{material}")

    return " - ".join(parts)


def infer_meta_description_pattern(products: list[ClassifiedDict]) -> str:
    family = _common_attr(products, "family") or _common_classification(products, "family")
    material = _common_attr(products, "material")
    use_case = _common_attr(products, "use_case")
    cultural = _common_list_attr(products, "cultural_terms")

    fragments = ["{title}"]
    if material:
        fragments.append(f"made with {material}")
    if family:
        fragments.append(f"for {family}")
    if use_case:
        fragments.append(f"inspired by {use_case}")
    elif cultural:
        fragments.append(f"with {cultural} inspired details")

    description = " ".join(fragments).strip() + "."
    if len(description) < 80:
        description += " Review this placeholder before approval."
    return description


def infer_description_template(products: list[ClassifiedDict]) -> str:
    family = _common_attr(products, "family") or _common_classification(products, "family") or "product"
    material = _common_attr(products, "material")
    use_case = _common_attr(products, "use_case")
    details = []
    if material:
        details.append(f" made with {material}")
    if use_case:
        details.append(f" for {use_case}")
    detail_text = "".join(details)
    return f"<p>This {family}{detail_text} uses details detected from the existing catalog data.</p>"


def infer_image_alt_template(products: list[ClassifiedDict]) -> str:
    if _attr_presence(products, "design") >= 0.60:
        return "{title} with {design} design."
    if _attr_presence(products, "color") >= 0.60:
        return "{title} in {color}."
    return "{title} product image."


def render_template(template: str, attributes: AttributeDict, title: str = "") -> str:
    values = {key: _stringify(value) for key, value in attributes.items()}
    values["title"] = title
    values["design_slug"] = _slug(values.get("design", ""))
    values["family_slug"] = _slug(values.get("family", ""))

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, "")

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace, template).strip()


def placeholders(template: str) -> set[str]:
    return set(re.findall(r"\{([a-zA-Z0-9_]+)\}", template))


def _attr_presence(products: list[ClassifiedDict], name: str) -> float:
    present = 0
    for product in products:
        value = _attributes(product).get(name)
        if value:
            present += 1
    return ratio(present, len(products))


def _common_attr(products: list[ClassifiedDict], name: str) -> str | None:
    counter: Counter[str] = Counter()
    for product in products:
        value = _attributes(product).get(name)
        if isinstance(value, list):
            counter.update(str(item) for item in value if item)
        elif value:
            counter[str(value)] += 1
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _common_list_attr(products: list[ClassifiedDict], name: str) -> str | None:
    value = _common_attr(products, name)
    return value


def _common_classification(products: list[ClassifiedDict], name: str) -> str | None:
    counter: Counter[str] = Counter()
    for product in products:
        value = _classification(product).get(name)
        if value:
            counter[str(value)] += 1
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _attributes(product: ClassifiedDict) -> AttributeDict:
    attributes = product.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _classification(product: ClassifiedDict) -> dict[str, object]:
    classification = product.get("classification")
    return classification if isinstance(classification, dict) else {}


def _stringify(value: object) -> str:
    if isinstance(value, list):
        return " and ".join(str(item) for item in value if item)
    if value is None:
        return ""
    return str(value)


def _handle_pattern(title_pattern: str) -> str:
    value = title_pattern.casefold()
    value = value.replace("{design}", "{design_slug}")
    value = value.replace("{family}", "{family_slug}")
    value = value.replace("{size}", "{size_number}")
    value = re.sub(r"[^a-z0-9{}]+", "-", value).strip("-")
    return value


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")

