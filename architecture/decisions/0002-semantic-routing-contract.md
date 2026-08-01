# ADR 0002: Trusted Semantic Routing Contract

- Status: Accepted
- Date: 2026-08-01

## Context

The platform needs one deterministic ingress decision for requests associated with
application roles and providers. Argus/Reviewer requests need Forge retrieval,
Finance Consultant requests need Parallax retrieval, and Hephaestus requests need a
direct non-RAG model route. The current OpenAI-compatible request body contains the
model alias but does not carry the application-selected provider role and name.

Putting identity logic into a model startup script would couple routing policy to one
host and one model process. Inferring identity from prompts would make user-controlled
content part of routing authority. Routing solely by model alias would also discard
the requested role-first precedence.

## Decision

Define a versioned semantic route table in the umbrella repository. Resolve trusted
role identity first, provider identity second, and use the selected route's model
aliases only for validation. Unknown identities and model mismatches fail closed.

The route table selects logical services and does not contain concrete endpoints or
credentials. A host-specific router deployment will map those services to addresses.
The router implementation may live in this repository once the contract is adopted,
while its systemd or container installation remains host-specific.

Applications must project role and provider identity from canonical internal state.
Routers must not parse prompts or trust unauthenticated caller headers. Product
repositories retain ownership of transport adapters, prompts, retrieval, memory,
runtime data, and deployment behavior.

## Consequences

- Role/provider precedence is consistent across current and future RAG products.
- Generic roles can fall through to a provider-specific match without being globally
  assigned to one product.
- Provider/model configuration drift becomes a visible rejection or diagnostic.
- The same contract can be tested without running a product or a model server.
- TOF requires a separate adapter change before a network router can receive trusted
  role and provider metadata.
- Concrete port mappings and authentication still require a deployment overlay.
