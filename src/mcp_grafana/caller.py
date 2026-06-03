"""Per-request caller identity extraction.

The calling session pod's mcp-auth-proxy sidecar exchanges its projected
auth.romaine.life service-account token for a role=service JWT and forwards it
in X-Auth-Romaine-Token. Tool handlers pass that JWT to Grafana as the
Authorization bearer.
"""
from __future__ import annotations

from contextvars import ContextVar

SERVICE_BEARER: ContextVar[str | None] = ContextVar(
    "mcp_grafana_service_bearer",
    default=None,
)

SERVICE_BEARER_HEADER = "x-auth-romaine-token"


def current_service_bearer() -> str | None:
    return SERVICE_BEARER.get()
