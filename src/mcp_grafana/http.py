"""HTTP entrypoint - streamable-http transport.

Inbound transport gate is kube-rbac-proxy. Per-caller identity is the
auth.romaine.life service-principal JWT forwarded by the calling pod's
mcp-auth-proxy sidecar in X-Auth-Romaine-Token.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from .caller import SERVICE_BEARER, SERVICE_BEARER_HEADER
from .client import GrafanaClient
from .tools import register_tools

log = logging.getLogger(__name__)


class CallerIdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        bearer = request.headers.get(SERVICE_BEARER_HEADER)
        if bearer is not None:
            bearer = bearer.strip() or None
        token = SERVICE_BEARER.set(bearer)
        try:
            return await call_next(request)
        finally:
            SERVICE_BEARER.reset(token)


def build_app() -> Starlette:
    mcp = FastMCP(
        "grafana-mcp",
        stateless_http=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
    register_tools(mcp, GrafanaClient())

    async def healthz(_: Request) -> Response:
        return Response("ok", media_type="text/plain")

    async def delete_session(_: Request) -> Response:
        return Response(status_code=200)

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/", delete_session, methods=["DELETE"]),
            Mount("/", app=mcp.streamable_http_app()),
        ],
        middleware=[Middleware(CallerIdentityMiddleware)],
        lifespan=lifespan,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(build_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
