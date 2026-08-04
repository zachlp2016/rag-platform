# Product intel-source ownership

Each product fetches into its own raw/feed/vector paths. Products may use the
same public upstream, but they must not read or copy another product's runtime
archive or vector store.

## Scheduled ownership

| Upstream | Parallax | Forge | Treatment |
| --- | --- | --- | --- |
| NewsAPI | yes | no | Parallax general market/news intake |
| Google Trends | yes | no | Parallax demand/attention signal |
| Twitter/X | yes | yes | Product-specific configured timelines |
| RSS | yes | no | Parallax's existing separate RSS registry |
| Hacker News | no | yes | Forge engineering/security intake |
| Reddit | no | yes | Forge developer-focused communities |
| GitHub Trending | no | yes | Forge engineering intake |
| Dev.to | no | yes | Forge engineering intake |
| arXiv | no | yes | Forge technical research intake |
| Product Hunt | no | review only | Weekly promotional/low-trust queue; never automatic RAG |
| Mastodon | no | allowlist only | Curated security/developer accounts; no global trending |

Mastodon global trending is disabled. It may be reconsidered later as a Nexus
social-signal input, but it is not trusted knowledge and no Nexus runtime change
is part of this adoption.

Parallax's structured finance pipelines—FRED, Beige Book, market data,
Treasury, funding/liquidity, options, and quant—are outside this general-intel
registry and remain Parallax-owned.

Inactive collector implementations may remain temporarily for migration
compatibility. The product's explicit `active_intel_collectors()` registry is
the scheduling authority, except Forge's separately scheduled Product Hunt
review ledger. Historical observations are retained; changing the registry
does not delete or migrate runtime evidence.

## Adopted revisions

- Forge: `3a8df47` (`feat: quarantine low-trust ecosystem intake`), following
  `0a07a58` (`refactor: assign developer intel to Forge`)
- Parallax: `1d29894` (`refactor: narrow Parallax intel sources`)

## Verification findings

Parallax revision `08a2673` records a post-split, non-destructive source
rehearsal. Only RSS returned data: NewsAPI and Twitter/X were unconfigured, and
the current Google Trends adapter returned HTTP 404. Of 30 RSS observations,
16 were new revisions relative to the local-day archive. The local 2B quality
worker made 16 single-item calls but produced unsafe geopolitical/policy
rejections, so its results were retained as test evidence and not promoted.

Parallax revision `8cfea00` then isolated a two-field global-finance
materiality call from quality typing and lane routing. On a balanced ten-case
gold set it scored 8/10 with 5/5 material cases retained, zero false negatives,
and a 30% reduction in automatic stage-two work. This is a promising TDD result,
not production authorization; broader blind and stability tests remain required.

Parallax revision `84ed310` tested 1–10 self-confidence in an isolated harness.
It classified 9/10 correctly with zero false negatives, but the numeric value
tracked answer polarity/materiality more than confidence in correctness: correct
negative answers received scores as low as 1. Numeric self-confidence is not an
adopted contract; a separately named materiality-likelihood score may be tested.

Parallax revision `9acdc5f` tested that score-only contract on 50 balanced cases.
With 8–10 pass, 3–7 review, and 1–2 reject, it retained all 25 material cases,
rejected 24/25 irrelevant cases, produced no irrelevant automatic passes, and
achieved ROC AUC 0.9856. Only 6/50 advanced automatically while 20 remained in
review, so review-backlog policy and repeated stability tests block promotion.
