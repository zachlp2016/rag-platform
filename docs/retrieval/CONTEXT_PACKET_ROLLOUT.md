# Context Packet Rollout

This plan broadens retrieval across the Nexus, Forge, and Parallax umbrella without
creating a shared vector store or a shared product memory. The umbrella owns the
packet contract, accounting rules, trust boundary, and conformance tests. Each
product continues to own its sources, ranking policy, prompts, retention, and
storage.

## Target request path

1. Select the authorized corpus/file source independently from retrieval depth using
   the [`Retrieval Decision Contract`](../../contracts/retrieval-decision.md), then
   apply the product-owned budget for the selected depth tier.
2. Plan one or more bounded search queries.
3. Retrieve a candidate pool that is deliberately larger than the final packet.
4. Fuse rankings, remove duplicates, and preserve useful source/time diversity.
5. Pack the best evidence to a token budget rather than a fixed chunk count.
6. Render stable evidence labels and provenance as untrusted data.
7. Synthesize once, cite evidence labels, and return a redacted packet summary.

The packet is an ephemeral request artifact. It is not written into user memory,
product memory, or another product's collection unless a separate, explicit memory
operation is requested and authorized.

## Shared and product-owned responsibilities

| Layer | Umbrella contract | Product policy |
| --- | --- | --- |
| Provider capacity | Effective-window discovery, reserves, accounting fields | Provider/model choice and local defaults |
| Planning | Query and lane interfaces, bounded-query invariants | Domain decomposition and intent rules |
| Evidence | Stable IDs, provenance, trust labels, content hashes | Source eligibility and point-in-time rules |
| Ranking | Fusion/dedup/diversity interfaces | Weights, freshness, authority, and domain boosts |
| Packing | Deterministic token admission and degradation events | Lane quotas and evidence-budget profile |
| Rendering | Retrieved content never becomes system policy | Persona and answer format |
| Observability | Redacted packet metrics and failure vocabulary | Local logs, alerts, and retention |

There is intentionally no umbrella vector collection, universal reranking model,
shared product prompt, or implicit cross-product memory lookup.

## Product lanes

### Parallax

- Structured market and macro facts
- Current versus historical research
- The single active/latest Beige Book, with prior releases archive-only by default
- News, filings, local documents, and explicitly relevant user memory
- Point-in-time correctness, ticker/entity matching, and future-data-leakage checks

### Nexus

- Primary and secondary sources
- Cross-domain facets and conversation-aware follow-ups
- Contradictory evidence, viewpoint diversity, geographic scope, and time scope
- Authority and uncertainty signals

### Forge

- Repository, path, symbol, diff, test, and build-result lanes
- Exact lexical and code-structure retrieval
- Deterministic security and quality knowledge bases
- Fail-closed required safety lanes and explicit trust-boundary activation

Forge needs a repository-aware source loader before its retrieval architecture can
match its repository-workflow role; document-only loading is not sufficient.

## Rollout sequence

1. Ratify Context Packet v1 and provider-neutral conformance fixtures in the
   umbrella repository.
2. Pilot adaptive requested retrieval in Parallax while preserving its current
   `answer` and `sources` API fields.
3. Add stable chunk IDs, source kinds, ordinals, hashes, and honest timestamp fields
   during product ingestion. Legacy records with unknown freshness stay marked
   unknown rather than receiving invented dates.
4. Add packet-level evaluation for recall, citation support, stale leakage, duplicate
   rate, source diversity, prompt-injection resistance, latency, and token use.
5. Adopt the contract independently in Nexus, then Forge, with product-specific
   lanes and commits.
6. Add Parallax's main library to finance chat only through an explicit `search`,
   `use indexed knowledge`, request flag, or tool invocation. Requested RAG remains
   requested; it is not injected into every finance prompt.
7. Consider extracting a shared packet assembler only after at least two products
   have conforming implementations and the v1 behavior has stabilized.

## Initial budget profiles

Budgets are caps for selected evidence, not retrieval-candidate counts.

| Mode | Initial evidence cap | Typical use |
| --- | ---: | --- |
| Lookup | 4,000-8,000 tokens | Narrow facts and direct questions |
| Standard synthesis | 8,000-16,000 tokens | Several related sources |
| Broad analysis | 20,000-24,000 tokens | Multi-facet comparison and synthesis |
| Deep research | Up to 32,000 tokens | Explicit deep mode or staged synthesis |

Every product must reserve tokens separately for instructions, conversation history,
reasoning, output, and a safety margin. It must use the provider's effective runtime
window, not merely the model's advertised training window. If exact tokenization is
unavailable, the packet records the estimator and applies a conservative margin.

## Adoption gates

A product is conforming only when tests demonstrate that:

- selected evidence never exceeds its declared budget;
- evidence IDs and source ordering are deterministic;
- exact and near duplicates cannot crowd out independent evidence;
- missing lanes and partial failures are reported rather than silently hidden;
- retrieved text is rendered as untrusted evidence, never as system instructions;
- citations resolve to packet evidence and no raw evidence is emitted to telemetry;
- product storage and memory remain isolated;
- old API response fields remain compatible during the migration window.
