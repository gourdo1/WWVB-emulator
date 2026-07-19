"""Real-time playback of the WWVB signal, aligned to the system clock."""

from __future__ import annotations

import datetime as dt
import math
import time

from .timecode import UTC, Symbol, encode_minute
from .waveform import second_waveform


def signal_now(offset: float = 0.0, time_source: str = "utc") -> dt.datetime:
    """The instant to encode right now, rounded to the nearest second.

    ``time_source`` "utc" encodes real UTC (the receiving clock applies its
    own time zone); "local" relabels the local wall time as UTC, for
    receivers with no time-zone setting.
    """
    if time_source == "local":
        base = dt.datetime.now().replace(tzinfo=UTC)
    else:
        base = dt.datetime.now(UTC)
    base += dt.timedelta(seconds=offset + 0.5)
    return base.replace(microsecond=0)


def iter_seconds(start: dt.datetime, count: int, **encode_kwargs):
    """Yield ``(datetime, Symbol)`` for ``count`` consecutive seconds."""
    t = start.replace(microsecond=0)
    frame_minute = None
    frame: list[Symbol] = []
    for _ in range(count):
        minute_start = t.replace(second=0)
        if minute_start != frame_minute:
            frame = encode_minute(minute_start, **encode_kwargs)
            frame_minute = minute_start
        yield t, frame[t.second]
        t += dt.timedelta(seconds=1)


def play(
    minutes: float,
    *,
    samplerate: int = 48_000,
    carrier: float = 20_000.0,
    amplitude: float = 1.0,
    device: int | str | None = None,
    offset: float = 0.0,
    time_source: str = "utc",
    start_time: dt.datetime | None = None,
    monitor_hz: float = 300.0,
    monitor_amplitude: float = 0.0,
    quiet: bool = False,
) -> None:
    """Stream the signal for ``minutes`` minutes (Ctrl+C stops early).

    Playback starts at the next wall-clock second so signal seconds line up
    with real ones; output latency (typically tens of ms) plus any desired
    lead can be compensated with ``offset``. A fixed ``start_time`` encodes
    that instant instead of the current time (``offset`` still applies).
    """
    import sounddevice as sd  # deferred: needs PortAudio, not used in tests

    encode_kwargs = {}
    if time_source == "local":
        # Local wall time already includes DST; stop the receiver from
        # applying a second shift.
        encode_kwargs["dst_override"] = (0, 0)

    stream = sd.OutputStream(
        samplerate=samplerate, channels=1, dtype="float32", device=device
    )

    now = time.time()
    time.sleep(math.ceil(now) - now)
    if start_time is not None:
        start = (start_time + dt.timedelta(seconds=offset)).replace(microsecond=0)
    else:
        start = signal_now(offset, time_source)
    stream.start()

    total_seconds = max(1, round(minutes * 60))
    if not quiet:
        print(
            f"Transmitting from {start:%Y-%m-%d %H:%M:%S} "
            f"({'local-as-UTC' if time_source == 'local' else 'UTC'}) "
            f"for {total_seconds} s — Ctrl+C to stop."
        )
    try:
        last_minute = None
        for t, symbol in iter_seconds(start, total_seconds, **encode_kwargs):
            if not quiet and t.minute != last_minute:
                last_minute = t.minute
                print(f"  minute {t:%H:%M} (starting at second :{t.second:02d})")
            stream.write(
                second_waveform(
                    symbol,
                    samplerate=samplerate,
                    carrier=carrier,
                    amplitude=amplitude,
                    monitor_hz=monitor_hz,
                    monitor_amplitude=monitor_amplitude,
                )
            )
    except KeyboardInterrupt:
        if not quiet:
            print("Stopped.")
    finally:
        stream.stop()
        stream.close()
