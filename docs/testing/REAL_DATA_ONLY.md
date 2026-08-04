# Real-data-only model and retrieval testing

## Shared policy

Effective 2026-08-04, new product tests that evaluate domain understanding,
classification, routing, retrieval, summarization, memory admission, or model
quality must use captured real product-owned data.

Synthetic, paraphrased, blended, templated, and model-generated domain examples
must not be used to calibrate a model, report accuracy or recall, compare a
prompt for adoption, or authorize production behavior.

## Required fixture contract

Each product owns its real-data corpus and keeps runtime stores isolated. A
portable test snapshot or manifest records:

- source and product provenance;
- stable source identity;
- publication, event, and capture times when available;
- deterministic selection criteria and cutoff;
- an immutable corpus/content hash; and
- independent audit labels kept outside model input.

Products preserve every per-item decision and audit every suppressive result.
Promotion requires a later, time-separated real sample using the intended
model, prompt, batch size, and fallback policy, followed by shadow-mode
validation. A discovered real failure becomes a permanent verbatim regression
record.

Existing constructed harnesses may remain as historical artifacts, but they
are frozen. They must not receive new cases or serve as release evidence.

## Allowed non-domain scaffolding

Deterministic mocks may still inject transport and state-machine faults such as
timeouts, malformed responses, duplicate identifiers, and missing files. These
tests establish software failure behavior only. They do not count as evidence
of domain accuracy or model safety.

## Origin

Parallax revision `12d73cb` demonstrated the boundary. A constructed 50-case
materiality set appeared safe, but a frozen unseen sample of 150 real retained
RSS records produced five confirmed unsafe rejections out of six and only 4%
downstream reduction. Single-item replay changed 16 of 25 non-pass decisions
and did not eliminate unsafe rejection.
