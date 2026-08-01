import json
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi.testclient import TestClient

from rag_platform.semantic_routing import CompiledRouteTable
from router.app import create_app
from router.config import (
    ConfigurationError,
    RouterSettings,
    ServiceTarget,
    load_settings,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "contracts" / "semantic-routing.routes.json").read_text(encoding="utf-8")
)


class StaticAsyncStream(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        yield self.content


class SemanticRouterTest(unittest.TestCase):
    def build_settings(self, **overrides):
        values = {
            "routes": CompiledRouteTable(MANIFEST),
            "services": {
                "forge": ServiceTarget("forge", "http://forge.test:9600"),
                "parallax": ServiceTarget("parallax", "http://parallax.test:9000"),
                "local-model": ServiceTarget(
                    "local-model", "http://local-model.test:8080"
                ),
            },
            "api_key": "router-secret",
        }
        values.update(overrides)
        return RouterSettings(**values)

    def route_headers(self, **overrides):
        headers = {
            "X-RAG-Router-Key": "router-secret",
            "X-RAG-Contract": "rag.semantic-routing",
            "X-RAG-Schema-Version": "1",
            "X-RAG-Route-Table-Version": "2026-08-01.1",
            "X-RAG-Request-ID": "usage-event-123",
            "X-RAG-Role-Key": "reviewer",
            "X-RAG-Provider-Name": "Argus",
        }
        headers.update(overrides)
        return headers

    def test_routes_all_declared_provider_packets(self):
        cases = [
            (
                {"X-RAG-Role-Key": "reviewer", "X-RAG-Provider-Name": "Argus"},
                "forge-consultant",
                "http://forge.test:9600/v1/chat/completions",
                "forge-rag",
            ),
            (
                {"X-RAG-Role-Key": "builder", "X-RAG-Provider-Name": "Hephaestus"},
                "qwen3.6-27b",
                "http://local-model.test:8080/v1/chat/completions",
                "hephaestus-direct",
            ),
            (
                {"X-RAG-Role-Key": "", "X-RAG-Provider-Name": "Finance Consultant"},
                "finance-consultant",
                "http://parallax.test:9000/v1/chat/completions",
                "parallax-rag",
            ),
        ]

        for identity_headers, model, expected_url, expected_route in cases:
            with self.subTest(route=expected_route):
                captured = []

                def upstream(request):
                    captured.append(request)
                    content = json.dumps(
                        {"choices": [{"message": {"content": "ok"}}]}
                    ).encode()
                    return httpx.Response(
                        200,
                        headers={"content-type": "application/json"},
                        stream=StaticAsyncStream(content),
                    )

                app = create_app(
                    self.build_settings(),
                    upstream_transport=httpx.MockTransport(upstream),
                )
                headers = self.route_headers(**identity_headers)
                headers["Authorization"] = "Bearer upstream-provider-key"
                headers["X-Caller-Metadata"] = "preserved"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": False,
                }

                with TestClient(app) as client:
                    response = client.post(
                        "/v1/chat/completions?probe=1",
                        headers=headers,
                        json=payload,
                    )

                self.assertEqual(200, response.status_code)
                self.assertEqual(expected_route, response.headers["x-rag-resolved-route"])
                self.assertEqual(1, len(captured))
                request = captured[0]
                self.assertEqual(f"{expected_url}?probe=1", str(request.url))
                self.assertEqual(payload, json.loads(request.content))
                self.assertEqual(
                    "Bearer upstream-provider-key", request.headers["authorization"]
                )
                self.assertEqual("preserved", request.headers["x-caller-metadata"])
                self.assertNotIn("x-rag-router-key", request.headers)
                self.assertNotIn("x-rag-provider-name", request.headers)
                self.assertNotIn("x-rag-role-key", request.headers)

    def test_streams_upstream_bytes_and_preserves_status(self):
        stream_body = b"data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}\n\ndata: [DONE]\n\n"

        def upstream(_request):
            return httpx.Response(
                206,
                headers={"content-type": "text/event-stream"},
                stream=StaticAsyncStream(stream_body),
            )

        app = create_app(
            self.build_settings(),
            upstream_transport=httpx.MockTransport(upstream),
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers=self.route_headers(),
                json={"model": "forge-consultant", "messages": [], "stream": True},
            )

        self.assertEqual(206, response.status_code)
        self.assertEqual("text/event-stream", response.headers["content-type"])
        self.assertEqual(stream_body, response.content)

    def test_requires_router_authentication(self):
        called = False

        def upstream(_request):
            nonlocal called
            called = True
            return httpx.Response(200)

        app = create_app(
            self.build_settings(),
            upstream_transport=httpx.MockTransport(upstream),
        )
        headers = self.route_headers()
        headers.pop("X-RAG-Router-Key")
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers=headers,
                json={"model": "forge-consultant", "messages": []},
            )

        self.assertEqual(401, response.status_code)
        self.assertEqual("unauthorized", response.json()["error"]["code"])
        self.assertFalse(called)

    def test_rejects_contract_version_drift(self):
        app = create_app(
            self.build_settings(),
            upstream_transport=httpx.MockTransport(lambda _: httpx.Response(200)),
        )
        headers = self.route_headers(**{"X-RAG-Route-Table-Version": "stale"})
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers=headers,
                json={"model": "forge-consultant", "messages": []},
            )

        self.assertEqual(409, response.status_code)
        self.assertEqual(
            "routing_contract_mismatch", response.json()["error"]["code"]
        )

    def test_rejects_model_mismatch_without_contacting_upstream(self):
        called = False

        def upstream(_request):
            nonlocal called
            called = True
            return httpx.Response(200)

        app = create_app(
            self.build_settings(),
            upstream_transport=httpx.MockTransport(upstream),
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers=self.route_headers(),
                json={"model": "qwen3.6-27b", "messages": []},
            )

        self.assertEqual(422, response.status_code)
        self.assertEqual("model_mismatch", response.json()["error"]["code"])
        self.assertFalse(called)

    def test_health_exposes_contract_not_endpoints(self):
        app = create_app(
            self.build_settings(),
            upstream_transport=httpx.MockTransport(lambda _: httpx.Response(200)),
        )
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual("2026-08-01.1", response.json()["route_table_version"])
        self.assertNotIn("9600", response.text)


class RouterConfigurationTest(unittest.TestCase):
    def test_loads_complete_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory) / "deployment.json"
            deployment.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "services": {
                            "forge": {"base_url": "http://127.0.0.1:9600"},
                            "parallax": {"base_url": "http://127.0.0.1:9000"},
                            "local-model": {"base_url": "http://127.0.0.1:8080"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            settings = load_settings(
                {
                    "RAG_ROUTER_API_KEY": "secret",
                    "RAG_ROUTER_DEPLOYMENT": str(deployment),
                }
            )

        self.assertEqual(
            {"forge", "parallax", "local-model"}, set(settings.services)
        )

    def test_rejects_incomplete_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            deployment = Path(directory) / "deployment.json"
            deployment.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "services": {
                            "forge": {"base_url": "http://127.0.0.1:9600"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "missing services"):
                load_settings(
                    {
                        "RAG_ROUTER_API_KEY": "secret",
                        "RAG_ROUTER_DEPLOYMENT": str(deployment),
                    }
                )


if __name__ == "__main__":
    unittest.main()
