# Product Title Normalization Workflow

## Summary

The Product Title Normalization Agent is a future audit and suggestion workflow for standardizing Shopify product titles across the catalog. Its goal is to improve consistency, readability, organization, and SEO while preserving the original product meaning.

This feature must not let AI freely rewrite product titles. The workflow should first understand the catalog, group related products, infer title structure, apply deterministic cleanup and formatting rules, then use AI only when confidence is low.

This is an audit-only system. It should generate suggestions for manual review and must not automatically update Shopify.

## Workflow Overview

```text
Pull Products
        |
        v
Analyze Catalog
        |
        v
Group Similar Products
        |
        v
Infer Group Structure
        |
        v
Generate Standard Format
        |
        v
Normalize Product Titles
        |
        v
Confidence Score
 ┌──────┴────────┐
 |               |
 v               v
Suggestion      AI Review
        |        |
        └───┬────┘
            v
      Review Report
            |
            v
     Manual Approval
            |
            v
 Future: Shopify Update
```

## Phase 1: Catalog Analysis

Before suggesting title changes, the agent should analyze the current catalog structure.

Generate statistics such as:

- Total products
- Product type counts
- Common title structures
- Most common prefixes
- Most common suffixes
- Duplicate titles
- Duplicate handles
- Product groups
- Missing product types
- Missing tags

This phase gives a clear overview of how the catalog is currently organized and where title inconsistency is most common.

## Phase 2: Product Group Detection

Group products that belong to the same product family. Grouping should use product type, title keywords, tags, collections, variant options, and title similarity.

Example product families:

- Ayoyotes
- Ayoyotes with Obsidian
- Abalone
- Abalone Earrings
- Macuahuitl
- Copilli
- Atecocolli
- Huaraches
- Calendars
- Hats

The goal is to discover reusable catalog families that future catalog optimization agents can also use.

## Phase 3: Learn Each Product Family

Each product family may need its own title structure. The agent should infer meaningful title attributes from existing product data without inventing missing information.

Example:

```text
Current:
Ayoyotes w/ Obsidian - Adult - Teal/ Black

Desired:
Ayoyotes with Obsidian - Teal and Black - Adult

Detected attributes:
Product Name: Ayoyotes with Obsidian
Color: Teal and Black
Age Group: Adult
```

Another example:

```text
Current:
Macuahuitl - 27"

Possible desired title:
Macuahuitl - Standard - 27"

or:
Macuahuitl - Obsidian Blade - 27"
```

The agent should only use `Standard`, `Obsidian Blade`, or any other design value when that information exists in trusted catalog data such as product title, product type, tags, collections, options, variants, description, or another approved source. Do not invent product attributes.

## Phase 4: Build Group Formatting Rules

Each product family should have a formatting template based on the attributes that are consistently available for that family.

Examples:

```text
Family:
Ayoyotes

Template:
Product - Color - Age Group

Result:
Ayoyotes - Brown - Adult
```

```text
Family:
Macuahuitl

Template:
Product - Design - Size

Result:
Macuahuitl - Aztec Calendar - 27"
```

```text
Family:
Huaraches

Template:
Product - Color - Size

Result:
Leather Huaraches - Brown - Size 10
```

Some product families may only need two segments.

```text
Abalone Earrings - Small
```

Do not force every product into a three-segment title. Formatting should adapt to each product family.

## Phase 5: Rule-Based Normalization

Apply deterministic cleanup before using AI. These rules should solve most title issues.

Normalize abbreviations and separators:

- Convert `w/` to `with`
- Convert `/` between colors to `and`
- Standardize quotation marks
- Standardize hyphens
- Standardize spacing around separators

Remove or fix formatting noise:

- Duplicate spaces
- Inconsistent capitalization
- Inconsistent punctuation
- Unnecessary parentheses
- Repeated words
- Trailing numbers that are not meaningful

The deterministic pass should produce a suggested title, a reason for change, and a confidence score.

## Phase 6: AI Review

Use AI only when deterministic rules cannot confidently normalize a title.

AI review should:

- Understand the product using available catalog context
- Preserve product meaning
- Maintain SEO value
- Follow the product family's formatting template
- Avoid inventing product attributes
- Return an explanation for every suggestion

Every AI-reviewed suggestion should include:

- Suggested title
- Explanation
- Confidence score
- Detected product family
- Detected attributes

AI output should still be treated as a suggestion for manual review, not as an automatic Shopify update.

## Phase 7: Review Report

Generate a CSV report for manual review.

Recommended columns:

- Current Title
- Suggested Title
- Detected Product Family
- Detected Attributes
- Reason For Change
- Confidence
- Approve
- Notes

The `Approve` and `Notes` columns are intended for a human reviewer. No changes should be pushed to Shopify in this phase.

## Future Workflow

Once title normalization is stable, future agents can reuse the same product grouping foundation.

Future modules may include:

- SEO optimization
- Product description cleanup
- Tag standardization
- Collection assignment
- Product type standardization
- Duplicate product detection
- Image alt text generation
- Variant cleanup
- URL handle optimization

The product grouping system should become the shared foundation for future catalog optimization agents.

## Implementation Notes

The current Python audit app is the likely implementation foundation. Future work should extend the existing audit-first approach rather than replacing it with direct Shopify mutations.

Useful existing product fields include:

- `title`
- `handle`
- `product_type`
- `category`
- `tags`
- `collections`
- `variants`
- `options`
- `seo_title`
- `seo_description`
- `description_html`
- `media`

Expected implementation behavior:

- Read products from the existing Shopify product pull or local snapshot.
- Analyze catalog-level title patterns before suggesting changes.
- Detect product families before applying title templates.
- Apply deterministic rules before AI review.
- Assign confidence scores to all suggestions.
- Generate a CSV review report.
- Keep Shopify updates out of scope until a later manual-approval workflow exists.

