# ADR 0005: Point-in-Time Structured Evidence Lanes

- Status: Accepted
- Date: 2026-08-04

## Context

Products need to combine document retrieval with structured observations and derived
features. Macro statistics are the first pilot, but the same temporal problem occurs
with market data, benchmark results, telemetry, inventories, and other revised series.

An observation date alone does not establish when a value was knowable. Publishers
release values later, revise prior periods, and expose vintages on different schedules.
If a retrieval lane selects the newest stored row without relating its exact vintage
to the request's `as_of`, historical analysis can silently use future information.

Moving raw structured rows into the umbrella would violate product isolation and
couple products to a shared database, unit model, and retention policy. Treating rows
as ordinary document chunks would also discard the temporal distinctions needed for
point-in-time evaluation.

## Decision

Define the version 1 `rag.structured-evidence` envelope as an ephemeral lane-boundary
record.

The envelope carries stable source and series identity, the observed/released/available
times, exact vintage and revision, units and frequency, a base value and bounded
derived features, freshness, payload provenance, and an explicit untrusted lifecycle.

No-lookahead eligibility is derived only from `available_at <= as_of`. Producers set
`available_at` to the latest availability of the exact vintage and every input used by
its derived features. `released_at <= available_at` is required when release time is
known. Observation and retrieval timestamps do not grant eligibility. Before context
admission, the product, request, and `as_of` identity must exactly match the originating
Retrieval Request, and the record must be no-lookahead eligible.

Raw rows and feature lineage remain in the product that ingested them. Only eligible,
compact summaries may be rendered as untrusted evidence in an ephemeral Context
Packet. Persistence or memory promotion is outside this contract and requires a
separate product-owned operation.

## Consequences

- Products can add structured lanes without sharing databases or source-specific
  schemas.
- Historical evaluations can reject later revisions deterministically and state why.
- Staleness remains observable without being conflated with future-data leakage.
- Unknown release times remain explicit and use a declared conservative availability
  basis rather than invented timestamps.
- Products must retain enough local vintage and feature lineage to support their
  `available_at` assertions.
- Context Packet v1 remains unchanged: products render selected structured summaries
  into its existing untrusted evidence records.
