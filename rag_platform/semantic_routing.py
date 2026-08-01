"""Provider-neutral evaluator for the versioned semantic routing contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import re
import unicodedata
from typing import Any


IDENTITY_SEPARATOR = re.compile(r"[\s_-]+", re.UNICODE)


class ManifestError(ValueError):
    """Raised when a route table cannot safely be activated."""


class RouteResolutionError(ValueError):
    """Raised when an individual request must be rejected."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Resolution:
    route_id: str
    service_id: str
    retrieval: bool
    canonical_model: str
    matched_by: str
    diagnostics: list[str]

    def to_result(self) -> dict[str, Any]:
        return {"status": "resolved", **asdict(self)}


def normalize_identity(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RouteResolutionError("invalid_identity")
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    value = IDENTITY_SEPARATOR.sub(" ", value)
    return value or None


def normalize_model(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RouteResolutionError("invalid_model")
    return value.strip() or None


def validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    _require_exact_keys(
        manifest,
        required={
            "contract",
            "schema_version",
            "route_table_version",
            "policy",
            "routes",
        },
        optional={"$schema"},
        label="manifest",
    )
    if manifest.get("contract") != "rag.semantic-routing":
        raise ManifestError("contract must be rag.semantic-routing")
    if manifest.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")

    version = manifest.get("route_table_version")
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}\.[1-9][0-9]*", version
    ):
        raise ManifestError("route_table_version must use YYYY-MM-DD.N")

    expected_policy = {
        "unknown_identity": "reject",
        "identity_conflict": "role_wins_with_diagnostic",
        "model_mismatch": "reject",
    }
    if not isinstance(manifest.get("policy"), dict):
        raise ManifestError("policy must be an object")
    _require_exact_keys(
        manifest["policy"],
        required=set(expected_policy),
        label="policy",
    )
    if manifest.get("policy") != expected_policy:
        raise ManifestError("policy does not match semantic routing contract version 1")

    routes = manifest.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ManifestError("routes must be a non-empty array")

    route_ids: set[str] = set()
    role_index: dict[str, str] = {}
    provider_index: dict[str, str] = {}

    for route in routes:
        if not isinstance(route, dict):
            raise ManifestError("each route must be an object")
        _require_exact_keys(
            route,
            required={"route_id", "match", "target"},
            label="route",
        )
        route_id = route.get("route_id")
        if not isinstance(route_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9._-]*", route_id
        ):
            raise ManifestError("route_id must be a lowercase logical identifier")
        if route_id in route_ids:
            raise ManifestError(f"duplicate route_id: {route_id}")
        route_ids.add(route_id)

        match = route.get("match")
        if not isinstance(match, dict):
            raise ManifestError(f"{route_id}: match must be an object")
        _require_exact_keys(
            match,
            required=set(),
            optional={"role_keys", "provider_names"},
            label=f"{route_id}: match",
        )
        role_keys = _string_list(match.get("role_keys"), f"{route_id}: role_keys")
        provider_names = _string_list(
            match.get("provider_names"), f"{route_id}: provider_names"
        )
        if not role_keys and not provider_names:
            raise ManifestError(f"{route_id}: at least one identity alias is required")

        _register_aliases(role_index, role_keys, route_id, "role")
        _register_aliases(provider_index, provider_names, route_id, "provider")

        target = route.get("target")
        if not isinstance(target, dict):
            raise ManifestError(f"{route_id}: target must be an object")
        _require_exact_keys(
            target,
            required={
                "service_id",
                "interface",
                "retrieval",
                "canonical_model",
                "accepted_models",
            },
            label=f"{route_id}: target",
        )
        service_id = target.get("service_id")
        if not isinstance(service_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9._-]*", service_id
        ):
            raise ManifestError(f"{route_id}: invalid service_id")
        if target.get("interface") != "openai_chat_completions":
            raise ManifestError(f"{route_id}: unsupported target interface")
        if not isinstance(target.get("retrieval"), bool):
            raise ManifestError(f"{route_id}: retrieval must be boolean")

        canonical_model = target.get("canonical_model")
        accepted_models = _string_list(
            target.get("accepted_models"), f"{route_id}: accepted_models", required=True
        )
        if not isinstance(canonical_model, str) or not canonical_model.strip():
            raise ManifestError(f"{route_id}: canonical_model is required")
        if canonical_model != canonical_model.strip():
            raise ManifestError(f"{route_id}: canonical_model must be trimmed")
        if accepted_models != target["accepted_models"]:
            raise ManifestError(f"{route_id}: accepted_models must be trimmed")
        if canonical_model.strip() not in accepted_models:
            raise ManifestError(
                f"{route_id}: canonical_model must appear in accepted_models"
            )


class CompiledRouteTable:
    """Validated immutable-in-practice route indexes loaded once per process."""

    def __init__(self, manifest: dict[str, Any]):
        validate_manifest(manifest)
        self._manifest = deepcopy(manifest)
        self._routes = {
            route["route_id"]: route for route in self._manifest["routes"]
        }
        self._role_index, self._provider_index = _identity_indexes(self._manifest)

    @property
    def contract(self) -> str:
        return self._manifest["contract"]

    @property
    def schema_version(self) -> int:
        return self._manifest["schema_version"]

    @property
    def route_table_version(self) -> str:
        return self._manifest["route_table_version"]

    @property
    def service_ids(self) -> frozenset[str]:
        return frozenset(route["target"]["service_id"] for route in self._routes.values())

    def resolve(
        self, *, role_key: Any, provider_name: Any, model: Any
    ) -> Resolution:
        normalized_role = normalize_identity(role_key)
        normalized_provider = normalize_identity(provider_name)
        role_route = (
            self._role_index.get(normalized_role) if normalized_role else None
        )
        provider_route = (
            self._provider_index.get(normalized_provider)
            if normalized_provider
            else None
        )

        diagnostics: list[str] = []
        if role_route:
            route_id = role_route
            matched_by = "role"
            if provider_route and provider_route != role_route:
                diagnostics.append("identity_conflict")
        elif provider_route:
            route_id = provider_route
            matched_by = "provider"
        else:
            raise RouteResolutionError("route_not_found")

        route = self._routes[route_id]
        target = route["target"]
        normalized_model = normalize_model(model)
        if normalized_model not in target["accepted_models"]:
            raise RouteResolutionError("model_mismatch")

        return Resolution(
            route_id=route_id,
            service_id=target["service_id"],
            retrieval=target["retrieval"],
            canonical_model=target["canonical_model"],
            matched_by=matched_by,
            diagnostics=diagnostics,
        )


def resolve(
    manifest: dict[str, Any], *, role_key: Any, provider_name: Any, model: Any
) -> Resolution:
    return CompiledRouteTable(manifest).resolve(
        role_key=role_key,
        provider_name=provider_name,
        model=model,
    )


def _string_list(value: Any, label: str, *, required: bool = False) -> list[str]:
    if value is None:
        if not required:
            return []
        raise ManifestError(f"{label} must be a non-empty string array")
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{label} must be a non-empty string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ManifestError(f"{label} must contain non-empty strings")
    stripped = [item.strip() for item in value]
    if len(stripped) != len(set(stripped)):
        raise ManifestError(f"{label} contains duplicate values")
    return stripped


def _require_exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    label: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required - value.keys()
    if missing:
        raise ManifestError(f"{label} missing keys: {', '.join(sorted(missing))}")
    unknown = value.keys() - required - optional
    if unknown:
        raise ManifestError(f"{label} has unknown keys: {', '.join(sorted(unknown))}")


def _register_aliases(
    index: dict[str, str], aliases: list[str], route_id: str, alias_type: str
) -> None:
    normalized_in_route: set[str] = set()
    for alias in aliases:
        normalized = normalize_identity(alias)
        if normalized is None:
            raise ManifestError(f"{route_id}: empty normalized {alias_type} alias")
        if normalized in normalized_in_route:
            raise ManifestError(
                f"{route_id}: duplicate normalized {alias_type} alias: {alias}"
            )
        normalized_in_route.add(normalized)
        owner = index.get(normalized)
        if owner and owner != route_id:
            raise ManifestError(
                f"normalized {alias_type} alias {alias!r} belongs to {owner} and {route_id}"
            )
        index[normalized] = route_id


def _identity_indexes(
    manifest: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str]]:
    role_index: dict[str, str] = {}
    provider_index: dict[str, str] = {}
    for route in manifest["routes"]:
        route_id = route["route_id"]
        match = route["match"]
        _register_aliases(role_index, match.get("role_keys", []), route_id, "role")
        _register_aliases(
            provider_index,
            match.get("provider_names", []),
            route_id,
            "provider",
        )
    return role_index, provider_index
