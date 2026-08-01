# Semantic Routing Contract

This contract defines how an authenticated client selects one logical RAG or direct
model destination without inspecting prompts or inferring transport behavior.

The contract is intentionally separate from deployment. It names logical services
and accepted public model aliases, but it does not contain hostnames, ports,
credentials, process supervisors, or product memory.

## Versioned artifacts

- `semantic-routing.schema.json` defines the route-table shape.
- `semantic-routing.routes.json` is the initial version 1 route table.
- `../fixtures/semantic-routing/cases.v1.json` defines conformance cases.
- `../rag_platform/semantic_routing.py` is the provider-neutral resolver.
- `../tools/check_semantic_routes.py` validates the table and fixtures.

## Trusted route envelope

A routing request consists of these identity fields in addition to the ordinary
OpenAI-compatible request:

| Field | Required | Meaning |
| --- | --- | --- |
| `role_key` | No | Canonical application-assigned role for this invocation |
| `provider_name` | No | Canonical provider identity selected by the application |
| `model` | Yes | Public model alias already recorded for the invocation |

At least one of `role_key` or `provider_name` must resolve to a configured route.
The application must derive identity fields from trusted provider configuration;
user prompt text and arbitrary client-supplied headers are not routing authority.

An HTTP adapter may project the fields as `X-RAG-Role-Key`,
`X-RAG-Provider-Key`, and the OpenAI `model` property. It should also send a route
contract version and request correlation identifier. A gateway must authenticate
the calling application and remove routing headers before forwarding upstream.

## Identity normalization

Role keys and provider names are normalized before lookup:

1. Apply Unicode NFKC normalization.
2. Trim leading and trailing whitespace.
3. Apply Unicode-aware case folding.
4. Replace each run of whitespace, `_`, or `-` with one ASCII space.

Every normalized role alias must identify at most one route. The same rule applies
independently to provider-name aliases. A route table with duplicate normalized
aliases is invalid and must not be activated.

Model aliases are trimmed but otherwise remain case-sensitive. Model identity is
validated after route selection; it is not a substitute for trusted role/provider
identity.

## Resolution algorithm

1. If `role_key` matches a configured role alias, select that route.
2. Otherwise, if `provider_name` matches a configured provider alias, select that
   route.
3. Otherwise reject the request with `route_not_found`.
4. If both fields resolve and disagree, the role-selected route remains primary and
   the result must include an `identity_conflict` diagnostic.
5. Require `model` to appear in the selected route's `accepted_models`. Reject a
   mismatch with `model_mismatch`; do not silently rewrite it.

An unrecognized role is not a failure by itself. It falls through to provider-name
matching. This permits a generic role such as `builder` to remain application-owned
while a specific provider such as Hephaestus routes correctly.

There is no catch-all destination. Unknown identity and model mismatches fail closed
so that configuration drift cannot silently send a request to a non-RAG model.

## Logical targets

Each route selects a logical `service_id`, states whether retrieval is expected, and
declares the OpenAI-compatible public model aliases accepted by that service. A host
deployment maps `service_id` to a concrete upstream address and operational policy.

The deployment mapping must remain outside this contract because ports, credentials,
timeouts, and local network policy differ by host. Likewise, the selected product
continues to own its prompts, retrieval behavior, durable memory, and transport
adapter configuration.

## Diagnostics and audit

A successful resolution records at least:

- route-table version
- selected route and logical service
- whether role or provider name selected it
- normalized identity values
- diagnostic codes, including any identity conflict
- request correlation identifier

Logs must not contain authorization headers, API keys, prompt content, retrieved
documents, or product memory.
