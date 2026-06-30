# Repository Structure

This repository is the Python v1 for auditing and safely updating a Shopify
catalog. It is intentionally script-first: the current goal is repeatable data
pulls, reports, previews, guarded writes, and verification before any later AI
agent layer is added.

## Source Code

- `src/shopify/`
  - `client.py`: Shopify Admin GraphQL client and environment configuration.
  - `products.py`: product fetch query and product snapshot writer.
  - `snapshot.py`: load local product snapshots from `data/raw/products.json`.
  - `product_updates.py`: guarded product update and media alt-text mutations.
- `src/models/`
  - `product.py`: normalized product, variant, and media dataclasses.
- `src/audits/`
  - Catalog, SEO, title, tag, collection, family, and menu-path analysis.
  - Title cleanup is deterministic and produces suggestions with confidence.
- `src/reports/`
  - CSV report builders for manual review.

## CLI Scripts

- `scripts/test_connection.py`: validates Shopify API access.
- `scripts/report_title_suggestions.py`: creates active-product title suggestion
  reports, optionally filtered by category/collection/tag/product type.
- `scripts/report_malformed_titles.py`: reports malformed title patterns.
- `scripts/export_product_images.py`: exports matching product images into ZIPs.
- `scripts/fetch_menu.py`: fetches or refreshes menu/category data.
- `scripts/update_macuahuitl_seo.py`: guarded Macuahuitl SEO/product update
  workflow. It is dry-run by default and requires `--apply` for live writes.

## Data Directories

- `data/main-2025-menu.json`: checked-in menu/category source used by the audit.
- `data/raw/`: generated product snapshots. Not committed except `.gitkeep`.
- `data/processed/`: generated intermediate data. Not committed except `.gitkeep`.
- `data/reports/`: generated CSV, Markdown, and ZIP outputs. Not committed
  except `.gitkeep`.

## Tests

The `tests/` directory covers Shopify client behavior, product parsing, catalog
analysis, title cleanup, family/menu detection, report scripts, image export,
and guarded product update payloads.

Run all tests with:

```bash
pytest
```

## Excluded Work

The nested `catalog-agent/` Shopify app scaffold is ignored for this v1 commit.
It can be revisited later as a separate app/frontend effort after the Python
audit and safe-update workflow is stable.
