# Architecture Boundaries

The platform uses a shared-kernel boundary, not a shared-memory boundary. Common
behavior is centralized only when every product can consume it without importing
another product's identity or domain assumptions.

## Ownership matrix

| Concern | Umbrella architecture repo | Product repo |
| --- | --- | --- |
| OpenAI-compatible message and streaming rules | Contract and fixtures | Adapter integration and deployment |
| LLM/embedding provider interface | Stable interface and compatibility policy | Selected models, credentials, fallbacks |
| Document ingestion and retrieval | Generic interfaces and invariants | Domain loaders, weights, ranking, tuning |
| Memory | Generic isolation/portability contract | Schema extensions, records, retention, vector collection |
| Prompts and persona | No ownership | Full ownership |
| Domain knowledge and tools | No ownership | Full ownership |
| Observability and error shape | Common event contract | Product sinks, alerts, and operational policy |
| Releases | Compatible revision registry | Independent version and deployment |

## Extraction rule

A component is ready for a shared package when all of these are true:

1. At least two products need materially the same behavior.
2. The public inputs, outputs, errors, and configuration can be stated without a
   product name or persona.
3. Contract tests can validate the behavior outside a product runtime.
4. The package can be versioned so products can adopt it independently.

Identical files alone are evidence of duplication, not permission to centralize them.
For example, a formatter may look shared today but still encode product presentation
policy. Start with its contract and extract it only after the ownership boundary is
clear.

## Memory isolation

Each product must use its own storage path and vector collection. Shared code may
define a memory interface, serialization version, redaction rules, or migration
protocol, but it must never contain or automatically aggregate product memory records.

Cross-product memory movement must be explicit, scoped, and auditable. A future export
format may support deliberate transfer, but implicit reads across Nexus, Forge, and
Parallax are outside the platform boundary.

## Coordinated incident workflow

For a cross-product API problem:

1. Reproduce it as a provider-neutral payload and expected response/forwarded request.
2. Add the case under `contracts/` before coupling the fix to one product.
3. Identify affected products from `providers.json`.
4. Implement and test adoption independently in each affected repository.
5. Record incompatible or deferred adoption explicitly.
6. Update the umbrella pins only after the corresponding product commits exist.
