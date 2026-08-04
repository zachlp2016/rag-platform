import copy
import json
import math
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from rag_platform.structured_evidence import (
    AVAILABILITY_BASES,
    FRESHNESS_BASES,
    STRUCTURED_EVIDENCE_CONTRACT,
    StructuredEvidenceError,
    validate_structured_evidence,
    validate_structured_evidence_admission,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "structured-evidence.schema.json"
FIXTURES_PATH = (
    ROOT / "fixtures" / "structured-evidence" / "conformance.v1.json"
)


def _apply_mutation(document, mutation):
    target = document
    path = mutation["path"]
    for part in path[:-1]:
        target = target[part]
    operation = mutation["operation"]
    if operation in {"add", "replace"}:
        target[path[-1]] = mutation["value"]
    elif operation == "remove":
        del target[path[-1]]
    else:
        raise AssertionError(f"unsupported fixture mutation: {operation}")


class StructuredEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        cls.schema_validator = Draft202012Validator(
            cls.schema, format_checker=FormatChecker()
        )
        cls.valid_cases = {
            case["name"]: case["evidence"]
            for case in cls.fixtures["valid_cases"]
        }

    def retrieval_request_for(self, evidence):
        return {
            "contract": "rag.retrieval-request",
            "schema_version": 1,
            "product_id": evidence["product_id"],
            "request_id": evidence["request_id"],
            "created_at": "2026-08-04T15:59:00Z",
            "query": {
                "text": "Analyze the selected structured series.",
                "intent": "analysis",
                "as_of": evidence["as_of"],
                "conversation": [],
            },
            "scopes": [evidence["lane_id"]],
            "budget": {
                "context_window_tokens": 8192,
                "reserved_output_tokens": 1024,
                "reserved_reasoning_tokens": 0,
                "safety_margin_tokens": 512,
                "instruction_tokens": 500,
                "conversation_tokens": 0,
                "tool_tokens": 0,
                "requested_evidence_tokens": 4096,
                "max_evidence_items": 8,
            },
            "token_accounting": {
                "method": "conservative_estimate",
                "counter_id": "fixture-estimator:v1",
            },
            "lifecycle": {
                "mode": "ephemeral",
                "persist_packet": False,
                "log_evidence_content": False,
            },
        }

    def test_schema_exposes_versioned_ephemeral_untrusted_record(self):
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(
            STRUCTURED_EVIDENCE_CONTRACT,
            self.schema["properties"]["contract"]["const"],
        )
        self.assertEqual(1, self.schema["properties"]["schema_version"]["const"])
        self.assertEqual("untrusted", self.schema["properties"]["trust"]["const"])
        lifecycle = self.schema["$defs"]["lifecycle"]["properties"]
        self.assertEqual("ephemeral", lifecycle["mode"]["const"])
        self.assertFalse(lifecycle["persist_evidence"]["const"])
        self.assertFalse(lifecycle["log_values"]["const"])

    def test_schema_has_point_in_time_identity_and_value_fields(self):
        source = self.schema["$defs"]["source"]["required"]
        observation = self.schema["$defs"]["observation"]["required"]
        self.assertIn("source_id", source)
        self.assertIn("series_id", source)
        self.assertTrue(
            {
                "observed_at",
                "released_at",
                "available_at",
                "vintage",
                "unit",
                "frequency",
                "value",
                "features",
            }.issubset(observation)
        )
        self.assertEqual(
            {
                "source_release",
                "source_vintage",
                "first_seen",
                "ingestion",
            },
            set(AVAILABILITY_BASES),
        )
        self.assertEqual({"observed_at", "available_at"}, set(FRESHNESS_BASES))

    def test_all_valid_conformance_cases_match_schema_and_helper(self):
        for case in self.fixtures["valid_cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    [], list(self.schema_validator.iter_errors(case["evidence"]))
                )
                validate_structured_evidence(case["evidence"])

    def test_all_invalid_conformance_mutations(self):
        for case in self.fixtures["invalid_cases"]:
            with self.subTest(case=case["name"]):
                evidence = copy.deepcopy(self.valid_cases[case["base"]])
                mutations = case.get("mutations") or [case["mutation"]]
                for mutation in mutations:
                    _apply_mutation(evidence, mutation)

                schema_errors = list(self.schema_validator.iter_errors(evidence))
                self.assertEqual(case["schema_valid"], not schema_errors)
                with self.assertRaises(StructuredEvidenceError) as raised:
                    validate_structured_evidence(evidence)
                self.assertEqual(case["expected_error"], raised.exception.code)

    def test_no_lookahead_uses_availability_not_observation_or_retrieval_time(self):
        evidence = copy.deepcopy(
            self.valid_cases["released_series_with_derived_feature_is_eligible"]
        )
        evidence["observation"]["observed_at"] = "2026-09-30T23:59:59Z"
        evidence["provenance"]["retrieved_at"] = "2026-08-10T12:00:00Z"

        validate_structured_evidence(evidence)
        self.assertTrue(evidence["eligibility"]["no_lookahead"])

    def test_stale_evidence_can_still_be_point_in_time_eligible(self):
        evidence = self.valid_cases[
            "historical_revision_can_be_stale_and_eligible"
        ]
        validate_structured_evidence(evidence)
        self.assertEqual("stale", evidence["freshness"]["status"])
        self.assertTrue(evidence["eligibility"]["no_lookahead"])

    def test_admission_binds_record_to_request_and_requires_eligibility(self):
        eligible = self.valid_cases[
            "released_series_with_derived_feature_is_eligible"
        ]
        validate_structured_evidence_admission(
            self.retrieval_request_for(eligible), eligible
        )

        ineligible = self.valid_cases[
            "later_vintage_is_explicitly_ineligible_for_earlier_as_of"
        ]
        with self.assertRaises(StructuredEvidenceError) as raised:
            validate_structured_evidence_admission(
                self.retrieval_request_for(ineligible), ineligible
            )
        self.assertEqual("ineligible_evidence", raised.exception.code)

    def test_admission_rejects_lane_selected_as_of_drift(self):
        evidence = copy.deepcopy(
            self.valid_cases["released_series_with_derived_feature_is_eligible"]
        )
        request = self.retrieval_request_for(evidence)
        request["query"]["as_of"] = "2026-08-05T16:00:00Z"

        with self.assertRaises(StructuredEvidenceError) as raised:
            validate_structured_evidence_admission(request, evidence)
        self.assertEqual("request_evidence_mismatch", raised.exception.code)

    def test_non_finite_derived_values_fail_closed(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                evidence = copy.deepcopy(
                    self.valid_cases[
                        "released_series_with_derived_feature_is_eligible"
                    ]
                )
                evidence["observation"]["features"][0]["value"] = value
                with self.assertRaises(StructuredEvidenceError) as raised:
                    validate_structured_evidence(evidence)
                self.assertEqual("invalid_value", raised.exception.code)

    def test_boolean_schema_version_is_not_version_one(self):
        evidence = copy.deepcopy(
            self.valid_cases["released_series_with_derived_feature_is_eligible"]
        )
        evidence["schema_version"] = True

        self.assertTrue(list(self.schema_validator.iter_errors(evidence)))
        with self.assertRaises(StructuredEvidenceError) as raised:
            validate_structured_evidence(evidence)
        self.assertEqual("invalid_version", raised.exception.code)

    def test_unknown_fields_do_not_echo_values(self):
        evidence = copy.deepcopy(
            self.valid_cases["released_series_with_derived_feature_is_eligible"]
        )
        secret_marker = "raw-source-value-must-not-be-echoed"
        evidence["raw_payload"] = secret_marker

        with self.assertRaises(StructuredEvidenceError) as raised:
            validate_structured_evidence(evidence)

        self.assertEqual("unknown_field", raised.exception.code)
        self.assertNotIn(secret_marker, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
