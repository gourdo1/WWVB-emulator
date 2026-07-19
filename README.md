# WWVB Emulator

This tool syncs radio-controlled ("atomic") clocks and watches without the Fort
Collins broadcast: it generates the WWVB legacy AM time code as audio.
It plays a 20 kHz tone whose **3rd harmonic — created by ordinary analog
distortion in your sound card and headphone cable — lands exactly on WWVB's
60 kHz carrier**. A pair of earbuds coiled next to the clock acts as a tiny
near-field antenna.

## Install

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## Use

1. **Disable Windows audio enhancements** for your output device (loudness
   equalization, spatial sound, "enhance audio") — they mangle a 20 kHz tone.
   Settings → Sound → device Properties → Enhancements/Advanced.
2. You will need to set your system volume to a very high level or **maximum**
   (harmonic distortion is the mechanism used to create the 60kHz tones).
3. You may need to put the watch near a coil of wire such as earbuds, a
   headphone cable or the output speaker itself, as the audio waves must be
   converted into RF for the watch's reciever to pick up the signal.
4. Put the clock/watch into **manual receive mode** (often holding a button —
   check its manual).
5. Run: .venv\Scripts\wwvb-emulator

A lock typically takes 3–10 minutes. Reposition the loop if it fails.

### Useful options

| Option | Purpose |
| --- | --- |
| `--list-devices` / `--device N` | pick a specific audio output |
| `--offset SECONDS` | shift encoded time (compensate latency, or set a clock deliberately fast) |
| `--time-source local` | encode local wall time as UTC, for receivers with no time-zone setting |
| `--time 2026-07-17T15:30` | transmit a fixed time (testing); taken as UTC, or append an offset (`09:30-06:00`) |
| `--zone America/Denver` | interpret a naive `--time` in a named IANA zone, DST handled automatically |
| `--monitor 0.05` | mix in a faint audible tone (default 300 Hz, set with `--monitor-freq`) that follows the bit pattern, so you can hear the transmission |
| `--wav out.wav` | render to a WAV file instead of playing (inspect in Audacity) |
| `--mode direct --samplerate 192000` | synthesize a true 60 kHz carrier if your DAC supports 192 kHz |

## How it works

WWVB sends one bit per second in 60-second frames: carrier power drops 17 dB
at the start of each second and returns after 0.2 s (bit 0), 0.5 s (bit 1),
or 0.8 s (position marker). Frames carry BCD-encoded UTC minute, hour,
day-of-year, year, DUT1, leap-year/leap-second flags, and DST status. See
`PLAN.md` for the design and module layout.

## Troubleshooting

- **No lock:** try a different output device (`--list-devices`) — some clean
  USB DACs produce too little harmonic distortion. Cheap built-in audio often
  works better. Try `--mode direct` with a 192 kHz-capable device.
- **Clock off by whole hours:** check the clock's time-zone setting, or try
  `--time-source local`.
- **Consistently a fraction of a second late:** add `--offset 0.1` (or your
  measured audio latency).
