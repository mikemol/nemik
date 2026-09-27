from nemik.rank import Weights, load_weights


def test_packaged_weights_favor_peer_edges() -> None:
    w = load_weights()
    assert w == Weights(local=1, peer=3)
    assert w.peer > w.local


def test_weights_override_from_text() -> None:
    assert load_weights("local = 2\npeer = 5\n") == Weights(local=2, peer=5)
