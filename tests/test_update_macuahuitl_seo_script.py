from proof_of_concept.macuahuitl.update_macuahuitl_seo import (
    SeoReportRow,
    build_image_alt_text,
    build_product_handle,
    build_product_description_html,
    build_product_title,
    build_seo_description,
    build_seo_title,
    build_update,
    parse_inventory,
    select_rows,
)


def make_row(
    title: str,
    *,
    product_id: str = "gid://shopify/Product/1",
    status: str = "ACTIVE",
    inventory: int | None = 1,
    family: str = "Macuahuitl",
    suggested_title: str = "Macuahuitl - Eagle Jaguar - 27\"",
    seo_title: str = "Macuahuitl - Eagle Jaguar - 27\"",
    seo_description: str = "Handmade macuahuitl product page.",
) -> SeoReportRow:
    return SeoReportRow(
        product_id=product_id,
        status=status,
        inventory=inventory,
        current_title=title,
        suggested_title=suggested_title,
        handle=title.lower().replace(" ", "-"),
        detected_family=family,
        current_tags=["Existing tag"],
        suggested_seo_title=seo_title,
        suggested_seo_description=seo_description,
    )


def test_parse_inventory_handles_blank_and_invalid_values() -> None:
    assert parse_inventory("7") == 7
    assert parse_inventory("") is None
    assert parse_inventory("n/a") is None


def test_select_rows_defaults_to_active_in_stock_macuahuitls_only() -> None:
    selected = select_rows(
        [
            make_row("In Stock"),
            make_row("Out Of Stock", inventory=0),
            make_row("Inactive", status="ARCHIVED"),
            make_row("Tecpatl", family="Tecpatl"),
        ],
        families=["Macuahuitl"],
        product_id=None,
        include_out_of_stock=False,
        update_all=True,
        limit=1,
        size=None,
    )

    assert [row.current_title for row in selected] == ["In Stock"]


def test_select_rows_without_all_respects_limit() -> None:
    selected = select_rows(
        [
            make_row("First", product_id="gid://shopify/Product/1"),
            make_row("Second", product_id="gid://shopify/Product/2"),
        ],
        families=["Macuahuitl"],
        product_id=None,
        include_out_of_stock=False,
        update_all=False,
        limit=1,
        size=None,
    )

    assert [row.current_title for row in selected] == ["First"]


def test_select_rows_for_first_test_prefers_full_product_over_spare_blades() -> None:
    selected = select_rows(
        [
            make_row("Macuahuitl (Aztec Club) spare blades"),
            make_row(
                "Macuahuitl (Aztec Club) 27” Jaguar Print 2",
                product_id="gid://shopify/Product/2",
            ),
            make_row(
                'Macuahuitl (Aztec Club) - Blue - 40"',
                product_id="gid://shopify/Product/3",
            ),
        ],
        families=["Macuahuitl"],
        product_id=None,
        include_out_of_stock=False,
        update_all=False,
        limit=1,
        size=None,
    )

    assert [row.current_title for row in selected] == [
        "Macuahuitl (Aztec Club) 27” Jaguar Print 2"
    ]


def test_select_rows_can_target_one_product_id() -> None:
    selected = select_rows(
        [
            make_row("First", product_id="gid://shopify/Product/1"),
            make_row("Second", product_id="gid://shopify/Product/2"),
        ],
        families=["Macuahuitl"],
        product_id="gid://shopify/Product/2",
        include_out_of_stock=False,
        update_all=True,
        limit=1,
        size=None,
    )

    assert [row.current_title for row in selected] == ["Second"]


def test_build_update_appends_default_macuahuitl_tags() -> None:
    update = build_update(make_row("Macuahuitl"))

    assert update.tags == [
        "Existing tag",
        "Macuahuitl",
        "Aztec club",
        "Wooden macuahuitl",
        "Mexica",
        "Danza Azteca",
        "Ceremonial tool",
        "Cultural education",
    ]


def test_build_update_can_include_visible_title_and_description() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    update = build_update(row, update_title=True, update_description=True)

    assert update.title == 'Macuahuitl (Aztec Club) - Eagle Jaguar - 27"'
    assert update.description_html == build_product_description_html(row)
    assert update.description_html == (
        "<p>This is a handmade wooden macuahuitl inspired by Mexica ceremonial "
        "clubs.</p>"
        "<p>Each macuahuitl is handmade to order with a 6-8 week lead time. "
        "Finish, color, and detail placement can vary slightly from piece to "
        "piece.</p>"
    )


def test_build_update_can_include_url_handle() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    update = build_update(row, update_title=True, update_handle=True)

    assert update.handle == "macuahuitl-aztec-club-eagle-jaguar-27"


def test_build_product_title_preserves_aztec_club_modifier() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    assert build_product_title(row) == 'Macuahuitl (Aztec Club) - Eagle Jaguar - 27"'


def test_build_seo_fields_match_visible_macuahuitl_name() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    assert build_seo_title(row) == 'Macuahuitl (Aztec Club) - Eagle Jaguar - 27"'
    assert build_seo_description(row) == (
        'Macuahuitl (Aztec Club) - Eagle Jaguar - 27" handmade wooden '
        "macuahuitl inspired by Mexica ceremonial clubs. Handmade to order "
        "with a 6-8 week lead time."
    )


def test_build_product_handle_matches_visible_title() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    assert build_product_handle(row) == "macuahuitl-aztec-club-eagle-jaguar-27"


def test_build_image_alt_text_describes_design_and_material_details() -> None:
    row = make_row("Macuahuitl (Aztec Club) 27” Eagle Jaguar")

    assert build_image_alt_text(row) == (
        'Macuahuitl (Aztec Club) - Eagle Jaguar - 27" handmade wooden '
        "macuahuitl with Eagle Jaguar design, wooden handle, and "
        "obsidian-style blade details."
    )


def test_select_rows_can_filter_by_size() -> None:
    selected = select_rows(
        [
            make_row("27 Inch"),
            make_row(
                "17 Inch",
                product_id="gid://shopify/Product/2",
                suggested_title='Macuahuitl - Eagle Jaguar - 17"',
            ),
        ],
        families=["Macuahuitl"],
        product_id=None,
        include_out_of_stock=False,
        update_all=True,
        limit=1,
        size='27"',
    )

    assert [row.current_title for row in selected] == ["27 Inch"]
