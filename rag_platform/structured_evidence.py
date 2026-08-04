"""Standard-library validator for ``rag.structured-evidence`` version 1."""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any


STRUCTURED_EVIDENCE_CONTRACT = "rag.structured-evidence"
SCHEMA_VERSION = 1

FRESHNESS_STATUSES = frozenset({"fresh", "stale", "unknown"})
FRESHNESS_BASES = frozenset({"observed_at", "available_at"})
AVAILABILITY_BASES = frozenset(
    {"source_release", "source_vintage", "first_seen", "ingestion"}
)

_LOGICAL_ID = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_PAYLOAD_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_LIFECYCLE = {
    "mode": "ephemeral",
    "persist_evidence": False,
    "log_values": False,
}


class StructuredEvidenceError(ValueError):
    """Raised when structured evidence violates contract version 1."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{code} at {path}: {message}")
        self.code = code
        self.path = path


def validate_structured_evidence(evidence: dict[str, Any]) -> None:
    """Validate one point-in-time structured-evidence lane record."""

    _object(evidence, "evidence")
    _exact_keys(
        evidence,
        required={
            "contract",
            "schema_version",
            "product_id",
            "request_id",
            "lane_id",
            "evidence_id",
            "as_of",
            "source",
            "observation",
            "freshness",
            "provenance",
            "eligibility",
            "trust",
            "lifecycle",
        },
        optional={"$schema"},
        path="evidence",
    )
    if evidence["contract"] != STRUCTURED_EVIDENCE_CONTRACT:
        _fail("invalid_contract", "evidence.contract", "unsupported contract")
    if (
        isinstance(evidence["schema_version"], bool)
        or evidence["schema_version"] != SCHEMA_VERSION
    ):
        _fail(
            "invalid_version",
            "evidence.schema_version",
            "unsupported schema version",
        )
    if "$schema" in evidence:
        _text(evidence["$schema"], "evidence.$schema", maximum=4096)

    _logical_id(evidence["product_id"], "evidence.product_id")
    _opaque_id(evidence["request_id"], "evidence.request_id")
    _logical_id(evidence["lane_id"], "evidence.lane_id")
    _opaque_id(evidence["evidence_id"], "evidence.evidence_id")
    as_of = _timestamp(evidence["as_of"], "evidence.as_of")

    _validate_source(evidence["source"])
    temporal = _validate_observation(evidence["observation"])
    _validate_freshness(evidence["freshness"], as_of=as_of, temporal=temporal)
    _validate_provenance(
        evidence["provenance"], released_at=temporal["released_at"]
    )
    _validate_eligibility(
        evidence["eligibility"],
        as_of=as_of,
        available_at=temporal["available_at"],
    )

    if evidence["trust"] != "untrusted":
        _fail(
            "invalid_trust",
            "evidence.trust",
            "structured evidence cannot carry instruction authority",
        )
    _validate_lifecycle(evidence["lifecycle"])


def validate_structured_evidence_admission(
    request: dict[str, Any], evidence: dict[str, Any]
) -> None:
    """Validate that one structured record may enter a request's Context Packet."""

    # Imported here to keep the standalone record validator independently usable.
    from rag_platform.context_packet import validate_retrieval_request

    validate_retrieval_request(request)
    validate_structured_evidence(evidence)

    comparisons = (
        ("product_id", request["product_id"]),
        ("request_id", request["request_id"]),
        ("as_of", request["query"]["as_of"]),
    )
    for field, expected in comparisons:
        if evidence[field] != expected:
            _fail(
                "request_evidence_mismatch",
                f"evidence.{field}",
                "structured evidence does not match its retrieval request",
            )
    if not evidence["eligibility"]["no_lookahead"]:
        _fail(
            "ineligible_evidence",
            "evidence.eligibility.no_lookahead",
            "future-available structured evidence cannot enter model context",
        )


def _validate_source(value: Any) -> None:
    source = _object(value, "evidence.source")
    _exact_keys(
        source,
        required={"kind", "source_id", "series_id", "uri"},
        path="evidence.source",
    )
    _logical_id(source["kind"], "evidence.source.kind")
    _opaque_id(source["source_id"], "evidence.source.source_id")
    _opaque_id(source["series_id"], "evidence.source.series_id")
    if source["uri"] is not None:
        _text(source["uri"], "evidence.source.uri", maximum=4096)


def _validate_observation(value: Any) -> dict[str, datetime | None]:
    observation = _object(value, "evidence.observation")
    _exact_keys(
        observation,
        required={
            "observed_at",
            "released_at",
            "available_at",
            "vintage",
            "unit",
            "frequency",
            "value",
            "features",
        },
        path="evidence.observation",
    )
    observed_at = _timestamp(
        observation["observed_at"], "evidence.observation.observed_at"
    )
    released_at = None
    if observation["released_at"] is not None:
        released_at = _timestamp(
            observation["released_at"], "evidence.observation.released_at"
        )
    available_at = _timestamp(
        observation["available_at"], "evidence.observation.available_at"
    )
    if released_at is not None and available_at < released_at:
        _fail(
            "invalid_temporal_order",
            "evidence.observation.available_at",
            "availability cannot predate the exact vintage's release",
        )

    vintage = _object(observation["vintage"], "evidence.observation.vintage")
    _exact_keys(
        vintage,
        required={"vintage_id", "revision_id"},
        path="evidence.observation.vintage",
    )
    _opaque_id(
        vintage["vintage_id"], "evidence.observation.vintage.vintage_id"
    )
    if vintage["revision_id"] is not None:
        _opaque_id(
            vintage["revision_id"], "evidence.observation.vintage.revision_id"
        )

    _opaque_id(observation["unit"], "evidence.observation.unit", maximum=128)
    _logical_id(observation["frequency"], "evidence.observation.frequency")
    _scalar(observation["value"], "evidence.observation.value")
    features = _array(observation["features"], "evidence.observation.features")
    if len(features) > 64:
        _fail(
            "invalid_features",
            "evidence.observation.features",
            "at most 64 derived features may be emitted",
        )
    feature_ids: set[str] = set()
    for index, feature in enumerate(features):
        path = f"evidence.observation.features[{index}]"
        feature = _object(feature, path)
        _exact_keys(
            feature,
            required={"feature_id", "value", "unit"},
            path=path,
        )
        feature_id = _logical_id(feature["feature_id"], f"{path}.feature_id")
        if feature_id in feature_ids:
            _fail("invalid_features", f"{path}.feature_id", "duplicate feature")
        feature_ids.add(feature_id)
        _scalar(feature["value"], f"{path}.value")
        _opaque_id(feature["unit"], f"{path}.unit", maximum=128)

    if observation["value"] is None and not features:
        _fail(
            "empty_observation",
            "evidence.observation",
            "a selected record requires a value or derived feature",
        )
    return {
        "observed_at": observed_at,
        "released_at": released_at,
        "available_at": available_at,
    }


def _validate_freshness(
    value: Any,
    *,
    as_of: datetime,
    temporal: dict[str, datetime | None],
) -> None:
    freshness = _object(value, "evidence.freshness")
    _exact_keys(
        freshness,
        required={"status", "basis", "max_age_seconds"},
        path="evidence.freshness",
    )
    status = freshness["status"]
    if not isinstance(status, str) or status not in FRESHNESS_STATUSES:
        _fail("invalid_freshness", "evidence.freshness.status", "unsupported status")
    basis = freshness["basis"]
    if not isinstance(basis, str) or basis not in FRESHNESS_BASES:
        _fail("invalid_freshness", "evidence.freshness.basis", "unsupported basis")

    maximum = freshness["max_age_seconds"]
    if maximum is None:
        if status != "unknown":
            _fail(
                "invalid_freshness",
                "evidence.freshness.status",
                "a missing threshold requires unknown freshness",
            )
        return
    _integer(
        maximum,
        "evidence.freshness.max_age_seconds",
        minimum=0,
        code="invalid_freshness",
    )
    if status == "unknown":
        _fail(
            "invalid_freshness",
            "evidence.freshness.status",
            "a declared threshold requires fresh or stale status",
        )

    basis_time = temporal[basis]
    assert isinstance(basis_time, datetime)
    if basis_time > as_of:
        _fail(
            "invalid_freshness",
            "evidence.freshness.basis",
            "future-dated freshness requires an unknown status",
        )
    expected = "fresh" if (as_of - basis_time).total_seconds() <= maximum else "stale"
    if status != expected:
        _fail(
            "invalid_freshness",
            "evidence.freshness.status",
            "status does not match the declared basis and threshold",
        )


def _validate_provenance(value: Any, *, released_at: datetime | None) -> None:
    provenance = _object(value, "evidence.provenance")
    _exact_keys(
        provenance,
        required={"retrieved_at", "availability_basis", "payload_hash"},
        path="evidence.provenance",
    )
    _timestamp(provenance["retrieved_at"], "evidence.provenance.retrieved_at")
    basis = provenance["availability_basis"]
    if not isinstance(basis, str) or basis not in AVAILABILITY_BASES:
        _fail(
            "invalid_provenance",
            "evidence.provenance.availability_basis",
            "unsupported availability basis",
        )
    if basis == "source_release" and released_at is None:
        _fail(
            "invalid_provenance",
            "evidence.provenance.availability_basis",
            "source_release requires a known released_at",
        )
    payload_hash = provenance["payload_hash"]
    if not isinstance(payload_hash, str) or not _PAYLOAD_HASH.fullmatch(payload_hash):
        _fail(
            "invalid_provenance",
            "evidence.provenance.payload_hash",
            "must identify the product-owned source payload by SHA-256",
        )


def _validate_eligibility(
    value: Any, *, as_of: datetime, available_at: datetime
) -> None:
    eligibility = _object(value, "evidence.eligibility")
    _exact_keys(
        eligibility,
        required={"no_lookahead", "reason_codes"},
        path="evidence.eligibility",
    )
    if type(eligibility["no_lookahead"]) is not bool:
        _fail(
            "invalid_eligibility",
            "evidence.eligibility.no_lookahead",
            "must be a boolean",
        )
    reasons = eligibility["reason_codes"]
    if not isinstance(reasons, list):
        _fail(
            "invalid_eligibility",
            "evidence.eligibility.reason_codes",
            "must be an array",
        )
    expected = available_at <= as_of
    expected_reasons = [] if expected else ["available_after_as_of"]
    if eligibility["no_lookahead"] is not expected or reasons != expected_reasons:
        _fail(
            "invalid_eligibility",
            "evidence.eligibility",
            "eligibility must be derived from available_at <= as_of",
        )


def _validate_lifecycle(value: Any) -> None:
    lifecycle = _object(value, "evidence.lifecycle")
    _exact_keys(lifecycle, required=set(_LIFECYCLE), path="evidence.lifecycle")
    if lifecycle != _LIFECYCLE:
        _fail(
            "invalid_lifecycle",
            "evidence.lifecycle",
            "version 1 structured evidence is ephemeral and value logging is disabled",
        )


def _scalar(value: Any, path: str) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            _fail("invalid_value", path, "numeric values must be finite")
        return
    if isinstance(value, str) and value.strip() and len(value) <= 4096:
        return
    _fail("invalid_value", path, "must be a finite JSON scalar")


def _integer(value: Any, path: str, *, minimum: int, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(code, path, f"must be an integer >= {minimum}")
    return value


def _logical_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _LOGICAL_ID.fullmatch(value):
        _fail("invalid_identifier", path, "must be a lowercase logical identifier")
    return value


def _opaque_id(value: Any, path: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
    ):
        _fail("invalid_identifier", path, "must be a non-blank trimmed string")
    return value


def _text(value: Any, path: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _fail("invalid_text", path, "must be a non-blank bounded string")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("invalid_type", path, "must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("invalid_type", path, "must be an array")
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


def _timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str):
        _fail("invalid_timestamp", path, "must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("invalid_timestamp", path, "must be an RFC 3339 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("invalid_timestamp", path, "timestamp must include a UTC offset")
    return parsed


def _fail(code: str, path: str, message: str) -> None:
    raise StructuredEvidenceError(code, path, message)
