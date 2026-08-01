# ADR 0001: Umbrella Architecture and Independent Product Repositories

- Status: Accepted
- Date: 2026-08-01

## Context

Nexus, Forge, and Parallax share substantial RAG and OpenAI-compatible API behavior,
but each serves a different domain and maintains different prompts, tools, knowledge,
data, and durable memory. Shared API failures have required similar fixes in multiple
repositories. Combining all source and memory into a single product would make those
domain boundaries harder to preserve.

## Decision

Use this repository as an umbrella architecture repository. Register the product
repositories as Git submodules so the umbrella can identify a tested, compatible set
of revisions while every product keeps independent history and releases.

The umbrella owns shared contracts, architecture decisions, conformance fixtures, and
workspace coordination. It does not own product personas, domain behavior, runtime
data, or memory records.

Begin with contract-first coordination. Introduce a versioned shared Python package
only when a component satisfies the extraction rule in `architecture/BOUNDARIES.md`.

## Consequences

- Cross-product failures gain one canonical contract and regression fixture.
- Each product can adopt a fix on its own schedule and keep its own memory context.
- Submodule pointers make compatible revisions explicit.
- Some temporary duplication remains until an interface is stable enough to extract.
- Coordinated changes require validation in both the umbrella and affected products.
