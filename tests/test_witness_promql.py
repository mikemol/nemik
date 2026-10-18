# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""nemik:W501: a waypoint's witness may be a bare PromQL expression, as --wait has always read one.

luthen-observability:W1054 stores its executor-load witness as one PromQL string; a Rego wrapper with its
escaped label quotes was the error-prone step nobody should write by hand. A bare PromQL holds while its
instant query returns a sample (the PromQL meaning of a comparison), is false on an empty result, and is
undefined when the probe cannot answer: unknown is never false.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from nemik import witnesses
from nemik.witnesses import is_rego, open_witnesses, witness
from nemik.witwait import poller, promql_poll, rego_poll

# luthen-observability:W1054's witness, verbatim
EXECUTOR_LOAD = (
    '(sum(rate(container_cpu_usage_seconds_total{namespace="buildbuddy",'
    'pod=~"buildbuddy-executor-.*",container="executor"}[5m])) > '
    "quantile_over_time(0.9, sum(rate(container_cpu_usage_seconds_total{"
    'namespace="buildbuddy",pod=~"buildbuddy-executor-.*",container="executor"}[5m]))[7d:5m])) '
    'and on() (max(kube_pod_container_resource_limits{namespace="buildbuddy",'
    'pod=~"buildbuddy-executor-.*",resource="cpu"}) < 24)'
)


def _answer(
    monkeypatch: pytest.MonkeyPatch, result: list[Any] | None
) -> list[dict[str, str]]:
    """Make the VictoriaMetrics probe answer `result` (None: unreachable); returns the queries asked."""
    asked: list[dict[str, str]] = []

    def get(env: str, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        asked.append(params)
        if result is None:
            return None
        return {"status": "success", "data": {"result": result}}

    monkeypatch.setattr(witnesses, "_get", get)
    return asked


def test_a_sample_means_the_witness_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _answer(monkeypatch, [{"value": [1, "31.5"]}])
    verdict, doc, missing = witness(EXECUTOR_LOAD)
    assert (verdict, missing) == ("true", [])
    assert doc["promql"][EXECUTOR_LOAD] == {"values": [31.5], "empty": False}
    assert asked == [{"query": EXECUTOR_LOAD}], (
        "the expression went to the probe unchanged"
    )


def test_an_empty_result_means_not_yet(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, [])
    verdict, doc, _ = witness(EXECUTOR_LOAD)
    assert verdict == "false"
    assert doc["promql"][EXECUTOR_LOAD]["empty"] is True


def test_an_unreachable_probe_is_undefined_never_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answer(monkeypatch, None)
    verdict, _, missing = witness(EXECUTOR_LOAD)
    assert verdict == "undefined"
    assert missing == [f'promql["{EXECUTOR_LOAD}"]']


def test_what_is_rego_and_what_is_promql() -> None:
    assert is_rego('input.file["/x"].exists')
    assert is_rego(
        'time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")'
    )
    assert not is_rego(EXECUTOR_LOAD)
    assert not is_rego("up == 0")
    assert not is_rego('rate(http_requests_total{job="input"}[5m]) > 1')


def test_wait_and_the_queue_choose_the_same_evaluator() -> None:
    assert poller(EXECUTOR_LOAD).__qualname__ == promql_poll(EXECUTOR_LOAD).__qualname__
    time_witness = 'time.parse_rfc3339_ns(input.now) >= time.parse_rfc3339_ns("2026-10-01T00:00:00Z")'
    # a time witness names no observer fact but is Rego: it used to be sent to the PromQL probe
    assert poller(time_witness).__qualname__ == rego_poll(time_witness).__qualname__


def test_the_queue_scan_finds_a_bare_promql_witness(tmp_path: Path) -> None:
    queue = tmp_path / "luthen-observability" / "paths-forward.json"
    queue.parent.mkdir()
    queue.write_text(
        json.dumps(
            {
                "waypoints": [
                    {"symbol": "W1054", "status": "blocked", "witness": EXECUTOR_LOAD},
                    {"symbol": "W2", "status": "done", "witness": "up == 0"},
                ]
            }
        )
    )
    found = open_witnesses(tmp_path)
    assert [(repo, sym, query) for repo, _, sym, query, _lang in found] == [
        ("luthen-observability", "W1054", EXECUTOR_LOAD)
    ]
