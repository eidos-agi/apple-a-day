# aad health contract

Any Eidos program becomes aad-monitorable by dropping a manifest here
(`~/.config/eidos/health.d/<name>.json`). aad discovers every manifest and
probes it uniformly — no per-tool Go. See `internal/aad/health_contract.go`.

Probes are REAL, never age-based:
- **liveness** (is it running?): `launchd` label with a live PID, a listening
  `port`, or a `pidfile` whose PID answers signal 0. Optional — CLI/analyst
  tools omit it.
- **health** (is it ok?): a `url` returning 200 (and not `{"ok":false}`), or a
  `command` emitting `{"ok":bool,"detail":"..."}`.

```json
{"name":"Resource Sentinel","kind":"actuator","scope":"node",
 "repo":"eidos-agi/resource-sentinel","summary":"...",
 "liveness":{"launchd":"com.eidos.resource-sentinel"},
 "health":{"url":"http://127.0.0.1:9341/status"}}
```
