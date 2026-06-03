from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_grafana.client import GrafanaClient  # noqa: E402


def _client(handler):
    return GrafanaClient(
        "https://grafana.example.test",
        transport=httpx.MockTransport(handler),
    )


def test_prometheus_query_uses_datasource_proxy_and_bearer() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/datasources/proxy/uid/prometheus/api/v1/query"
        assert request.headers["Authorization"] == "Bearer jwt"
        assert request.url.params["query"] == "up"
        return httpx.Response(200, json={"status": "success"})

    result = _client(handler).prometheus_query("jwt", query="up")

    assert result == {"status": "success"}
    assert [request.url.path for request in requests] == [
        "/api/datasources/proxy/uid/prometheus/api/v1/query",
    ]


def test_loki_query_uses_default_loki_uid() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/datasources/proxy/uid/loki/loki/api/v1/query_range"
        assert request.url.params["query"] == "{namespace=\"tank-operator\"}"
        assert request.url.params["limit"] == "50"
        return httpx.Response(200, json={"status": "success"})

    result = _client(handler).loki_query(
        "jwt",
        query='{namespace="tank-operator"}',
        limit=50,
    )

    assert result == {"status": "success"}
    assert [request.url.path for request in requests] == [
        "/api/datasources/proxy/uid/loki/loki/api/v1/query_range",
    ]


def test_prometheus_alerts_filters_firing_and_limits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/datasources/proxy/uid/prometheus/api/v1/alerts"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "alerts": [
                        {"labels": {"alertname": "A"}, "state": "pending"},
                        {"labels": {"alertname": "B"}, "state": "firing"},
                        {"labels": {"alertname": "C"}, "state": "firing"},
                    ]
                },
            },
        )

    result = _client(handler).prometheus_alerts("jwt", state="firing", limit=1)

    assert result["alert_count"] == 3
    assert result["returned"] == 1
    assert result["alerts"][0]["labels"]["alertname"] == "B"
