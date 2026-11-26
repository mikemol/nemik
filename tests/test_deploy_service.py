# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W2494: nemik has a headless Service beside its ClusterIP one, so each pod is scrapeable.

luthen-observability:W1670: one ClusterIP Service gives the scrape job one random pod per scrape,
and the two builders' nemik_build_* gauges interleave. A headless Service (clusterIP None) with the
same selector and port lets luthen's dns_sd job reach every pod.
"""

from pathlib import Path
from typing import TypedDict

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "deploy" / "service.yaml"
KUSTOMIZATION = ROOT / "deploy" / "kustomization.yaml"
PORT = 8750


class Metadata(TypedDict, total=False):
    """The metadata of a manifest."""

    name: str


class ServicePort(TypedDict, total=False):
    """A ports entry of a Service."""

    name: str
    port: int
    targetPort: str


class ServiceSpec(TypedDict, total=False):
    """The spec of a Service, as far as these tests read it."""

    clusterIP: str
    selector: dict[str, str]
    ports: list[ServicePort]


class Service(TypedDict, total=False):
    """One document of deploy/service.yaml."""

    kind: str
    metadata: Metadata
    spec: ServiceSpec


def _services() -> dict[str, Service]:
    """Read the Services of deploy/service.yaml by name.

    Returns:
        Each document, keyed by its metadata name.

    """
    docs: list[Service] = list(yaml.safe_load_all(SERVICE.read_text(encoding="utf-8")))
    return {doc["metadata"]["name"]: doc for doc in docs}


def test_both_services_exist() -> None:
    """The ClusterIP Service and its headless peer, each of kind Service."""
    services = _services()
    assert set(services) == {"nemik", "nemik-headless"}
    assert all(doc["kind"] == "Service" for doc in services.values())


def test_the_headless_one_has_no_cluster_ip_and_the_same_selector_and_port() -> None:
    """MUTANT: a headless Service with another selector would scrape other pods."""
    services = _services()
    headless, normal = services["nemik-headless"], services["nemik"]
    assert headless["spec"]["clusterIP"] == "None"
    assert "clusterIP" not in normal["spec"]
    assert headless["spec"]["selector"] == normal["spec"]["selector"]
    assert headless["spec"]["ports"] == normal["spec"]["ports"]
    assert headless["spec"]["ports"][0]["port"] == PORT


def test_kustomize_ships_the_file_both_services_are_in() -> None:
    """Flux applies service.yaml through the kustomization, so the file has to be listed."""
    assert "service.yaml" in KUSTOMIZATION.read_text(encoding="utf-8")
