"""nemik:W174: waypoints with the same witness query share one weather id; the query stays private."""

import json

from nemik.adapter import NEMIK, queue_graph, waypoint_uri


def _q(tmp_path, repo, witnesses):
    p = tmp_path / f"{repo}.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "project_root": "/x",
                "counter": len(witnesses),
                "residue": [],
                "waypoints": [
                    {
                        "symbol": f"W{i}",
                        "title": "weather",
                        "status": "blocked",
                        "blocked_on": ["W0"],
                        "blocked_kind": "agent",
                        **({"witness": w} if w else {}),
                    }
                    for i, w in enumerate(witnesses, 1)
                ],
            }
        )
    )
    return queue_graph(repo, p)


def test_same_query_same_weather_across_repos_whitespace_aside(tmp_path) -> None:
    q = 'input.alert["RegistryDown"].state == "inactive"'
    a, b = (
        _q(tmp_path, "a", [q, None, 'input.now > "2026-10-03"']),
        _q(tmp_path, "b", ["  " + q.replace(" == ", "  ==\t")]),
    )
    wa = str(a.value(waypoint_uri("a", "W1"), NEMIK.weather))
    assert wa.startswith("wx:") and wa == str(
        b.value(waypoint_uri("b", "W1"), NEMIK.weather)
    )
    assert a.value(waypoint_uri("a", "W2"), NEMIK.weather) is None
    assert str(a.value(waypoint_uri("a", "W3"), NEMIK.weather)) != wa
    assert "RegistryDown" not in a.serialize(
        format="turtle"
    )  # the query text is not in the graph
