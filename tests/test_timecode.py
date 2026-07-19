import datetime as dt

import pytest

from wwvb_emulator.timecode import UTC, Symbol, encode_minute

MARKERS = (0, 9, 19, 29, 39, 49, 59)
ALWAYS_ZERO = (4, 10, 11, 14, 20, 21, 24, 34, 35, 44, 54)

MINUTE_FIELD = tuple(zip((1, 2, 3, 5, 6, 7, 8), (40, 20, 10, 8, 4, 2, 1)))
HOUR_FIELD = tuple(zip((12, 13, 15, 16, 17, 18), (20, 10, 8, 4, 2, 1)))
DOY_FIELD = tuple(
    zip((22, 23, 25, 26, 27, 28, 30, 31, 32, 33), (200, 100, 80, 40, 20, 10, 8, 4, 2, 1))
)
YEAR_FIELD = tuple(zip((45, 46, 47, 48, 50, 51, 52, 53), (80, 40, 20, 10, 8, 4, 2, 1)))


def _field(frame, pos_weights):
    return sum(w for p, w in pos_weights if frame[p] is Symbol.ONE)


def test_frame_structure():
    frame = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC))
    assert len(frame) == 60
    for pos in MARKERS:
        assert frame[pos] is Symbol.MARK
    for pos in ALWAYS_ZERO:
        assert frame[pos] is Symbol.ZERO
    assert sum(1 for s in frame if s is Symbol.MARK) == 7


@pytest.mark.parametrize(
    "when",
    [
        dt.datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC),
        dt.datetime(2024, 12, 31, 23, 59, tzinfo=UTC),  # day-of-year 366
        dt.datetime(2000, 2, 29, 12, 34, tzinfo=UTC),
        dt.datetime(2026, 10, 5, 9, 59, tzinfo=UTC),
    ],
)
def test_round_trip_fields(when):
    frame = encode_minute(when)
    assert _field(frame, MINUTE_FIELD) == when.minute
    assert _field(frame, HOUR_FIELD) == when.hour
    assert _field(frame, DOY_FIELD) == when.timetuple().tm_yday
    assert _field(frame, YEAR_FIELD) == when.year % 100


def test_known_vector_2026_07_17_1530():
    frame = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC))
    bits = [1 if s is Symbol.ONE else 0 for s in frame]
    # minute 30 = 20 + 10
    assert [bits[i] for i in (1, 2, 3, 5, 6, 7, 8)] == [0, 1, 1, 0, 0, 0, 0]
    # hour 15 = 10 + 4 + 1
    assert [bits[i] for i in (12, 13, 15, 16, 17, 18)] == [0, 1, 0, 1, 0, 1]
    # day-of-year 198 = 100 + 80 + 10 + 8
    assert [bits[i] for i in (22, 23, 25, 26, 27, 28, 30, 31, 32, 33)] == [
        0, 1, 1, 0, 0, 1, 1, 0, 0, 0,
    ]
    # year 26 = 20 + 4 + 2
    assert [bits[i] for i in (45, 46, 47, 48, 50, 51, 52, 53)] == [0, 0, 1, 0, 0, 1, 1, 0]


def test_leap_year_indicator():
    assert encode_minute(dt.datetime(2024, 6, 1, tzinfo=UTC))[55] is Symbol.ONE
    assert encode_minute(dt.datetime(2026, 6, 1, tzinfo=UTC))[55] is Symbol.ZERO


def test_dut1_default_positive_zero():
    frame = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC))
    assert [frame[i] for i in (36, 37, 38)] == [Symbol.ONE, Symbol.ZERO, Symbol.ONE]
    assert all(frame[i] is Symbol.ZERO for i in (40, 41, 42, 43))


def test_dut1_negative_magnitude():
    frame = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC), dut1=-0.3)
    assert [frame[i] for i in (36, 37, 38)] == [Symbol.ZERO, Symbol.ONE, Symbol.ZERO]
    assert sum(w for i, w in zip((40, 41, 42, 43), (8, 4, 2, 1)) if frame[i] is Symbol.ONE) == 3


@pytest.mark.parametrize(
    ("when", "dst1", "dst2"),
    [
        (dt.datetime(2026, 7, 17, 15, 0, tzinfo=UTC), 1, 1),   # mid-DST
        (dt.datetime(2026, 1, 15, 15, 0, tzinfo=UTC), 0, 0),   # standard time
        (dt.datetime(2026, 3, 8, 4, 0, tzinfo=UTC), 1, 0),     # DST begins today
        (dt.datetime(2026, 11, 1, 4, 0, tzinfo=UTC), 0, 1),    # DST ends today
    ],
)
def test_dst_bits(when, dst1, dst2):
    frame = encode_minute(when)
    assert frame[57] is (Symbol.ONE if dst1 else Symbol.ZERO)
    assert frame[58] is (Symbol.ONE if dst2 else Symbol.ZERO)


def test_dst_override():
    frame = encode_minute(dt.datetime(2026, 7, 17, tzinfo=UTC), dst_override=(0, 0))
    assert frame[57] is Symbol.ZERO
    assert frame[58] is Symbol.ZERO


def test_naive_datetime_treated_as_utc():
    aware = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC))
    naive = encode_minute(dt.datetime(2026, 7, 17, 15, 30))
    assert aware == naive
