import copy
import json
from pathlib import Path
import unittest

from tools.semantic_routing_contract import (
    ManifestError,
    RouteResolutionError,
    normalize_identity,
    resolve,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "contracts" / "semantic-routing.routes.json"
FIXTURES_PATH = ROOT / "fixtures" / "semantic-routing" / "cases.v1.json"


class SemanticRoutingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_valid(self):
        validate_manifest(self.manifest)

    def test_all_conformance_cases(self):
        for case in self.fixtures["cases"]:
            with self.subTest(case=case["name"]):
                try:
                    actual = resolve(self.manifest, **case["input"]).to_result()
                except RouteResolutionError as error:
                    actual = {"status": "rejected", "error": error.code}
                self.assertEqual(case["expected"], actual)

    def test_identity_normalization_collapses_declared_separators(self):
        self.assertEqual("finance consultant", normalize_identity(" Finance_Consultant "))
        self.assertEqual("finance consultant", normalize_identity("finance-consultant"))

    def test_duplicate_normalized_role_aliases_are_invalid(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"][1]["match"]["role_keys"].append("reviewer")
        with self.assertRaisesRegex(ManifestError, "belongs to"):
            validate_manifest(manifest)

    def test_canonical_model_must_be_accepted(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"][0]["target"]["accepted_models"] = ["another-model"]
        with self.assertRaisesRegex(ManifestError, "canonical_model"):
            validate_manifest(manifest)

    def test_unknown_manifest_fields_are_invalid(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["fallback_url"] = "http://127.0.0.1:8080"
        with self.assertRaisesRegex(ManifestError, "unknown keys"):
            validate_manifest(manifest)

    def test_present_alias_arrays_cannot_be_empty(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["routes"][0]["match"]["role_keys"] = []
        with self.assertRaisesRegex(ManifestError, "non-empty"):
            validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
