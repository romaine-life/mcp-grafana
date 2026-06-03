# mcp-grafana

In-cluster MCP server for read-only Grafana, Prometheus, Alertmanager, and Loki
diagnostics.

## Tools

- `get_grafana_health()` - Grafana health/status.
- `list_datasources()` - compact datasource inventory.
- `query_prometheus()` - instant PromQL through Grafana's Prometheus datasource proxy.
- `query_prometheus_range()` - range PromQL through Grafana's Prometheus datasource proxy.
- `list_prometheus_alerts()` - Prometheus alert state from the datasource proxy.
- `list_alertmanager_alerts()` - Alertmanager alerts from the datasource proxy.
- `query_loki()` - Loki range query through the Grafana datasource proxy.

## Auth

Inbound transport is gated by `kube-rbac-proxy` using Kubernetes
TokenReview/SubjectAccessReview, matching the other romaine.life MCP servers.

Outbound calls to Grafana use the calling session pod's `auth.romaine.life`
service-principal JWT, forwarded by the pod's `mcp-auth-proxy` sidecar in the
`X-Auth-Romaine-Token` header. Grafana validates that JWT via its `[auth.jwt]`
configuration, so this server does not mint or store a separate Grafana service
account token.
