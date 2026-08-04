"""Standard-library validator for ``rag.retrieval-decision`` version 1."""

from __future__ import annotations

import math
import re
from typing import Any


RETRIEVAL_DECISION_CONTRACT = "rag.retrieval-decision"
SCHEMA_VERSION = 1

SOURCE_SCOPES = frozenset({"corpus", "file"})
SOURCE_METHODS = frozenset(
    {"explicit", "structural", "conversation_state", "fallback"}
)
DEPTH_TIERS = frozenset({"lookup", "standard", "analysis", "deep"})
DEPTH_METHODS = frozenset(
    {"explicit", "structural", "utility_model", "fallback"}
)

_LOGICAL_ID = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_LIFECYCLE = {
    "mode": "ephemeral",
    "persist_decision": False,
    "log_raw_query": False,
}


class RetrievalDecisionError(ValueError):
    """Raised when a retrieval decision violates contract version 1."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{code} at {path}: {message}")
        self.code = code
        self.path = path


def validate_retrieval_decision(decision: dict[str, Any]) -> None:
    """Validate one provider-neutral retrieval-decision envelope."""

    _object(decision, "decision")
    _exact_keys(
        decision,
        required={
            "contract",
            "schema_version",
            "request_id",
            "product_id",
            "source",
            "depth",
            "lifecycle",
        },
        optional={"$schema"},
        path="decision",
    )
    if decision["contract"] != RETRIEVAL_DECISION_CONTRACT:
        _fail("invalid_contract", "decision.contract", "unsupported contract")
    if decision["schema_version"] != SCHEMA_VERSION:
        _fail(
            "invalid_version",
            "decision.schema_version",
            "unsupported schema version",
        )
    if "$schema" in decision:
        _text(decision["$schema"], "decision.$schema")
    _opaque_id(decision["request_id"], "decision.request_id")
    _logical_id(decision["product_id"], "decision.product_id")
    _validate_source(decision["source"])
    _validate_depth(decision["depth"])
    _validate_lifecycle(decision["lifecycle"])


def _validate_source(value: Any) -> None:
    source = _object(value, "decision.source")
    _exact_keys(
        source,
        required={"scope", "source_id", "method", "confidence", "reason_codes"},
        path="decision.source",
    )
    scope = source["scope"]
    if not isinstance(scope, str) or scope not in SOURCE_SCOPES:
        _fail("invalid_source", "decision.source.scope", "unsupported source scope")

    source_id = source["source_id"]
    if scope == "corpus":
        if source_id is not None:
            _fail(
                "invalid_source",
                "decision.source.source_id",
                "corpus scope requires a null source_id",
            )
    else:
        _opaque_id(source_id, "decision.source.source_id")

    method = source["method"]
    if method == "utility_model":
        _fail(
            "source_authority_violation",
            "decision.source.method",
            "a utility model may choose depth only",
        )
    if not isinstance(method, str) or method not in SOURCE_METHODS:
        _fail("invalid_source", "decision.source.method", "unsupported source method")
    _confidence(source["confidence"], "decision.source.confidence")
    _reason_codes(source["reason_codes"], "decision.source.reason_codes")


def _validate_depth(value: Any) -> None:
    depth = _object(value, "decision.depth")
    _exact_keys(
        depth,
        required={
            "tier",
            "evidence_budget_tokens",
            "facet_count",
            "method",
            "confidence",
            "reason_codes",
        },
        path="decision.depth",
    )
    if not isinstance(depth["tier"], str) or depth["tier"] not in DEPTH_TIERS:
        _fail("invalid_depth", "decision.depth.tier", "unsupported depth tier")
    _integer(
        depth["evidence_budget_tokens"],
        "decision.depth.evidence_budget_tokens",
        minimum=1,
    )
    _integer(depth["facet_count"], "decision.depth.facet_count", minimum=1)
    if not isinstance(depth["method"], str) or depth["method"] not in DEPTH_METHODS:
        _fail("invalid_depth", "decision.depth.method", "unsupported depth method")
    _confidence(depth["confidence"], "decision.depth.confidence")
    _reason_codes(depth["reason_codes"], "decision.depth.reason_codes")


def _validate_lifecycle(value: Any) -> None:
    lifecycle = _object(value, "decision.lifecycle")
    _exact_keys(lifecycle, required=set(_LIFECYCLE), path="decision.lifecycle")
    if lifecycle != _LIFECYCLE:
        _fail(
            "invalid_lifecycle",
            "decision.lifecycle",
            "version 1 decisions must be ephemeral and disable raw-query logging",
        )


def _reason_codes(value: Any, path: str) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        _fail("invalid_reason_codes", path, "must contain between 1 and 32 codes")
    seen: set[str] = set()
    for index, code in enumerate(value):
        code_path = f"{path}[{index}]"
        _logical_id(code, code_path)
        if code in seen:
            _fail("invalid_reason_codes", code_path, "duplicate reason code")
        seen.add(code)


def _confidence(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_confidence", path, "must be a finite number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        _fail("invalid_confidence", path, "must be between 0 and 1")


def _integer(value: Any, path: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_integer", path, f"must be an integer >= {minimum}")
    return value


def _logical_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _LOGICAL_ID.fullmatch(value):
        _fail("invalid_identifier", path, "must be a lowercase logical identifier")
    return value


def _opaque_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("invalid_identifier", path, "must be a non-blank trimmed string")
    if len(value) > 512:
        _fail("invalid_identifier", path, "must not exceed 512 characters")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_text", path, "must be a non-blank string")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("invalid_type", path, "must be an object")
    return value


def _exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    path: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required - set(value)
    unknown = set(value) - required - optional
    if missing:
        _fail("missing_field", path, f"missing fields: {sorted(missing)}")
    if unknown:
        _fail("unknown_field", path, f"unknown fields: {sorted(unknown)}")


def _fail(code: str, path: str, message: str) -> None:
    raise RetrievalDecisionError(code, path, message)
