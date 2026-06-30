# Future Category SEO Agent

The future agent should generalize the Macuahuitl cleanup workflow across any
store category. It should discover patterns, propose deterministic rules, create
previews, update one product, verify the result, and only then bulk apply
approved rows.

## Agent Responsibilities

1. Analyze active products by category, collection, product type, tag, menu path,
   size, vendor, and inventory status.
2. Detect product families and identify when a category is too broad.
3. Extract reusable attributes such as family, style, design, size, color,
   material, audience, age group, set count, and numeric identifiers.
4. Propose rules for product title, handle, SEO title, SEO description, product
   description, image alt text, and tags.
5. Generate a preview report before every write.
6. Update one representative test product first.
7. Refetch and verify Shopify data after the test and after bulk writes.

## Architecture

- Analyzer: reads Shopify data and local menu/category sources.
- Classifier: assigns products to category/subgroup and extracts attributes.
- Rule proposer: suggests title, SEO, handle, description, image-alt, and tag
  templates.
- Preview builder: writes CSV/Markdown review outputs with warnings.
- Approval gate: requires a user-approved row set before writes.
- Writer: applies approved deterministic values to Shopify.
- Verifier: refetches updated products and reports mismatches.

The AI layer should propose patterns and explain low-confidence decisions. The
write layer should remain deterministic and reviewable.

## Required Warnings

Preview reports should flag:

- duplicate suggested handles
- shared media IDs
- missing images
- low-confidence attribute extraction
- inactive or archived products
- products with multiple competing categories
- descriptions that are too short or too generic
- SEO titles or descriptions that are too long
- handle changes that may affect existing URLs

## Example Rule

```json
{
  "group": "Macuahuitls 27 inch",
  "match": {
    "family": "Macuahuitl",
    "size": "27\""
  },
  "title_pattern": "Macuahuitl (Aztec Club) - {design} - {size}",
  "handle_pattern": "macuahuitl-aztec-club-{design_slug}-{size_number}",
  "meta_title_pattern": "{title}",
  "meta_description_pattern": "{title} handmade wooden macuahuitl inspired by Mexica ceremonial clubs. Handmade to order with a 6-8 week lead time.",
  "description_template": "<p>This is a handmade wooden macuahuitl inspired by Mexica ceremonial clubs.</p><p>Each macuahuitl is handmade to order with a 6-8 week lead time. Finish, color, and detail placement can vary slightly from piece to piece.</p>",
  "image_alt_template": "{title} handmade wooden macuahuitl with {design} design, wooden handle, and obsidian-style blade details.",
  "append_tags": ["Macuahuitl", "Aztec club", "Wooden macuahuitl", "Mexica", "Danza Azteca"],
  "update_fields": ["title", "handle", "seo", "description", "first_image_alt", "tags"]
}
```

## Suggested CLI

```bash
python3 scripts/category_seo_agent.py analyze --category "Macuahuitls"
python3 scripts/category_seo_agent.py preview --category "Macuahuitls" --size '27"'
python3 scripts/category_seo_agent.py apply-one --category "Macuahuitls" --product-id gid://shopify/Product/...
python3 scripts/category_seo_agent.py apply-approved --preview data/reports/macuahuitls_27_preview.csv
```

The first implementation should stay read-first and preview-first. Bulk writes
should require explicit approval and post-write verification.
