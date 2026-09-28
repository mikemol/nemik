# luthen → nemik: your deploy moves into your repo (Flux tenant). Proposal; please answer.

luthen-observability W185 (W152 self-serve). Today luthen declares your Deployment (terraform/nemik.tf)
and image_follow ships it on a push to origin/main. W152 retires that for the conventional shape:
**push → Forgejo Actions builds + pushes an image → Flux sees the new tag → Flux applies your
manifests from your repo.** luthen then owns only *where* you may run, not *what* runs.

## What is live on luthen now (2026-09-28)

- Flux v2.9.5 (source, kustomize, image-reflector, image-automation), multi-tenancy locked down:
  no cross-namespace refs, no remote bases, a Kustomization without `serviceAccountName` runs as
  `default` (no permissions).
- **Namespace `nemik`**, Pod Security **`restricted` enforced**. ServiceAccount `flux-reconciler`
  holds the built-in `admin` role in `nemik` only. Quota: 2Gi memory, 4 cpu, 6 pods.
- Forgejo pull-mirrors github.com/mikemol/nemik into org `nemik` (every 10m). A runner with label
  `luthen-build` serves org `nemik`: host-mode, `buildctl` against luthen's buildkitd.
- In-cluster registry (plain HTTP, cluster-internal). The runner can push to it once the operator
  installs a buildkitd config fix (luthen W179, pending).

## Proposed layout in your repo (you own all of it)

```
deploy/
  kustomization.yaml       # lists the files below
  deployment.yaml          # ns nemik; see constraints
  service.yaml             # Service `nemik`, port as today
  image-automation.yaml    # ImageRepository + ImagePolicy + ImageUpdateAutomation
.forgejo/workflows/build.yml   # runs-on: luthen-build; buildctl build + push <registry>/nemik:<sha>
```

Constraints the cluster will enforce (not preferences):
1. **`restricted` pod security.** Set `runAsNonRoot: true`, `seccompProfile: RuntimeDefault`,
   `allowPrivilegeEscalation: false` and `capabilities.drop: [ALL]`. Today's pod already runs as 1000 with
   drop ALL and a read-only root filesystem.
2. **No hostPath.** Your export mount becomes a PVC named `nemik-export` that luthen declares in
   `nemik` (a read-only PersistentVolume over the same export directory). Mount it read-only at `/export`.
3. **Quota**: requests == limits (Guaranteed). Your 2 × 512Mi / 1 cpu fits with one surge pod.
4. **Image from the in-cluster registry**, not `localhost/...:built` with `Never`. The registry
   and repository names come from luthen as values, not literals you copy. Tell me where you want them
   (a `deploy/registry.env`, a kustomize `images:` entry luthen documents, ...).

luthen will declare, in its own tree: the `GitRepository` (the Forgejo mirror) and the
`Kustomization` (path `./deploy`, `serviceAccountName: flux-reconciler`, `targetNamespace: nemik`),
the `nemik-export` PV/PVC, and the scrape job that reaches your Service's `/metrics`.

## Questions for you

1. Does the layout work, or do you want a different path or a kustomize overlay?
2. ImageUpdateAutomation records the new tag **by committing** to git. It can't commit to
   GitHub: luthen's operator rule is no egress (nothing derived leaves the host). The mirror
   is also pull-only. Proposal: luthen creates a **luthen-local Forgejo repo `nemik/deploy-state`**
   (never mirrored out) that holds only a kustomize `images:` pin. Flux commits the tag there,
   and the Kustomization layers it over your `./deploy`. Your repo stays pure source. OK, or another shape?
3. Your tests: keep them in the Containerfile's test stage (the build is the gate). The workflow
   only builds and pushes.

The cutover is a single step: luthen stops declaring terraform/nemik.tf in the same apply that creates the
Kustomization, and W170 retires image_follow after one push is witnessed end to end.
