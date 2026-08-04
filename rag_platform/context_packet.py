"""Provider-neutral validator for Retrieval Request / Context Packet contract v1."""

from __future__ import annotations

from datetime import datetime
import hashlib
import math
import re
from typing import Any


RETRIEVAL_REQUEST_CONTRACT = "rag.retrieval-request"
CONTEXT_PACKET_CONTRACT = "rag.context-packet"
SCHEMA_VERSION = 1

_LOGICAL_ID = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_CONTENT_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_CITATION_ID = re.compile(r"^E(?=[0-9]{3,}$)0*[1-9][0-9]*$")

_LIFECYCLE = {
    "mode": "ephemeral",
    "persist_packet": False,
    "log_evidence_content": False,
}

_BUDGET_KEYS = {
    "context_window_tokens",
    "reserved_output_tokens",
    "reserved_reasoning_tokens",
    "safety_margin_tokens",
    "instruction_tokens",
    "conversation_tokens",
    "tool_tokens",
    "requested_evidence_tokens",
    "max_evidence_items",
}

_EFFECTIVE_CONTEXT_KEYS = {
    "context_window_tokens",
    "reserved_output_tokens",
    "reserved_reasoning_tokens",
    "safety_margin_tokens",
    "max_input_tokens",
    "non_evidence_input_tokens",
    "requested_evidence_tokens",
    "available_evidence_tokens",
    "selected_evidence_tokens",
    "max_evidence_items",
    "selected_evidence_items",
}

_INTENTS = {"lookup", "synthesis", "analysis", "deep_research", "file_focused"}
_PLAN_STRATEGIES = {"single_query", "decomposed", "iterative"}
_PACKET_STATUSES = {"complete", "degraded", "empty"}
_LANE_STATUSES = {"complete", "empty", "failed", "skipped"}


class ContextContractError(ValueError):
    """Raised when a retrieval request or context packet violates contract v1."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{code} at {path}: {message}")
        self.code = code
        self.path = path


def compute_effective_context(
    budget: dict[str, Any],
    *,
    selected_evidence_tokens: int = 0,
    selected_evidence_items: int = 0,
) -> dict[str, int]:
    """Calculate the provider-neutral evidence capacity for one request."""

    values = _validate_budget(budget, "budget")
    _integer(
        selected_evidence_tokens,
        "selected_evidence_tokens",
        minimum=0,
        code="invalid_effective_context",
    )
    _integer(
        selected_evidence_items,
        "selected_evidence_items",
        minimum=0,
        code="invalid_effective_context",
    )

    max_input = (
        values["context_window_tokens"]
        - values["reserved_output_tokens"]
        - values["reserved_reasoning_tokens"]
        - values["safety_margin_tokens"]
    )
    non_evidence = (
        values["instruction_tokens"]
        + values["conversation_tokens"]
        + values["tool_tokens"]
    )
    remaining = max_input - non_evidence
    if max_input <= 0 or remaining <= 0:
        _fail(
            "invalid_budget",
            "budget",
            "fixed reservations must leave positive evidence capacity",
        )

    available = min(values["requested_evidence_tokens"], remaining)
    if selected_evidence_tokens > available:
        _fail(
            "budget_exceeded",
            "selected_evidence_tokens",
            "selected evidence exceeds effective token capacity",
        )
    if selected_evidence_items > values["max_evidence_items"]:
        _fail(
            "budget_exceeded",
            "selected_evidence_items",
            "selected evidence exceeds the item cap",
        )

    return {
        "context_window_tokens": values["context_window_tokens"],
        "reserved_output_tokens": values["reserved_output_tokens"],
        "reserved_reasoning_tokens": values["reserved_reasoning_tokens"],
        "safety_margin_tokens": values["safety_margin_tokens"],
        "max_input_tokens": max_input,
        "non_evidence_input_tokens": non_evidence,
        "requested_evidence_tokens": values["requested_evidence_tokens"],
        "available_evidence_tokens": available,
        "selected_evidence_tokens": selected_evidence_tokens,
        "max_evidence_items": values["max_evidence_items"],
        "selected_evidence_items": selected_evidence_items,
    }


def validate_retrieval_request(request: dict[str, Any]) -> None:
    """Validate one ``rag.retrieval-request`` version 1 envelope."""

    _object(request, "request")
    _exact_keys(
        request,
        required={
            "contract",
            "schema_version",
            "product_id",
            "request_id",
            "created_at",
            "query",
            "scopes",
            "budget",
            "token_accounting",
            "lifecycle",
        },
        optional={"$schema"},
        path="request",
    )
    _contract_header(request, RETRIEVAL_REQUEST_CONTRACT, "request")
    if "$schema" in request:
        _text(request["$schema"], "request.$schema")
    _logical_id(request["product_id"], "request.product_id")
    _opaque_id(request["request_id"], "request.request_id")
    _timestamp(request["created_at"], "request.created_at")
    _validate_lifecycle(request["lifecycle"], "request.lifecycle")

    query = _object(request["query"], "request.query")
    _exact_keys(
        query,
        required={"text", "intent", "as_of", "conversation"},
        path="request.query",
    )
    _text(query["text"], "request.query.text")
    if not isinstance(query["intent"], str) or query["intent"] not in _INTENTS:
        _fail("invalid_query", "request.query.intent", "unsupported intent")
    _timestamp(query["as_of"], "request.query.as_of")

    conversation = _array(query["conversation"], "request.query.conversation")
    for index, turn in enumerate(conversation):
        path = f"request.query.conversation[{index}]"
        turn = _object(turn, path)
        _exact_keys(turn, required={"role", "content"}, path=path)
        if not isinstance(turn["role"], str) or turn["role"] not in {
            "user",
            "assistant",
        }:
            _fail("invalid_query", f"{path}.role", "unsupported conversation role")
        _text(turn["content"], f"{path}.content")

    _logical_id_list(request["scopes"], "request.scopes", require_nonempty=True)
    _validate_token_accounting(
        request["token_accounting"], "request.token_accounting"
    )
    compute_effective_context(request["budget"])


def validate_context_packet(packet: dict[str, Any]) -> None:
    """Validate one ``rag.context-packet`` version 1 envelope."""

    _object(packet, "packet")
    _exact_keys(
        packet,
        required={
            "contract",
            "schema_version",
            "product_id",
            "packet_id",
            "request_id",
            "generated_at",
            "token_accounting",
            "lifecycle",
            "plan",
            "effective_context",
            "evidence",
            "diagnostics",
        },
        optional={"$schema"},
        path="packet",
    )
    _contract_header(packet, CONTEXT_PACKET_CONTRACT, "packet")
    if "$schema" in packet:
        _text(packet["$schema"], "packet.$schema")
    _logical_id(packet["product_id"], "packet.product_id")
    _opaque_id(packet["packet_id"], "packet.packet_id")
    _opaque_id(packet["request_id"], "packet.request_id")
    _timestamp(packet["generated_at"], "packet.generated_at")
    _validate_token_accounting(
        packet["token_accounting"], "packet.token_accounting"
    )
    _validate_lifecycle(packet["lifecycle"], "packet.lifecycle")

    query_lanes, planned_lanes = _validate_plan(packet["plan"])
    evidence = _array(packet["evidence"], "packet.evidence")
    evidence_counts, selected_tokens, provenance_unknown = _validate_evidence(
        evidence, query_lanes
    )
    _validate_effective_context(
        packet["effective_context"],
        selected_tokens=selected_tokens,
        selected_items=len(evidence),
    )
    _validate_diagnostics(
        packet["diagnostics"],
        planned_lanes=planned_lanes,
        evidence_counts=evidence_counts,
        evidence_items=len(evidence),
        provenance_unknown=provenance_unknown,
    )


def validate_exchange(
    request: dict[str, Any], packet: dict[str, Any]
) -> dict[str, int]:
    """Validate a request/packet pair and return its effective-context accounting."""

    validate_retrieval_request(request)
    validate_context_packet(packet)

    if packet["request_id"] != request["request_id"]:
        _fail(
            "request_packet_mismatch",
            "packet.request_id",
            "packet does not identify its retrieval request",
        )
    if packet["product_id"] != request["product_id"]:
        _fail(
            "request_packet_mismatch",
            "packet.product_id",
            "packet does not belong to the request product",
        )
    if packet["token_accounting"] != request["token_accounting"]:
        _fail(
            "request_packet_mismatch",
            "packet.token_accounting",
            "request and packet token accounting differ",
        )
    if packet["lifecycle"] != request["lifecycle"]:
        _fail(
            "request_packet_mismatch",
            "packet.lifecycle",
            "request and packet lifecycle declarations differ",
        )
    if _timestamp(packet["generated_at"], "packet.generated_at") < _timestamp(
        request["created_at"], "request.created_at"
    ):
        _fail(
            "request_packet_mismatch",
            "packet.generated_at",
            "packet predates its request",
        )

    primary_queries = [
        item
        for item in packet["plan"]["queries"]
        if item["purpose"] == "primary" and item["text"] == request["query"]["text"]
    ]
    if len(primary_queries) != 1:
        _fail(
            "request_packet_mismatch",
            "packet.plan.queries",
            "plan must contain exactly one primary copy of the request query",
        )

    selected_tokens = sum(item["token_count"] for item in packet["evidence"])
    expected = compute_effective_context(
        request["budget"],
        selected_evidence_tokens=selected_tokens,
        selected_evidence_items=len(packet["evidence"]),
    )
    if packet["effective_context"] != expected:
        _fail(
            "request_packet_mismatch",
            "packet.effective_context",
            "effective context does not reproduce the request budget",
        )
    return expected


def validate_envelope(envelope: dict[str, Any]) -> None:
    """Dispatch validation by the envelope's declared contract name."""

    _object(envelope, "envelope")
    contract = envelope.get("contract")
    if contract == RETRIEVAL_REQUEST_CONTRACT:
        validate_retrieval_request(envelope)
        return
    if contract == CONTEXT_PACKET_CONTRACT:
        validate_context_packet(envelope)
        return
    _fail("invalid_contract", "envelope.contract", "unsupported contract")


def _validate_budget(budget: Any, path: str) -> dict[str, int]:
    budget = _object(budget, path)
    _exact_keys(budget, required=_BUDGET_KEYS, path=path)
    minimums = {
        "context_window_tokens": 1,
        "reserved_output_tokens": 1,
        "reserved_reasoning_tokens": 0,
        "safety_margin_tokens": 0,
        "instruction_tokens": 0,
        "conversation_tokens": 0,
        "tool_tokens": 0,
        "requested_evidence_tokens": 1,
        "max_evidence_items": 1,
    }
    for key, minimum in minimums.items():
        _integer(budget[key], f"{path}.{key}", minimum=minimum, code="invalid_budget")
    return budget


def _validate_token_accounting(value: Any, path: str) -> None:
    value = _object(value, path)
    _exact_keys(value, required={"method", "counter_id"}, path=path)
    if not isinstance(value["method"], str) or value["method"] not in {
        "provider_tokenizer",
        "conservative_estimate",
    }:
        _fail(
            "invalid_token_accounting",
            f"{path}.method",
            "unsupported token accounting method",
        )
    _opaque_id(value["counter_id"], f"{path}.counter_id")


def _validate_lifecycle(value: Any, path: str) -> None:
    value = _object(value, path)
    _exact_keys(value, required=set(_LIFECYCLE), path=path)
    if (
        value.get("mode") != "ephemeral"
        or type(value.get("persist_packet")) is not bool
        or value.get("persist_packet") is not False
        or type(value.get("log_evidence_content")) is not bool
        or value.get("log_evidence_content") is not False
    ):
        _fail(
            "persistence_not_ephemeral",
            path,
            "version 1 requires ephemeral, non-persistent, non-content-logging use",
        )


def _validate_plan(plan: Any) -> tuple[dict[str, set[str]], set[str]]:
    plan = _object(plan, "packet.plan")
    _exact_keys(plan, required={"strategy", "queries"}, path="packet.plan")
    if not isinstance(plan["strategy"], str) or plan["strategy"] not in _PLAN_STRATEGIES:
        _fail("invalid_plan", "packet.plan.strategy", "unsupported plan strategy")

    queries = _array(plan["queries"], "packet.plan.queries", require_nonempty=True)
    query_lanes: dict[str, set[str]] = {}
    planned_lanes: set[str] = set()
    for index, query in enumerate(queries):
        path = f"packet.plan.queries[{index}]"
        query = _object(query, path)
        _exact_keys(
            query,
            required={"query_id", "text", "purpose", "round", "lane_ids"},
            path=path,
        )
        query_id = _logical_id(query["query_id"], f"{path}.query_id")
        if query_id in query_lanes:
            _fail("invalid_plan", f"{path}.query_id", "duplicate planned query ID")
        _text(query["text"], f"{path}.text")
        _logical_id(query["purpose"], f"{path}.purpose")
        _integer(query["round"], f"{path}.round", minimum=1, code="invalid_plan")
        lanes = set(
            _logical_id_list(query["lane_ids"], f"{path}.lane_ids", require_nonempty=True)
        )
        query_lanes[query_id] = lanes
        planned_lanes.update(lanes)
    return query_lanes, planned_lanes


def _validate_evidence(
    evidence: list[Any], query_lanes: dict[str, set[str]]
) -> tuple[dict[str, int], int, bool]:
    evidence_ids: set[str] = set()
    citation_ids: set[str] = set()
    chunk_keys: set[tuple[str, str]] = set()
    content_hashes: set[str] = set()
    counts: dict[str, int] = {}
    token_total = 0
    provenance_unknown = False

    for index, item in enumerate(evidence):
        path = f"packet.evidence[{index}]"
        item = _object(item, path)
        _exact_keys(
            item,
            required={
                "evidence_id",
                "citation_id",
                "query_ids",
                "lane_id",
                "rank",
                "text",
                "token_count",
                "trust",
                "source",
                "provenance",
                "scores",
            },
            path=path,
        )
        evidence_id = _opaque_id(item["evidence_id"], f"{path}.evidence_id")
        if evidence_id in evidence_ids:
            _fail("duplicate_evidence", f"{path}.evidence_id", "duplicate evidence ID")
        evidence_ids.add(evidence_id)

        citation_id = item["citation_id"]
        if not isinstance(citation_id, str) or not _CITATION_ID.fullmatch(citation_id):
            _fail("invalid_evidence", f"{path}.citation_id", "invalid citation ID")
        expected_rank = index + 1
        if item["rank"] != expected_rank or citation_id != f"E{expected_rank:03d}":
            _fail(
                "invalid_evidence",
                path,
                "evidence order, rank, and citation ID must agree",
            )
        if citation_id in citation_ids:
            _fail("duplicate_evidence", f"{path}.citation_id", "duplicate citation ID")
        citation_ids.add(citation_id)

        lane_id = _logical_id(item["lane_id"], f"{path}.lane_id")
        query_ids = _logical_id_list(
            item["query_ids"], f"{path}.query_ids", require_nonempty=True
        )
        for query_id in query_ids:
            if query_id not in query_lanes:
                _fail(
                    "invalid_evidence",
                    f"{path}.query_ids",
                    "evidence refers to an undeclared planned query",
                )
            if lane_id not in query_lanes[query_id]:
                _fail(
                    "invalid_evidence",
                    f"{path}.lane_id",
                    "evidence lane is not enabled for its planned query",
                )

        _text(item["text"], f"{path}.text")
        token_count = _integer(
            item["token_count"], f"{path}.token_count", minimum=1, code="invalid_evidence"
        )
        token_total += token_count
        if item["trust"] != "untrusted":
            _fail(
                "invalid_trust_boundary",
                f"{path}.trust",
                "context packet evidence cannot carry instruction authority",
            )

        _validate_source(item["source"], f"{path}.source")
        document_id, chunk_id, content_hash, ingested_at_unknown = _validate_provenance(
            item["provenance"], f"{path}.provenance"
        )
        expected_hash = "sha256:" + hashlib.sha256(
            item["text"].encode("utf-8")
        ).hexdigest()
        if content_hash != expected_hash:
            _fail(
                "invalid_provenance",
                f"{path}.provenance.content_hash",
                "content hash does not match exact UTF-8 evidence text",
            )
        provenance_unknown = provenance_unknown or ingested_at_unknown
        chunk_key = (document_id, chunk_id)
        if chunk_key in chunk_keys or content_hash in content_hashes:
            _fail(
                "duplicate_evidence",
                f"{path}.provenance",
                "selected evidence must be deduplicated by chunk and content hash",
            )
        chunk_keys.add(chunk_key)
        content_hashes.add(content_hash)
        _validate_scores(item["scores"], f"{path}.scores")
        counts[lane_id] = counts.get(lane_id, 0) + 1

    return counts, token_total, provenance_unknown


def _validate_source(source: Any, path: str) -> None:
    source = _object(source, path)
    _exact_keys(
        source,
        required={"kind", "source_id"},
        optional={"title", "uri"},
        path=path,
    )
    _logical_id(source["kind"], f"{path}.kind")
    _opaque_id(source["source_id"], f"{path}.source_id")
    if "title" in source:
        _text(source["title"], f"{path}.title")
    if "uri" in source:
        _text(source["uri"], f"{path}.uri", maximum=4096)


def _validate_provenance(
    provenance: Any, path: str
) -> tuple[str, str, str, bool]:
    provenance = _object(provenance, path)
    _exact_keys(
        provenance,
        required={
            "document_id",
            "chunk_id",
            "chunk_ordinal",
            "content_hash",
            "ingested_at",
            "published_at",
            "valid_from",
            "valid_to",
            "source_revision",
        },
        path=path,
    )
    document_id = _opaque_id(provenance["document_id"], f"{path}.document_id")
    chunk_id = _opaque_id(provenance["chunk_id"], f"{path}.chunk_id")
    _integer(
        provenance["chunk_ordinal"],
        f"{path}.chunk_ordinal",
        minimum=0,
        code="invalid_provenance",
    )
    content_hash = provenance["content_hash"]
    if not isinstance(content_hash, str) or not _CONTENT_HASH.fullmatch(content_hash):
        _fail(
            "invalid_provenance",
            f"{path}.content_hash",
            "content hash must be lowercase sha256:<hex>",
        )
    ingested_at = _nullable_timestamp(
        provenance["ingested_at"], f"{path}.ingested_at"
    )
    published_at = _nullable_timestamp(provenance["published_at"], f"{path}.published_at")
    valid_from = _nullable_timestamp(provenance["valid_from"], f"{path}.valid_from")
    valid_to = _nullable_timestamp(provenance["valid_to"], f"{path}.valid_to")
    if valid_from is not None and valid_to is not None and valid_to < valid_from:
        _fail(
            "invalid_provenance",
            f"{path}.valid_to",
            "valid_to predates valid_from",
        )
    revision = provenance["source_revision"]
    if revision is not None:
        _opaque_id(revision, f"{path}.source_revision")
    _ = published_at
    return document_id, chunk_id, content_hash, ingested_at is None


def _validate_scores(scores: Any, path: str) -> None:
    scores = _object(scores, path)
    _exact_keys(scores, required={"final", "components"}, path=path)
    final = _number(scores["final"], f"{path}.final", code="invalid_evidence")
    if not 0 <= final <= 1:
        _fail("invalid_evidence", f"{path}.final", "final score must be between 0 and 1")
    components = _object(scores["components"], f"{path}.components")
    for name, value in components.items():
        _logical_id(name, f"{path}.components")
        _number(value, f"{path}.components.{name}", code="invalid_evidence")


def _validate_effective_context(
    context: Any, *, selected_tokens: int, selected_items: int
) -> None:
    context = _object(context, "packet.effective_context")
    _exact_keys(
        context,
        required=_EFFECTIVE_CONTEXT_KEYS,
        path="packet.effective_context",
    )
    positive = {
        "context_window_tokens",
        "reserved_output_tokens",
        "max_input_tokens",
        "requested_evidence_tokens",
        "available_evidence_tokens",
        "max_evidence_items",
    }
    for key in _EFFECTIVE_CONTEXT_KEYS:
        _integer(
            context[key],
            f"packet.effective_context.{key}",
            minimum=1 if key in positive else 0,
            code="invalid_effective_context",
        )

    expected_max_input = (
        context["context_window_tokens"]
        - context["reserved_output_tokens"]
        - context["reserved_reasoning_tokens"]
        - context["safety_margin_tokens"]
    )
    if context["max_input_tokens"] != expected_max_input:
        _fail(
            "invalid_effective_context",
            "packet.effective_context.max_input_tokens",
            "max input arithmetic is inconsistent",
        )
    remaining = context["max_input_tokens"] - context["non_evidence_input_tokens"]
    expected_available = min(context["requested_evidence_tokens"], remaining)
    if remaining <= 0 or context["available_evidence_tokens"] != expected_available:
        _fail(
            "invalid_effective_context",
            "packet.effective_context.available_evidence_tokens",
            "available evidence arithmetic is inconsistent",
        )
    if context["selected_evidence_tokens"] != selected_tokens:
        _fail(
            "invalid_effective_context",
            "packet.effective_context.selected_evidence_tokens",
            "selected token count does not match evidence",
        )
    if context["selected_evidence_items"] != selected_items:
        _fail(
            "invalid_effective_context",
            "packet.effective_context.selected_evidence_items",
            "selected item count does not match evidence",
        )
    if selected_tokens > context["available_evidence_tokens"]:
        _fail(
            "budget_exceeded",
            "packet.effective_context.selected_evidence_tokens",
            "selected evidence exceeds effective token capacity",
        )
    if selected_items > context["max_evidence_items"]:
        _fail(
            "budget_exceeded",
            "packet.effective_context.selected_evidence_items",
            "selected evidence exceeds item cap",
        )


def _validate_diagnostics(
    diagnostics: Any,
    *,
    planned_lanes: set[str],
    evidence_counts: dict[str, int],
    evidence_items: int,
    provenance_unknown: bool,
) -> None:
    diagnostics = _object(diagnostics, "packet.diagnostics")
    _exact_keys(
        diagnostics,
        required={
            "status",
            "degradation_codes",
            "coverage_gaps",
            "candidate_count",
            "post_deduplication_candidate_count",
            "selected_count",
            "dropped_for_budget_count",
            "lanes",
        },
        path="packet.diagnostics",
    )
    status = diagnostics["status"]
    if not isinstance(status, str) or status not in _PACKET_STATUSES:
        _fail("invalid_diagnostics", "packet.diagnostics.status", "unsupported status")
    degradation_codes = _logical_id_list(
        diagnostics["degradation_codes"], "packet.diagnostics.degradation_codes"
    )
    coverage_gaps = _logical_id_list(
        diagnostics["coverage_gaps"], "packet.diagnostics.coverage_gaps"
    )
    counts = {}
    for key in (
        "candidate_count",
        "post_deduplication_candidate_count",
        "selected_count",
        "dropped_for_budget_count",
    ):
        counts[key] = _integer(
            diagnostics[key],
            f"packet.diagnostics.{key}",
            minimum=0,
            code="invalid_diagnostics",
        )
    if not (
        counts["candidate_count"]
        >= counts["post_deduplication_candidate_count"]
        >= counts["selected_count"]
    ):
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics",
            "candidate, deduplicated, and selected counts are inconsistent",
        )
    if counts["dropped_for_budget_count"] > (
        counts["post_deduplication_candidate_count"] - counts["selected_count"]
    ):
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.dropped_for_budget_count",
            "budget drops exceed unselected deduplicated candidates",
        )
    if counts["selected_count"] != evidence_items:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.selected_count",
            "selected count does not match evidence",
        )

    lanes = _array(diagnostics["lanes"], "packet.diagnostics.lanes", require_nonempty=True)
    lane_ids: set[str] = set()
    lane_candidate_total = 0
    lane_selected_total = 0
    failed_required_lane = False
    for index, lane in enumerate(lanes):
        path = f"packet.diagnostics.lanes[{index}]"
        lane = _object(lane, path)
        _exact_keys(
            lane,
            required={
                "lane_id",
                "required",
                "status",
                "candidate_count",
                "selected_count",
                "diagnostic_codes",
            },
            path=path,
        )
        lane_id = _logical_id(lane["lane_id"], f"{path}.lane_id")
        if lane_id in lane_ids:
            _fail("invalid_diagnostics", f"{path}.lane_id", "duplicate lane diagnostic")
        lane_ids.add(lane_id)
        if type(lane["required"]) is not bool:
            _fail("invalid_diagnostics", f"{path}.required", "required must be boolean")
        if not isinstance(lane["status"], str) or lane["status"] not in _LANE_STATUSES:
            _fail("invalid_diagnostics", f"{path}.status", "unsupported lane status")
        lane_candidates = _integer(
            lane["candidate_count"],
            f"{path}.candidate_count",
            minimum=0,
            code="invalid_diagnostics",
        )
        lane_selected = _integer(
            lane["selected_count"],
            f"{path}.selected_count",
            minimum=0,
            code="invalid_diagnostics",
        )
        if lane_selected > lane_candidates:
            _fail("invalid_diagnostics", path, "lane selected count exceeds candidates")
        lane_codes = _logical_id_list(
            lane["diagnostic_codes"], f"{path}.diagnostic_codes"
        )
        if lane["status"] in {"empty", "failed", "skipped"} and lane_selected:
            _fail(
                "invalid_diagnostics",
                f"{path}.selected_count",
                "a non-complete lane cannot contribute selected evidence",
            )
        if lane["status"] == "skipped" and lane_candidates:
            _fail(
                "invalid_diagnostics",
                f"{path}.candidate_count",
                "a skipped lane cannot report candidates",
            )
        if lane["status"] == "failed" and not lane_codes:
            _fail(
                "invalid_diagnostics",
                f"{path}.diagnostic_codes",
                "a failed lane requires a logical diagnostic code",
            )
        if lane_selected != evidence_counts.get(lane_id, 0):
            _fail(
                "invalid_diagnostics",
                f"{path}.selected_count",
                "lane selected count does not match evidence",
            )
        lane_candidate_total += lane_candidates
        lane_selected_total += lane_selected
        failed_required_lane = failed_required_lane or (
            lane["required"] and lane["status"] == "failed"
        )

    if lane_ids != planned_lanes:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.lanes",
            "lane diagnostics must cover every planned lane exactly once",
        )
    if lane_candidate_total != counts["candidate_count"]:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.candidate_count",
            "aggregate candidate count does not match lanes",
        )
    if lane_selected_total != counts["selected_count"]:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.selected_count",
            "aggregate selected count does not match lanes",
        )

    if status == "complete" and (
        degradation_codes
        or coverage_gaps
        or failed_required_lane
        or provenance_unknown
    ):
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.status",
            "complete packets cannot report degradation",
        )
    if status == "degraded" and not degradation_codes:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.degradation_codes",
            "degraded packets require a logical degradation code",
        )
    if status == "empty" and evidence_items:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.status",
            "empty packets cannot contain selected evidence",
        )
    if status == "complete" and not evidence_items:
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.status",
            "a packet with no evidence must be empty or degraded",
        )
    if failed_required_lane and status != "degraded":
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.status",
            "a failed required lane requires degraded packet status",
        )
    if provenance_unknown and (
        status != "degraded" or "provenance_unknown" not in degradation_codes
    ):
        _fail(
            "invalid_diagnostics",
            "packet.diagnostics.degradation_codes",
            "unknown ingestion provenance requires degraded provenance_unknown status",
        )


def _contract_header(value: dict[str, Any], expected: str, path: str) -> None:
    if value.get("contract") != expected:
        _fail("invalid_contract", f"{path}.contract", "unexpected contract name")
    if type(value.get("schema_version")) is not int or value.get(
        "schema_version"
    ) != SCHEMA_VERSION:
        _fail(
            "invalid_schema_version",
            f"{path}.schema_version",
            "unsupported schema version",
        )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("invalid_shape", path, "expected an object")
    return value


def _array(value: Any, path: str, *, require_nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        _fail("invalid_shape", path, "expected an array")
    if require_nonempty and not value:
        _fail("invalid_shape", path, "array must not be empty")
    return value


def _exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    path: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required - value.keys()
    if missing:
        _fail("invalid_shape", path, "required field is missing")
    unknown = value.keys() - required - optional
    if unknown:
        _fail("invalid_shape", path, "unknown field is present")


def _text(value: Any, path: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_shape", path, "expected non-empty text")
    if maximum is not None and len(value) > maximum:
        _fail("invalid_shape", path, "text exceeds maximum length")
    return value


def _opaque_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 512:
        _fail("invalid_identifier", path, "invalid stable identifier")
    return value


def _logical_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _LOGICAL_ID.fullmatch(value):
        _fail("invalid_identifier", path, "invalid logical identifier")
    return value


def _logical_id_list(
    value: Any, path: str, *, require_nonempty: bool = False
) -> list[str]:
    items = _array(value, path, require_nonempty=require_nonempty)
    result = [_logical_id(item, f"{path}[{index}]") for index, item in enumerate(items)]
    if len(result) != len(set(result)):
        _fail("invalid_identifier", path, "logical identifiers must be unique")
    return result


def _integer(
    value: Any, path: str, *, minimum: int, code: str
) -> int:
    if type(value) is not int or value < minimum:
        _fail(code, path, "invalid integer")
    return value


def _number(value: Any, path: str, *, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(code, path, "invalid number")
    number = float(value)
    if not math.isfinite(number):
        _fail(code, path, "number must be finite")
    return number


def _timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_timestamp", path, "expected an RFC 3339 timestamp")
    raw = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        _fail("invalid_timestamp", path, "expected an RFC 3339 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("invalid_timestamp", path, "timestamp must include an offset")
    return parsed


def _nullable_timestamp(value: Any, path: str) -> datetime | None:
    return None if value is None else _timestamp(value, path)


def _fail(code: str, path: str, message: str) -> None:
    raise ContextContractError(code, path, message)
