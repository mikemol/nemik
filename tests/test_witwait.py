"""nemik:W258: nemik-witnesses --wait blocks on a witness and exits 0 held, 1 timeout, 2 unknown."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nemik.witnesses import main
from nemik.witwait import HELD, NOT_YET, UNKNOWN, promql_poll, seconds, wait


def _script(*steps: tuple[str, str]):
    """A poll that plays `steps` in order, then repeats the last one."""
    queue = list(steps)

    def poll() -> tuple[str, str]:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return poll


class _Clock:
    """A clock the loop advances by sleeping, so no test really waits."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = 0

    def clock(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s
        self.sleeps += 1


def _wait(poll, timeout: float = 100, every: float = 10) -> tuple[int, str, _Clock]:
    t = _Clock()
    code, line = wait(
        poll,
        timeout,
        every,
        sleep=t.sleep,
        clock=t.clock,
        stamp=lambda: "2026-10-09T07:00:00Z",
    )
    return code, line, t


def test_it_returns_zero_with_the_value_that_crossed() -> None:
    poll = _script((NOT_YET, "0.4"), (NOT_YET, "0.9"), (HELD, "0.995"))
    code, line, t = _wait(poll)
    assert code == 0
    assert line == "HELD at 2026-10-09T07:00:00Z: 0.995"
    assert t.sleeps == 2


def test_it_times_out_with_the_last_value_never_an_empty_line() -> None:
    code, line, _ = _wait(_script((NOT_YET, "0.9")), timeout=35, every=10)
    assert code == 1
    assert line == "TIMEOUT, last value: 0.9"


def test_unknown_is_not_false_and_a_few_blips_are_tolerated() -> None:
    blips = _script(
        (UNKNOWN, "probe"), (UNKNOWN, "probe"), (UNKNOWN, "probe"), (HELD, "1")
    )
    assert _wait(blips)[0] == 0
    down = _script((UNKNOWN, "probe unreachable"))
    code, line, _ = _wait(down)
    assert code == 2
    assert "UNKNOWN after 4 polls" in line


def test_an_unknown_last_poll_at_the_timeout_is_exit_two_not_one() -> None:
    poll = _script((NOT_YET, "0.9"), (UNKNOWN, "probe unreachable"))
    code, line, _ = _wait(poll, timeout=10, every=10)
    assert code == 2 and "UNKNOWN at the timeout" in line


def test_durations() -> None:
    assert (seconds("90s"), seconds("30m"), seconds("12h"), seconds("1d")) == (
        90.0,
        1800.0,
        43200.0,
        86400.0,
    )
    with pytest.raises(ValueError, match="not a duration"):
        seconds("soon")


def test_a_bad_duration_on_the_command_line_is_exit_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--wait", "up", "--timeout", "forever"])
    assert stop.value.code == 2
    assert "not a duration" in capsys.readouterr().err


@contextmanager
def _victoria(series: list[list[str]]) -> Iterator[str]:
    """A local /api/v1/query that answers each request with the next list of sample values."""
    answers = list(series)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            values = answers.pop(0) if len(answers) > 1 else answers[0]
            body = {
                "status": "success",
                "data": {"result": [{"value": [0, v]} for v in values]},
            }
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def test_a_series_crossing_the_threshold_between_polls_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `x > 0.99` returns the series only while it is true: empty, empty, then the crossing value.
    with _victoria([[], [], ["0.995"]]) as url:
        monkeypatch.setenv("NEMIK_VM_URL", url)
        code, line = wait(
            promql_poll("synced / total > 0.99"),
            5,
            0.01,
            stamp=lambda: "T",
        )
    assert (code, line) == (0, "HELD at T: 0.995")


def test_many_matching_series_print_a_readable_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _victoria([[str(i) for i in range(8)]]) as url:
        monkeypatch.setenv("NEMIK_VM_URL", url)
        code, line = wait(promql_poll("up == 1"), 5, 0.01, stamp=lambda: "T")
    assert (code, line) == (0, "HELD at T: 0, 1, 2, 3, 4 (+3 more series)")


def test_a_probe_that_is_down_is_exit_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEMIK_VM_URL", "http://127.0.0.1:9")
    code, line = wait(promql_poll("up"), 5, 0.01)
    assert code == 2 and "unreachable" in line


def test_an_unset_endpoint_is_unknown_not_not_yet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEMIK_VM_URL", raising=False)
    assert promql_poll("up")()[0] == UNKNOWN
