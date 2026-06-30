from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shopify.client import ShopifyConfig, ShopifyGraphQLClient


MENU_QUERY = """
query Menus {
  menus(first: 50) {
    edges {
      node {
        id
        handle
        title
        items {
          id
          title
          type
          url
          resourceId
          tags
          items {
            id
            title
            type
            url
            resourceId
            tags
            items {
              id
              title
              type
              url
              resourceId
              tags
            }
          }
        }
      }
    }
  }
}
"""


def find_menu(data: dict[str, Any], title: str) -> dict[str, Any]:
    edges = ((data.get("menus") or {}).get("edges")) or []
    menus = [edge.get("node") or {} for edge in edges]

    for menu in menus:
        if menu.get("title") == title:
            return menu

    available = ", ".join(sorted(str(menu.get("title")) for menu in menus))
    raise ValueError(f"Menu not found: {title}. Available menus: {available}")


def print_items(items: list[dict[str, Any]], indent: int = 0) -> None:
    prefix = "  " * indent
    for item in items:
        details = []
        if item.get("type"):
            details.append(str(item["type"]))
        if item.get("url"):
            details.append(str(item["url"]))
        if item.get("resourceId"):
            details.append(str(item["resourceId"]))

        suffix = f" ({' | '.join(details)})" if details else ""
        print(f"{prefix}- {item.get('title', '(untitled)')}{suffix}")
        children = item.get("items") or []
        if children:
            print_items(children, indent + 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Main 2025 Menu")
    parser.add_argument("--output", default="data/main-2025-menu.json")
    args = parser.parse_args()

    load_dotenv()
    client = ShopifyGraphQLClient(ShopifyConfig.from_env())
    menu = find_menu(client.execute(MENU_QUERY), args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(menu, indent=2), encoding="utf-8")

    print(f"{menu.get('title')} ({menu.get('handle')})")
    print(f"id: {menu.get('id')}")
    print(f"saved: {output_path}")
    print()
    print_items(menu.get("items") or [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
