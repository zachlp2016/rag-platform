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
- Parallax: `e1d8201` (`test: measure real entry evidence compression`),
  followed by `262aea7` (`Make retained intel fail open and rank by recency`),
  then `7bdc464` (`Add full real intel provisioning master harness v2`),
  followed by `883e77d` (`Freeze full real corpus for provisioning harness v2`),
  following `1d29894` (`refactor: narrow Parallax intel sources`)

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

Parallax revision `1099c34` reran the same 50 cases after interpreting 5–10 as
pass, 3–4 as review, and 1–2 as reject. It reproduced the original scores and
retained all material fixtures, but this demonstrated consistency only on the
threshold-development set.

Parallax revision `12d73cb` then froze 150 previously unused retained-RSS
records from Financial Times and ZeroHedge. Eight-item batching required 19
local 2B calls and yielded 125 pass, 19 review, and 6 reject. Independent audit
found five of the six rejections material, including Big Tech credit risk,
cross-country unemployment, and Apple's $5tn valuation. Automatic rejection
would have reduced downstream work by only 4%. Single-item rechecks changed 16
of 25 non-pass decisions and recovered several obvious errors, but still
rejected material evidence.

Parallax revision `e1d8201` tested non-destructive entry compression on a
second non-overlapping 150-record real RSS corpus. Exact repeated-title removal
reduced bounded characters by 15.71% with no model call. The 2B exact-span
worker required 19 multi-minute calls, failed extraction validation on 120/150
records, and reduced only another 1.52% after fallback. Audit found material
omissions in 4 of the 13 outputs that actually reduced size. It is not a
promotion candidate.

The same test found that canonical URL is not a safe deduplication key: 498 RSS
observations contained 498 distinct identity-plus-content revisions even
though they occupied 462 canonical URLs. Thirty-two identities had changed
content. Only exact repeated content may be collapsed; later content at an
existing URL remains new evidence.

## Cross-product gate consequence

All future corpora used to evaluate this behavior follow the shared
[real-data-only testing policy](testing/REAL_DATA_ONLY.md). Earlier constructed
fixtures are historical only and cannot authorize promotion.

A utility-model score may rank, annotate, or queue evidence, but it must not
delete, suppress, or mark source evidence terminal unless a source-specific,
time-separated unseen test has zero unsafe rejections. The original raw archive
remains authoritative regardless of the derived decision.

Batch size is part of the tested inference contract. A score calibrated on
single items cannot authorize batched rejection, and a batched result cannot be
assumed stable when replayed alone. Products should separately test each source
class because a gate that provides useful reduction on a noisy social feed may
provide negligible benefit on a curated finance feed.

For curated or high-base-rate sources, prefer non-destructive utility labels
such as evidence type, observed versus forecast, opinion or promotion,
reliability cues, and candidate axes. Hard source admission for noisier streams
requires its own fail-open harness and promotion gate.

Token reduction should first use deterministic structure that is provably
redundant while preserving the original field separately, such as removing an
exact title prefix from a description when the title remains in the packet.
Generative entry compression must meet the same real-data, per-item audit, and
fail-open requirements as a suppressive gate. Small aggregate savings do not
justify added calls or omitted qualifiers.

## Retained-source admission and recency

Parallax revision `262aea7` makes source ownership—not a broad finance
classifier—the general-intel RAG admission boundary. NewsAPI, Google Trends,
Twitter/X, and configured RSS fail open into general retrieval. Finance
relevance remains auditable and continues to govern narrower product-specific
destinations such as market memory. A failed utility call cannot block retained
evidence. Sources assigned to Forge remain ineligible in Parallax even when
historical chunks still exist locally.

Every new intel observation has an effective timestamp: publication time when
available, otherwise collection time. Raw archives stay append-only. Products
may replace the active revision of one logical item while retaining its prior
raw observations for provenance.

Across different articles, recency is a ranking feature rather than a deletion
rule. Parallax applies a bounded `0.01` bonus with a seven-day half-life after
semantic fusion and same-item revision collapse. A newer article can break a
near tie but cannot displace substantially better semantic evidence. Context
packet manifests expose the configured weight, half-life, and per-item bonus.

This is currently a Parallax adoption, not yet a shared implementation library.
Other products may adopt the contract in separate commits after testing their
own source classes with captured real data.

## Full-corpus Parallax provisioning rehearsal

Parallax revision `7bdc464` repeated the fail-open/recency contract over the
complete frozen 2026-08-04 raw archive and then applied the validated plan to
the live Parallax library with a recoverable backup.

The 1,287 real observations contained 253 Parallax-owned RSS occurrences and
1,034 occurrences from sources assigned to Forge. The RSS set reduced to 87
content revisions and 86 latest logical items. The finance classifier labeled
82 of those 86 items negative, confirming at full-corpus scale that it cannot
serve as the general-library admission authority.

The application run added 72 missing RSS items, preserved three revisions newer
than the frozen archive, and archived five items beyond the normal 90-day RSS
window. The resulting live library had 1,069 eligible RSS chunks; all 1,215
intel chunks had an effective date, while 146 historical Forge-source chunks
remained excluded. A no-write replay made zero updates.

Three real semantic retrieval probes returned their direct recent evidence
first—Hormuz/Aramco supply, yen intervention, and HSBC profits/buybacks—while
retaining older relevant evidence below it. No 2B or 27B call was needed for
planning, provisioning, or validation.

This validates source ownership, latest-revision selection, effective dating,
idempotent provisioning, and bounded recency. It does not validate automatic
fluff rejection: source-owned fail-open evidence may still be low-value, and a
future quality worker requires a separate time-separated real-data gate.
