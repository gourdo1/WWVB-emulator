import datetime as dt

import numpy as np
import pytest

from wwvb_emulator.timecode import LOW_POWER_SECONDS, UTC, Symbol, encode_minute
from wwvb_emulator.waveform import (
    REDUCED_AMPLITUDE,
    minute_waveform,
    second_waveform,
)

FS = 48_000
CARRIER = 20_000.0


@pytest.mark.parametrize("symbol", list(Symbol))
def test_length_and_dtype(symbol):
    data = second_waveform(symbol, samplerate=FS, carrier=CARRIER)
    assert data.dtype == np.float32
    assert len(data) == FS


@pytest.mark.parametrize("symbol", list(Symbol))
def test_envelope_ratio_and_timing(symbol):
    data = second_waveform(symbol, samplerate=FS, carrier=CARRIER).astype(np.float64)
    n_low = round(LOW_POWER_SECONDS[symbol] * FS)
    n_ramp = 48  # 1 ms

    low = data[n_ramp : n_low]
    high = data[n_low + n_ramp :]
    rms_low = np.sqrt(np.mean(low**2))
    rms_high = np.sqrt(np.mean(high**2))
    assert rms_high == pytest.approx(1.0 / np.sqrt(2), rel=1e-3)
    assert rms_low / rms_high == pytest.approx(REDUCED_AMPLITUDE, rel=1e-2)


def test_carrier_phase_and_continuity():
    # An integer-Hz carrier means every second starts at phase zero, so the
    # high-power region must exactly match a global reference sine and
    # concatenated seconds stay phase-continuous.
    t = np.arange(FS) / FS
    reference = np.sin(2 * np.pi * CARRIER * t)
    for symbol in Symbol:
        data = second_waveform(symbol, samplerate=FS, carrier=CARRIER).astype(np.float64)
        n_low = round(LOW_POWER_SECONDS[symbol] * FS)
        region = slice(n_low + 48, FS)
        np.testing.assert_allclose(data[region], reference[region], atol=1e-5)


def test_minute_waveform_length():
    frame = encode_minute(dt.datetime(2026, 7, 17, 15, 30, tzinfo=UTC))
    data = minute_waveform(frame, samplerate=FS, carrier=CARRIER)
    assert len(data) == 60 * FS


def test_amplitude_scaling():
    data = second_waveform(Symbol.ZERO, samplerate=FS, carrier=CARRIER, amplitude=0.5)
    assert np.max(np.abs(data)) <= 0.5 + 1e-6


def test_direct_mode_needs_high_samplerate():
    with pytest.raises(ValueError):
        second_waveform(Symbol.ZERO, samplerate=FS, carrier=60_000.0)
    data = second_waveform(Symbol.ZERO, samplerate=192_000, carrier=60_000.0)
    assert len(data) == 192_000


def test_non_integer_carrier_rejected():
    with pytest.raises(ValueError):
        second_waveform(Symbol.ZERO, samplerate=FS, carrier=20_000.5)


def test_monitor_tone_present_at_correct_level():
    data = second_waveform(
        Symbol.ZERO, samplerate=FS, carrier=CARRIER, monitor_amplitude=0.05
    ).astype(np.float64)
    # Analyze the last 0.5 s: full power, whole cycles of both tones.
    seg = data[FS // 2 :]
    spectrum = 2.0 * np.abs(np.fft.rfft(seg)) / len(seg)
    freqs = np.fft.rfftfreq(len(seg), 1.0 / FS)
    assert spectrum[freqs == 300.0][0] == pytest.approx(0.05, rel=1e-3)
    assert spectrum[freqs == CARRIER][0] == pytest.approx(0.95, rel=1e-3)


def test_monitor_never_clips():
    for symbol in Symbol:
        data = second_waveform(
            symbol, samplerate=FS, carrier=CARRIER, monitor_amplitude=0.05
        )
        assert np.max(np.abs(data)) <= 1.0 + 1e-6


def test_monitor_follows_envelope():
    data = second_waveform(
        Symbol.MARK, samplerate=FS, carrier=CARRIER, monitor_amplitude=0.5
    ).astype(np.float64)
    n_low = round(LOW_POWER_SECONDS[Symbol.MARK] * FS)
    rms_low = np.sqrt(np.mean(data[48:n_low] ** 2))
    rms_high = np.sqrt(np.mean(data[n_low + 48 :] ** 2))
    assert rms_low / rms_high == pytest.approx(REDUCED_AMPLITUDE, rel=1e-2)


def test_monitor_validation():
    with pytest.raises(ValueError):  # louder than the total amplitude
        second_waveform(Symbol.ZERO, samplerate=FS, carrier=CARRIER,
                        amplitude=0.5, monitor_amplitude=0.6)
    with pytest.raises(ValueError):  # non-integer frequency
        second_waveform(Symbol.ZERO, samplerate=FS, carrier=CARRIER,
                        monitor_amplitude=0.05, monitor_hz=300.5)
