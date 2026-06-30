# Shopify Catalog Agent

A Python toolkit for auditing Shopify catalog data, generating product title and
SEO review reports, and running guarded Shopify product updates after preview.

This is the v1 foundation for a later category SEO agent. The current project is
script-first and deterministic: AI should eventually help discover patterns, but
Shopify writes should remain previewed, explicit, and verified.

## What This Repo Contains

- Shopify Admin GraphQL client and product snapshot tooling.
- Catalog, SEO, title, collection, tag, family, and menu-path audits.
- Deterministic title normalization and report generation.
- Image export utilities for product review.
- Guarded product update scripts for tested workflows such as Macuahuitls.
- Unit tests for the audit, report, Shopify read, and guarded write code.

See [Repository Structure](docs/repo-structure.md) for a file-by-file overview.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file:

```bash
cp .env.example .env
```

4. Fill in:

- `SHOPIFY_STORE_DOMAIN`
- `SHOPIFY_CLIENT_ID`
- `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_API_VERSION`

For your own store, the app uses Shopify's client credentials flow to request a
24-hour Admin API access token from:

```text
https://{shop}.myshopify.com/admin/oauth/access_token
```

If you already have an Admin API access token, set
`SHOPIFY_ADMIN_ACCESS_TOKEN` instead of `SHOPIFY_CLIENT_ID` and
`SHOPIFY_CLIENT_SECRET`.

## Core Commands

Test Shopify access:

```bash
python3 scripts/test_connection.py
```

Run the catalog audit:

```bash
python3 -m src.main
```

Generate title suggestions:

```bash
python3 scripts/report_title_suggestions.py
```

Generate suggestions for a category:

```bash
python3 scripts/report_title_suggestions.py --category "Clothing" --output data/reports/title_suggestions_clothing.csv
```

Export matching product images:

```bash
python3 scripts/export_product_images.py --starts-with "Macuahuitl" --contains "27" --cover-only --flat
```

## Guarded Product Updates

Live Shopify writes are dry-run by default and require `--apply`.

Preview 27-inch Macuahuitl updates:

```bash
python3 scripts/update_macuahuitl_seo.py --size '27"' --include-out-of-stock --all --update-title --update-description --update-handle --update-image-alt
```

Apply only after preview approval:

```bash
set -a; source .env; set +a; python3 scripts/update_macuahuitl_seo.py --size '27"' --include-out-of-stock --all --update-title --update-description --update-handle --update-image-alt --apply
```

The update script refetches Shopify data after writes and reports mismatches.
Image alt text is updated through Shopify media mutations. If multiple products
share the same Shopify media ID, they also share one alt text value.

See [V1 Audit Workflow](docs/v1-audit-workflow.md) for the current workflow.

## Generated Data

Generated Shopify data is intentionally ignored by git:

- `data/raw/*`
- `data/processed/*`
- `data/reports/*`

Only `.gitkeep` placeholders and reusable source files are committed. Do not
commit store snapshots, report CSVs, ZIP exports, `.env`, or secrets.

## Current Audit Coverage

- Total products
- Products by product type
- Products by vendor
- Missing product type
- Missing tags
- Missing SEO title
- Missing meta description
- Missing descriptions
- Missing images
- Missing image alt text
- Missing collections
- Missing SKU
- Duplicate titles
- Duplicate handles
- Product title format findings
- Product family and menu-path title suggestions

## Future Agent Direction

The next major step is a category SEO agent that can analyze one category at a
time, detect when categories should be split, propose rules, preview every
change, update one test product, and only then bulk-apply approved rows.

See [Future Category SEO Agent](docs/future-category-seo-agent.md).

## Tests

```bash
pytest
```
