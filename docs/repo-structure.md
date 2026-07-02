# Repository Structure

This repository is the Python foundation for read-only Shopify catalog SEO
audits, deterministic product classification, proposed cleanup rules,
read-only preview reports, and one-product test updates. It is
intentionally script-first: the production path fetches data, normalizes
products, analyzes catalog health, classifies product families/subgroups,
proposes editable JSON rules, previews changes, and supports one approved
one-product test update before any later AI, approval, or bulk update layer is
added.

## Source Code

- `src/shopify/`
  - `client.py`: Shopify Admin GraphQL client and environment configuration.
  - `fetch_products.py`: read-only product pagination and raw/normalized
    snapshot writer.
  - `products.py`: product fetch query and product snapshot writer.
  - `snapshot.py`: load local product snapshots from `data/raw/products.json`.
- `src/catalog/`
  - `models.py`: canonical Phase 1 product, image, and variant dataclasses.
  - `normalize.py`: Shopify product node to canonical product normalization.
  - `analyzer.py`: deterministic catalog, group, title-pattern, and broad-group
    analysis.
  - `reports.py`: timestamped Markdown and CSV report writers.
  - `classification_config.py`: JSON-backed classification defaults loader.
  - `attribute_extractor.py`: deterministic attribute extraction from existing
    product data.
  - `subgroup_detector.py`: deterministic subgroup candidate detection.
  - `classifier.py`: family/subgroup classification and confidence scoring.
  - `classification_reports.py`: enriched classification snapshot and report
    writers.
  - `utils.py`: local JSON, timestamp, and text helpers.
- `src/rules/`
  - `rule_models.py`: stable proposed-rule dataclasses and JSON shape.
  - `template_inferer.py`: deterministic template inference and rendering.
  - `rule_validator.py`: safety and placeholder validation helpers.
  - `rule_proposer.py`: subgroup/family grouping and proposed rule generation.
  - `rule_reports.py`: rule proposal Markdown and CSV reports.
  - `rule_utils.py`: rule slugging and collection helpers.
- `src/preview/`
  - `preview_models.py`: stable preview document and row dataclasses.
  - `rule_renderer.py`: deterministic rule/product matching and template rendering.
  - `preview_builder.py`: preview document construction from rules and products.
  - `preview_validator.py`: warning generation for risky preview rows.
  - `preview_reports.py`: preview CSV, JSON, Markdown, and warning report writers.
  - `diff_utils.py`: tag, handle, and important-word diff helpers.
- `src/writer/`
  - `approved_row_loader.py`: loads exactly one preview CSV row.
  - `safety_checks.py`: validates approval, active status, safe fields, and
    append-only tags.
  - `shopify_writer.py`: one-product Shopify mutation and post-write refetch.
  - `verification.py`: compares expected preview values with refetched Shopify
    values.
  - `writer_reports.py`: one-product verification Markdown and JSON reports.
  - `write_models.py`: writer and verification dataclasses.
- `src/models/`
  - `product.py`: normalized product, variant, and media dataclasses.
- `src/audits/`
  - Catalog, SEO, title, tag, collection, family, and menu-path analysis.
  - Title cleanup is deterministic and produces suggestions with confidence.
- `src/reports/`
  - CSV report builders for manual review.

## CLI Scripts

- `scripts/category_seo_agent.py`: fetch/analyze/classify/propose-rules,
  preview, apply-one, and verify-one CLI.
- `scripts/test_connection.py`: validates Shopify API access.
- `scripts/report_title_suggestions.py`: creates active-product title suggestion
  reports, optionally filtered by category/collection/tag/product type.
- `scripts/report_malformed_titles.py`: reports malformed title patterns.
- `scripts/export_product_images.py`: exports matching product images into ZIPs.
- `scripts/fetch_menu.py`: fetches or refreshes menu/category data.

## Proof-of-Concept Code

- `proof_of_concept/macuahuitl/`: legacy Macuahuitl-specific update workflow
  and Shopify mutation helper. This is intentionally outside the production
  Phase 1 source tree.

## Data Directories

- `data/main-2025-menu.json`: checked-in menu/category source used by the audit.
- `data/raw/`: generated product snapshots. Not committed except `.gitkeep`.
- `data/processed/`: generated intermediate data. Not committed except `.gitkeep`.
- `data/snapshots/`: generated Phase 1 raw and normalized snapshots. Not
  committed except `.gitkeep`.
- `data/classified/`: generated enriched classified product snapshots. Not
  committed except `.gitkeep`.
- `data/rules/proposed/`: generated proposed cleanup rules. Not committed
  except `.gitkeep`.
- `data/rules/approved/`: reserved for later human-approved rules. Not committed
  except `.gitkeep`.
- `data/previews/`: generated read-only product-by-product previews. Not
  committed except `.gitkeep`.
- `data/config/classification_defaults.json`: committed deterministic default
  keyword/rule config for Phase 2 classification.
- `data/reports/`: generated CSV, Markdown, and ZIP outputs. Not committed
  except `.gitkeep`.

## Tests

The `tests/` directory covers Shopify client behavior, product parsing, catalog
analysis, title cleanup, family/menu detection, report scripts, image export,
Phase 1 reporting, and quarantined proof-of-concept update payloads.

Run all tests with:

```bash
pytest
```

## Excluded Work

The nested `catalog-agent/` Shopify app scaffold is ignored for this Phase 1
work. It can be revisited later as a separate app/frontend effort after the
Python read-only audit workflow is stable.
