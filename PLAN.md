# WWVB Emulator — Project Plan

A small Python/Windows project that generates audio waveforms emulating the WWVB
60 kHz time signal, so radio-controlled clocks and watches ("atomic" clocks) can
be synced without receiving the real Fort Collins broadcast.

## 1. How this works physically (the core trick)

- WWVB broadcasts on a **60 kHz carrier**. No consumer sound card can output
  60 kHz directly (48 kHz sample rate → 24 kHz Nyquist limit; even 192 kHz
  hardware tops out at 96 kHz theoretical, with steep output filtering).
- The standard hobbyist workaround: generate a **20 kHz tone** and rely on the
  **3rd harmonic** (3 × 20 kHz = 60 kHz) created by nonlinear distortion in the
  sound card output stage / amplifier / earbud wire. Driving the output near max
  volume increases harmonic content.
- The "antenna" is simply a pair of earbuds or a small wire loop placed within a
  few centimeters of the watch/clock ferrite antenna.
- Practical requirement: run at **48 kHz sample rate** (20 kHz is comfortably
  under Nyquist and 48 kHz divides evenly: 2400 samples per 20 kHz-cycle-aligned
  frame). Optionally support 96/192 kHz if the device allows.

## 2. The WWVB time code (what we must generate)

- **1 bit per second, 60-second frame**, aligned to the top of the minute.
- Amplitude-shift keying: carrier power drops **-17 dB at the start of each
  second**, restored after:
  - **0.2 s** → bit `0`
  - **0.5 s** → bit `1`
  - **0.8 s** → **marker** (seconds 0, 9, 19, 29, 39, 49, 59; two consecutive
    markers identify the start of a minute)
- Frame contents (BCD-encoded): minutes, hours, day-of-year, 2-digit year,
  DUT1 sign/magnitude, leap-year flag, leap-second warning, DST status bits.
- **Important:** WWVB transmits **UTC**; the clock applies its configured time
  zone. We must convert local Windows time → UTC before encoding. (Alternately,
  offer a "lie about the time" option that encodes local time as UTC for watches
  with no zone setting.)
- The modern **BPSK phase modulation** (added 2012) is *out of scope* — nearly
  all consumer clocks use the legacy AM code, and audio-harmonic emulation can't
  carry phase reliably anyway.

## 3. Proposed architecture

```
wwvb_emulator/
├── pyproject.toml
├── README.md
├── src/wwvb_emulator/
│   ├── __init__.py
│   ├── timecode.py      # datetime (UTC) -> 60-element frame of symbols {ZERO, ONE, MARK}
│   ├── waveform.py      # frame + second-index -> numpy float32 samples (AM-modulated 20 kHz)
│   ├── player.py        # real-time streaming to audio device, aligned to system clock
│   └── cli.py           # argparse entry point: options, device selection, duration
└── tests/
    ├── test_timecode.py # known-vector tests (e.g., NIST documented example frames)
    └── test_waveform.py # envelope timing, sample counts, no clipping/discontinuities
```

### Module responsibilities

- **timecode.py** — pure function, no I/O: `encode_minute(dt_utc) -> list[Symbol]`.
  Handles BCD fields, DST flags (derive from US DST rules), leap year bit.
  Easily unit-tested against published NIST example frames.
- **waveform.py** — pure numpy: generate one second of samples given a symbol.
  20 kHz sine at 48 kHz; reduced-amplitude portion at ~14% amplitude (-17 dB).
  Apply short raised-cosine ramps (~1 ms) at amplitude transitions to avoid
  clicks that confuse receivers. Phase-continuous across seconds.
- **player.py** — `sounddevice` callback-driven output stream. Key challenge:
  **alignment to real time** — start each second's waveform at the actual
  system-clock second boundary, and periodically re-sync to compensate for
  sound-card clock drift (drop/insert a few samples between minutes).
- **cli.py** — options: `--minutes N` (run duration, default ~10 so a watch can
  lock), `--device` (list/select output), `--offset SECONDS` (advance the
  encoded time to compensate for propagation/processing delay or to
  deliberately set a clock ahead), `--timezone-mode utc|local-as-utc`,
  `--samplerate`, `--volume`.

## 4. Dependencies

- **numpy** — waveform math.
- **sounddevice** (PortAudio, wheels available for Windows) — low-latency
  output with device selection. Fallback consideration: `simpleaudio` or
  `winsound` are not suitable (no streaming/callback control).
- Python **3.11+**, standard `zoneinfo` for DST logic. No other runtime deps.
- Dev: `pytest`, `ruff`.

## 5. Verification strategy

1. **Unit tests** for the encoder against NIST's documented example frame and
   edge cases (year rollover, DST transition days, leap years).
2. **Offline waveform inspection**: render a minute to a WAV file; check the
   envelope timing in Audacity/scipy (0.2/0.5/0.8 s low-power windows, -17 dB
   ratio).
3. **Hardware test**: put a radio-controlled watch/clock in manual-receive mode
   with earbuds coiled next to it; expect lock within 3–10 minutes. Windows
   audio "enhancements" (loudness EQ, spatial sound) must be disabled — they
   filter/compress the 20 kHz tone; document this in the README.

## 6. Milestones

1. **M1 — Encoder**: `timecode.py` + passing unit tests. (No audio yet.)
2. **M2 — Waveform**: render a full minute to WAV; verify envelope offline.
3. **M3 — Real-time playback**: streaming with second-boundary alignment.
4. **M4 — CLI polish**: device selection, offset, duration, README with
   hardware setup instructions (volume, earbud placement, Windows audio
   settings).
5. **M5 (stretch)**: auto-repeat with drift correction for multi-hour runs;
   optional 96/192 kHz modes; simple "did it lock?" troubleshooting guide.

## 7. Risks / open questions

- **Harmonic strength varies by hardware** — some USB DACs are too clean
  (little 3rd-harmonic distortion). Mitigation: offer a `--square` option
  (band-limited squarish wave has strong odd harmonics) and document trying
  different output devices/volumes.
- **Windows audio latency/jitter** — WASAPI shared mode adds buffering delay.
  The `--offset` option plus measuring stream latency from `sounddevice`
  should keep encoded time within ±0.1 s of true time, which is ample for
  consumer clocks.
- **Legal note**: this is a near-field audio device, not a radio transmitter;
  intentional radiators at 60 kHz have FCC Part 15 limits, but earbud-leakage
  field strength at centimeter range is the standard, accepted hobby approach.
