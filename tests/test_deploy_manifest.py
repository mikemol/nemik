# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W504: the pod keeps luthen-observability's constraints and names real commands.

nemik is shipped as snapshots: a builder container publishes into a shared volume and
a server container only serves it (W500). luthen-observability deploys it and agreed
that shape on four conditions, each a test here, so a later edit that breaks one fails
in the repo and not in the cluster. The commands the manifest runs are held to the real
command lines, so a flag renamed in the tool cannot leave the pod crash-looping.
"""

from pathlib import Path
from typing import Any

import installed
import yaml

from nemik import staticserve

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT = ROOT / "deploy" / "deployment.yaml"
TENANT_QUOTA_MI = 5 * 1024  # luthen's namespace quota on limits.memory (5Gi)
SNAPSHOT_MI = 77  # one published snapshot, measured 2026-10-26 (W1087)
SNAPSHOTS_AT_PEAK = 5  # the three kept, the one served, and the one being written


def _spec() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load(DEPLOYMENT.read_text())
    return doc


def _pod() -> dict[str, Any]:
    pod: dict[str, Any] = _spec()["spec"]["template"]["spec"]
    return pod


def _containers() -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in _pod()["containers"]}


def _mi(quantity: str) -> float:
    units = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024}
    for suffix, factor in units.items():
        if quantity.endswith(suffix):
            return float(quantity.removesuffix(suffix)) * factor
    message = f"unrecognised memory quantity {quantity!r}"
    raise AssertionError(message)


def _mounts(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["name"]: m for m in container["volumeMounts"]}


def test_the_pod_is_a_builder_and_a_server() -> None:
    """The pod has exactly the two containers luthen's workloads row names."""
    assert set(_containers()) == {"server", "builder"}


def test_the_snapshot_volume_is_disk_backed_with_a_size_limit() -> None:
    """(a) Published files are not charged to a container's memory."""
    volumes = {v["name"]: v for v in _pod()["volumes"]}
    empty = volumes["snapshots"]["emptyDir"]
    assert "medium" not in empty, "a Memory emptyDir would charge container memory"
    assert empty.get("sizeLimit"), "the snapshot volume has no declared size limit"


def test_the_snapshot_volume_holds_every_snapshot_a_build_has_at_its_peak() -> None:
    """The kept snapshots and the one being written fit: two evictions came of 256Mi."""
    text = DEPLOYMENT.read_text()
    declared = text.split("- name: snapshots\n          emptyDir: {sizeLimit: ")[1]
    assert _mi(declared.split("}")[0]) >= SNAPSHOT_MI * SNAPSHOTS_AT_PEAK


def test_the_builder_has_a_cpu_limit_and_memory_bounds() -> None:
    """(b) The builder is bounded and loops the publish verb (tests/test_publish.py)."""
    builder = _containers()["builder"]["resources"]
    assert builder["limits"]["cpu"], "no cpu limit on the builder"
    assert _mi(builder["requests"]["memory"]) <= _mi(builder["limits"]["memory"])
    command = " ".join(_containers()["builder"]["args"])
    assert "--publish /srv" in command
    assert "nemik-serve" in command


def test_the_servers_probes_do_not_depend_on_the_builder() -> None:
    """(c) A stale snapshot that is served beats a restart."""
    server, builder = _containers()["server"], _containers()["builder"]
    assert server["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert server["readinessProbe"]["httpGet"]["path"] == "/metrics"
    assert "livenessProbe" not in builder
    assert "readinessProbe" not in builder


def test_the_servers_command_line_is_one_the_tool_accepts() -> None:
    """The server's argv parses under nemik-static's own parser."""
    server = _containers()["server"]
    assert server["command"] == ["/app/.venv/bin/nemik-static"]
    args = staticserve.parser().parse_args(server["args"])
    assert str(args.root) == "/srv"
    assert args.port == server["ports"][0]["containerPort"]


def test_the_builders_flags_are_flags_its_commands_have() -> None:
    """Every flag the builder loop passes appears in --help of the command it is passed to.

    The loop runs nemik-exports and then nemik-serve --publish with the exports directory and the
    luthen withheld list, refusing a list older than 900 s (nemik:W636, W647).
    """
    command = " ".join(_containers()["builder"]["args"])
    exports_part, _, serve_part = command.partition("/app/.venv/bin/nemik-serve")
    exports_flags = {w for w in exports_part.split() if w.startswith("--")}
    serve_flags = {w for w in serve_part.split() if w.startswith("--")}
    assert exports_flags >= {"--root", "--withheld", "--out"}
    assert serve_flags >= {"--root", "--publish", "--exports", "--withheld"}
    assert "--withheld-max-age 900" in serve_part
    for tool, flags in (("nemik-exports", exports_flags), ("nemik-serve", serve_flags)):
        help_text = installed.run(tool, "--help").stdout
        assert [f for f in sorted(flags) if f not in help_text] == []


def test_the_snapshot_is_written_by_the_builder_and_only_read_by_the_server() -> None:
    """(d) The server mounts the snapshot read-only and never the export."""
    server, builder = _containers()["server"], _containers()["builder"]
    assert _mounts(server)["snapshots"]["readOnly"] is True
    assert not _mounts(builder)["snapshots"].get("readOnly")
    assert "export" not in _mounts(server), "the export is the builder's input only"
    assert _mounts(builder)["export"]["readOnly"] is True
    server_path = _mounts(server)["snapshots"]["mountPath"]
    assert server_path == _mounts(builder)["snapshots"]["mountPath"]


def test_the_builder_keeps_its_cache_on_a_claim_that_outlives_the_pod() -> None:
    """The cache serve saves under the publish directory is on luthen's claim, builder only."""
    text = DEPLOYMENT.read_text()
    server_part, builder_part = text.split("- name: builder")
    assert "{name: cache, mountPath: /srv/.cache}" in builder_part
    assert "name: cache" not in server_part, "the server only serves the snapshot"
    assert "persistentVolumeClaim: {claimName: nemik-cache}" in builder_part


def test_the_builder_knows_its_pod_so_its_gauges_read_apart() -> None:
    """Two builders sit behind one scrape target: the pod name reaches the gauges (W1074)."""
    builder_part = DEPLOYMENT.read_text().split("- name: builder")[1]
    assert "name: NEMIK_POD" in builder_part
    assert "fieldPath: metadata.name" in builder_part


def test_the_pod_fits_the_tenant_quota_with_a_surge_pod() -> None:
    """Replicas plus one surge pod, at their limits, stay under the tenant quota."""
    limits = sum(
        _mi(c["resources"]["limits"]["memory"]) for c in _containers().values()
    )
    pods = _spec()["spec"]["replicas"] + 1
    assert limits * pods <= TENANT_QUOTA_MI, (
        f"{pods} pods x {limits:.0f} Mi > {TENANT_QUOTA_MI} Mi"
    )


def test_every_container_keeps_the_restricted_security_context() -> None:
    """Restricted Pod Security: no escalation, read-only root, all capabilities dropped."""
    for name, container in _containers().items():
        context = container["securityContext"]
        assert context["allowPrivilegeEscalation"] is False, name
        assert context["readOnlyRootFilesystem"] is True, name
        assert context["capabilities"]["drop"] == ["ALL"], name
