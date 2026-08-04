# SPX Options Analytics Implementation Checklist

- Status: proposed
- Priority: high
- Primary product: Parallax / FinanceConsultant
- Planning boundary: this file coordinates the work; product code and market data
  remain product-owned.

## Outcome

Build a deterministic SPX options analytics engine that Parallax can call. The model
explains and synthesizes calculated evidence; it must not invent option levels or
perform the primary quantitative calculations itself.

The intended division of responsibility is:

- RAG: curated options knowledge, interpretation, limitations, and explanation.
- Options engine: forwards, IV, Greeks, expected moves, exposure maps, volatility
  surfaces, regimes, and candidate zones.
- Time-series store: raw chain snapshots, source vintages, derived measurements, and
  backtest results.
- Operator/FinanceConsultant: combines options measurements with ES/Bookmap market
  structure and turns a bounded evidence packet into a probabilistic response.

Core design principle:

> ES futures order-book data supplies the path. SPX options supply the pressure zones.

## Non-negotiable rules

- [ ] Keep calculations deterministic and testable outside the LLM.
- [ ] Treat SPX, SPXW, SPY, and ES as distinct instruments.
- [ ] Model SPX expiration, settlement, multiplier, and time-to-expiration correctly.
- [ ] Attach an exact `as_of`, source timestamp, collection timestamp, and latency to
      every live or delayed result.
- [ ] Label delayed data prominently and prevent it from masquerading as real time.
- [ ] Call OI-derived exposure **Modeled GEX**, never observed dealer positioning.
- [ ] Preserve the GEX sign method and confidence with every calculation.
- [ ] Treat OCC open interest as previous-clearing-state input, not intraday flow.
- [ ] State uncertainty when a trade may be part of a complex or multi-leg order.
- [ ] Return target zones with invalidation, confidence, and limitations—not exact
      deterministic predictions.
- [ ] Store raw data and calculations in structured storage, not as RAG chunks.
- [ ] Render only request-scoped, bounded, untrusted summaries into model context.
- [ ] Record source licensing and redistribution permissions with every dataset.

## Phase 0 — Architecture and source decisions

- [ ] Decide whether the engine will be a new independent repository/service such as
      `tof-options-engine` or a Parallax-owned service boundary.
- [ ] Define the service API and versioned calculation contracts before wiring Rails,
      Solid Queue, or Parallax callers.
- [ ] Select the initial structured store:
  - [ ] Partitioned Postgres tables; or
  - [ ] Partitioned Parquet with a small metadata/catalog database.
- [ ] Define retention for raw quotes, normalized chains, derived surfaces, exposure
      maps, and backtest packets.
- [ ] Define one canonical market clock and expiration calendar, including Eastern and
      Central time handling, holidays, early closes, AM settlement, and PM settlement.
- [ ] Document source priority and failover behavior.
- [ ] Reuse the umbrella point-in-time vocabulary (`observed_at`, `available_at`,
      `as_of`, vintage, freshness, provenance) for request admission.
- [ ] Define an options analytics packet contract only when its public boundary and
      versioning are clear.

## Phase 1 — Free delayed morning-map collector

### Cboe delayed SPX chain

- [ ] Confirm current Cboe terms permit the intended internal prototype use.
- [ ] Treat the undocumented `_SPX` JSON endpoint as a replaceable prototype adapter,
      not a stable production contract.
- [ ] Collect the delayed SPX/SPXW chain every five minutes.
- [ ] Parse option identity into root, expiration, call/put right, and strike.
- [ ] Preserve raw source payload hashes and adapter/version metadata.
- [ ] Capture at minimum:
  - [ ] Bid, ask, last, bid size, ask size, and volume when supplied.
  - [ ] Open interest when supplied.
  - [ ] Underlying/current-price field and source timestamp.
  - [ ] `collected_at`, `is_delayed`, and measured/declared latency.
- [ ] Validate schema drift, empty chains, malformed symbols, duplicate contracts,
      crossed markets, and implausible quotes without silently accepting them.
- [ ] Persist failed fetch status independently from the last valid snapshot.

### OCC overnight open interest

- [ ] Import OCC open interest and volume nightly.
- [ ] Preserve the clearing/business date separately from ingestion time.
- [ ] Reconcile expiration, strike, right, and contract identity with the Cboe chain.
- [ ] Report unmatched or inactive series instead of dropping them silently.
- [ ] Calculate day-over-day OI changes only after both clearing snapshots are valid.

### Additional free validation sources

- [ ] Import Cboe 3:00 p.m. Central indicative SPX/SPXW marking-price files.
- [ ] Use marking prices to validate end-of-day IV and Greek calculations.
- [ ] Ingest public Cboe historical volume only for volume/regime research; do not
      represent it as a historical NBBO chain.

## Phase 2 — Normalization and quantitative engine

### Instrument and curve inputs

- [ ] Normalize SPX and SPXW contract specifications and the $100 multiplier.
- [ ] Calculate precise time to expiration using the correct settlement timestamp.
- [ ] Select and version the risk-free curve and dividend/carry assumptions.
- [ ] Reject calculations when required inputs are stale, missing, or internally
      inconsistent.

### Synthetic forward

- [ ] Estimate an expiration-specific synthetic forward using liquid paired strikes:

  ```text
  Forward ≈ Strike + exp(rT) × (Call midpoint − Put midpoint)
  ```

- [ ] Use multiple nearby strikes and robust aggregation rather than trusting one
      potentially noisy pair.
- [ ] Store the selected strikes, quote timestamps, method, and disagreement measure.

### Implied volatility and Greeks

- [ ] Start with a tested vectorized Black-Scholes implementation or `py_vollib`.
- [ ] Add QuantLib only when curve construction, calibration, or richer surface models
      require it.
- [ ] Compute IV, delta, gamma, vega, theta, vanna, and charm.
- [ ] Add unit tests against known analytic values and Cboe marking-price snapshots.
- [ ] Make solver failure, arbitrage-bound violations, and wide-spread uncertainty
      explicit.

### Expected move

- [ ] Calculate an ATM-straddle range around the synthetic forward.
- [ ] Calculate a volatility range:

  ```text
  Forward × IV × sqrt(time)
  ```

- [ ] Preserve expiration, calculation time, underlying/forward input, and method.
- [ ] Return ranges and confidence, never a promise that price remains inside them.

### Modeled gamma exposure

- [ ] Calculate dollar gamma for a 1% move:

  ```text
  GEX = gamma × open_interest × multiplier × spot² × 0.01
  ```

- [ ] Aggregate by strike, expiration, call/put, 0DTE versus later expirations, and
      distance from the synthetic forward.
- [ ] For the first version, record:

  ```text
  sign_method = "calls_positive_puts_negative_heuristic"
  sign_confidence = "low"
  ```

- [ ] Never silently change sign methodology between runs or data sources.
- [ ] Produce:
  - [ ] Largest absolute-gamma strikes.
  - [ ] Gamma-weighted center of mass.
  - [ ] Gamma above and below spot/forward.
  - [ ] Estimated zero-gamma transition.
  - [ ] Change in the gamma map since the open.
  - [ ] 0DTE-only and all-expiration maps.
- [ ] Describe zero gamma as a scenario boundary, not a magical price line.

### Volatility surface

- [ ] Compute ATM IV by expiration.
- [ ] Compute 25-delta put and call IV.
- [ ] Compute put skew and term structure.
- [ ] Track intraday skew changes.
- [ ] Compare 0DTE IV with 1DTE and 7DTE.
- [ ] Compare implied volatility with realized intraday volatility.
- [ ] Add a surface-instability/disagreement measure that reduces target confidence.

## Phase 3 — ES and Bookmap market-structure integration

- [ ] Ingest or expose ES liquidity walls, pulling/stacking, absorption, and iceberg
      observations through a versioned interface.
- [ ] Add VWAP, opening range, overnight high/low, prior close, volume profile, HVNs,
      and LVNs.
- [ ] Calculate and version the ES/SPX basis used to translate levels.
- [ ] Preserve the source and timestamp of each translated level.
- [ ] Prevent a stale options snapshot from overriding materially fresher ES evidence.
- [ ] Test basis behavior around the cash open, major macro releases, and futures-roll
      periods.

## Phase 4 — Target-zone composer

- [ ] Generate candidate levels deterministically before the model sees them.
- [ ] Candidate sources should include:
  - [ ] Major 0DTE gamma strikes.
  - [ ] Major total-OI gamma strikes.
  - [ ] Estimated zero-gamma transition.
  - [ ] ATM-straddle boundaries.
  - [ ] One-standard-deviation boundaries.
  - [ ] Large live-flow strikes when real-time data becomes available.
  - [ ] ES liquidity walls translated to SPX equivalents.
  - [ ] Overnight high/low, prior close, VWAP, opening range, HVNs, and LVNs.
- [ ] Implement a versioned score resembling:

  ```text
  target_score =
      gamma_concentration
    + option_volume_concentration
    + expected_move_proximity
    + ES_orderbook_liquidity
    + volume_profile_confluence
    + VWAP_or_opening_range_confluence
    + historical_reaction_rate
    - data_staleness_penalty
    - model_disagreement_penalty
  ```

- [ ] Normalize every component and persist the score breakdown.
- [ ] Classify at least:
  - [ ] Positive-gamma / mean-reversion regime.
  - [ ] Negative-gamma / expansion regime.
  - [ ] 0DTE pinning regime.
- [ ] Every proposed zone must include:
  - [ ] Zone bounds rather than one exact price.
  - [ ] Direction/role (magnet, resistance, support, expansion target, boundary).
  - [ ] Invalidation conditions.
  - [ ] Confidence and score breakdown.
  - [ ] Exact `as_of` and data latency.
  - [ ] Source freshness and limitations.

## Phase 5 — Parallax and orchestration integration

- [ ] Expose engine operations as bounded, idempotent jobs or tools:

  ```text
  options.chain.snapshot
  options.chain.normalize
  options.forward.compute
  options.greeks.compute
  options.surface.compute
  options.exposure.compute
  options.flow.classify
  market.es_microstructure.snapshot
  intraday.targets.compose
  review.options_packet
  answer.options.synthesize
  ```

- [ ] Keep Rails/Solid Queue as orchestrator if that remains the application boundary;
      keep quantitative ownership in the Python engine.
- [ ] Give Parallax a request-scoped tool interface rather than automatically injecting
      the full options store into every conversation.
- [ ] Send only the bounded analytics packet to the 27B synthesis model.
- [ ] Keep packet values out of ordinary logs; log redacted counts, status, age, source,
      method versions, and warnings.
- [ ] Fail closed when the packet is missing an exact timestamp, latency, provenance,
      or declared data mode (`delayed` or `real_time`).

## Phase 6 — Curated options knowledge library

- [ ] Create one authoritative document per concept using this template:

  ```text
  Concept
  Definition
  Formula
  Required inputs
  Assumptions
  Valid horizons
  Interpretation
  Common misuse
  Failure modes
  Worked example
  Related tool/job
  ```

- [ ] Cover this initial curriculum:
  1. SPX versus SPXW, AM versus PM settlement, and expiration mechanics.
  2. Calls, puts, parity, and synthetic forwards.
  3. Delta, gamma, vega, theta, vanna, and charm.
  4. Implied volatility, skew, and term structure.
  5. Open interest versus volume.
  6. Modeled GEX and sign uncertainty.
  7. 0DTE behavior.
  8. Simple versus complex orders.
  9. Expected-move calculations.
  10. ES/SPX basis and Bookmap liquidity.
  11. Data latency and licensing.
  12. Probabilistic target language.
- [ ] Add hard response rules:
  - [ ] Never call open interest inherently bullish or bearish.
  - [ ] Never describe modeled GEX as observed dealer positioning.
  - [ ] Never provide an intraday target without an as-of timestamp.
  - [ ] Always identify delayed versus real-time chain data.
  - [ ] Always provide a zone, invalidation, and confidence.
  - [ ] Always distinguish SPX, SPXW, SPY, and ES.
  - [ ] Never infer an outright directional trade from a potentially complex print
        without stating the uncertainty.

## Phase 7 — Validation and backtesting

- [ ] Build immutable fixtures for contract parsing, forward calculation, IV inversion,
      Greeks, expected move, GEX, and surface calculations.
- [ ] Add point-in-time tests that prevent later OI, revisions, quotes, and marks from
      entering an earlier backtest.
- [ ] Compare calculated close IV against Cboe indicative marking prices.
- [ ] Backtest reaction rates around generated zones by regime and time of day.
- [ ] Measure touch, rejection, acceptance, overshoot, and invalidation rates.
- [ ] Separate calibration data from evaluation data.
- [ ] Evaluate confidence calibration rather than only directional accuracy.
- [ ] Record stale-data failures and source outages as first-class outcomes.
- [ ] Add regression tests ensuring the LLM cannot alter calculated levels or omit
      required limitations.
- [ ] Define go/no-go thresholds before replacing any collector with paid real-time
      data.

## Phase 8 — Paid real-time upgrade, after delayed v1 proves useful

- [ ] Evaluate licensed consolidated OPRA/Options Lite providers.
- [ ] Evaluate direct Cboe C1 BBO, simple-book depth, trade, complex-order, and auction
      feeds.
- [ ] Evaluate Cboe Open-Close data for participant and opening/closing inference.
- [ ] Add trade-side classification (ask, bid, inside spread, complex/possibly complex).
- [ ] Calculate session live-flow gamma separately from overnight OI exposure.
- [ ] Upgrade sign metadata only when participant/trade-side evidence supports it:

  ```text
  sign_method = "participant_and_trade_side_inference"
  sign_confidence = "medium"
  ```

- [ ] Preserve the delayed collector as a degraded-mode source and validation path.
- [ ] Confirm vendor, display, derived-data, and redistribution licensing before any
      external user receives live or derived output.

## Licensing metadata

- [ ] Store these fields with each source and derived artifact:

  ```text
  source_license
  internal_use_allowed
  display_allowed
  derived_distribution_allowed
  raw_redistribution_allowed
  ```

- [ ] Add a policy gate that prevents prohibited raw or derived redistribution.
- [ ] Keep licensed raw feeds product-local; the umbrella may define contracts but must
      not become a shared licensed-data store.

## Delayed v1 acceptance criteria

- [ ] Five-minute Cboe delayed-chain collection is stable and observable.
- [ ] OCC nightly OI reconciliation completes with explicit mismatch reporting.
- [ ] Synthetic forward, IV, Greeks, expected move, Modeled GEX, gamma zones, and basic
      surface measures pass deterministic fixtures.
- [ ] Every result is point-in-time safe and carries source, vintage, latency,
      freshness, and calculation-version provenance.
- [ ] ES/Bookmap confluence can be included without confusing ES and SPX price levels.
- [ ] The target composer returns bounded zones, invalidations, confidence, and
      limitations.
- [ ] Backtests show whether the zones add useful information relative to simple VWAP,
      opening-range, and expected-move baselines.
- [ ] Parallax explicitly says the data is delayed and labels exposure as modeled.
- [ ] No LLM-generated number can replace a deterministic engine output.
- [ ] Source outages degrade safely without presenting stale data as current.

## Explicitly deferred from delayed v1

- Live 0DTE trade-flow inference.
- Observed participant/dealer positioning.
- Reliable complex-order decomposition.
- Tick-level NBBO or depth reconstruction.
- External redistribution of live or derived licensed data.
- Claims that an option level predicts an exact SPX close.

## Reference analytics packet

```json
{
  "as_of": "2026-08-03T14:35:00-04:00",
  "data_mode": "delayed",
  "data_latency_seconds": 900,
  "underlying": {
    "spx": 7600.25,
    "es": 7618.50,
    "synthetic_forward": 7604.80
  },
  "regime": {
    "classification": "positive_gamma_near_pin",
    "confidence": 0.71
  },
  "expected_move": {
    "lower": 7578.0,
    "upper": 7631.0,
    "expiration": "2026-08-03"
  },
  "levels": [
    {
      "lower": 7598.0,
      "upper": 7602.0,
      "type": "zero_dte_gamma_magnet",
      "strength": 0.91
    }
  ],
  "invalidation": [
    "Sustained ES acceptance above the basis-adjusted boundary",
    "The 0DTE gamma map changes regime",
    "Book liquidity pulls from the target"
  ],
  "limitations": [
    "The chain is delayed",
    "Open interest is from the prior clearing day",
    "Exposure sign is inferred",
    "Complex-order classification is unavailable"
  ]
}
```

## Source references

- [Cboe SPX specifications](https://www.cboe.com/tradable_products/sp_500/spx_options/specifications/)
- [Cboe delayed SPX quotes](https://www.cboe.com/delayed_quotes/spx/quote_table/)
- [OCC daily volume and open interest](https://www.theocc.com/market-data/market-data-reports/volume-and-open-interest/daily-volume)
- [Cboe historical options data](https://www.cboe.com/us/options/market_statistics/historical_data/)
- [Cboe proprietary index marking prices](https://www.cboe.com/us/options/market_statistics/proprietary_index_marking_prices/)
- [QuantLib volatility documentation](https://quantlib-python-docs.readthedocs.io/en/latest/termstructures/volatility.html)
- [Cboe Options Lite](https://www.cboe.com/insights/posts/cboe-options-lite-access-real-time-options-data-with-less-cost-and-complexity/)
- [Cboe Open-Close data](https://datashop.cboe.com/cboe-options-open-close-volume-summary)
- [OPRA](https://www.opraplan.com/)
