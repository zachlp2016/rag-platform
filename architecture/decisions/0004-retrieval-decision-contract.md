# ADR 0004: Orthogonal Source and Retrieval-Depth Decisions

- Status: Accepted
- Date: 2026-08-03

## Context

Retrieval routing has historically treated a file-focused request as though it were
also a retrieval-depth tier. That combines two independent questions:

1. **Where may retrieval look?**
2. **How much evidence should retrieval gather?**

A narrow fact from one selected file may need less evidence than a corpus lookup. An
exhaustive audit of that same file may need more evidence than an ordinary corpus
analysis. Conflating source selection with depth makes both behavior and backtests
hard to interpret.

Model-assisted classification can help estimate depth, but allowing a classifier to
select a file, tool, product memory, or authorization scope would turn a probabilistic
output into an authority decision. That is outside the umbrella retrieval boundary.

## Decision

Define the provider-neutral `rag.retrieval-decision` envelope at
`schema_version: 1`.

The envelope records two orthogonal decisions:

- `source` selects either the product corpus or one explicit product-owned file; and
- `depth` selects `lookup`, `standard`, `analysis`, or `deep`, together with the
  product-selected evidence-token budget and observed facet count.

Source selection may use explicit caller state, deterministic structural rules,
authenticated conversation/document state, or an explicit fallback. It may not use a
utility model. A utility model may classify **depth only** and may not choose a file,
corpus, tool, memory scope, product, or authorization boundary.

Fallbacks are never implicit. Producers record `method: fallback`, confidence, and
bounded reason codes. Each product owns the numeric evidence budget associated with a
tier; the umbrella defines tier meaning and envelope invariants, not universal token
amounts.

Version 1 decisions are ephemeral. The envelope contains no raw query or conversation
text, cannot be persisted, and explicitly disables raw-query logging.

## Consequences

- File selection no longer implies a large context packet, and deep retrieval no
  longer implies corpus-wide access.
- Products can compare deterministic and utility-model depth classifiers without
  changing source authority.
- The umbrella can validate decisions and maintain evaluation fixtures without
  implementing a universal classifier.
- Products must map tiers to budgets, choose fallback tiers, and authorize source,
  tool, and memory access locally.
- Existing retrieval-request and context-packet contracts remain responsible for
  detailed token accounting, retrieval plans, evidence, provenance, and diagnostics.
