"""nemik:W327: arrival pacing as a token bucket over each repo's new cards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nemik.pacing import bucket, limits

START = datetime(2026, 10, 1, tzinfo=UTC)


def test_within_the_burst_the_bucket_never_goes_over() -> None:
    stamps = [START + timedelta(hours=i) for i in range(10)]
    overdraft, level = bucket(
        stamps, rate=5, burst=10, start=START, now=START + timedelta(hours=10)
    )
    assert overdraft == 0.0
    assert 0 < level <= 10


def test_a_flood_past_the_burst_is_an_overdraft_that_refills_at_the_rate() -> None:
    flood = [
        START + timedelta(minutes=i) for i in range(30)
    ]  # 30 cards in half an hour
    overdraft, _ = bucket(
        flood, rate=10, burst=10, start=START, now=START + timedelta(hours=1)
    )
    assert overdraft > 19  # 30 taken from a bucket of 10, barely refilled
    later = bucket(
        flood, rate=10, burst=10, start=START, now=START + timedelta(days=3)
    )[1]
    assert later == 10.0  # three days at 10 a day refill it to the burst


def test_the_declared_table_is_read_and_defaults_otherwise() -> None:
    assert limits("[pacing]\nrate = 3\nburst = 7\nwindow_days = 2\n") == (3.0, 7.0, 2)
    assert limits("") == (50.0, 150.0, 14)
