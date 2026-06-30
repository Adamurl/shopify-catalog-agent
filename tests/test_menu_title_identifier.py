import json

from src.audits.menu_title_identifier import detect_menu_title_identifier
from src.models.product import Product


def make_product(
    title: str,
    collections: list[str],
    product_type: str | None = None,
) -> Product:
    return Product(
        id="1",
        title=title,
        handle=title.lower().replace(" ", "-"),
        vendor="Vendor",
        product_type=product_type,
        category=None,
        tags=[],
        status="ACTIVE",
        seo_title=None,
        seo_description=None,
        description_html=None,
        collections=collections,
        variants=[],
        options=[],
        media=[],
    )


def write_menu(tmp_path):
    menu = {
        "items": [
            {
                "title": "Clothing",
                "items": [
                    {
                        "title": "Men",
                        "items": [
                            {"title": "Tops", "items": []},
                            {"title": "Tank Tops", "items": []},
                        ],
                    },
                    {
                        "title": "Women",
                        "items": [
                            {"title": "Tops", "items": []},
                            {"title": "Tank Tops", "items": []},
                            {"title": "Zip-Up Hoodies", "items": []},
                        ],
                    },
                ],
            },
            {
                "title": "Macuahuitls",
                "items": [
                    {
                        "title": "Macuahuitls",
                        "items": [{"title": '27"', "items": []}],
                    },
                    {
                        "title": "Obsidian",
                        "items": [
                            {"title": "Blade", "items": []},
                            {"title": "Letter Openers", "items": []},
                        ],
                    }
                ],
            },
            {
                "title": "Jewelry",
                "items": [
                    {
                        "title": "Earrings",
                        "items": [{"title": "Wing Earrings", "items": []}],
                    }
                ],
            },
            {
                "title": "Accessories",
                "items": [
                    {
                        "title": "Headwear",
                        "items": [{"title": "Hats", "items": []}],
                    }
                ],
            },
        ]
    }
    path = tmp_path / "menu.json"
    path.write_text(json.dumps(menu), encoding="utf-8")
    return path


def test_detect_menu_title_identifier_keeps_ladies_tank_top_under_women(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Ladies Tank Top - Tochtli - Red",
            ["Clothing", "Men", "Tank Tops - Ladies"],
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Ladies"
    assert detection.source == "ladies_clothing_rule"
    assert detection.menu_path == ("Clothing", "Women", "Tank Tops")
    assert detection.attributes == {"Audience": "Ladies", "Garment": "Tank Top"}


def test_detect_menu_title_identifier_keeps_ladies_top_under_women(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Ladies Top - Mexica - Black",
            ["Clothing", "Women", "Tops - Ladies"],
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Ladies"
    assert detection.source == "ladies_clothing_rule"
    assert detection.menu_path == ("Clothing", "Women", "Tops")
    assert detection.attributes == {"Audience": "Ladies", "Garment": "Top"}


def test_detect_menu_title_identifier_keeps_macuahuitl_size_as_attribute(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Macuahuitl (Aztec Club) 27” Aztec Calendar",
            ["Macuahuitls", "Macuahuitl 27”"],
            product_type="Macuahuitl",
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Macuahuitl"
    assert detection.attributes == {"Design": "Aztec Calendar", "Size": '27"'}


def test_detect_menu_title_identifier_does_not_use_broad_grouping_nodes(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product("Unknown Product", ["Clothing", "Men"]),
        write_menu(tmp_path),
    )

    assert detection is None


def test_detect_menu_title_identifier_parses_numbered_earring_family(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product("Feather wing Earrings 8", ["Jewelry"]),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Earring"
    assert detection.menu_path == ("Jewelry", "Earrings", "Wing Earrings")
    assert detection.attributes == {"Style": "Feather Wing", "Number": "8"}


def test_detect_menu_title_identifier_prioritizes_numbered_family_over_generic_collection(
    tmp_path,
) -> None:
    detection = detect_menu_title_identifier(
        make_product("Feather wing Earrings 716", ["Earrings", "Jewelry"]),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.source == "numbered_title_pattern"
    assert detection.identifier == "Earring"
    assert detection.menu_path == ("Jewelry", "Earrings", "Wing Earrings")
    assert detection.attributes == {"Style": "Feather Wing", "Number": "716"}


def test_detect_menu_title_identifier_parses_generic_numbered_title(tmp_path) -> None:
    detection = detect_menu_title_identifier(
        make_product("Hunab Ku Hat 2", ["Headwear"]),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Hat"
    assert detection.attributes == {"Style": "Hunab Ku", "Number": "2"}


def test_detect_menu_title_identifier_routes_zip_up_hoodie_to_single_category(
    tmp_path,
) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Hoodie - Unisex Mictlancihuatl Full Zip-up - Coral",
            ["Hoodies", "Clothing"],
            product_type="Sweater/Hoodies",
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Zip-Up Hoodie"
    assert detection.source == "zip_up_hoodie_rule"
    assert detection.menu_path == ("Clothing", "Women", "Zip-Up Hoodies")


def test_detect_menu_title_identifier_routes_tecpatl_blade_separately(
    tmp_path,
) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Tecpatl - Obsidian blade w wood Skull handle",
            ["Macuahuitls", "Obsidian", "Tecpatl", "Blades"],
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Tecpatl"
    assert detection.source == "tecpatl_rule"
    assert detection.menu_path == ("Macuahuitls", "Obsidian", "Blade")
    assert detection.attributes == {
        "Type": "Obsidian Blade",
        "Detail": "With Wood Skull Handle",
    }


def test_detect_menu_title_identifier_routes_tecpatl_letter_opener_separately(
    tmp_path,
) -> None:
    detection = detect_menu_title_identifier(
        make_product(
            "Tecpatl - obsidian letter opener - 8”",
            ["Macuahuitls", "Obsidian Letter Openers"],
        ),
        write_menu(tmp_path),
    )

    assert detection is not None
    assert detection.identifier == "Tecpatl"
    assert detection.menu_path == ("Macuahuitls", "Obsidian", "Letter Openers")
    assert detection.attributes == {
        "Type": "Obsidian Letter Opener",
        "Size": '8"',
    }
