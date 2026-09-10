# ADR-0005 - Separate Review Tables with Shared Columns

- **Status:** Accepted
- **Date:** 2026-09-06

## Decision

Keep hospital and competitor reviews in the existing `reviews` and
`competitor_reviews` tables, and share only their identical Google review columns
through a declarative mixin. The separate tables preserve the OneBox ingestion boundary,
table-specific foreign keys, analysis and sync fields, relationships, indexes, and
constraints without a migration or data movement. A discriminator-based merged table is
deferred until a concrete cross-table requirement justifies its schema and rollout risk.
