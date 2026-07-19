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
3. Plug ordinary wired earbuds/headphones into the computer's audio output —
   the same jack you'd listen to music through, and the output this program
   plays on (`--list-devices` if you have several). Coil the cable into a
   small loop (a few turns) and lay it directly against the watch or clock,
   within a few centimeters of its antenna. The sound coming out of the
   earbuds is irrelevant — the earpieces just complete the circuit so current
   flows through the cable, and the coil works as a tiny magnetic
   transmitting antenna (see
   [How the coil couples to the watch](#how-the-coil-couples-to-the-watch)).
   Alternatively, hold the watch directly in front of an active (amplified)
   speaker at high volume: the speaker's voice coil is itself a coil carrying
   the signal current, and its amplifier provides the distortion.
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

### How the coil couples to the watch

The signal never travels through the air as sound **or** as a normal radio
broadcast — the coupling is magnetic, like a transformer:

1. **The signal is electrical current, not sound.** Playing the 20 kHz tone
   drives an alternating current through the headphone cable, and the sound
   card's analog distortion adds a 3rd-harmonic component at 60 kHz to that
   current. What the earbuds do acoustically doesn't matter; what matters is
   the current in the wire.
2. **A coil concentrates the magnetic field.** Any current-carrying wire is
   surrounded by a magnetic field, but a straight cable spreads it thinly.
   Winding the cable into a loop makes each turn's field add up in the
   middle — N turns gives roughly N× the field strength. A loudspeaker works
   too, without any winding on your part: its voice coil is a ready-made
   multi-turn coil carrying the signal current, which is why a watch held
   directly in front of an active speaker can lock.
3. **The watch receives magnetically.** WWVB receivers use a small ferrite-rod
   loopstick antenna that responds to the *magnetic* component of the 60 kHz
   signal. At 60 kHz the wavelength is 5 km, so a few centimeters of wire
   radiates essentially nothing as a propagating radio wave. Instead, coil and
   ferrite rod act like the primary and secondary windings of a loosely
   coupled air-core transformer: the coil's oscillating field induces a
   voltage directly in the watch's antenna, indistinguishable to the receiver
   from the real Fort Collins signal.
4. **This is why position matters.** The near field falls off roughly as
   1/distance³ — doubling the distance costs about 9× (18 dB) of coupling —
   so the loop must be within a few centimeters. Orientation matters too: the
   coil's field lines must run *along* the ferrite rod's axis, which is why
   repositioning or rotating the loop can make the difference between locking
   and not.

## Troubleshooting

- **No lock:** try a different output device (`--list-devices`) — some clean
  USB DACs produce too little harmonic distortion. Cheap built-in audio often
  works better. Try `--mode direct` with a 192 kHz-capable device.
- **No lock in front of a speaker:** the speaker's crossover may send the
  20 kHz tone only to the tweeter, so try holding the watch in front of the
  tweeter rather than the woofer. Speakers with DSP processing may also
  filter or resample the tone away entirely — earbuds are the more reliable
  fallback.
- **Clock off by whole hours:** check the clock's time-zone setting, or try
  `--time-source local`.
- **Consistently a fraction of a second late:** add `--offset 0.1` (or your
  measured audio latency).
