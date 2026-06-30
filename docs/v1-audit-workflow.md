# V1 Audit Workflow

The v1 workflow is built around local review and explicit approval. Shopify
data is fetched, normalized, analyzed, previewed, and only then updated through
guarded scripts.

## 1. Configure Access

Create `.env` from `.env.example` and set the Shopify store credentials:

```bash
cp .env.example .env
```

The Python tools read:

- `SHOPIFY_STORE_DOMAIN`
- `SHOPIFY_CLIENT_ID`
- `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_API_VERSION`
- optional `SHOPIFY_ADMIN_ACCESS_TOKEN`

## 2. Fetch And Audit

Test the connection:

```bash
python3 scripts/test_connection.py
```

Run the catalog audit:

```bash
python3 -m src.main
```

This creates local generated files under `data/raw/` and `data/reports/`.
Generated outputs are ignored by git because they are store-specific and can be
large.

## 3. Generate Review Reports

Create title suggestion reports:

```bash
python3 scripts/report_title_suggestions.py
```

Filter to a category or collection:

```bash
python3 scripts/report_title_suggestions.py --category "Clothing" --output data/reports/title_suggestions_clothing.csv
```

The report is active-product only by default.

## 4. Guarded Shopify Updates

Live writes are intentionally explicit. The Macuahuitl updater previews changes
unless `--apply` is passed.

Preview all 27-inch Macuahuitl updates:

```bash
python3 scripts/update_macuahuitl_seo.py --size '27"' --include-out-of-stock --all --update-title --update-description --update-handle --update-image-alt
```

Apply only after preview approval:

```bash
set -a; source .env; set +a; python3 scripts/update_macuahuitl_seo.py --size '27"' --include-out-of-stock --all --update-title --update-description --update-handle --update-image-alt --apply
```

The script refetches each product after writing and verifies the returned title,
handle, SEO description, product description, tags, and first image alt text.

## Safety Defaults

- Dry-run by default.
- Active products only unless a script explicitly exposes another option.
- Tags are appended and de-duplicated by default.
- Handles are updated only when `--update-handle` is passed.
- Image alt text updates use Shopify `productUpdateMedia`.
- Shared Shopify media IDs cannot have separate alt text per product.
- Generated reports and snapshots are not committed.
