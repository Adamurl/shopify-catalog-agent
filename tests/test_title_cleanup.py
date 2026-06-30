from src.audits.family_detection import FamilyDetection
from src.audits.menu_title_identifier import MenuTitleIdentifier
from src.audits.title_cleanup import cleanup_title
from src.models.product import Product


def make_product(title: str) -> Product:
    return Product(
        id="1",
        title=title,
        handle="handle",
        vendor="Vendor",
        product_type=None,
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


def make_detection(family: str = "Ayoyotes") -> FamilyDetection:
    return FamilyDetection(family=family, source="keyword_match", reason="test")


def make_menu_identifier(
    identifier: str,
    attributes: dict[str, str] | None = None,
) -> MenuTitleIdentifier:
    return MenuTitleIdentifier(
        identifier=identifier,
        menu_path=("Clothing", "Men", identifier),
        source="test",
        reason="test",
        attributes=attributes or {},
        confidence=0.95,
    )


def test_cleanup_title_expands_with_abbreviation() -> None:
    suggestion = cleanup_title(
        make_product("Ayoyotes w/ Obsidian - Brown - Adult"),
        make_detection("Ayoyotes with Obsidian"),
    )

    assert suggestion.suggested_title == "Ayoyotes with Obsidian - Brown - Adult"
    assert "Expanded abbreviation" in suggestion.reason_for_change
    assert suggestion.confidence == 0.90


def test_cleanup_title_normalizes_color_slash() -> None:
    suggestion = cleanup_title(
        make_product("Ayoyotes - Teal/ Black - Adult"),
        make_detection(),
    )

    assert suggestion.suggested_title == "Ayoyotes - Teal and Black - Adult"
    assert "Normalized color separator" in suggestion.reason_for_change
    assert suggestion.confidence == 0.90


def test_cleanup_title_normalizes_double_spaces_and_hyphens() -> None:
    suggestion = cleanup_title(
        make_product("Huaraches  -Aztec Calendar-  Brown"),
        make_detection("Huaraches"),
    )

    assert suggestion.suggested_title == "Huaraches - Aztec Calendar - Brown"
    assert "Normalized spacing" in suggestion.reason_for_change
    assert suggestion.confidence == 0.95


def test_cleanup_title_keeps_internal_hyphen_clothing_terms() -> None:
    suggestion = cleanup_title(
        make_product("Zip-Up Hoodie - Aztec Calendar - Turquoise"),
        make_detection("Zip-Up Hoodie"),
    )

    assert suggestion.suggested_title == "Zip-Up Hoodie - Aztec Calendar - Turquoise"
    assert suggestion.reason_for_change == "No change needed"


def test_cleanup_title_keeps_full_zip_as_single_detail() -> None:
    suggestion = cleanup_title(
        make_product("Windbreaker - Aztec Calendar - Black - Full-Zip"),
        make_detection("Windbreaker"),
    )

    assert suggestion.suggested_title == (
        "Windbreaker - Aztec Calendar - Black - Full-Zip"
    )


def test_cleanup_title_reorders_ayoyotes_age_group() -> None:
    suggestion = cleanup_title(
        make_product("Ayoyotes w/ Obsidian - Adult - Teal/ Black"),
        make_detection("Ayoyotes with Obsidian"),
    )

    assert suggestion.suggested_title == (
        "Ayoyotes with Obsidian - Teal and Black - Adult"
    )
    assert "Moved age group to final segment" in suggestion.reason_for_change
    assert suggestion.confidence == 0.85


def test_cleanup_title_no_change_behavior() -> None:
    suggestion = cleanup_title(
        make_product("Huaraches - Aztec Calendar - Brown"),
        make_detection("Huaraches"),
    )

    assert suggestion.suggested_title == "Huaraches - Aztec Calendar - Brown"
    assert suggestion.reason_for_change == "No change needed"
    assert suggestion.confidence == 0.70


def test_cleanup_title_keeps_apostrophe_suffix_lowercase() -> None:
    suggestion = cleanup_title(
        make_product("Shorts - LADIE'S Cotton Shorts - Tochtli"),
        make_detection("Shorts"),
    )

    assert suggestion.suggested_title == "Shorts - Ladie's Cotton Shorts - Tochtli"


def test_cleanup_title_applies_ladies_tank_top_structure() -> None:
    suggestion = cleanup_title(
        make_product("Ladies Tank Top - Tochtli - Red"),
        make_detection("Ladies"),
        MenuTitleIdentifier(
            identifier="Ladies",
            menu_path=("Clothing", "Women", "Tank Tops"),
            source="ladies_clothing_rule",
            reason="test",
            attributes={"Audience": "Ladies", "Garment": "Tank Top"},
            confidence=0.98,
        ),
    )

    assert suggestion.suggested_title == "Ladies - Tank Top - Tochtli - Red"
    assert "Applied ladies clothing title structure" in suggestion.reason_for_change
    assert suggestion.detected_attributes["Menu Title Identifier"] == "Ladies"


def test_cleanup_title_removes_duplicate_ladies_from_tank_top_detail() -> None:
    suggestion = cleanup_title(
        make_product("Tank Top - Ladies Flowy Razor Back - Mexica Flag"),
        make_detection("Ladies"),
        MenuTitleIdentifier(
            identifier="Ladies",
            menu_path=("Clothing", "Women", "Tank Tops"),
            source="ladies_clothing_rule",
            reason="test",
            attributes={"Audience": "Ladies", "Garment": "Tank Top"},
            confidence=0.98,
        ),
    )

    assert suggestion.suggested_title == (
        "Ladies - Tank Top - Flowy Razor Back - Mexica Flag"
    )


def test_cleanup_title_applies_ladies_top_structure() -> None:
    suggestion = cleanup_title(
        make_product("Ladies Top - Mexica - Black"),
        make_detection("Ladies"),
        MenuTitleIdentifier(
            identifier="Ladies",
            menu_path=("Clothing", "Women", "Tops"),
            source="ladies_clothing_rule",
            reason="test",
            attributes={"Audience": "Ladies", "Garment": "Top"},
            confidence=0.98,
        ),
    )

    assert suggestion.suggested_title == "Ladies - Top - Mexica - Black"
    assert "Applied ladies clothing title structure" in suggestion.reason_for_change


def test_cleanup_title_structures_macuahuitl_size_and_design() -> None:
    suggestion = cleanup_title(
        make_product("Macuahuitl (Aztec Club) 27” Aztec Calendar"),
        make_detection("Macuahuitl"),
        make_menu_identifier(
            "Macuahuitl",
            {"Design": "Aztec Calendar", "Size": '27"'},
        ),
    )

    assert suggestion.suggested_title == 'Macuahuitl - Aztec Calendar - 27"'
    assert "Applied Macuahuitl title structure" in suggestion.reason_for_change


def test_cleanup_title_structures_numbered_menu_family() -> None:
    suggestion = cleanup_title(
        make_product("Feather wing Earrings 8"),
        make_detection("Feather wing Earrings 8"),
        make_menu_identifier(
            "Earring",
            {"Style": "Feather Wing", "Number": "8"},
        ),
    )

    assert suggestion.suggested_title == "Earring - Feather Wing - 8"
    assert "Applied numbered family title structure" in suggestion.reason_for_change


def test_cleanup_title_applies_zip_up_hoodie_structure() -> None:
    suggestion = cleanup_title(
        make_product("Hoodie - Unisex Mictlancihuatl Full Zip-up - Coral"),
        make_detection("Sweater/Hoodies"),
        MenuTitleIdentifier(
            identifier="Zip-Up Hoodie",
            menu_path=("Clothing", "Women", "Zip-Up Hoodies"),
            source="zip_up_hoodie_rule",
            reason="test",
            attributes={"Garment": "Zip-Up Hoodie"},
            confidence=0.99,
        ),
    )

    assert suggestion.suggested_title == (
        "Zip-Up Hoodie - Unisex Mictlancihuatl - Coral"
    )
    assert "Applied zip-up hoodie title structure" in suggestion.reason_for_change


def test_cleanup_title_applies_tecpatl_blade_structure() -> None:
    suggestion = cleanup_title(
        make_product("Tecpatl - Obsidian blade w wood Skull handle"),
        make_detection("Tecpatl"),
        MenuTitleIdentifier(
            identifier="Tecpatl",
            menu_path=("Macuahuitls", "Obsidian", "Blade"),
            source="tecpatl_rule",
            reason="test",
            attributes={
                "Type": "Obsidian Blade",
                "Detail": "With Wood Skull Handle",
            },
            confidence=0.99,
        ),
    )

    assert suggestion.suggested_title == (
        "Tecpatl - Obsidian Blade - With Wood Skull Handle"
    )
    assert "Applied Tecpatl title structure" in suggestion.reason_for_change


def test_cleanup_title_applies_tecpatl_letter_opener_structure() -> None:
    suggestion = cleanup_title(
        make_product("Tecpatl - obsidian letter opener - 8”"),
        make_detection("Tecpatl"),
        MenuTitleIdentifier(
            identifier="Tecpatl",
            menu_path=("Macuahuitls", "Obsidian", "Letter Openers"),
            source="tecpatl_rule",
            reason="test",
            attributes={"Type": "Obsidian Letter Opener", "Size": '8"'},
            confidence=0.99,
        ),
    )

    assert suggestion.suggested_title == 'Tecpatl - Obsidian Letter Opener - 8"'
    assert "Applied Tecpatl title structure" in suggestion.reason_for_change
