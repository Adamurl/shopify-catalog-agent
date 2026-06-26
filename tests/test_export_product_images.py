from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest

from scripts.export_product_images import (
    ExportImage,
    ExportProduct,
    TitleFilters,
    export_images_to_zip,
    image_extension_from_url,
    sanitize_path_part,
    title_matches_filters,
    title_matches_prefix,
)


class FakeResponse:
    def __init__(self, content: bytes = b"image", should_fail: bool = False) -> None:
        self.content = content
        self.should_fail = should_fail

    def raise_for_status(self) -> None:
        if self.should_fail:
            raise RuntimeError("download failed")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        return self.responses.pop(0)


def test_title_matches_prefix_ignores_case_and_outer_spacing() -> None:
    assert title_matches_prefix(
        "  Macuahuitl (Aztec Club) 27” - Aztec Calendar",
        "Macuahuitl (Aztec Club) 27” ",
    )


def test_title_matches_filters_requires_all_provided_filters() -> None:
    filters = TitleFilters(
        starts_with="Macuahuitl",
        ends_with="Brown",
        contains="Aztec Club",
    )

    assert title_matches_filters("Macuahuitl (Aztec Club) 27” - Brown", filters)
    assert not title_matches_filters("Macuahuitl (Aztec Club) 27” - Black", filters)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Macuahuitl (Aztec Club) 27” - Red", "macuahuitl-aztec-club-27-red"),
        ("", "product"),
        ("gid://shopify/MediaImage/123", "gid-shopify-mediaimage-123"),
    ],
)
def test_sanitize_path_part(value: str, expected: str) -> None:
    assert sanitize_path_part(value) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://cdn.shopify.com/image.png?v=1", ".png"),
        ("https://cdn.shopify.com/image.jpeg", ".jpeg"),
        ("https://cdn.shopify.com/image", ".jpg"),
    ],
)
def test_image_extension_from_url(url: str, expected: str) -> None:
    assert image_extension_from_url(url) == expected


def test_export_images_to_zip_writes_product_folders(tmp_path: Path) -> None:
    products = [
        ExportProduct(
            product_id="gid://shopify/Product/1",
            title="Macuahuitl (Aztec Club) 27” - Aztec Calendar",
            handle="macuahuitl-aztec-club-27-aztec-calendar",
            images=[
                ExportImage(
                    media_id="gid://shopify/MediaImage/100",
                    url="https://cdn.shopify.com/image.jpg",
                    alt_text="Front",
                )
            ],
        )
    ]
    output_path = tmp_path / "images.zip"
    session = FakeSession([FakeResponse(content=b"jpg-bytes")])

    result = export_images_to_zip(products, output_path, session=session)  # type: ignore[arg-type]

    assert result.matched_products == 1
    assert result.downloaded_images == 1
    assert result.failed_images == 0
    with ZipFile(output_path) as archive:
        assert archive.namelist() == [
            "macuahuitl-aztec-club-27-aztec-calendar/01_100.jpg"
        ]
        assert archive.read(archive.namelist()[0]) == b"jpg-bytes"


def test_export_images_to_zip_can_write_flat_files(tmp_path: Path) -> None:
    products = [
        ExportProduct(
            product_id="gid://shopify/Product/1",
            title="Macuahuitl (Aztec Club) 27” - Aztec Calendar",
            handle="macuahuitl-aztec-club-27-aztec-calendar",
            images=[
                ExportImage(
                    media_id="gid://shopify/MediaImage/100",
                    url="https://cdn.shopify.com/image.jpg",
                    alt_text="Front",
                )
            ],
        )
    ]
    output_path = tmp_path / "images.zip"
    session = FakeSession([FakeResponse(content=b"jpg-bytes")])

    export_images_to_zip(
        products,
        output_path,
        session=session,  # type: ignore[arg-type]
        use_product_folders=False,
    )

    with ZipFile(output_path) as archive:
        assert archive.namelist() == [
            "macuahuitl-aztec-club-27-aztec-calendar_01_100.jpg"
        ]
