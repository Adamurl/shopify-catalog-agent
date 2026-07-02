# Shopify Catalog Agent

A Python toolkit for read-only Shopify catalog SEO audits and local report
generation.

Phase 1 is deterministic and read-only. It fetches Shopify product data,
normalizes it into a local canonical format, analyzes catalog health by category
signals, and writes JSON/CSV/Markdown reports. It does not generate AI copy and
does not update Shopify products.

Phase 2 adds deterministic product intelligence and classification. It loads
normalized snapshots, extracts structured attributes from existing Shopify data,
classifies products into family/subgroup candidates, flags manual-review rows,
and writes local enriched snapshots plus reports.

Phase 3 adds deterministic rule proposals. It loads classified snapshots and
creates human-editable proposed JSON rules for future title, SEO, and tag
cleanup. Rules are proposals only and are not approved or applied.

Phase 4 adds read-only preview reports. It renders proposed/approved rules
against classified products and writes product-by-product before/after preview
CSV, JSON, Markdown, and warning reports.

Phase 5 adds the first Shopify writer path, limited to one approved preview row
per command. It writes deterministic preview values only, refetches the product,
verifies written fields, and writes a verification report. Bulk updates are not
implemented.

## What This Repo Contains

- Shopify Admin GraphQL read client and product snapshot tooling.
- Canonical catalog product normalization.
- Deterministic catalog, group, SEO, image-alt, duplicate, weak-description, and
  title-pattern analysis.
- Configurable deterministic product family, subgroup, and attribute
  classification.
- Deterministic, human-editable JSON rule proposal generation.
- Deterministic product-by-product preview report generation.
- One-product approved preview row writer with post-write verification.
- Timestamped local JSON/CSV/Markdown report generation.
- Legacy proof-of-concept update scripts under `proof_of_concept/`, kept out of
  the Phase 1 production path.

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
- `SHOPIFY_ADMIN_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION=2025-10`

## Core Commands

Test Shopify access:

```bash
python3 scripts/test_connection.py
```

Fetch raw and normalized snapshots:

```bash
python3 scripts/category_seo_agent.py fetch
```

Analyze the latest normalized snapshot:

```bash
python3 scripts/category_seo_agent.py analyze
```

Analyze a specific slice:

```bash
python3 scripts/category_seo_agent.py analyze --category "Macuahuitls"
python3 scripts/category_seo_agent.py analyze --product-type "Shirts"
python3 scripts/category_seo_agent.py analyze --tag "Huaraches"
python3 scripts/category_seo_agent.py analyze --collection "Jewelry"
```

By default, `analyze` includes only `ACTIVE` products. Use `--include-inactive`
only when you intentionally want `DRAFT` and `ARCHIVED` products in the local
report.

Classify the latest normalized snapshot:

```bash
python3 scripts/category_seo_agent.py classify
```

Classify an explicit snapshot or slice:

```bash
python3 scripts/category_seo_agent.py classify --snapshot data/snapshots/normalized_products_<timestamp>.json
python3 scripts/category_seo_agent.py classify --category "Macuahuitls"
python3 scripts/category_seo_agent.py classify --product-type "Shirts"
python3 scripts/category_seo_agent.py classify --collection "Jewelry"
python3 scripts/category_seo_agent.py classify --tag "Huaraches"
python3 scripts/category_seo_agent.py classify --vendor "Vendor Name"
python3 scripts/category_seo_agent.py classify --status DRAFT
```

Classification defaults are stored in
`data/config/classification_defaults.json`. Add store-specific colors,
materials, audience terms, family keywords, and subgroup keywords there instead
of hardcoding them in source.

Propose editable cleanup rules from the latest classified snapshot:

```bash
python3 scripts/category_seo_agent.py propose-rules
```

Propose rules from an explicit classified snapshot or slice:

```bash
python3 scripts/category_seo_agent.py propose-rules --classified data/classified/classified_products_<timestamp>.json
python3 scripts/category_seo_agent.py propose-rules --family "Macuahuitl"
python3 scripts/category_seo_agent.py propose-rules --subgroup "Macuahuitl 27 inch"
python3 scripts/category_seo_agent.py propose-rules --product-type "Shirts"
python3 scripts/category_seo_agent.py propose-rules --collection "Jewelry"
python3 scripts/category_seo_agent.py propose-rules --tag "Huaraches"
python3 scripts/category_seo_agent.py propose-rules --min-confidence 0.8
```

Render previews from classified products and rules:

```bash
python3 scripts/category_seo_agent.py preview
python3 scripts/category_seo_agent.py preview --rule data/rules/proposed/macuahuitls_27_inch_rule.json
python3 scripts/category_seo_agent.py preview --classified data/classified/classified_products_<timestamp>.json
python3 scripts/category_seo_agent.py preview --family "Macuahuitl"
python3 scripts/category_seo_agent.py preview --subgroup "Macuahuitl 27 inch"
python3 scripts/category_seo_agent.py preview --approved-rules-only
```

Apply exactly one approved preview row:

```bash
python3 scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --product-id "gid://shopify/Product/123"
python3 scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --row-index 4
```

Refetch and verify one product against an expected preview row:

```bash
python3 scripts/category_seo_agent.py verify-one --product-id "gid://shopify/Product/123" --expected data/previews/preview.csv
```

## Phase 1 Safety

- `scripts/category_seo_agent.py` is read-only.
- It uses Shopify GraphQL queries only.
- It does not call `productUpdate`, media mutations, SEO updates, handle
  updates, description updates, tag updates, or bulk operations.
- It does not generate AI-written product copy.
- It writes only local files under `data/snapshots/`, `data/classified/`, and
  `data/rules/proposed/`, and `data/reports/`.
- Proposed rules are saved with `status: proposed`; they are not approved.
- Proposed handle, description, and image alt updates are disabled by default.
- Preview approval values default to `PENDING`; no approvals are auto-filled.
- `apply-one` requires `approval=APPROVED`.
- `apply-one` updates exactly one product, then refetches and verifies it.
- Bulk writing is not implemented.

## Generated Reports

`analyze` creates timestamped files:

- `data/reports/catalog_summary_<timestamp>.md`
- `data/reports/group_summary_<timestamp>.csv`
- `data/reports/missing_seo_<timestamp>.csv`
- `data/reports/missing_image_alt_<timestamp>.csv`
- `data/reports/duplicate_titles_<timestamp>.csv`
- `data/reports/duplicate_handles_<timestamp>.csv`
- `data/reports/weak_descriptions_<timestamp>.csv`
- `data/reports/title_patterns_<timestamp>.csv`
- `data/reports/broad_groups_<timestamp>.csv`

`classify` creates timestamped files:

- `data/classified/classified_products_<timestamp>.json`
- `data/reports/classification_summary_<timestamp>.md`
- `data/reports/classified_products_<timestamp>.csv`
- `data/reports/manual_review_<timestamp>.csv`
- `data/reports/subgroup_candidates_<timestamp>.csv`
- `data/reports/extracted_attributes_<timestamp>.csv`

`propose-rules` creates timestamped files:

- `data/rules/proposed/<safe_group_name>_rule_<timestamp>.json`
- `data/reports/rule_proposal_summary_<timestamp>.md`
- `data/reports/proposed_rules_<timestamp>.csv`
- `data/reports/rule_manual_review_<timestamp>.csv`

`preview` creates timestamped files:

- `data/previews/preview_<group>_<timestamp>.csv`
- `data/previews/preview_<group>_<timestamp>.json`
- `data/reports/preview_summary_<group>_<timestamp>.md`
- `data/reports/preview_warnings_<group>_<timestamp>.csv`

`apply-one` and `verify-one` create timestamped files:

- `data/reports/one_product_verification_<timestamp>.md`
- `data/reports/one_product_verification_<timestamp>.json`

## Generated Data

Generated Shopify data is intentionally ignored by git:

- `data/raw/*`
- `data/processed/*`
- `data/reports/*`
- `data/snapshots/*`
- `data/classified/*`
- `data/rules/proposed/*`
- `data/rules/approved/*`
- `data/previews/*`

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

## Proof-of-Concept Code

Older product-specific update experiments live under `proof_of_concept/`. They
are not part of the Phase 1 read-only production workflow.

## Future Agent Direction

The next major step is a category SEO agent that can analyze one category at a
time, detect when categories should be split, propose rules, preview every
change, update one test product, and only then bulk-apply approved rows.

See [Future Category SEO Agent](docs/future-category-seo-agent.md).

## Tests

```bash
pytest
```
