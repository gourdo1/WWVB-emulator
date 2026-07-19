"""Synthesis of the amplitude-modulated carrier as audio samples.

The audible carrier is 20 kHz; the sound card's analog output stage
distorts it, and the 3rd harmonic lands exactly on WWVB's 60 kHz. At
sample rates of 144 kHz or more the 60 kHz carrier can be synthesized
directly instead.
"""

from __future__ import annotations

import numpy as np

from .timecode import LOW_POWER_SECONDS, Symbol

#: WWVB reduces carrier power by 17 dB at the start of each second.
REDUCED_AMPLITUDE = 10 ** (-17 / 20)  # ~0.141

HARMONIC_CARRIER_HZ = 20_000.0  # 3rd harmonic = 60 kHz
DIRECT_CARRIER_HZ = 60_000.0


def second_waveform(
    symbol: Symbol,
    *,
    samplerate: int = 48_000,
    carrier: float = HARMONIC_CARRIER_HZ,
    amplitude: float = 1.0,
    ramp_time: float = 0.001,
    monitor_hz: float = 300.0,
    monitor_amplitude: float = 0.0,
) -> np.ndarray:
    """Render one second of the signal for ``symbol`` as float32 samples.

    Each second starts at reduced power and returns to full power after
    0.2 s (ZERO), 0.5 s (ONE), or 0.8 s (MARK). Amplitude transitions use
    short raised-cosine ramps to avoid broadband clicks. ``carrier`` must be
    an integer number of cycles per second so that every second starts at
    phase zero and concatenated seconds stay phase-continuous.

    A nonzero ``monitor_amplitude`` mixes in an audible ``monitor_hz`` tone
    that follows the same envelope, so the transmission can be heard. It is
    carved out of ``amplitude`` (carrier + monitor peaks sum to exactly
    ``amplitude``) so the output never clips.
    """
    if carrier >= samplerate / 2:
        raise ValueError(
            f"carrier {carrier} Hz needs a sample rate above {2 * carrier:.0f} Hz"
        )
    if carrier != int(carrier):
        raise ValueError("carrier frequency must be an integer number of Hz")
    if monitor_amplitude:
        if not 0.0 < monitor_amplitude < amplitude:
            raise ValueError("monitor_amplitude must be in (0, amplitude)")
        if monitor_hz != int(monitor_hz):
            raise ValueError("monitor frequency must be an integer number of Hz")
        if monitor_hz >= samplerate / 2:
            raise ValueError(f"monitor frequency {monitor_hz} Hz is above Nyquist")

    n = int(samplerate)
    n_low = round(LOW_POWER_SECONDS[symbol] * samplerate)
    n_ramp = max(1, round(ramp_time * samplerate))

    envelope = np.full(n, 1.0, dtype=np.float64)
    envelope[:n_low] = REDUCED_AMPLITUDE

    # Raised-cosine ramps: down at the start of the second (the previous
    # second always ends at full power), up where full power resumes.
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n_ramp))
    lo, hi = REDUCED_AMPLITUDE, 1.0
    envelope[:n_ramp] = hi + (lo - hi) * ramp
    envelope[n_low : n_low + n_ramp] = lo + (hi - lo) * ramp[: max(0, n - n_low)]

    t = np.arange(n, dtype=np.float64) / samplerate
    tone = (amplitude - monitor_amplitude) * np.sin(2.0 * np.pi * carrier * t)
    if monitor_amplitude:
        tone += monitor_amplitude * np.sin(2.0 * np.pi * monitor_hz * t)
    return (envelope * tone).astype(np.float32)


def minute_waveform(frame: list[Symbol], **kwargs) -> np.ndarray:
    """Render a full 60-second frame; mainly for offline inspection/WAV export."""
    return np.concatenate([second_waveform(sym, **kwargs) for sym in frame])
