# nemik's public base URL: none yet (nemik:W2030)

W941 wants actors and cards to have http(s) identifiers a peer can fetch, which needs a base URL for
the pod. This reads what the repo's deployment says about one, and records luthen-observability's
answer about the route on its side.

## What the manifests say

`deploy/` holds four files, applied by luthen's Flux Kustomization into the namespace `nemik`
(`deploy/kustomization.yaml`): the Deployment, the Service, the image automation, and the
kustomization itself.

- **No Ingress, no HTTPRoute, no host name.** A search of `deploy/` for ingress, host, hostname,
  httproute, domain and any `http(s)://` finds only the in-cluster registry
  (`registry.buildbuddy.svc.cluster.local:5000/nemik`, `deploy/image-automation.yaml`).
- **One ClusterIP Service `nemik`, port 8750 (`http`)**, and, from nemik:W2494, a headless
  `nemik-headless` on the same port for luthen's per-pod scrape. Both are reachable only inside the
  cluster: `http://nemik.nemik.svc.cluster.local:8750/` (the server container's `--port 8750`).
- The pod serves a published snapshot (`/srv`, read-only) plus `/metrics` and `/healthz`.

## What luthen-observability says (2026-11-26, read from its source)

- **No public route exists.** luthen's `endpoints.json` carries `nemik-http` (service nemik, port
  8750, namespace nemik) with consumers "operator (browser: dependency-graph view)" and "vmagent
  scrape /metrics", and its own note: "GET only, no auth; ClusterIP only (D3)". Nothing a peer
  outside the cluster can fetch is declared. The operator's browser reaches it from the host's own
  network, by an address `endpoints.json` holds under the name `nemik-http`: cite it by that name,
  never by an address copied elsewhere, which reads as authoritative and can move.
- **Stability.** The in-cluster name above is as stable as the Service name and the namespace,
  which are nemik's. The address behind `nemik-http` is allocated and can move through
  `endpoints.json` and its projector.

## What follows for identifiers

Mint identifiers against the in-cluster name, or against a name that a declared route would give,
never against an address. For a peer outside the cluster the honest answer today is **none yet**.
W941 stays blocked on nemik:W964, the operator's answer on the base URL, which none-yet does not
replace.

## If an externally fetchable URL is wanted

That is a design question on luthen-observability's side: the standing options for public exposure
there are Tailscale Funnel, a GCP relay or static GCS (never Cloudflare), and the view has no auth,
so what may be public is the first question. luthen will card it on nemik's word.
