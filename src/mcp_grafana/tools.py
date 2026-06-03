"""Read-only Grafana MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .caller import current_service_bearer
from .client import GrafanaClient


def _service_bearer() -> str:
    bearer = current_service_bearer()
    if not bearer:
        raise ValueError(
            "service-principal authentication required: mcp-auth-proxy must forward X-Auth-Romaine-Token"
        )
    return bearer


def register_tools(mcp: FastMCP, client: GrafanaClient) -> None:
    @mcp.tool()
    def get_grafana_health() -> dict[str, Any]:
        """Get Grafana health and version status."""
        return client.health(_service_bearer())

    @mcp.tool()
    def list_datasources(
        datasource_type: str | None = None,
        name_contains: str | None = None,
        limit: int | None = 100,
    ) -> list[dict[str, Any]]:
        """List Grafana datasources with uid, name, type, URL, and default/read-only flags.

        Use `datasource_type` for exact type filters such as `prometheus`,
        `alertmanager`, or `loki`. `name_contains` filters datasource names.
        """
        return client.list_datasources(
            _service_bearer(),
            datasource_type=datasource_type,
            name_contains=name_contains,
            limit=limit,
        )

    @mcp.tool()
    def query_prometheus(
        query: str,
        datasource_uid: str = "prometheus",
        time: str | None = None,
        timeout: str | None = None,
    ) -> dict[str, Any]:
        """Run an instant PromQL query through Grafana's Prometheus datasource proxy.

        `datasource_uid` defaults to `prometheus`, matching the provisioned
        kube-prometheus-stack datasource. Pass `time` as a Unix timestamp or
        RFC3339 string when querying a specific instant.
        """
        return client.prometheus_query(
            _service_bearer(),
            query=query,
            datasource_uid=datasource_uid,
            time=time,
            timeout=timeout,
        )

    @mcp.tool()
    def query_prometheus_range(
        query: str,
        start: str,
        end: str,
        step: str,
        datasource_uid: str = "prometheus",
        timeout: str | None = None,
    ) -> dict[str, Any]:
        """Run a range PromQL query through Grafana's Prometheus datasource proxy.

        `start` and `end` may be Unix timestamps or RFC3339 strings. `step`
        accepts Prometheus durations such as `30s`, `1m`, or a seconds value.
        """
        return client.prometheus_query_range(
            _service_bearer(),
            query=query,
            start=start,
            end=end,
            step=step,
            datasource_uid=datasource_uid,
            timeout=timeout,
        )

    @mcp.tool()
    def list_prometheus_alerts(
        datasource_uid: str = "prometheus",
        state: str | None = "firing",
        limit: int | None = 100,
    ) -> dict[str, Any]:
        """List Prometheus alerts from Grafana's Prometheus datasource proxy.

        `state` defaults to `firing`; pass `None` to include all Prometheus
        alert states.
        """
        return client.prometheus_alerts(
            _service_bearer(),
            datasource_uid=datasource_uid,
            state=state,
            limit=limit,
        )

    @mcp.tool()
    def list_alertmanager_alerts(
        datasource_uid: str = "alertmanager",
        active: bool = True,
        silenced: bool = True,
        inhibited: bool = True,
        filters: list[str] | None = None,
        limit: int | None = 100,
    ) -> dict[str, Any]:
        """List Alertmanager alerts through Grafana's Alertmanager datasource proxy.

        `filters` accepts Alertmanager matcher strings such as
        `alertname=TankRunnerDown` or `namespace=~tank-operator.*`.
        """
        return client.alertmanager_alerts(
            _service_bearer(),
            datasource_uid=datasource_uid,
            active=active,
            silenced=silenced,
            inhibited=inhibited,
            filters=filters,
            limit=limit,
        )

    @mcp.tool()
    def query_loki(
        query: str,
        datasource_uid: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = 100,
        direction: str = "backward",
    ) -> dict[str, Any]:
        """Run a Loki range query through Grafana's Loki datasource proxy.

        If `datasource_uid` is omitted, the server resolves the provisioned
        `Loki` datasource by type/name. `start` and `end` may be Unix
        nanoseconds or RFC3339 strings.
        """
        return client.loki_query(
            _service_bearer(),
            query=query,
            datasource_uid=datasource_uid,
            start=start,
            end=end,
            limit=limit,
            direction=direction,
        )
