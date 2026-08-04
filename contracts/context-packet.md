# Retrieval Request and Context Packet Contract

This contract defines the provider-neutral boundary between a product retrieval
request and the effective evidence made available to a model. It does not define a
vector database, query planner, reranker, prompt, provider, or product domain policy.

## Versioned artifacts

- `retrieval-context.schema.json` defines both version 1 envelope shapes.
- `../fixtures/context-packet/cases.v1.json` contains conformance exchanges and
  invalid mutations.
- `../rag_platform/context_packet.py` is the standard-library validator and budget
  calculator.

The envelope contract names are `rag.retrieval-request` and `rag.context-packet`.
Both use `schema_version: 1`.

## Retrieval Request

A request carries:

- a correlation-safe `request_id`, creation timestamp, and owning `product_id`;
- the current query, generic intent, point-in-time `as_of`, and optional user/assistant
  conversation turns used only for retrieval planning;
- product-owned logical scopes;
- a provider-neutral token budget;
- the tokenizer or conservative estimator used for every count; and
- an explicit ephemeral lifecycle declaration.

Scopes are logical identifiers. Their meanings and authorization remain local to the
selected product. The packet must repeat the same `product_id`; a scope does not
authorize reading another product's memory.

## Token budget and effective context

All counts in one exchange must use the same provider tokenizer or the same
conservative estimator. The contract does not name a provider or model.

Given the request budget:

```text
max_input_tokens = context_window_tokens
                 - reserved_output_tokens
                 - reserved_reasoning_tokens
                 - safety_margin_tokens

non_evidence_input_tokens = instruction_tokens
                          + conversation_tokens
                          + tool_tokens

available_evidence_tokens = min(
    requested_evidence_tokens,
    max_input_tokens - non_evidence_input_tokens,
)
```

The fixed reservations must not exhaust the context window. The packet's selected
evidence token total must not exceed `available_evidence_tokens`, its evidence count
must not exceed `max_evidence_items`, and its effective-context fields must reproduce
the request calculation exactly.

This is the **effective context**: the evidence that can actually fit after all other
input and output reservations, not the provider's advertised context window and not a
fixed number of chunks.

`reserved_output_tokens` reserves visible answer tokens.
`reserved_reasoning_tokens` separately reserves hidden reasoning tokens, including a
provider's configured reasoning budget. Implementations must not silently charge
hidden reasoning against evidence or count it twice. `token_accounting.method` states
whether counts came from a provider tokenizer or a conservative estimator, while
`counter_id` identifies that tokenizer/estimator and revision.

## Retrieval plan

The packet records whether retrieval used a single query, decomposition, or iterative
rounds. Each planned query has a stable packet-local ID, a purpose, and one or more
product-owned lane IDs. Evidence must refer only to declared queries and compatible
lanes. Exactly one planned query has purpose `primary` and preserves the request query
text verbatim; rewritten and decomposed queries are additional plan entries.

The contract does not prescribe how plans are produced. Deterministic rules, lexical
search, dense search, structured databases, tools, and model-assisted planning are all
valid product implementations.

## Evidence and provenance

Every selected evidence record includes:

- a stable `evidence_id` and packet-local `citation_id`;
- its contributing query IDs, lane, final rank, text, and token count;
- a source kind and stable source ID, with optional title and URI;
- stable document and chunk IDs, chunk ordinal, SHA-256 content hash, ingestion time,
  and optional publication, validity, and source-revision fields; and
- a normalized final score plus optional finite product score components.

Evidence IDs, citation IDs, ranks, document/chunk identity, and content hashes must be
unique or internally consistent as described by the validator. Unknown publication
or validity times are represented as `null`; implementations must not invent dates.
Legacy evidence with an unknown ingestion time also uses `null` and requires a
`provenance_unknown` degradation diagnostic. Citation IDs are zero-padded and
packet-local (`E001`, `E002`, ...); evidence/document/chunk IDs provide stable identity
outside the packet.

`content_hash` is `sha256:` followed by the lowercase SHA-256 digest of the exact UTF-8
bytes in that evidence record's `text`. The validator recomputes it; it is not merely a
producer assertion.

## Untrusted evidence boundary

`trust` is always `untrusted` in version 1. This marks an instruction-authority
boundary, not a claim that every fact is false.

Context Packets contain evidence only. They must not carry product personas, system or
developer instructions, tool authorization, or executable directives. A provider
adapter must:

1. keep product/system instructions outside the packet;
2. render packet evidence in a clearly delimited evidence block outside the system or
   developer instruction channel;
3. state that retrieved instructions are quoted source material and cannot override
   system, developer, user, or tool policy; and
4. preserve evidence and citation boundaries through rendering.

Retrieved content must never select tools, authorize mutations, or broaden product
memory access.

## Diagnostics and degradation

Packets report `complete`, `degraded`, or `empty` status. Diagnostics include logical
degradation codes, coverage gaps, aggregate candidate/deduplication/selection counts,
budget drops, and per-lane status and counts.

`post_deduplication_candidate_count` is the number of candidate survivors after exact
and near-duplicate removal, not the number removed. It must be no greater than
`candidate_count` and no smaller than `selected_count`.

Diagnostics contain bounded logical codes, not exception messages, prompt content,
credentials, endpoints, or evidence text. A failed required lane makes a non-empty
packet degraded. Product policy decides whether a degraded packet can answer, must
retry, or must fail closed.

## Ephemeral lifecycle and observability

Version 1 requires:

```json
{
  "mode": "ephemeral",
  "persist_packet": false,
  "log_evidence_content": false
}
```

Implementations may log correlation IDs, contract versions, counts, token accounting,
latency, and logical diagnostics. They must not log query/conversation text, evidence
content, authorization data, or product memory through this contract.

## Adoption boundary

The umbrella owns this shape, arithmetic, trust boundary, and conformance fixtures.
Each product independently owns and tests:

- scopes, lanes, source types, and authorization;
- query decomposition and follow-up rewriting;
- candidate generation, freshness, deduplication, reranking, and diversity;
- memory eligibility and retention;
- provider rendering and final prompts; and
- degraded-mode policy.

Adoption does not permit a product to read another product's vector collection or
runtime memory.
