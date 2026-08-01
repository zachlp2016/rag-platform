#!/usr/bin/env python3
"""Validate the semantic route table and execute its conformance fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag_platform.semantic_routing import (
    ManifestError,
    RouteResolutionError,
    resolve,
    validate_manifest,
)


DEFAULT_MANIFEST = ROOT / "contracts" / "semantic-routing.routes.json"
DEFAULT_CASES = ROOT / "fixtures" / "semantic-routing" / "cases.v1.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ManifestError(f"{path}: expected a JSON object")
    return value


def evaluate_case(manifest: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    request = case["input"]
    try:
        result = resolve(
            manifest,
            role_key=request.get("role_key"),
            provider_name=request.get("provider_name"),
            model=request.get("model"),
        )
        return result.to_result()
    except RouteResolutionError as error:
        return {"status": "rejected", "error": error.code}


def run_cases(manifest: dict[str, Any], fixtures: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    cases = fixtures.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ManifestError("conformance fixture must contain a non-empty cases array")
    for case in cases:
        actual = evaluate_case(manifest, case)
        expected = case.get("expected")
        if actual != expected:
            failures.append(
                f"{case.get('name', '<unnamed>')}: expected {expected!r}; got {actual!r}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()

    try:
        manifest = load_json(args.manifest)
        fixtures = load_json(args.cases)
        validate_manifest(manifest)
        failures = run_cases(manifest, fixtures)
    except (OSError, json.JSONDecodeError, KeyError, ManifestError) as error:
        print(f"semantic routing contract invalid: {error}", file=sys.stderr)
        return 1

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        f"semantic routing contract valid: {manifest['route_table_version']} "
        f"({len(fixtures['cases'])} cases)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
