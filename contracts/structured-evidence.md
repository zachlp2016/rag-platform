# Point-in-Time Structured Evidence Contract

This contract defines the provider-neutral boundary between a product-owned
structured-data store and one request-scoped retrieval lane. Macro statistics are the
first intended adoption, but the shape is not tied to FRED, finance, a database, or a
provider.

It does not define source ingestion, release calendars, unit conversions, feature
formulas, freshness thresholds, ranking, or durable storage.

## Versioned artifacts

- `structured-evidence.schema.json` defines the version 1 envelope.
- `../fixtures/structured-evidence/conformance.v1.json` contains compact valid and
  invalid point-in-time cases.
- `../rag_platform/structured_evidence.py` is the standard-library semantic
  validator and pre-Context-Packet admission guard.

The envelope contract name is `rag.structured-evidence` with `schema_version: 1`.

## Identity and ownership

Each record belongs to one `product_id`, `request_id`, and `lane_id`. The product and
request IDs and `as_of` must copy the originating `rag.retrieval-request` unchanged;
a lane cannot choose a more convenient cutoff. `evidence_id` identifies the exact
request-scoped evidence view. Source identity has two stable parts:

- `source_id` identifies the publisher, dataset, or product-owned source adapter;
- `series_id` identifies a series within that source.

`kind` is a generic source category. `uri` is nullable because a stable external URI
does not exist for every database or licensed feed. Product authorization still
controls whether a lane may read the source; this envelope grants no source access.

Raw observations, revision histories, source payloads, release calendars, and feature
lineage remain in the producing product. They are never copied into the umbrella
repository or a shared cross-product store.

## Point-in-time semantics

The timestamps have deliberately different meanings:

| Field | Meaning |
| --- | --- |
| `observed_at` | Period or instant described by the value; it is not a knowledge timestamp. |
| `released_at` | When the publisher released this exact vintage, or `null` when the source does not provide a defensible value. |
| `available_at` | Earliest defensible time this exact vintage and every input used by its features could be treated as known. |
| `as_of` | Request cutoff against which eligibility and freshness are evaluated. |
| `retrieved_at` | When the product fetched or reconstructed the record; it may be later than `as_of` during an archival replay. |

When `released_at` is known, `released_at <= available_at` is required. Producers must
not substitute `observed_at`, a file modification time, or the current time for an
unknown release. `availability_basis` records whether availability came from a source
release, archival source vintage, first observation, or local ingestion.

For a raw value, `available_at` covers the exact source vintage. For a derived feature,
it is the maximum availability time of **all** observations, revisions, and other
inputs used to compute that feature. A revision of an old observation therefore does
not become historically available on the old observation date.

No-lookahead eligibility is deterministic:

```text
no_lookahead = available_at <= as_of
```

An eligible record has `no_lookahead: true` and no reason codes. A later vintage has
`no_lookahead: false` with `available_after_as_of`. Only eligible records may be
rendered into Context Packet evidence. Ineligible records may be counted in redacted
lane diagnostics, but their values must not enter model context.

An archival replay may have `retrieved_at > as_of`; that is not lookahead when the
exact vintage has a defensible, earlier `available_at` from source-vintage metadata.
The product must retain the local lineage needed to support that assertion.

## Vintage, values, and features

`vintage_id` identifies the exact source snapshot used. `revision_id` is nullable only
when the source has no distinct revision identifier. Producers must change vintage or
revision identity when corrected source values become available.

The base `value` is a finite JSON scalar or `null`. A selected record must contain a
non-null base value or at least one derived feature. Every feature has a stable logical
ID, finite JSON scalar, and explicit unit. Base units and observation frequency are
also required; the umbrella does not prescribe a universal unit ontology or infer
frequency from dates.

## Freshness is not eligibility

Freshness is evaluated against either `observed_at` or `available_at`, using a
product-selected `max_age_seconds`. The declared `fresh` or `stale` status must match
that basis and threshold. If no defensible threshold exists, the status is `unknown`
and the threshold is `null`.

A stale record can still be point-in-time eligible. Conversely, a newly released
future vintage is ineligible for an earlier `as_of` even if a freshness policy would
otherwise call it fresh. Products own frequency-aware thresholds and the policy for
whether stale evidence can answer a request.

## Provenance and trust boundary

`payload_hash` identifies the exact product-owned source payload by SHA-256 without
placing that raw payload in the envelope. Products retain the mapping from the hash,
source/series identity, vintage, and revision to their local rows.

Structured evidence is always `untrusted`. Values and source text are evidence, never
system/developer instructions, tool authorization, or permission to mutate data. The
version 1 lifecycle is request-scoped and requires:

```json
{
  "mode": "ephemeral",
  "persist_evidence": false,
  "log_values": false
}
```

For context admission, a product renders only an eligible, compact structured summary
as an ordinary `rag.context-packet` evidence record. It preserves `evidence_id`, source
identity, vintage/revision provenance, `as_of`, units, and freshness in that summary;
the Context Packet's content hash binds the exact rendered text. The structured view
and Context Packet are ephemeral. Durable ingestion or memory promotion is a separate,
explicit product-owned operation.

Adapters call `validate_structured_evidence_admission(request, evidence)` before
rendering. In addition to validating both records, it requires exact product, request,
and `as_of` identity and rejects a correctly labeled but ineligible future candidate.

## Adoption boundary

The umbrella owns this shape, temporal vocabulary, eligibility equation, trust
boundary, and conformance cases. Each product independently owns and tests:

- authoritative source and series catalogs;
- source-specific timestamps, time zones, release calendars, and vintage APIs;
- raw schemas, corrections, backfills, retention, and payload hashing;
- unit normalization, feature formulas, input lineage, and missing-value policy;
- freshness thresholds, ranking, summary rendering, and degraded-mode behavior; and
- admission into its own Context Packets without reading another product's data.
