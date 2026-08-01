"""Strict startup configuration for the semantic routing gateway."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from rag_platform.semantic_routing import CompiledRouteTable, ManifestError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTE_TABLE = ROOT / "contracts" / "semantic-routing.routes.json"
DEFAULT_DEPLOYMENT = ROOT / "router" / "deployment.local.json"


class ConfigurationError(ValueError):
    """Raised when the gateway cannot safely start."""


@dataclass(frozen=True)
class ServiceTarget:
    service_id: str
    base_url: str


@dataclass(frozen=True)
class RouterSettings:
    routes: CompiledRouteTable
    services: Mapping[str, ServiceTarget]
    api_key: str
    max_request_bytes: int = 16 * 1024 * 1024
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 900.0


def load_settings(environment: Mapping[str, str] | None = None) -> RouterSettings:
    environment = environment or os.environ
    route_table_path = Path(
        environment.get("RAG_ROUTER_ROUTE_TABLE", str(DEFAULT_ROUTE_TABLE))
    ).expanduser()
    deployment_path = Path(
        environment.get("RAG_ROUTER_DEPLOYMENT", str(DEFAULT_DEPLOYMENT))
    ).expanduser()
    api_key = environment.get("RAG_ROUTER_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError("RAG_ROUTER_API_KEY is required")

    try:
        routes = CompiledRouteTable(_load_json(route_table_path))
    except (OSError, json.JSONDecodeError, ManifestError) as error:
        raise ConfigurationError(f"invalid route table: {error}") from error

    services = _load_deployment(deployment_path)
    missing_services = routes.service_ids - services.keys()
    if missing_services:
        missing = ", ".join(sorted(missing_services))
        raise ConfigurationError(f"deployment is missing services: {missing}")

    return RouterSettings(
        routes=routes,
        services=services,
        api_key=api_key,
        max_request_bytes=_positive_int(
            environment.get("RAG_ROUTER_MAX_REQUEST_BYTES"),
            default=16 * 1024 * 1024,
            label="RAG_ROUTER_MAX_REQUEST_BYTES",
        ),
        connect_timeout_seconds=_positive_float(
            environment.get("RAG_ROUTER_CONNECT_TIMEOUT_SECONDS"),
            default=5.0,
            label="RAG_ROUTER_CONNECT_TIMEOUT_SECONDS",
        ),
        read_timeout_seconds=_positive_float(
            environment.get("RAG_ROUTER_READ_TIMEOUT_SECONDS"),
            default=900.0,
            label="RAG_ROUTER_READ_TIMEOUT_SECONDS",
        ),
    )


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path}: expected a JSON object")
    return value


def _load_deployment(path: Path) -> dict[str, ServiceTarget]:
    try:
        deployment = _load_json(path)
    except (OSError, json.JSONDecodeError, ConfigurationError) as error:
        raise ConfigurationError(f"invalid deployment: {error}") from error

    if set(deployment) != {"schema_version", "services"}:
        raise ConfigurationError(
            "deployment must contain only schema_version and services"
        )
    if deployment["schema_version"] != 1:
        raise ConfigurationError("deployment schema_version must be 1")
    raw_services = deployment["services"]
    if not isinstance(raw_services, dict) or not raw_services:
        raise ConfigurationError("deployment services must be a non-empty object")

    services: dict[str, ServiceTarget] = {}
    for service_id, raw_target in raw_services.items():
        if not isinstance(service_id, str) or not service_id.strip():
            raise ConfigurationError("deployment service ids must be non-empty strings")
        if not isinstance(raw_target, dict) or set(raw_target) != {"base_url"}:
            raise ConfigurationError(
                f"deployment service {service_id!r} must contain only base_url"
            )
        base_url = _validated_base_url(raw_target["base_url"], service_id)
        services[service_id] = ServiceTarget(
            service_id=service_id,
            base_url=base_url,
        )
    return services


def _validated_base_url(value: Any, service_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"deployment service {service_id!r} needs base_url")
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError(
            f"deployment service {service_id!r} must use an absolute HTTP(S) URL"
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError(
            f"deployment service {service_id!r} base_url cannot contain "
            "credentials, query, or fragment"
        )
    return value


def _positive_int(value: str | None, *, default: int, label: str) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{label} must be a positive integer") from error
    if parsed <= 0:
        raise ConfigurationError(f"{label} must be a positive integer")
    return parsed


def _positive_float(value: str | None, *, default: float, label: str) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{label} must be positive") from error
    if parsed <= 0:
        raise ConfigurationError(f"{label} must be positive")
    return parsed
