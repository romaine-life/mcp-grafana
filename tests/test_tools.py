from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_grafana.caller import SERVICE_BEARER  # noqa: E402
from mcp_grafana.tools import register_tools  # noqa: E402


@contextlib.contextmanager
def _bearer(jwt: str | None):
    token = SERVICE_BEARER.set(jwt)
    try:
        yield
    finally:
        SERVICE_BEARER.reset(token)


def _get_tool(mcp: FastMCP, name: str):
    for tool in mcp._tool_manager._tools.values():
        if tool.name == name:
            return tool.fn
    raise KeyError(f"tool {name!r} not registered")


@pytest.fixture()
def mcp_client_pair():
    mcp = FastMCP("test-grafana-mcp")
    client = MagicMock()
    register_tools(mcp, client)
    return mcp, client


def test_tools_require_service_bearer(mcp_client_pair) -> None:
    mcp, _ = mcp_client_pair
    fn = _get_tool(mcp, "get_grafana_health")
    with _bearer(None):
        with pytest.raises(ValueError, match="service-principal authentication required"):
            fn()


def test_query_prometheus_delegates_to_client(mcp_client_pair) -> None:
    mcp, client = mcp_client_pair
    client.prometheus_query.return_value = {"status": "success"}
    fn = _get_tool(mcp, "query_prometheus")
    with _bearer("eyJ.fake.jwt"):
        result = fn(query="up", datasource_uid="prometheus", time="123", timeout="10s")
    client.prometheus_query.assert_called_once_with(
        "eyJ.fake.jwt",
        query="up",
        datasource_uid="prometheus",
        time="123",
        timeout="10s",
    )
    assert result == {"status": "success"}


def test_list_alertmanager_alerts_delegates_to_client(mcp_client_pair) -> None:
    mcp, client = mcp_client_pair
    client.alertmanager_alerts.return_value = {"alerts": []}
    fn = _get_tool(mcp, "list_alertmanager_alerts")
    with _bearer("jwt"):
        result = fn(filters=["namespace=tank-operator"], limit=5)
    client.alertmanager_alerts.assert_called_once_with(
        "jwt",
        datasource_uid="alertmanager",
        active=True,
        silenced=True,
        inhibited=True,
        filters=["namespace=tank-operator"],
        limit=5,
    )
    assert result == {"alerts": []}
