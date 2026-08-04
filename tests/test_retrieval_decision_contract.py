import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from rag_platform.retrieval_decision import (
    DEPTH_METHODS,
    DEPTH_TIERS,
    RETRIEVAL_DECISION_CONTRACT,
    RetrievalDecisionError,
    SOURCE_METHODS,
    validate_retrieval_decision,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "retrieval-decision.schema.json"
CONFORMANCE_PATH = (
    ROOT / "fixtures" / "retrieval-decision" / "conformance.v1.json"
)
EVALUATION_PATH = (
    ROOT / "fixtures" / "retrieval-decision" / "evaluation-cases.v1.json"
)
BLIND_PATH = ROOT / "fixtures" / "retrieval-decision" / "blind-analysis.v1.json"


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


class RetrievalDecisionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.conformance = json.loads(
            CONFORMANCE_PATH.read_text(encoding="utf-8")
        )
        cls.schema_validator = Draft202012Validator(cls.schema)

    def test_schema_exposes_the_versioned_envelope(self):
        self.assertEqual(
            "rag.retrieval-decision",
            self.schema["properties"]["contract"]["const"],
        )
        self.assertEqual(1, self.schema["properties"]["schema_version"]["const"])
        self.assertFalse(self.schema["additionalProperties"])
        self.assertNotIn("query", self.schema["properties"])

    def test_schema_keeps_source_and_depth_orthogonal(self):
        source = self.schema["$defs"]["sourceDecision"]["properties"]
        depth = self.schema["$defs"]["depthDecision"]["properties"]
        self.assertEqual(["corpus", "file"], source["scope"]["enum"])
        self.assertNotIn("utility_model", source["method"]["enum"])
        self.assertIn("utility_model", depth["method"]["enum"])
        self.assertEqual(
            ["lookup", "standard", "analysis", "deep"], depth["tier"]["enum"]
        )
        self.assertEqual(2, len(self.schema["$defs"]["sourceDecision"]["allOf"]))

    def test_public_validator_constants_match_schema(self):
        self.assertEqual("rag.retrieval-decision", RETRIEVAL_DECISION_CONTRACT)
        self.assertEqual(
            {"explicit", "structural", "conversation_state", "fallback"},
            set(SOURCE_METHODS),
        )
        self.assertEqual(
            {"explicit", "structural", "utility_model", "fallback"},
            set(DEPTH_METHODS),
        )
        self.assertEqual(
            {"lookup", "standard", "analysis", "deep"}, set(DEPTH_TIERS)
        )

    def test_all_valid_conformance_cases(self):
        for case in self.conformance["valid_cases"]:
            with self.subTest(case=case["name"]):
                validate_retrieval_decision(case["decision"])

    def test_json_schema_matches_conformance_cases(self):
        Draft202012Validator.check_schema(self.schema)
        for case in self.conformance["valid_cases"]:
            with self.subTest(case=case["name"], expected="valid"):
                self.assertEqual(
                    [], list(self.schema_validator.iter_errors(case["decision"]))
                )

        base = self.conformance["base_decision"]
        for case in self.conformance["invalid_cases"]:
            with self.subTest(case=case["name"], expected="invalid"):
                decision = copy.deepcopy(base)
                mutations = case.get("mutations") or [case["mutation"]]
                for mutation in mutations:
                    _apply_mutation(decision, mutation)
                self.assertTrue(list(self.schema_validator.iter_errors(decision)))

    def test_all_invalid_conformance_cases(self):
        base = self.conformance["base_decision"]
        for case in self.conformance["invalid_cases"]:
            with self.subTest(case=case["name"]):
                decision = copy.deepcopy(base)
                mutations = case.get("mutations") or [case["mutation"]]
                for mutation in mutations:
                    _apply_mutation(decision, mutation)
                with self.assertRaises(RetrievalDecisionError) as raised:
                    validate_retrieval_decision(decision)
                self.assertEqual(case["expected_error"], raised.exception.code)

    def test_unknown_raw_query_is_rejected_without_echoing_its_value(self):
        decision = copy.deepcopy(self.conformance["base_decision"])
        decision["query"] = "private-query-value-must-not-appear"
        with self.assertRaises(RetrievalDecisionError) as raised:
            validate_retrieval_decision(decision)
        self.assertEqual("unknown_field", raised.exception.code)
        self.assertNotIn("private-query-value-must-not-appear", str(raised.exception))

    def test_product_specific_budget_values_are_not_globally_mapped(self):
        low = copy.deepcopy(self.conformance["base_decision"])
        high = copy.deepcopy(self.conformance["base_decision"])
        low["depth"]["evidence_budget_tokens"] = 1000
        high["depth"]["evidence_budget_tokens"] = 64000
        validate_retrieval_decision(low)
        validate_retrieval_decision(high)

    def test_evaluation_fixture_has_frozen_shape(self):
        evaluation = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        self.assertTrue(evaluation["frozen"])
        self.assertEqual(1, evaluation["schema_version"])
        self.assertEqual(100, len(evaluation["cases"]))
        ids = [case["id"] for case in evaluation["cases"]]
        self.assertEqual(100, len(set(ids)))

        category_counts = {}
        source_depth_pairs = set()
        for case in evaluation["cases"]:
            self.assertEqual(
                {"id", "category", "query", "conversation", "expected"},
                set(case),
            )
            self.assertTrue(case["query"].strip())
            self.assertIsInstance(case["conversation"], list)
            for turn in case["conversation"]:
                self.assertEqual({"role", "content"}, set(turn))
                self.assertIn(turn["role"], {"user", "assistant"})
                self.assertTrue(turn["content"].strip())
            category_counts[case["category"]] = (
                category_counts.get(case["category"], 0) + 1
            )
            expected = case["expected"]
            self.assertEqual({"source", "depth"}, set(expected))
            source = expected["source"]
            self.assertEqual({"scope", "source_id"}, set(source))
            self.assertIn(source["scope"], {"corpus", "file"})
            if source["scope"] == "file":
                self.assertIsInstance(source["source_id"], str)
                self.assertTrue(source["source_id"].strip())
            else:
                self.assertIsNone(source["source_id"])
            self.assertEqual({"tier"}, set(expected["depth"]))
            self.assertIn(expected["depth"]["tier"], DEPTH_TIERS)
            source_depth_pairs.add((source["scope"], expected["depth"]["tier"]))

        self.assertEqual(10, len(category_counts))
        self.assertEqual({10}, set(category_counts.values()))
        self.assertEqual(
            {
                (scope, tier)
                for scope in ("corpus", "file")
                for tier in ("lookup", "standard", "analysis", "deep")
            },
            source_depth_pairs,
        )

    def test_blind_analysis_fixture_has_five_strong_and_five_weak_cases(self):
        blind = json.loads(BLIND_PATH.read_text(encoding="utf-8"))
        self.assertTrue(blind["frozen"])
        self.assertEqual(10, len(blind["cases"]))
        strengths = [case["expected_strength"] for case in blind["cases"]]
        self.assertEqual(5, strengths.count("strong"))
        self.assertEqual(5, strengths.count("weak"))
        for case in blind["cases"]:
            self.assertEqual("corpus", case["expected"]["source"]["scope"])
            expected_tier = (
                "analysis" if case["expected_strength"] == "strong" else "standard"
            )
            self.assertEqual(expected_tier, case["expected"]["depth"]["tier"])


if __name__ == "__main__":
    unittest.main()
