# ADR 0003: Retrieval Request and Context Packet Contract

- Status: Accepted
- Date: 2026-08-03

## Context

Nexus, Forge, and Parallax need broader, query-driven retrieval without sharing a
vector store, memory records, prompts, or domain ranking policy. Their existing
retrieval paths primarily use fixed chunk counts and render retrieved text directly
into provider messages. That makes context size difficult to reason about, hides
partial retrieval failures, and can blur the boundary between trusted instructions
and untrusted evidence.

The platform boundary already assigns generic retrieval interfaces and invariants to
the umbrella while leaving loaders, weights, ranking, and tuning to each product.
A provider-neutral exchange format is therefore appropriate before extracting any
shared retrieval implementation.

## Decision

Define version 1 of two related envelopes:

1. A **Retrieval Request** describes the query, point-in-time boundary, owning product,
   product-owned scopes, token-counting method, and an explicit token budget.
2. A **Context Packet** returns the product-owned retrieval plan, selected evidence,
   stable provenance, effective-context accounting, and degradation diagnostics.

All evidence in a Context Packet is evidence, not instruction authority. Every
evidence record is explicitly marked `untrusted`, and provider adapters must keep it
outside system/developer instructions. The packet contains no persona or prompt.

The effective evidence budget is derived from the declared context window after
reserving visible output, hidden reasoning, safety margin, instructions, conversation,
and tool-schema tokens.
Selected evidence must fit both that token budget and the declared item cap.

Version 1 packets are ephemeral and non-persistent by contract. Persisting packet
content, logging evidence, or moving evidence between products requires a separate,
explicit, product-owned and auditable feature; the packet itself grants no such
authority.

## Consequences

- Products can broaden retrieval using decomposition, hybrid search, reranking, and
  iterative passes while returning one comparable envelope.
- Context limits are expressed in tokens rather than a universal chunk count.
- Callers can distinguish complete, degraded, and empty retrieval without receiving
  raw exception details.
- Citations can refer to stable evidence, document, chunk, and content-hash identity.
- Prompt safety becomes a transport invariant instead of a prompt-writing convention.
- Products still own retrieval lanes, source policy, freshness, ranking, prompts,
  storage, memory eligibility, and adoption timing.
- The umbrella does not aggregate product memory or provide a cross-product retriever.
