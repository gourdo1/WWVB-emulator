import datetime as dt

import pytest

from wwvb_emulator.cli import _parse_time, main
from wwvb_emulator.timecode import UTC


def test_naive_time_is_utc():
    assert _parse_time("2026-07-17T15:30") == dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC)


def test_explicit_offset_converted_to_utc():
    assert _parse_time("2026-07-17T09:30-06:00") == dt.datetime(
        2026, 7, 17, 15, 30, tzinfo=UTC
    )


def test_zone_applies_dst():
    # July: America/Denver is UTC-6 (MDT)
    assert _parse_time("2026-07-17T09:30", "America/Denver") == dt.datetime(
        2026, 7, 17, 15, 30, tzinfo=UTC
    )
    # January: UTC-7 (MST)
    assert _parse_time("2026-01-17T09:30", "America/Denver") == dt.datetime(
        2026, 1, 17, 16, 30, tzinfo=UTC
    )


def test_zone_conflicts_with_explicit_offset():
    with pytest.raises(ValueError, match="drop the offset or drop --zone"):
        _parse_time("2026-07-17T09:30-06:00", "America/Denver")


def test_cli_rejects_zone_without_time(capsys):
    assert main(["--zone", "America/Denver", "--wav", "unused.wav"]) == 2
    assert "--zone requires --time" in capsys.readouterr().err


def test_cli_rejects_unknown_zone(capsys):
    assert main(["--time", "2026-07-17T09:30", "--zone", "Mars/Olympus",
                 "--wav", "unused.wav"]) == 2
    assert "unknown time zone" in capsys.readouterr().err


def test_cli_rejects_monitor_louder_than_volume(capsys):
    assert main(["--monitor", "0.5", "--volume", "0.4", "--wav", "unused.wav"]) == 2
    assert "--monitor must be" in capsys.readouterr().err


def test_cli_rejects_bad_monitor_freq(capsys):
    assert main(["--monitor", "0.05", "--monitor-freq", "30000",
                 "--wav", "unused.wav"]) == 2
    assert "--monitor-freq" in capsys.readouterr().err


def test_cli_wav_with_monitor(tmp_path):
    out = tmp_path / "m.wav"
    assert main(["--time", "2026-07-17T15:30", "--minutes", "0.02",
                 "--monitor", "0.05", "--wav", str(out), "--quiet"]) == 0
    assert out.stat().st_size > 0


def test_cli_wav_uses_zone(tmp_path, capsys):
    out = tmp_path / "t.wav"
    assert main(["--time", "2026-07-17T09:30", "--zone", "America/Denver",
                 "--minutes", "0.02", "--wav", str(out)]) == 0
    assert "2026-07-17 15:30:00 UTC" in capsys.readouterr().out
    assert out.stat().st_size > 0
