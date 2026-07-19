"""WWVB legacy AM/pulse-width time code encoding.

One frame is 60 symbols, one per second, transmitted during the minute whose
time it encodes; the frame starts on the minute boundary. Reference: NIST
SP 432 ("NIST Time and Frequency Services") and SP 250-67.
"""

from __future__ import annotations

import calendar
import datetime as dt
from enum import Enum
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc


class Symbol(Enum):
    ZERO = 0
    ONE = 1
    MARK = 2


#: Duration (seconds) of the reduced-power interval at the start of each
#: second. Full power is restored for the remainder of the second.
LOW_POWER_SECONDS = {
    Symbol.ZERO: 0.2,
    Symbol.ONE: 0.5,
    Symbol.MARK: 0.8,
}

_MARKER_POSITIONS = (0, 9, 19, 29, 39, 49, 59)

# WWVB transmits from Fort Collins, CO; any US zone that observes the
# nationwide DST rules works for computing the DST status bits.
_US_DST_ZONE = ZoneInfo("America/Denver")


def _is_us_dst(t: dt.datetime) -> bool:
    return t.astimezone(_US_DST_ZONE).dst() != dt.timedelta(0)


def _bcd(value: int, weights: tuple[int, ...]) -> list[int]:
    """Greedy expansion over per-digit 8-4-2-1 weights; exact BCD for
    values whose digits are each <= 9 (always true here)."""
    bits = []
    for w in weights:
        if value >= w:
            bits.append(1)
            value -= w
        else:
            bits.append(0)
    return bits


def encode_minute(
    minute: dt.datetime,
    *,
    dut1: float = 0.0,
    leap_second_pending: bool = False,
    dst_override: tuple[int, int] | None = None,
) -> list[Symbol]:
    """Encode one 60-second WWVB frame for the minute containing ``minute``.

    ``minute`` must be timezone-aware (converted to UTC internally); a naive
    datetime is assumed to already be UTC. ``dst_override`` forces the two
    DST status bits (bit 57, bit 58) instead of deriving them from US rules.
    """
    if minute.tzinfo is None:
        minute = minute.replace(tzinfo=UTC)
    t = minute.astimezone(UTC).replace(second=0, microsecond=0)

    doy = t.timetuple().tm_yday
    year2 = t.year % 100

    if dst_override is not None:
        dst1, dst2 = dst_override
    else:
        day_start = t.replace(hour=0, minute=0)
        # Bit 57 (DST1) changes at 00:00 UTC on the day of a DST transition,
        # bit 58 (DST2) follows 24 h later: 57 = status at 24:00Z today,
        # 58 = status at 00:00Z today.
        dst1 = int(_is_us_dst(day_start + dt.timedelta(days=1)))
        dst2 = int(_is_us_dst(day_start))

    dut1_positive = dut1 >= 0
    dut1_tenths = min(9, round(abs(dut1) * 10))

    frame = [Symbol.ZERO] * 60
    for pos in _MARKER_POSITIONS:
        frame[pos] = Symbol.MARK

    def put(pos: int, bit: int | bool) -> None:
        frame[pos] = Symbol.ONE if bit else Symbol.ZERO

    for pos, bit in zip((1, 2, 3, 5, 6, 7, 8), _bcd(t.minute, (40, 20, 10, 8, 4, 2, 1))):
        put(pos, bit)
    for pos, bit in zip((12, 13, 15, 16, 17, 18), _bcd(t.hour, (20, 10, 8, 4, 2, 1))):
        put(pos, bit)
    for pos, bit in zip(
        (22, 23, 25, 26, 27, 28, 30, 31, 32, 33),
        _bcd(doy, (200, 100, 80, 40, 20, 10, 8, 4, 2, 1)),
    ):
        put(pos, bit)

    # DUT1 sign: "+" -> bits 36, 38 set; "-" -> bit 37 set.
    put(36, dut1_positive)
    put(37, not dut1_positive)
    put(38, dut1_positive)
    for pos, bit in zip((40, 41, 42, 43), _bcd(dut1_tenths, (8, 4, 2, 1))):
        put(pos, bit)

    for pos, bit in zip(
        (45, 46, 47, 48, 50, 51, 52, 53), _bcd(year2, (80, 40, 20, 10, 8, 4, 2, 1))
    ):
        put(pos, bit)

    put(55, calendar.isleap(t.year))
    put(56, leap_second_pending)
    put(57, dst1)
    put(58, dst2)
    return frame
