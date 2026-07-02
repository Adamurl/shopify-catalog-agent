# Read-Only Audit And Classification Workflow

The current workflow is built around local read-only review. Shopify data is
fetched, normalized, analyzed, classified, proposed as editable rules, previewed,
and reported locally. Phase 5 can update exactly one approved preview row for a
test update; bulk updates are not implemented.

## 1. Configure Access

Create `.env` from `.env.example` and set the Shopify store credentials:

```bash
cp .env.example .env
```

The Python tools read:

- `SHOPIFY_STORE_DOMAIN`
- `SHOPIFY_ADMIN_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION=2025-10`

## 2. Fetch And Audit

Test the connection:

```bash
python3 scripts/test_connection.py
```

Fetch raw and normalized snapshots:

```bash
python3 scripts/category_seo_agent.py fetch
```

This creates local generated files under `data/snapshots/`. Generated outputs
are ignored by git because they are store-specific and can be large.

## 3. Generate Review Reports

Create audit reports:

```bash
python3 scripts/category_seo_agent.py analyze
```

Filter to a category or collection:

```bash
python3 scripts/category_seo_agent.py analyze --category "Macuahuitls"
python3 scripts/category_seo_agent.py analyze --collection "Jewelry"
```

The report is active-product only by default.

## 4. Classify Products

Classify the latest normalized snapshot:

```bash
python3 scripts/category_seo_agent.py classify
```

Classify one slice:

```bash
python3 scripts/category_seo_agent.py classify --product-type "Shirts"
python3 scripts/category_seo_agent.py classify --collection "Jewelry"
python3 scripts/category_seo_agent.py classify --tag "Huaraches"
```

Classification writes enriched snapshots under `data/classified/` and reports
under `data/reports/`. Rules are deterministic and configured in
`data/config/classification_defaults.json`.

## 5. Propose Rules

Generate proposed JSON cleanup rules from the latest classified snapshot:

```bash
python3 scripts/category_seo_agent.py propose-rules
```

Filter proposals to a family, subgroup, or confidence threshold:

```bash
python3 scripts/category_seo_agent.py propose-rules --family "Macuahuitl"
python3 scripts/category_seo_agent.py propose-rules --subgroup "Macuahuitl 27 inch"
python3 scripts/category_seo_agent.py propose-rules --min-confidence 0.8
```

Proposed rules are saved under `data/rules/proposed/` with `status: proposed`.
They must be human-edited and reviewed before preview work.

## 6. Preview Rule Effects

Render product-by-product previews:

```bash
python3 scripts/category_seo_agent.py preview
python3 scripts/category_seo_agent.py preview --family "Macuahuitl"
python3 scripts/category_seo_agent.py preview --approved-rules-only
```

Preview files are written under `data/previews/` and warning summaries under
`data/reports/`. Approval values default to `PENDING`.

## 7. Apply One Approved Preview Row

After manually reviewing a preview CSV, set exactly one row to
`approval=APPROVED`, then run:

```bash
python3 scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --product-id "gid://shopify/Product/123"
```

Or select by 1-based data row index:

```bash
python3 scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --row-index 4
```

The command writes one product, refetches it from Shopify, verifies the written
fields, and writes verification reports under `data/reports/`.

To verify later without writing:

```bash
python3 scripts/category_seo_agent.py verify-one --product-id "gid://shopify/Product/123" --expected data/previews/preview.csv
```

## 8. Proof-of-Concept Code

Legacy product-specific update experiments are kept under
`proof_of_concept/macuahuitl/`. They are not part of the main production
workflow.

## Safety Defaults

- Phases 1-4 are read-only.
- Shopify mutations are limited to the Phase 5 one-product test writer.
- Active products only unless a script explicitly exposes another option.
- No AI-written product copy is generated.
- Classification uses deterministic config-based rules.
- Rule proposals are local JSON files only and are not approved by default.
- Handle, description, and image alt updates are disabled in proposed rules by
  default.
- Previews are local reports only and do not write to Shopify.
- Preview approval values default to `PENDING`.
- `apply-one` requires `approval=APPROVED`.
- `apply-one` updates exactly one product and verifies after refetch.
- Bulk updates are not implemented.
- Generated reports and snapshots are not committed.
