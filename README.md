# AI RAG Platform

This repository is the architecture and coordination layer for the RAG products in
this workspace. It exists so a provider-neutral problem can be solved once, recorded
once, and then adopted deliberately by each product repository.

The product repositories remain independently deployable and keep their own Git
history, prompts, domain knowledge, runtime data, and durable memories.

## Repositories

| Product | Local path | Responsibility |
| --- | --- | --- |
| Nexus | `nexus-rag/` | Strategic, cross-domain research |
| Forge | `forge-rag/` | Coding, repository, security, and quality workflows |
| Parallax | `parallax-rag/` | Markets, macroeconomics, and finance research |

They are registered in [`providers.json`](providers.json) and declared as Git
submodules in [`.gitmodules`](.gitmodules). Each umbrella commit pins compatible
product revisions; it does not merge their source histories.

## What belongs here

- Cross-product architecture and architectural decision records
- Provider/transport contracts, including OpenAI-compatible request behavior
- Reusable contract fixtures and conformance expectations
- Compatibility policy and coordinated migration plans
- Read-only workspace tooling for seeing all product repositories together

## What stays in each product

- Personas and system prompts
- Domain-specific retrieval, ranking, sources, tools, and knowledge bases
- Concrete memory schemas and all memory records
- Runtime data, vector stores, exports, logs, and secrets
- Product deployment settings and release history

See [`architecture/BOUNDARIES.md`](architecture/BOUNDARIES.md) for the full ownership
rules and [`architecture/decisions/0001-umbrella-and-product-repositories.md`](architecture/decisions/0001-umbrella-and-product-repositories.md)
for the first decision record.

Git publication follows [`docs/git/COMMIT_PUSH_MERGE_SYNC.md`](docs/git/COMMIT_PUSH_MERGE_SYNC.md),
adapted from the TOF-AI-APP workflow.

## Manage the workspace

The coordinator is intentionally read-only except when it runs a product's declared
test command.

```bash
python3 tools/rag_workspace.py list
python3 tools/rag_workspace.py check
python3 tools/rag_workspace.py status
python3 tools/rag_workspace.py test nexus forge
```

Product tests run in the caller's Python environment. Activate an environment with
the dependencies from the affected product's `requirements.txt` before using `test`.

The umbrella Git status ignores uncommitted content inside product submodules so an
unrelated product edit cannot contaminate an architecture commit. Use the coordinator's
`status` command to inspect every product worktree explicitly.

## Shared-change workflow

1. Describe the provider-neutral behavior as an architecture decision or contract.
2. Add a reusable fixture or conformance test here.
3. Implement or adapt the change in each affected product on its own branch.
4. Run each product's tests and release it independently.
5. Advance the umbrella repository's pinned product revisions after validation.

For example, the OpenAI-compatible system-message ordering failure is a shared
contract issue. The normalization invariant belongs here; Nexus, Forge, and any
other affected product still own their integrations and deployment decisions.
