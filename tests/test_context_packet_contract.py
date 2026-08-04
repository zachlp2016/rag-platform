import copy
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from rag_platform.context_packet import (
    CONTEXT_PACKET_CONTRACT,
    RETRIEVAL_REQUEST_CONTRACT,
    ContextContractError,
    compute_effective_context,
    validate_context_packet,
    validate_envelope,
    validate_exchange,
    validate_retrieval_request,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "retrieval-context.schema.json"
FIXTURES_PATH = ROOT / "fixtures" / "context-packet" / "cases.v1.json"


def _replace_json_pointer(document, pointer, value):
    parts = [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.lstrip("/").split("/")
        if part
    ]
    target = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = value
    else:
        target[final] = value


class ContextPacketContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        cls.schema_validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )
        cls.exchanges = {
            item["name"]: item for item in cls.fixtures["valid_exchanges"]
        }

    def test_schema_declares_both_v1_envelopes(self):
        definitions = self.schema["$defs"]
        self.assertEqual(
            RETRIEVAL_REQUEST_CONTRACT,
            definitions["retrievalRequest"]["properties"]["contract"]["const"],
        )
        self.assertEqual(
            CONTEXT_PACKET_CONTRACT,
            definitions["contextPacket"]["properties"]["contract"]["const"],
        )
        self.assertEqual(
            "ephemeral", definitions["lifecycle"]["properties"]["mode"]["const"]
        )
        self.assertFalse(
            definitions["lifecycle"]["properties"]["persist_packet"]["const"]
        )
        self.assertEqual(
            "^E(?=[0-9]{3,}$)0*[1-9][0-9]*$",
            definitions["evidence"]["properties"]["citation_id"]["pattern"],
        )

    def test_all_valid_conformance_exchanges(self):
        for case in self.fixtures["valid_exchanges"]:
            with self.subTest(case=case["name"]):
                actual = validate_exchange(case["request"], case["packet"])
                self.assertEqual(case["expected_effective_context"], actual)
                validate_envelope(case["request"])
                validate_envelope(case["packet"])

    def test_valid_fixtures_match_json_schema(self):
        for case in self.fixtures["valid_exchanges"]:
            for envelope_name in ("request", "packet"):
                with self.subTest(case=case["name"], envelope=envelope_name):
                    errors = list(
                        self.schema_validator.iter_errors(case[envelope_name])
                    )
                    self.assertEqual([], errors)

    def test_all_invalid_conformance_mutations(self):
        validators = {
            "request": lambda request, _packet: validate_retrieval_request(request),
            "packet": lambda _request, packet: validate_context_packet(packet),
            "exchange": validate_exchange,
        }
        for case in self.fixtures["invalid_mutations"]:
            with self.subTest(case=case["name"]):
                base = self.exchanges[case["base"]]
                request = copy.deepcopy(base["request"])
                packet = copy.deepcopy(base["packet"])
                target = request if case["target"] == "request" else packet
                for operation in case["operations"]:
                    self.assertEqual("replace", operation["op"])
                    _replace_json_pointer(
                        target, operation["path"], operation.get("value")
                    )
                with self.assertRaises(ContextContractError) as raised:
                    validators[case["validation"]](request, packet)
                self.assertEqual(case["expected_error"], raised.exception.code)

    def test_reasoning_reservation_reduces_effective_input(self):
        budget = {
            "context_window_tokens": 10000,
            "reserved_output_tokens": 1000,
            "reserved_reasoning_tokens": 512,
            "safety_margin_tokens": 488,
            "instruction_tokens": 500,
            "conversation_tokens": 500,
            "tool_tokens": 0,
            "requested_evidence_tokens": 9000,
            "max_evidence_items": 10,
        }

        result = compute_effective_context(
            budget, selected_evidence_tokens=3000, selected_evidence_items=3
        )

        self.assertEqual(8000, result["max_input_tokens"])
        self.assertEqual(7000, result["available_evidence_tokens"])
        self.assertEqual(3000, result["selected_evidence_tokens"])

    def test_content_hash_binds_exact_utf8_evidence_text(self):
        packet = copy.deepcopy(
            self.exchanges["complete_decomposed_analysis"]["packet"]
        )
        packet["evidence"][0]["text"] += " changed"

        with self.assertRaises(ContextContractError) as raised:
            validate_context_packet(packet)

        self.assertEqual("invalid_provenance", raised.exception.code)

    def test_fixture_hash_is_exact_utf8_sha256(self):
        packet = self.exchanges["complete_decomposed_analysis"]["packet"]
        evidence = packet["evidence"][0]
        expected = "sha256:" + hashlib.sha256(
            evidence["text"].encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, evidence["provenance"]["content_hash"])

    def test_failed_lane_cannot_claim_selected_evidence(self):
        packet = copy.deepcopy(
            self.exchanges["complete_decomposed_analysis"]["packet"]
        )
        lane = packet["diagnostics"]["lanes"][0]
        lane["status"] = "failed"
        lane["diagnostic_codes"] = ["lane_failed"]
        packet["diagnostics"]["status"] = "degraded"
        packet["diagnostics"]["degradation_codes"] = ["lane_failed"]

        with self.assertRaises(ContextContractError) as raised:
            validate_context_packet(packet)

        self.assertEqual("invalid_diagnostics", raised.exception.code)

    def test_unknown_fields_fail_closed_without_echoing_query(self):
        request = copy.deepcopy(
            self.exchanges["complete_decomposed_analysis"]["request"]
        )
        secret_marker = "do-not-echo-this-query-marker"
        request["query"]["text"] = secret_marker
        request["deployment_url"] = "http://internal.invalid"

        with self.assertRaises(ContextContractError) as raised:
            validate_retrieval_request(request)

        self.assertEqual("invalid_shape", raised.exception.code)
        self.assertNotIn(secret_marker, str(raised.exception))

    def test_malformed_scalar_types_raise_contract_errors(self):
        request = copy.deepcopy(
            self.exchanges["complete_decomposed_analysis"]["request"]
        )
        request["query"]["intent"] = ["analysis"]

        with self.assertRaises(ContextContractError) as raised:
            validate_retrieval_request(request)

        self.assertEqual("invalid_query", raised.exception.code)

    def test_schema_and_stdlib_reject_blank_text_and_padded_ids(self):
        base = self.exchanges["complete_decomposed_analysis"]["request"]
        cases = []

        blank = copy.deepcopy(base)
        blank["query"]["text"] = "   "
        cases.append(blank)

        padded = copy.deepcopy(base)
        padded["request_id"] = " request-analysis-001 "
        cases.append(padded)

        for request in cases:
            with self.subTest(request_id=request["request_id"]):
                self.assertTrue(list(self.schema_validator.iter_errors(request)))
                with self.assertRaises(ContextContractError):
                    validate_retrieval_request(request)

    def test_schema_and_stdlib_reject_zero_citation(self):
        packet = copy.deepcopy(
            self.exchanges["complete_decomposed_analysis"]["packet"]
        )
        packet["evidence"][0]["citation_id"] = "E000"

        self.assertTrue(list(self.schema_validator.iter_errors(packet)))
        with self.assertRaises(ContextContractError) as raised:
            validate_context_packet(packet)
        self.assertEqual("invalid_evidence", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
