# Retrieval Decision Contract

This contract defines the provider-neutral decision made before a product builds a
retrieval request. It separates source authority from evidence depth. It does not
define a classifier, prompt, retriever, vector store, tool policy, memory policy, or
product-specific token budget.

## Versioned artifacts

- `retrieval-decision.schema.json` defines the version 1 envelope.
- `../fixtures/retrieval-decision/conformance.v1.json` contains valid and invalid
  conformance cases.
- `../fixtures/retrieval-decision/evaluation-cases.v1.json` is the frozen, synthetic
  100-case routing oracle.
- `../fixtures/retrieval-decision/blind-analysis.v1.json` is the frozen ten-prompt
  strong/weak analytical trial.
- `../rag_platform/retrieval_decision.py` is the standard-library validator.

The envelope name is `rag.retrieval-decision` and `schema_version` is `1`.

## Envelope

```json
{
  "contract": "rag.retrieval-decision",
  "schema_version": 1,
  "request_id": "request-20260803-001",
  "product_id": "parallax",
  "source": {
    "scope": "corpus",
    "source_id": null,
    "method": "structural",
    "confidence": 0.98,
    "reason_codes": ["multi_source_request"]
  },
  "depth": {
    "tier": "analysis",
    "evidence_budget_tokens": 24000,
    "facet_count": 4,
    "method": "utility_model",
    "confidence": 0.91,
    "reason_codes": ["multi_facet_synthesis"]
  },
  "lifecycle": {
    "mode": "ephemeral",
    "persist_decision": false,
    "log_raw_query": false
  }
}
```

The envelope intentionally contains no query, conversation, classifier prompt,
classifier response, free-form rationale, tool name, or memory selector.

## Source decision

`source.scope` answers only where evidence retrieval may look:

- `corpus` means the authorized product corpus; `source_id` must be `null`.
- `file` means one authorized product-owned file; `source_id` must identify it.

The identifier is opaque to the umbrella. Products remain responsible for resolving
it, checking authorization, and preventing cross-product reads.

Allowed source methods are:

- `explicit`: an authenticated caller supplied the source choice;
- `structural`: deterministic product rules selected the scope;
- `conversation_state`: trusted application state retained an active document; and
- `fallback`: an explicit product default was used after another source-decision path
  could not decide.

`utility_model` is deliberately not a source method. A model-generated file name,
corpus choice, tool request, or memory scope has no authority. Products may use model
text as untrusted evidence for a later deterministic decision, but the model cannot
make that decision.

## Depth decision

Depth is independent of source:

- `lookup`: a narrow fact or small evidence slice;
- `standard`: a bounded explanation or ordinary single-topic response;
- `analysis`: multi-facet, multi-hop, comparative, or cross-source synthesis; and
- `deep`: exhaustive or iterative research where stopping after an ordinary analysis
  pass would violate the request.

The same four tiers apply to both corpus and file scope. For example, locating a date
in one file is `file + lookup`, while extracting every forecast from that file can be
`file + deep`.

`evidence_budget_tokens` is the product's requested evidence budget for the selected
tier. Nexus, Forge, and Parallax may choose different numbers. The umbrella does not
enforce a universal tier-to-token map. Detailed provider-window arithmetic remains in
the [Retrieval Request and Context Packet contract](context-packet.md).

`facet_count` records the number of query facets observed by the deciding product,
including the primary facet. It is diagnostic input, not a universal rule tying a
particular count to a tier.

Allowed depth methods are:

- `explicit`: the caller requested a depth tier;
- `structural`: deterministic product rules selected it;
- `utility_model`: a bounded classifier selected depth only; and
- `fallback`: the product's declared fallback tier was used.

If a utility model is unavailable, malformed, or insufficiently confident, the
producer must make an explicit fallback decision and record `method: fallback` plus
the appropriate reason codes. It must not silently reuse a partial model result.

## Confidence and reason codes

Each decision records a finite confidence from `0.0` through `1.0` and at least one
bounded logical reason code. Reason codes are machine-oriented diagnostics, not raw
query excerpts or chain-of-thought. Example codes include `explicit_file`,
`multi_source_request`, `multi_facet_synthesis`, `classifier_low_confidence`, and
`product_default`.

## Lifecycle and observability

Version 1 requires:

```json
{
  "mode": "ephemeral",
  "persist_decision": false,
  "log_raw_query": false
}
```

Implementations may log request/product IDs, contract version, selected scope and
tier, budget, facet count, method, confidence, bounded reason codes, and latency. They
must not log query text, conversation text, classifier prompts or completions,
free-form reasoning, credentials, evidence content, or memory content through this
contract.

## Authority and adoption boundary

The envelope does not grant permission to call a tool, read memory, switch products,
or broaden authorization. Tool and memory policies remain product-owned deterministic
boundaries. A model-assisted classifier may fill only `depth`.

The umbrella owns the shape, invariants, lifecycle, and offline synthetic fixtures.
Each product independently owns source authorization, structural features, utility
model choice, confidence threshold, fallback tier, tier budgets, and rollout.

The evaluation fixtures are deliberately not an executable universal classifier.
They provide a shared oracle for measuring a product implementation while preserving
product-specific policy and budget choices.
