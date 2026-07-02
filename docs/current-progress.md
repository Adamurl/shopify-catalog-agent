# Current Progress: Shopify Catalog Agent

This document summarizes the current state of the repository after the first
five phases of work. Phases 1-4 are read-only. Phase 5 adds a guarded
one-product Shopify writer for approved preview rows only.

## High-Level Status

We moved the project toward a phased catalog cleanup workflow:

1. Phase 1: Fetch, normalize, analyze, and report on Shopify catalog data.
2. Phase 2: Classify products and extract structured product intelligence.
3. Phase 3: Generate deterministic, human-editable proposed cleanup rules.
4. Phase 4: Render product-by-product read-only preview reports from rules.
5. Phase 5: Apply exactly one approved preview row and verify after refetch.

The production path is now centered around:

```bash
python scripts/category_seo_agent.py fetch
python scripts/category_seo_agent.py analyze
python scripts/category_seo_agent.py classify
python scripts/category_seo_agent.py propose-rules
python scripts/category_seo_agent.py preview
python scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --product-id "gid://shopify/Product/123"
python scripts/category_seo_agent.py verify-one --product-id "gid://shopify/Product/123" --expected data/previews/preview.csv
```

Only `apply-one` writes to Shopify, and it is limited to one approved preview
row per command.

## Safety Boundaries

Current safe behavior:

- Phases 1-4 do not write to Shopify.
- Phase 5 writes exactly one product per command.
- No bulk updates.
- No AI/LLM product copy generation.
- Rules are saved as `status: proposed`, not approved.
- Handle, description, and image alt changes are disabled by default in proposed rules.
- `apply-one` requires `approval=APPROVED`.
- `apply-one` refetches after writing and verifies written fields.

Legacy product-specific update proof-of-concept code was moved out of the
production path into:

```text
proof_of_concept/macuahuitl/
```

## Phase 1: Read-Only Catalog Audit

Phase 1 added a deterministic read-only catalog audit layer.

### What Phase 1 Does

- Fetches Shopify products through GraphQL Admin API queries.
- Saves raw Shopify product snapshots.
- Normalizes raw Shopify data into a local canonical product shape.
- Analyzes product health issues.
- Groups analysis by product type, collection, tag, vendor, and category.
- Writes Markdown and CSV reports.
- Defaults analysis to `ACTIVE` products only.

### Main Commands

```bash
python scripts/category_seo_agent.py fetch
python scripts/category_seo_agent.py analyze
python scripts/category_seo_agent.py analyze --category "Macuahuitls"
python scripts/category_seo_agent.py analyze --product-type "Shirts"
python scripts/category_seo_agent.py analyze --tag "Huaraches"
python scripts/category_seo_agent.py analyze --collection "Jewelry"
```

### Phase 1 Outputs

```text
data/snapshots/raw_products_<timestamp>.json
data/snapshots/normalized_products_<timestamp>.json
data/reports/catalog_summary_<timestamp>.md
data/reports/group_summary_<timestamp>.csv
data/reports/missing_seo_<timestamp>.csv
data/reports/missing_image_alt_<timestamp>.csv
data/reports/duplicate_titles_<timestamp>.csv
data/reports/duplicate_handles_<timestamp>.csv
data/reports/weak_descriptions_<timestamp>.csv
data/reports/title_patterns_<timestamp>.csv
data/reports/broad_groups_<timestamp>.csv
```

### Phase 1 Files Added

`scripts/category_seo_agent.py`

- Main CLI entrypoint for `fetch`, `analyze`, `classify`, and `propose-rules`.
- Logs `READ ONLY MODE`.
- Loads `.env`.
- Routes commands to the correct phase logic.

`src/shopify/fetch_products.py`

- Read-only Shopify GraphQL product fetcher.
- Supports product pagination.
- Fetches product fields needed by Phase 1.
- Writes raw and normalized snapshots.

`src/catalog/models.py`

- Canonical local dataclasses:
  - `CatalogProduct`
  - `CatalogImage`
  - `CatalogVariant`
- Provides `to_dict()` and `from_dict()` helpers.

`src/catalog/normalize.py`

- Converts raw Shopify product nodes into `CatalogProduct`.
- Extracts descriptions, images/media, first image alt text, variants,
  collections, tags, inventory, timestamps, SEO fields, etc.

`src/catalog/analyzer.py`

- Deterministic catalog health analysis.
- Finds missing SEO, missing image alt text, duplicate titles/handles, weak
  descriptions, missing tags, missing product types, title patterns, broad
  groups, and more.
- Contains shared product filtering used by later phases.

`src/catalog/reports.py`

- Writes Phase 1 Markdown and CSV reports.
- Ensures report rows include useful product identifiers and issue details.

`src/catalog/utils.py`

- Shared helpers for timestamps, JSON read/write, directory creation, text
  cleanup, HTML-to-text conversion, and latest-file discovery.

## Phase 2: Product Intelligence And Classification

Phase 2 added deterministic classification and attribute extraction.

### What Phase 2 Does

- Loads normalized snapshots from Phase 1.
- Classifies products into product families and subgroups.
- Extracts structured attributes from existing catalog data.
- Assigns explainable confidence scores.
- Flags products needing manual review.
- Writes enriched classified product snapshots.
- Writes classification reports.

### Attributes Extracted

The extractor looks for:

- family
- subgroup
- style/design
- size
- size number
- color
- material
- audience
- gender
- age group
- number/index
- set quantity
- variant type
- accessory type
- cultural/traditional terms
- use case

Sources used:

- title
- handle
- product type
- collections
- tags
- description text
- variant titles
- first image alt text

### Main Commands

```bash
python scripts/category_seo_agent.py classify
python scripts/category_seo_agent.py classify --snapshot data/snapshots/normalized_products_<timestamp>.json
python scripts/category_seo_agent.py classify --category "Macuahuitls"
python scripts/category_seo_agent.py classify --product-type "Shirts"
python scripts/category_seo_agent.py classify --collection "Jewelry"
python scripts/category_seo_agent.py classify --tag "Huaraches"
python scripts/category_seo_agent.py classify --vendor "Vendor Name"
python scripts/category_seo_agent.py classify --status DRAFT
```

### Phase 2 Outputs

```text
data/classified/classified_products_<timestamp>.json
data/reports/classification_summary_<timestamp>.md
data/reports/classified_products_<timestamp>.csv
data/reports/manual_review_<timestamp>.csv
data/reports/subgroup_candidates_<timestamp>.csv
data/reports/extracted_attributes_<timestamp>.csv
```

### Phase 2 Files Added

`data/config/classification_defaults.json`

- Configurable deterministic defaults.
- Contains known colors, materials, audience terms, cultural terms, accessory
  keywords, family keyword mappings, subgroup keyword mappings, and size
  patterns.
- This is where store-specific keyword tuning should happen before hardcoding
  anything in source.

`src/catalog/classification_config.py`

- Loads and validates `classification_defaults.json`.
- Provides the `ClassificationConfig` dataclass.

`src/catalog/attribute_extractor.py`

- Extracts structured attributes from existing product data.
- Emits both final attributes and row-level extraction evidence for reports.
- Handles deterministic patterns such as:
  - `27"`, `27”`, `27 inch`, `27-inch` -> `27 inch`
  - `No. 4`, `#4`, `Number 4` -> `number_index: 4`
  - `2 pack`, `set of 2` -> `set_quantity: 2`

`src/catalog/subgroup_detector.py`

- Detects subgroup candidates.
- Uses family, size, design, product type, collection, tags, accessory type, and
  configured subgroup keywords.

`src/catalog/classifier.py`

- Classifies each product.
- Adds:
  - `classification.family`
  - `classification.subgroup`
  - `classification.category_intent`
  - `classification.confidence`
  - `classification.matched_signals`
  - `classification.warnings`
- Flags manual-review conditions such as missing family, missing subgroup,
  missing tags, no image, conflicting group signals, ambiguous size/color, etc.

`src/catalog/classification_reports.py`

- Writes Phase 2 classified JSON and CSV/Markdown reports.
- Produces manual-review rows and subgroup candidate summaries.

## Phase 3: Deterministic Rule Proposals

Phase 3 added a local rule proposal layer.

### What Phase 3 Does

- Loads classified product snapshots from Phase 2.
- Groups products by subgroup first, then family.
- Infers proposed templates from existing classified attributes.
- Generates editable JSON rules.
- Validates rules for safety and risk.
- Writes rule proposal reports.
- Keeps all rules as proposals only.

### Main Commands

```bash
python scripts/category_seo_agent.py propose-rules
python scripts/category_seo_agent.py propose-rules --classified data/classified/classified_products_<timestamp>.json
python scripts/category_seo_agent.py propose-rules --family "Macuahuitl"
python scripts/category_seo_agent.py propose-rules --subgroup "Macuahuitl 27 inch"
python scripts/category_seo_agent.py propose-rules --product-type "Shirts"
python scripts/category_seo_agent.py propose-rules --collection "Jewelry"
python scripts/category_seo_agent.py propose-rules --tag "Huaraches"
python scripts/category_seo_agent.py propose-rules --min-confidence 0.8
```

### Phase 3 Outputs

```text
data/rules/proposed/<safe_group_name>_rule_<timestamp>.json
data/reports/rule_proposal_summary_<timestamp>.md
data/reports/proposed_rules_<timestamp>.csv
data/reports/rule_manual_review_<timestamp>.csv
```

### Proposed Rule Defaults

Every generated rule defaults to:

```json
{
  "status": "proposed",
  "fields": {
    "update": ["title", "seo", "tags"],
    "leave_alone": ["handle", "description", "image_alt"]
  },
  "constraints": {
    "allow_handle_updates": false,
    "allow_description_updates": false,
    "allow_image_alt_updates": false
  },
  "tags": {
    "remove": [],
    "replace_existing": false
  }
}
```

So proposed rules are safe by default and are not approvals.

### Phase 3 Files Added

`src/rules/rule_models.py`

- Stable dataclasses for proposed rules:
  - `ProposedRule`
  - `RuleMatch`
  - `RuleTemplates`
  - `RuleTags`
  - `RuleFields`
  - `RuleConstraints`
  - `RuleExample`
  - `RuleConfidence`

`src/rules/template_inferer.py`

- Infers title, handle, SEO, description, and image alt templates.
- Prefers extracted attributes over raw rewriting.
- Includes helpers for placeholder detection and template rendering.

`src/rules/rule_validator.py`

- Validates proposed rules.
- Checks for:
  - missing match criteria
  - missing templates
  - unsupported placeholders
  - missing placeholders in products
  - unsafe field updates
  - tags not append-only
  - low confidence
  - small groups
  - likely SEO length issues

`src/rules/rule_proposer.py`

- Groups classified products.
- Builds proposed rule JSON objects.
- Infers required match attributes.
- Proposes append-only tags.
- Builds examples.
- Applies validation warnings.
- Writes rule JSON files under `data/rules/proposed/`.

`src/rules/rule_reports.py`

- Writes Phase 3 reports:
  - rule proposal summary Markdown
  - proposed rules CSV
  - rule manual review CSV

`src/rules/rule_utils.py`

- Shared rule helpers for slugs, safe file names, deduplication, and ratios.

## Other Important Changes

`.env.example`

- Updated to prefer:

```text
SHOPIFY_STORE_DOMAIN=
SHOPIFY_ADMIN_ACCESS_TOKEN=
SHOPIFY_API_VERSION=2025-10
```

`.gitignore`

- Ignores generated snapshots, classified outputs, reports, and proposed rules.
- Keeps `.gitkeep` placeholders.

`src/shopify/client.py`

- Default Shopify API version changed to `2025-10`.

`proof_of_concept/macuahuitl/`

- Legacy product-specific update code moved here.
- This keeps mutation-oriented proof-of-concept code outside the production
  read-only CLI path.

## Tests Added

`tests/test_category_phase1.py`

- Covers Phase 1 normalization, filtering, title patterns, analysis, and report
  writing.

`tests/test_classification_phase2.py`

- Covers attribute extraction, classification, manual review flags, reports,
  and vendor/status filtering.

`tests/test_rule_proposals_phase3.py`

- Covers template inference, proposed rule defaults, validation, reports, and
  Phase 3 filters.

`tests/test_preview_phase4.py`

- Covers preview rendering, risky-field blocking, duplicate handle warnings,
  shared media warnings, preview reports, and rule discovery.

`tests/test_writer_phase5.py`

- Covers approved preview row loading, approval rejection, safety planning,
  Shopify writer payloads, verification mismatches, and verification reports.

## Current Verification

The full test suite currently passes:

```text
95 passed
```

Phases 1-4 remain read-only. Phase 5 includes Shopify mutations only in
`src/writer/shopify_writer.py`, limited to a one-product test update path.

## Suggested Next Steps

Before any future bulk update work, review and edit:

1. `data/config/classification_defaults.json`
   - Add or adjust store-specific families, subgroups, materials, colors, and
     terms.
2. Generated classification reports.
   - Check whether subgroup detection matches how you want to clean the catalog.
3. Generated proposed rule JSON files.
   - Edit templates, tags, match criteria, and warnings manually.
4. Rule manual-review CSV.
   - Decide which rules are too broad, too small, or need better attributes.
5. Generated preview CSV files.
   - Set approval values manually to `APPROVED`, `REJECTED`, or `REVIEW` only
     after reviewing the suggested values.
6. Preview warning CSV files.
   - Resolve duplicate handles, shared media warnings, missing attributes, and
     blocked fields before any future test update.

## Phase 4: Preview Report Builder

Phase 4 added read-only preview rendering.

### What Phase 4 Does

- Loads classified product snapshots.
- Loads proposed or approved rule JSON files.
- Matches products to rule match criteria.
- Renders deterministic suggested values from rule templates.
- Preserves existing tags and appends proposed tags with dedupe.
- Blocks handle, description, and image alt fields unless a rule explicitly
  allows them.
- Writes product-by-product CSV and JSON preview files.
- Writes Markdown summary and warning CSV reports.

### Main Commands

```bash
python scripts/category_seo_agent.py preview
python scripts/category_seo_agent.py preview --rule data/rules/proposed/macuahuitls_27_inch_rule.json
python scripts/category_seo_agent.py preview --classified data/classified/classified_products_<timestamp>.json
python scripts/category_seo_agent.py preview --family "Macuahuitl"
python scripts/category_seo_agent.py preview --subgroup "Macuahuitl 27 inch"
python scripts/category_seo_agent.py preview --approved-rules-only
```

### Phase 4 Outputs

```text
data/previews/preview_<group>_<timestamp>.csv
data/previews/preview_<group>_<timestamp>.json
data/reports/preview_summary_<group>_<timestamp>.md
data/reports/preview_warnings_<group>_<timestamp>.csv
```

### Phase 4 Files Added

`src/preview/preview_models.py`

- Stable dataclasses for preview documents and rows.
- Defines the default approval state as `PENDING`.

`src/preview/rule_renderer.py`

- Loads rule JSON files.
- Matches classified products to rule match criteria.
- Renders title, handle, SEO, description, image alt, and tag suggestions.
- Blocks risky fields according to rule constraints.

`src/preview/preview_builder.py`

- Finds proposed/approved rule files.
- Builds preview documents from classified products and rules.
- Applies row validation.

`src/preview/preview_validator.py`

- Adds warnings for duplicate handles, shared media IDs, disabled fields, SEO
  length issues, missing attributes/images, inactive products, low confidence,
  proposed rules, and other review conditions.

`src/preview/preview_reports.py`

- Writes preview CSV, preview JSON, Markdown summary, and warning CSV files.

`src/preview/diff_utils.py`

- Shared helpers for tag dedupe, tags-to-append, handle slugs, and important
  word loss detection.

## Phase 5: One-Product Shopify Writer

Phase 5 added a guarded Shopify writer for exactly one approved preview row.

### What Phase 5 Does

- Loads one preview CSV row by product ID or 1-based row index.
- Requires `approval=APPROVED`.
- Rejects inactive products by default.
- Rejects invalid Shopify product GIDs.
- Plans only deterministic fields from the preview row.
- Writes safe fields:
  - title
  - SEO title/description
  - append-only tags
- Can write risky fields only when the preview did not block them:
  - handle
  - description HTML
  - first image alt
- Refetches the product after writing.
- Verifies refetched Shopify values against expected preview values.
- Writes Markdown and JSON verification reports.

### Main Commands

```bash
python scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --product-id "gid://shopify/Product/123"
python scripts/category_seo_agent.py apply-one --preview data/previews/preview.csv --row-index 4
python scripts/category_seo_agent.py verify-one --product-id "gid://shopify/Product/123" --expected data/previews/preview.csv
```

### Phase 5 Outputs

```text
data/reports/one_product_verification_<timestamp>.md
data/reports/one_product_verification_<timestamp>.json
```

### Phase 5 Files Added

`src/writer/write_models.py`

- Dataclasses for approved preview rows, Shopify snapshots, update plans,
  mismatches, and verification results.

`src/writer/approved_row_loader.py`

- Loads one preview CSV row.
- Enforces exact product ID matching or 1-based row-index selection.
- Parses tags, blocked fields, warnings, and detected attributes.

`src/writer/safety_checks.py`

- Validates approval safety rules.
- Builds the exact one-product update plan.
- Ensures tags are append-only and risky fields are not written when blocked.

`src/writer/shopify_writer.py`

- Contains the Phase 5 Shopify GraphQL mutations.
- Supports one product update and optional first-media alt update.
- Refetches the product after mutation.

`src/writer/verification.py`

- Compares refetched Shopify values against expected preview values.
- Produces mismatch records.

`src/writer/writer_reports.py`

- Writes one-product verification Markdown and JSON reports.
