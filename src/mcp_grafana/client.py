"""Small Grafana API client for read-only operational diagnostics."""
from __future__ import annotations

import os
from typing import Any

import httpx

GRAFANA_URL = os.environ.get("GRAFANA_URL", "https://grafana.romaine.life")
_ERROR_BODY_CAP = 1200


def _check(response: httpx.Response) -> None:
    if response.is_success:
        return
    body = response.text or ""
    if len(body) > _ERROR_BODY_CAP:
        body = body[:_ERROR_BODY_CAP] + "...(truncated)"
    detail = f": {body}" if body else ""
    raise httpx.HTTPStatusError(
        f"{response.status_code} {response.reason_phrase} for "
        f"{response.request.method} {response.request.url}{detail}",
        request=response.request,
        response=response,
    )


def _clamp_limit(limit: int | None, *, default: int, maximum: int) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), maximum))


class GrafanaClient:
    def __init__(
        self,
        grafana_url: str = GRAFANA_URL,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = grafana_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    def _headers(self, service_jwt: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {service_jwt}"}

    def _request(
        self,
        service_jwt: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        with httpx.Client(
            base_url=self._url,
            headers=self._headers(service_jwt),
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = client.request(method, path, params=params)
        _check(response)
        return response.json() if response.text else {}

    def health(self, service_jwt: str) -> dict[str, Any]:
        return self._request(service_jwt, "GET", "/api/health")

    def datasources(self, service_jwt: str) -> list[dict[str, Any]]:
        body = self._request(service_jwt, "GET", "/api/datasources")
        if not isinstance(body, list):
            raise ValueError("Grafana /api/datasources returned a non-list payload")
        return body

    def list_datasources(
        self,
        service_jwt: str,
        *,
        datasource_type: str | None = None,
        name_contains: str | None = None,
        limit: int | None = 100,
    ) -> list[dict[str, Any]]:
        type_filter = datasource_type.lower() if datasource_type else None
        name_filter = name_contains.lower() if name_contains else None
        cap = _clamp_limit(limit, default=100, maximum=500)
        rows: list[dict[str, Any]] = []
        for ds in self.datasources(service_jwt):
            ds_type = ds.get("type")
            ds_name = ds.get("name")
            if type_filter and (not ds_type or ds_type.lower() != type_filter):
                continue
            if name_filter and (not ds_name or name_filter not in ds_name.lower()):
                continue
            rows.append(
                {
                    "id": ds.get("id"),
                    "uid": ds.get("uid"),
                    "name": ds_name,
                    "type": ds_type,
                    "url": ds.get("url"),
                    "access": ds.get("access"),
                    "isDefault": ds.get("isDefault"),
                    "readOnly": ds.get("readOnly"),
                }
            )
            if len(rows) >= cap:
                break
        return rows

    def resolve_datasource_uid(
        self,
        service_jwt: str,
        *,
        preferred_uid: str | None,
        datasource_type: str,
        name: str | None = None,
    ) -> str:
        if preferred_uid:
            try:
                self._request(service_jwt, "GET", f"/api/datasources/uid/{preferred_uid}")
                return preferred_uid
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise

        matches = self.list_datasources(
            service_jwt,
            datasource_type=datasource_type,
            name_contains=name,
            limit=20,
        )
        if name:
            exact = [ds for ds in matches if ds.get("name") == name]
            if exact:
                return str(exact[0]["uid"])
        if len(matches) == 1 and matches[0].get("uid"):
            return str(matches[0]["uid"])
        if not matches:
            label = f"{datasource_type} datasource"
            if name:
                label += f" named {name!r}"
            raise ValueError(f"Could not find {label}")
        names = ", ".join(f"{ds.get('name')}({ds.get('uid')})" for ds in matches)
        raise ValueError(f"Multiple {datasource_type} datasources matched; pass datasource_uid. Matches: {names}")

    def prometheus_query(
        self,
        service_jwt: str,
        *,
        query: str,
        datasource_uid: str = "prometheus",
        time: str | None = None,
        timeout: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query}
        if time:
            params["time"] = time
        if timeout:
            params["timeout"] = timeout
        uid = self.resolve_datasource_uid(
            service_jwt,
            preferred_uid=datasource_uid,
            datasource_type="prometheus",
        )
        return self._request(
            service_jwt,
            "GET",
            f"/api/datasources/proxy/uid/{uid}/api/v1/query",
            params=params,
        )

    def prometheus_query_range(
        self,
        service_jwt: str,
        *,
        query: str,
        start: str,
        end: str,
        step: str,
        datasource_uid: str = "prometheus",
        timeout: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        if timeout:
            params["timeout"] = timeout
        uid = self.resolve_datasource_uid(
            service_jwt,
            preferred_uid=datasource_uid,
            datasource_type="prometheus",
        )
        return self._request(
            service_jwt,
            "GET",
            f"/api/datasources/proxy/uid/{uid}/api/v1/query_range",
            params=params,
        )

    def prometheus_alerts(
        self,
        service_jwt: str,
        *,
        datasource_uid: str = "prometheus",
        state: str | None = "firing",
        limit: int | None = 100,
    ) -> dict[str, Any]:
        uid = self.resolve_datasource_uid(
            service_jwt,
            preferred_uid=datasource_uid,
            datasource_type="prometheus",
        )
        body = self._request(
            service_jwt,
            "GET",
            f"/api/datasources/proxy/uid/{uid}/api/v1/alerts",
        )
        alerts = body.get("data", {}).get("alerts", []) if isinstance(body, dict) else []
        cap = _clamp_limit(limit, default=100, maximum=500)
        rows = []
        for alert in alerts:
            if state and alert.get("state") != state:
                continue
            rows.append(alert)
            if len(rows) >= cap:
                break
        return {
            "status": body.get("status") if isinstance(body, dict) else None,
            "state_filter": state,
            "alert_count": len(alerts),
            "returned": len(rows),
            "alerts": rows,
        }

    def alertmanager_alerts(
        self,
        service_jwt: str,
        *,
        datasource_uid: str = "alertmanager",
        active: bool = True,
        silenced: bool = True,
        inhibited: bool = True,
        filters: list[str] | None = None,
        limit: int | None = 100,
    ) -> dict[str, Any]:
        uid = self.resolve_datasource_uid(
            service_jwt,
            preferred_uid=datasource_uid,
            datasource_type="alertmanager",
        )
        params: dict[str, Any] = {
            "active": str(active).lower(),
            "silenced": str(silenced).lower(),
            "inhibited": str(inhibited).lower(),
        }
        if filters:
            params["filter"] = filters
        body = self._request(
            service_jwt,
            "GET",
            f"/api/datasources/proxy/uid/{uid}/api/v2/alerts",
            params=params,
        )
        if not isinstance(body, list):
            raise ValueError("Alertmanager alerts endpoint returned a non-list payload")
        cap = _clamp_limit(limit, default=100, maximum=500)
        return {"alert_count": len(body), "returned": min(len(body), cap), "alerts": body[:cap]}

    def loki_query(
        self,
        service_jwt: str,
        *,
        query: str,
        datasource_uid: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = 100,
        direction: str = "backward",
    ) -> dict[str, Any]:
        uid = self.resolve_datasource_uid(
            service_jwt,
            preferred_uid=datasource_uid,
            datasource_type="loki",
            name="Loki",
        )
        params: dict[str, Any] = {
            "query": query,
            "limit": _clamp_limit(limit, default=100, maximum=1000),
            "direction": direction,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request(
            service_jwt,
            "GET",
            f"/api/datasources/proxy/uid/{uid}/loki/api/v1/query_range",
            params=params,
        )
