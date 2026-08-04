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

The versioned [`Semantic Routing Contract`](contracts/semantic-routing.md) defines
role-first, provider-second selection of Forge, Parallax, and direct model services.

The versioned [`Retrieval Decision Contract`](contracts/retrieval-decision.md)
separates authorized source selection from retrieval depth. Its
[`ADR 0004`](architecture/decisions/0004-retrieval-decision-contract.md),
[`JSON Schema`](contracts/retrieval-decision.schema.json), and frozen
[`evaluation fixtures`](fixtures/retrieval-decision/) let products test their own
classifiers without creating an umbrella classifier or granting model outputs source,
tool, or memory authority.

The versioned [`Retrieval Request and Context Packet Contract`](contracts/context-packet.md)
defines provider-neutral token accounting, evidence provenance, degradation reporting,
and the untrusted-evidence boundary. Its staged product adoption plan is recorded in
[`Context Packet Rollout`](docs/retrieval/CONTEXT_PACKET_ROLLOUT.md).

Validate the umbrella route table and contract fixtures with:

```bash
python3 tools/check_semantic_routes.py
python3 -m unittest discover -s tests -v
```

## Semantic router

The router exposes one authenticated OpenAI-compatible ingress on port `8000`.
It resolves only trusted role/provider metadata, validates the public model alias,
and streams the packet to a host-local logical service without inspecting prompts
or product memory.

```bash
python3 -m venv .venv-router
.venv-router/bin/pip install -r router/requirements.txt
cp router/deployment.example.json router/deployment.local.json
cp router/router.env.example ~/.config/rag-platform/router.env
.venv-router/bin/python -m uvicorn router.asgi:app --host 127.0.0.1 --port 8000
```

Use the systemd template in
[`deploy/systemd/rag-semantic-router.service`](deploy/systemd/rag-semantic-router.service)
when Docker clients need the host gateway. The committed deployment file is an
example only; the active service map and router secret remain host-local.

The scheduled [`Default Branch Contract`](.github/workflows/default-branch-contract.yml)
checks that GitHub still identifies `main` as the default branch. GitHub does not change
the default during ordinary pushes; changing it requires an explicit repository-settings
action by an administrator.

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
