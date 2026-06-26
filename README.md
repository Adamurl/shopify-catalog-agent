# Shopify Catalog Agent

A Python terminal application for auditing and analyzing a Shopify product catalog.
This initial foundation is audit-only: it reads from the Shopify Admin GraphQL API,
saves a local product snapshot, and generates summary reports. It does not include
AI features, a frontend, LangGraph workflows, or automated Shopify updates.

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

The Shopify app must have read access for products, collections, inventory, media,
and related catalog data. If you already have an Admin API access token, you can
set `SHOPIFY_ADMIN_ACCESS_TOKEN` instead of `SHOPIFY_CLIENT_ID` and
`SHOPIFY_CLIENT_SECRET`.

## Run

Test the Shopify connection first:

```bash
python3 scripts/test_connection.py
```

Run the catalog audit:

```bash
python3 -m src.main
```

Export images for matching products into a ZIP:

```bash
python3 scripts/export_product_images.py
```

By default this exports images for products with titles starting with
any title to `data/reports/product_images.zip`. Add filters to narrow the export:

```bash
python3 scripts/export_product_images.py --starts-with "Product title prefix" --output data/reports/images.zip
```

You can combine title filters and choose ZIP layout:

```bash
python3 scripts/export_product_images.py --starts-with "Macuahuitl" --contains "27" --cover-only --flat
```

The command writes:

- `data/raw/products.json`
- `data/reports/catalog_summary.csv`
- `data/reports/catalog_summary.md`

It also prints a high-level audit summary in the terminal.

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

## Tests

```bash
pytest
```
