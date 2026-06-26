from __future__ import annotations

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient

DEFAULT_OUTPUT_PATH = Path("data/reports/product_images.zip")
PRODUCTS_PAGE_SIZE = 50
MEDIA_PAGE_SIZE = 250
DOWNLOAD_TIMEOUT_SECONDS = 60

PRODUCT_IMAGES_QUERY = """
query ProductImages($first: Int!, $after: String, $mediaFirst: Int!) {
  products(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        title
        handle
        media(first: $mediaFirst) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              ... on MediaImage {
                id
                alt
                image {
                  url
                  altText
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

PRODUCT_MEDIA_PAGE_QUERY = """
query ProductMediaPage($id: ID!, $first: Int!, $after: String) {
  node(id: $id) {
    ... on Product {
      media(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            ... on MediaImage {
              id
              alt
              image {
                url
                altText
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class ExportImage:
    media_id: str
    url: str
    alt_text: str | None


@dataclass(frozen=True)
class ExportProduct:
    product_id: str
    title: str
    handle: str
    images: list[ExportImage]


@dataclass(frozen=True)
class ExportResult:
    matched_products: int
    downloaded_images: int
    failed_images: int
    output_path: Path


@dataclass(frozen=True)
class TitleFilters:
    starts_with: str | None = None
    ends_with: str | None = None
    contains: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export images for products that match title filters."
    )
    parser.add_argument(
        "--starts-with",
        default=None,
        help="Match products whose title starts with this text.",
    )
    parser.add_argument(
        "--title-prefix",
        default=None,
        help="Alias for --starts-with. Kept for backwards compatibility.",
    )
    parser.add_argument(
        "--ends-with",
        default=None,
        help="Match products whose title ends with this text.",
    )
    parser.add_argument(
        "--contains",
        default=None,
        help="Match products whose title contains this text.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit-products", type=int, default=None)
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Put images at the ZIP root instead of product folders.",
    )
    parser.add_argument(
        "--cover-only",
        action="store_true",
        help="Export only the first image for each matched product.",
    )
    return parser.parse_args()


def title_matches_prefix(title: str, prefix: str) -> bool:
    return title.strip().casefold().startswith(prefix.strip().casefold())


def title_matches_filters(title: str, filters: TitleFilters) -> bool:
    normalized_title = title.strip().casefold()
    starts_with = _normalize_filter(filters.starts_with)
    ends_with = _normalize_filter(filters.ends_with)
    contains = _normalize_filter(filters.contains)

    return all(
        [
            starts_with is None or normalized_title.startswith(starts_with),
            ends_with is None or normalized_title.endswith(ends_with),
            contains is None or contains in normalized_title,
        ]
    )


def sanitize_path_part(value: str, fallback: str = "product") -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    return sanitized.lower() or fallback


def image_extension_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}:
        return suffix
    return ".jpg"


def fetch_matching_products(
    client: ShopifyGraphQLClient,
    filters: TitleFilters,
    limit_products: int | None = None,
    cover_only: bool = False,
) -> list[ExportProduct]:
    products: list[ExportProduct] = []
    cursor: str | None = None

    while True:
        data = client.execute(
            PRODUCT_IMAGES_QUERY,
            variables={
                "first": PRODUCTS_PAGE_SIZE,
                "after": cursor,
                "mediaFirst": MEDIA_PAGE_SIZE,
            },
        )
        page = data.get("products") or {}
        for edge in page.get("edges") or []:
            node = edge.get("node") or {}
            title = node.get("title") or ""
            if not title_matches_filters(title, filters):
                continue

            media_connection = node.get("media") or {}
            images = _images_from_media_connection(media_connection)
            if cover_only:
                images = images[:1]
            else:
                images.extend(_fetch_remaining_images(client, node, media_connection))
            products.append(
                ExportProduct(
                    product_id=node.get("id") or "",
                    title=title,
                    handle=node.get("handle") or "",
                    images=images,
                )
            )
            if limit_products is not None and len(products) >= limit_products:
                return products

        page_info = page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return products
        cursor = page_info.get("endCursor")
        if not cursor:
            raise ValueError("Shopify product pagination has no endCursor")


def export_images_to_zip(
    products: list[ExportProduct],
    output_path: Path,
    session: requests.Session | None = None,
    use_product_folders: bool = True,
) -> ExportResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    http = session or requests.Session()
    downloaded_images = 0
    failed_images = 0

    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        used_flat_names: set[str] = set()
        for product in products:
            folder = sanitize_path_part(product.handle or product.title)
            used_names: set[str] = set()
            for index, image in enumerate(product.images, start=1):
                if use_product_folders:
                    archive_path = f"{folder}/{_unique_image_filename(index, image, used_names)}"
                else:
                    archive_path = _unique_flat_image_filename(
                        product,
                        index,
                        image,
                        used_flat_names,
                    )
                try:
                    response = http.get(image.url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
                    response.raise_for_status()
                except requests.RequestException:
                    failed_images += 1
                    continue

                archive.writestr(archive_path, response.content)
                downloaded_images += 1

    if downloaded_images == 0:
        raise RuntimeError("No images were downloaded")

    return ExportResult(
        matched_products=len(products),
        downloaded_images=downloaded_images,
        failed_images=failed_images,
        output_path=output_path,
    )


def main() -> int:
    args = parse_args()
    load_dotenv()
    filters = _filters_from_args(args)

    try:
        config = ShopifyConfig.from_env()
        client = ShopifyGraphQLClient(config)
        products = fetch_matching_products(
            client,
            filters=filters,
            limit_products=args.limit_products,
            cover_only=args.cover_only,
        )
        if not products:
            print(f"No products found for filters: {_describe_filters(filters)}")
            return 1

        result = export_images_to_zip(
            products,
            args.output,
            use_product_folders=not args.flat,
        )
    except Exception as exc:
        print(f"Image export failed: {exc}")
        return 1

    print("Image export complete")
    print(f"Products matched: {result.matched_products}")
    print(f"Images downloaded: {result.downloaded_images}")
    print(f"Images failed: {result.failed_images}")
    print(f"ZIP path: {result.output_path}")
    return 0


def _filters_from_args(args: argparse.Namespace) -> TitleFilters:
    starts_with = args.starts_with or args.title_prefix
    return TitleFilters(
        starts_with=starts_with,
        ends_with=args.ends_with,
        contains=args.contains,
    )


def _normalize_filter(value: str | None) -> str | None:
    normalized = value.strip().casefold() if value else ""
    return normalized or None


def _describe_filters(filters: TitleFilters) -> str:
    parts = []
    if filters.starts_with:
        parts.append(f"starts with {filters.starts_with!r}")
    if filters.ends_with:
        parts.append(f"ends with {filters.ends_with!r}")
    if filters.contains:
        parts.append(f"contains {filters.contains!r}")
    return ", ".join(parts) or "none"


def _images_from_media_connection(connection: dict[str, Any]) -> list[ExportImage]:
    images: list[ExportImage] = []
    for edge in connection.get("edges") or []:
        node = edge.get("node") or {}
        image = node.get("image") or {}
        url = image.get("url")
        if not url:
            continue
        images.append(
            ExportImage(
                media_id=node.get("id") or "",
                url=url,
                alt_text=image.get("altText") or node.get("alt"),
            )
        )
    return images


def _fetch_remaining_images(
    client: ShopifyGraphQLClient,
    product_node: dict[str, Any],
    media_connection: dict[str, Any],
) -> list[ExportImage]:
    product_id = product_node.get("id")
    page_info = media_connection.get("pageInfo") or {}
    cursor = page_info.get("endCursor")
    images: list[ExportImage] = []

    while product_id and page_info.get("hasNextPage"):
        data = client.execute(
            PRODUCT_MEDIA_PAGE_QUERY,
            variables={"id": product_id, "first": MEDIA_PAGE_SIZE, "after": cursor},
        )
        node = data.get("node") or {}
        media = node.get("media") or {}
        images.extend(_images_from_media_connection(media))
        page_info = media.get("pageInfo") or {}
        cursor = page_info.get("endCursor")
        if page_info.get("hasNextPage") and not cursor:
            raise ValueError("Shopify media pagination has no endCursor")

    return images


def _unique_image_filename(
    index: int,
    image: ExportImage,
    used_names: set[str],
) -> str:
    media_name = sanitize_path_part(image.media_id.rsplit("/", 1)[-1], "image")
    base = f"{index:02d}_{media_name}"
    filename = f"{base}{image_extension_from_url(image.url)}"
    counter = 2
    while filename in used_names:
        filename = f"{base}_{counter}{image_extension_from_url(image.url)}"
        counter += 1
    used_names.add(filename)
    return filename


def _unique_flat_image_filename(
    product: ExportProduct,
    index: int,
    image: ExportImage,
    used_names: set[str],
) -> str:
    product_name = sanitize_path_part(product.handle or product.title)
    image_name = _unique_image_filename(index, image, set())
    filename = f"{product_name}_{image_name}"
    counter = 2
    while filename in used_names:
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        filename = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(filename)
    return filename


if __name__ == "__main__":
    raise SystemExit(main())
