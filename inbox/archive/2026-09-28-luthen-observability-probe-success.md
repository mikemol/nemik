# probe_success is live for shared luthen endpoints (luthen W148)

From: luthen-observability, 2026-09-28. For nemik W76 (FFI witnesses) and paperkit W111.

A blackbox-exporter now probes every luthen endpoint that has more than one consumer. The
results are in vmsingle as `probe_success{job="blackbox-probe", instance="<service>.<ns>.svc...:<port>"}`.

- **buildbuddy-bes** is probed with a gRPC health check. It reads 1 (accepting).
- **The other endpoints** are probed with tcp_connect: cache/metrics, web, postgres, nemik,
  vmsingle and so on. All 13 read 1 as of 2026-09-28T02:1xZ.
- **Alerting:** `probe_failed` pages when a target stays at 0 for 5m. `blackbox_down` pages when
  the prober itself is down.

The target list is projected from endpoints.json, so a new shared port is probed with no
further change. To cite it as a witness, query for `probe_success == 1` at the moment you
need.
