"""Authenticated streaming gateway for semantic RAG routing."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import secrets
from time import perf_counter
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from rag_platform.semantic_routing import RouteResolutionError
from router.config import RouterSettings, load_settings


logger = logging.getLogger("rag_platform.semantic_router")

ROUTER_KEY_HEADER = "x-rag-router-key"
CONTRACT_HEADER = "x-rag-contract"
SCHEMA_VERSION_HEADER = "x-rag-schema-version"
ROUTE_TABLE_VERSION_HEADER = "x-rag-route-table-version"
ROLE_KEY_HEADER = "x-rag-role-key"
PROVIDER_NAME_HEADER = "x-rag-provider-name"
REQUEST_ID_HEADER = "x-rag-request-id"

ROUTING_HEADERS = {
    ROUTER_KEY_HEADER,
    CONTRACT_HEADER,
    SCHEMA_VERSION_HEADER,
    ROUTE_TABLE_VERSION_HEADER,
    ROLE_KEY_HEADER,
    PROVIDER_NAME_HEADER,
    REQUEST_ID_HEADER,
}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def create_app(
    settings: RouterSettings | None = None,
    *,
    upstream_transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(
            connect=settings.connect_timeout_seconds,
            read=settings.read_timeout_seconds,
            write=settings.read_timeout_seconds,
            pool=settings.connect_timeout_seconds,
        )
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        app.state.upstream_client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            transport=upstream_transport,
            follow_redirects=False,
        )
        try:
            yield
        finally:
            await app.state.upstream_client.aclose()

    app = FastAPI(
        title="RAG Semantic Router",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "contract": settings.routes.contract,
            "schema_version": settings.routes.schema_version,
            "route_table_version": settings.routes.route_table_version,
            "services": sorted(settings.routes.service_ids),
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        started_at = perf_counter()
        authentication_error = _authenticate(request, settings)
        if authentication_error:
            return authentication_error

        contract_error = _validate_contract_headers(request, settings)
        if contract_error:
            return contract_error

        request_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
        if not request_id:
            return _error(400, "missing_request_id", "Routing request id is required")

        declared_length = request.headers.get("content-length")
        if declared_length and declared_length.isdigit():
            if int(declared_length) > settings.max_request_bytes:
                return _error(413, "request_too_large", "Request exceeds router limit")

        body = await request.body()
        if len(body) > settings.max_request_bytes:
            return _error(413, "request_too_large", "Request exceeds router limit")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error(400, "invalid_json", "Request body must be valid JSON")
        if not isinstance(payload, dict):
            return _error(400, "invalid_json", "Request body must be a JSON object")

        try:
            resolution = settings.routes.resolve(
                role_key=request.headers.get(ROLE_KEY_HEADER),
                provider_name=request.headers.get(PROVIDER_NAME_HEADER),
                model=payload.get("model"),
            )
        except RouteResolutionError as error:
            status = 400 if error.code.startswith("invalid_") else 422
            return _error(status, error.code, "Semantic route rejected")

        target = settings.services.get(resolution.service_id)
        if target is None:
            logger.error(
                "semantic_route_target_missing",
                extra={"route_id": resolution.route_id, "request_id": request_id},
            )
            return _error(503, "route_unavailable", "Resolved service is unavailable")

        upstream_url = f"{target.base_url}{request.url.path}"
        client: httpx.AsyncClient = request.app.state.upstream_client
        upstream_request = client.build_request(
            method="POST",
            url=upstream_url,
            content=body,
            headers=_upstream_request_headers(request),
            params=request.query_params,
        )
        try:
            upstream = await client.send(upstream_request, stream=True)
        except httpx.TimeoutException:
            return _error(504, "upstream_timeout", "Resolved service timed out")
        except httpx.RequestError:
            return _error(502, "upstream_unavailable", "Resolved service is unavailable")

        elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
        logger.info(
            "semantic_route_resolved",
            extra={
                "request_id": request_id,
                "route_id": resolution.route_id,
                "service_id": resolution.service_id,
                "matched_by": resolution.matched_by,
                "diagnostics": resolution.diagnostics,
                "upstream_status": upstream.status_code,
                "dispatch_ms": elapsed_ms,
            },
        )

        response_headers = _upstream_response_headers(upstream)
        response_headers["X-RAG-Resolved-Route"] = resolution.route_id
        response_headers["X-RAG-Matched-By"] = resolution.matched_by
        if resolution.diagnostics:
            response_headers["X-RAG-Route-Diagnostics"] = ",".join(
                resolution.diagnostics
            )

        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
            background=BackgroundTask(upstream.aclose),
        )

    return app


def _authenticate(request: Request, settings: RouterSettings) -> JSONResponse | None:
    provided = request.headers.get(ROUTER_KEY_HEADER, "")
    if not provided or not secrets.compare_digest(provided, settings.api_key):
        return _error(401, "unauthorized", "Router authentication failed")
    return None


def _validate_contract_headers(
    request: Request, settings: RouterSettings
) -> JSONResponse | None:
    expected = {
        CONTRACT_HEADER: settings.routes.contract,
        SCHEMA_VERSION_HEADER: str(settings.routes.schema_version),
        ROUTE_TABLE_VERSION_HEADER: settings.routes.route_table_version,
    }
    for header, expected_value in expected.items():
        if request.headers.get(header, "").strip() != expected_value:
            return _error(
                409,
                "routing_contract_mismatch",
                "Routing contract version is not accepted",
            )
    return None


def _upstream_request_headers(request: Request) -> dict[str, str]:
    excluded = ROUTING_HEADERS | HOP_BY_HOP_HEADERS | {"host", "content-length"}
    return {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in excluded
    }


def _upstream_response_headers(response: httpx.Response) -> dict[str, str]:
    excluded = HOP_BY_HOP_HEADERS | {"content-length"}
    return {
        name: value
        for name, value in response.headers.items()
        if name.lower() not in excluded
    }


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
    )
