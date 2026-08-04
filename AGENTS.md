# AI RAG Platform Memory

## Real-data-only testing — applies to every harness

All new tests of domain understanding, classification, routing, retrieval,
summarization, memory admission, or model quality must use captured real
product-owned data under `docs/testing/REAL_DATA_ONLY.md`. Never create
synthetic, paraphrased, blended, templated, or model-generated domain fixtures.
Existing constructed harnesses are frozen historical artifacts and cannot
authorize promotion.

Deterministic mocks remain allowed only for non-domain transport and
state-machine faults. They cannot establish model or domain accuracy.

## Scope

This root repository is the provider-neutral architecture and coordination layer for
all RAG products in the workspace. Work here only when a concern affects more than
one product or defines a contract that future products should follow.

Nested product repositories have their own `AGENTS.md` files. Their local instructions
and memories are authoritative for product-specific work.

## Remember here

- Architecture decisions and compatibility policy
- Transport and API contracts
- Generic retrieval, ingestion, memory-interface, and observability boundaries
- Cross-product regression fixtures and migration plans
- Which product revisions conform to shared contracts

## Do not remember here

- User facts or conversation memories
- Product personas, domain prompts, or domain knowledge
- Secrets, runtime data, vector stores, logs, or exports
- Forge security/quality findings, Nexus research conclusions, or Parallax market views
- Implementation details that apply to only one product

## Change discipline

- Treat product directories as independent repositories, not source folders in a monorepo.
- Do not copy an entire product implementation into the shared layer.
- Extract a shared library only after its public contract and versioning boundary are clear.
- A shared decision does not authorize overwriting product-specific behavior.
- Test and commit adoption separately in each affected product.

## Git closeout

When the user says `commit, push, merge, and sync`, follow
`docs/git/COMMIT_PUSH_MERGE_SYNC.md`.

Completed work should not be left uncommitted unless the user asks for that. Before
committing, show the short status, review the intended diff, run relevant verification,
and run `git diff --check`. Stage only task-owned paths. Never include unrelated product
worktree changes merely because the umbrella coordinates several repositories.
