"""Command-line interface for the WWVB emulator."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import wave
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np

from .timecode import UTC
from .waveform import DIRECT_CARRIER_HZ, HARMONIC_CARRIER_HZ, second_waveform


def _parse_time(value: str, zone: str | None = None) -> dt.datetime:
    """Parse an ISO 8601 time; naive values are taken in ``zone`` (or UTC)."""
    t = dt.datetime.fromisoformat(value)
    if t.tzinfo is not None:
        if zone is not None:
            raise ValueError(
                f"--time {value!r} already carries a UTC offset; "
                "drop the offset or drop --zone"
            )
        return t.astimezone(UTC)
    return t.replace(tzinfo=ZoneInfo(zone) if zone else UTC).astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wwvb-emulator",
        description=(
            "Generate the WWVB time signal as audio. Play near max volume "
            "through earbuds coiled next to the clock's antenna; the sound "
            "card's 3rd-harmonic distortion of the 20 kHz tone provides the "
            "60 kHz carrier."
        ),
    )
    p.add_argument("--minutes", type=float, default=10.0,
                   help="how long to transmit (default: 10)")
    p.add_argument("--samplerate", type=int, default=48_000,
                   help="output sample rate in Hz (default: 48000)")
    p.add_argument("--mode", choices=("harmonic", "direct"), default="harmonic",
                   help="harmonic: 20 kHz tone, 60 kHz via distortion (default); "
                        "direct: true 60 kHz carrier, needs --samplerate >= 144000 "
                        "(use 192000)")
    p.add_argument("--volume", type=float, default=1.0,
                   help="amplitude 0..1 (default: 1.0; keep high — distortion is the point)")
    p.add_argument("--monitor", type=float, default=0.0, metavar="VOLUME",
                   help="mix in a faint audible tone following the same on/off "
                        "pattern so you can hear the transmission, e.g. 0.05 "
                        "(default: off; carved out of --volume, so keep it small)")
    p.add_argument("--monitor-freq", type=int, default=300, metavar="HZ",
                   help="frequency of the --monitor tone (default: 300)")
    p.add_argument("--offset", type=float, default=0.0,
                   help="shift the encoded time by this many seconds (compensate "
                        "latency, or deliberately set a clock fast/slow)")
    p.add_argument("--time-source", choices=("utc", "local"), default="utc",
                   help="utc: encode real UTC, receiver applies its zone (default); "
                        "local: encode local wall time as UTC for zone-less receivers")
    p.add_argument("--time", metavar="ISO8601",
                   help="encode a fixed start time instead of the current time "
                        "(taken as UTC unless it carries an offset like -06:00 "
                        "or --zone is given)")
    p.add_argument("--zone", metavar="IANA_NAME",
                   help="interpret a naive --time in this time zone, e.g. "
                        "America/Denver (DST handled automatically)")
    p.add_argument("--device", help="output device index or name substring")
    p.add_argument("--list-devices", action="store_true",
                   help="list audio output devices and exit")
    p.add_argument("--wav", metavar="PATH",
                   help="render --minutes of signal to a WAV file instead of playing")
    p.add_argument("--quiet", action="store_true", help="suppress progress output")
    p.add_argument("--options", action="help",
                   help="show all available options and exit")
    return p


def render_wav(path: str, start: dt.datetime, minutes: float, *,
               samplerate: int, carrier: float, amplitude: float,
               monitor_hz: float = 300.0, monitor_amplitude: float = 0.0,
               dst_override: tuple[int, int] | None = None) -> None:
    from .player import iter_seconds

    total_seconds = max(1, round(minutes * 60))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        for _, symbol in iter_seconds(start, total_seconds, dst_override=dst_override):
            data = second_waveform(
                symbol, samplerate=samplerate, carrier=carrier, amplitude=amplitude,
                monitor_hz=monitor_hz, monitor_amplitude=monitor_amplitude,
            )
            w.writeframes((np.clip(data, -1.0, 1.0) * 32767).astype("<i2").tobytes())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_devices:
        import sounddevice as sd

        print(sd.query_devices())
        return 0

    carrier = HARMONIC_CARRIER_HZ if args.mode == "harmonic" else DIRECT_CARRIER_HZ
    if args.samplerate <= 2 * carrier:
        need = "192000 (>= 144000)" if args.mode == "direct" else "48000"
        print(
            f"error: --samplerate {args.samplerate} is too low for "
            f"{args.mode} mode ({carrier:.0f} Hz carrier); use {need}",
            file=sys.stderr,
        )
        return 2

    if not 0.0 < args.volume <= 1.0:
        print("error: --volume must be in (0, 1]", file=sys.stderr)
        return 2

    if args.monitor and not 0.0 < args.monitor < args.volume:
        print("error: --monitor must be above 0 and below --volume", file=sys.stderr)
        return 2
    if args.monitor and not 20 <= args.monitor_freq < args.samplerate / 2:
        print(
            f"error: --monitor-freq must be between 20 and {args.samplerate // 2} Hz",
            file=sys.stderr,
        )
        return 2

    if args.zone and not args.time:
        print("error: --zone requires --time", file=sys.stderr)
        return 2

    fixed_time: dt.datetime | None = None
    if args.time:
        try:
            fixed_time = _parse_time(args.time, args.zone)
        except ZoneInfoNotFoundError:
            print(
                f"error: unknown time zone {args.zone!r}; "
                "use an IANA name like America/Denver",
                file=sys.stderr,
            )
            return 2
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

    if args.wav:
        from .player import signal_now

        start = fixed_time or signal_now(args.offset, args.time_source)
        dst_override = (0, 0) if args.time_source == "local" else None
        render_wav(
            args.wav, start, args.minutes,
            samplerate=args.samplerate, carrier=carrier, amplitude=args.volume,
            monitor_hz=args.monitor_freq, monitor_amplitude=args.monitor,
            dst_override=dst_override,
        )
        if not args.quiet:
            print(f"Wrote {args.minutes:g} min starting {start:%Y-%m-%d %H:%M:%S} UTC "
                  f"to {args.wav}")
        return 0

    device: int | str | None = args.device
    if device is not None and device.isdigit():
        device = int(device)

    from .player import play

    play(
        args.minutes,
        samplerate=args.samplerate,
        carrier=carrier,
        amplitude=args.volume,
        device=device,
        offset=args.offset,
        time_source=args.time_source,
        start_time=fixed_time,
        monitor_hz=args.monitor_freq,
        monitor_amplitude=args.monitor,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
