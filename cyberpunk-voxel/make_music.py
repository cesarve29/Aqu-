#!/usr/bin/env python3
"""Procedural synthwave loop for the cyberpunk voxel video.

Exactly 24 s at 120 BPM (12 bars of 4/4). Every note tail, delay and reverb is
wrapped circularly, so the end of the file flows into its start with no seam.
Usage: python3 make_music.py out.wav
"""
import sys
import wave
import numpy as np

SR = 48000
BPM = 120.0
BEAT = 60.0 / BPM
BARS = 12
N = int(round(BARS * 4 * BEAT * SR))  # 24 s
rng = np.random.default_rng(7)

L = np.zeros(N)
R = np.zeros(N)


def put(sig, t, gain=1.0, pan=0.0, bus=None):
    """Add a mono signal at time t (seconds), wrapping around the loop."""
    i = int(round(t * SR)) % N
    idx = (i + np.arange(len(sig))) % N
    gl, gr = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    tl, tr = bus if bus is not None else (L, R)
    np.add.at(tl, idx, sig * gain * gl)
    np.add.at(tr, idx, sig * gain * gr)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def saw(freq, dur, cutoff, detune=0.0, phase=0.0):
    """Additive band-limited saw with a per-harmonic low-pass (cutoff may be an array)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    f = freq * (1 + detune)
    kmax = int(min(40, (SR * 0.45) // f))
    for k in range(1, kmax + 1):
        amp = (1.0 / k) / np.sqrt(1 + (k * f / cutoff) ** 4)
        out += amp * np.sin(2 * np.pi * k * f * t + phase * k)
    return out


def env(n, a, d, s, r):
    """ADSR envelope over n samples (release included)."""
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    e = np.full(n, s)
    e[:a] = np.linspace(0, 1, a, endpoint=False)
    e[a:a + d] = np.linspace(1, s, d, endpoint=False)
    e[n - r:] *= np.linspace(1, 0, r)
    return e


# ---- harmony: Am F C G | Am F C G | F G Am E  (E pulls back into Am at the loop point)
CH = {
    "Am": (45, [57, 60, 64, 69]), "F": (41, [57, 60, 65, 69]), "C": (36, [55, 60, 64, 67]),
    "G": (43, [55, 59, 62, 67]), "E": (40, [56, 59, 64, 68]),
}
PROG = ["Am", "F", "C", "G", "Am", "F", "C", "G", "F", "G", "Am", "E"]
BAR = 4 * BEAT
S16 = BEAT / 4

drums = (np.zeros(N), np.zeros(N))
music = (np.zeros(N), np.zeros(N))
kick_env = np.zeros(N)

# ---- drums
for b in range(BARS * 4):
    t0 = b * BEAT
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * (48 * t + (150 - 48) * 0.035 * (1 - np.exp(-t / 0.035)))
    k = np.sin(ph) * np.exp(-t / 0.13) + 0.25 * rng.standard_normal(n) * np.exp(-t / 0.004)
    put(k, t0, 0.95, 0, drums)
    put(np.exp(-t / 0.11), t0, 1.0, 0, (kick_env, np.zeros(N)))
    if b % 2 == 1:  # snare / clap on 2 and 4
        n = int(0.28 * SR)
        t = np.arange(n) / SR
        nz = rng.standard_normal(n)
        nz = nz - np.convolve(nz, np.ones(24) / 24, "same")  # crude high-pass
        s = nz * np.exp(-t / 0.075) * 0.5 + np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.35
        put(s, t0, 0.55, 0.05, drums)
for s in range(BARS * 16):  # hats
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    nz = np.diff(rng.standard_normal(n + 1))
    op = (s % 4 == 2)
    h = nz * np.exp(-t / (0.035 if op else 0.012))
    g = 0.16 if op else (0.10 if s % 2 == 0 else 0.055)
    put(h, s * S16, g, 0.35 if s % 2 else -0.25, drums)

# ---- bass (16th-note octave pulse), pad, arp, lead
ARP = [0, 1, 2, 3, 2, 1, 2, 3, 0, 1, 2, 3, 2, 3, 1, 2]
for bar, name in enumerate(PROG):
    root, notes = CH[name]
    tb = bar * BAR
    for s in range(16):
        m = root - 12 + (12 if s % 4 == 2 else 0)
        dur = S16 * 0.9
        n = int(dur * SR)
        cut = 180 + 900 * np.exp(-np.arange(n) / SR / 0.07)
        put(saw(hz(m), dur, cut) * env(n, 0.004, 0.06, 0.6, 0.02), tb + s * S16, 0.42, 0, music)
    # pad: detuned saws, slow filter swell, stereo spread
    dur = BAR + 0.6
    n = int(dur * SR)
    sweep = 500 + 1300 * (0.5 - 0.5 * np.cos(2 * np.pi * (tb + np.arange(n) / SR) / (4 * BAR)))
    e = env(n, 0.35, 0.3, 0.85, 0.6)
    for m in notes:
        for det, pan in ((-0.004, -0.8), (0.004, 0.8), (0.0, 0.0)):
            put(saw(hz(m), dur, sweep, det, rng.uniform(0, 6.28)) * e, tb, 0.055, pan, music)
    # arp: plucky 16ths one octave up
    for s in range(16):
        m = notes[ARP[s]] + 12
        dur = S16 * 1.6
        n = int(dur * SR)
        cut = 900 + 3800 * np.exp(-np.arange(n) / SR / 0.05)
        put(saw(hz(m), dur, cut) * env(n, 0.003, 0.08, 0.25, 0.08), tb + s * S16, 0.12, 0.55 * np.sin(s * 1.3), music)

# lead motif (bars 5-12), last phrase climbs back to the tonic of bar 1
LEAD = [(4, 0, 76, 2), (4, 2, 72, 1), (4, 3, 74, 1), (5, 0, 72, 3), (5, 3, 69, 1),
        (6, 0, 67, 2), (6, 2, 72, 2), (7, 0, 74, 3), (7, 3, 71, 1),
        (8, 0, 72, 2), (8, 2, 77, 2), (9, 0, 74, 2), (9, 2, 79, 2),
        (10, 0, 76, 3), (10, 3, 72, 1), (11, 0, 71, 2), (11, 2, 76, 1), (11, 3, 80, 1)]
for bar, beat, m, beats in LEAD:
    dur = beats * BEAT * 0.95
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
    sig = np.zeros(n)
    f = hz(m)
    for k in range(1, 16, 2):  # soft square
        sig += np.sin(2 * np.pi * k * f * np.cumsum(vib) / SR) / k / (1 + (k * f / 3200) ** 2)
    put(sig * env(n, 0.02, 0.1, 0.7, 0.12), bar * BAR + beat * BEAT, 0.085, -0.15, music)

# ---- mix: sidechain, circular delay + circular convolution reverb (both seamless)
duck = 1 - 0.6 * np.clip(kick_env, 0, 1)
mL, mR = music[0] * duck, music[1] * duck
d = int(0.75 * BEAT * SR)  # dotted-eighth ping-pong delay
dl = sum(0.38 * (0.55 ** k) * np.roll(mR if k % 2 == 0 else mL, d * (k + 1)) for k in range(5))
dr = sum(0.38 * (0.55 ** k) * np.roll(mL if k % 2 == 0 else mR, d * (k + 1)) for k in range(5))
mL, mR = mL + dl, mR + dr


def reverb(x, seed, t60=2.4):
    r = np.random.default_rng(seed)
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-6.9 * t / t60)
    ir[: int(0.012 * SR)] = 0
    pad = np.zeros(N)
    pad[:n] = ir / np.sqrt(np.sum(ir ** 2))
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(pad), N)  # circular -> wraps the tail


send_l, send_r = mL + 0.25 * drums[0], mR + 0.25 * drums[1]
L[:] = mL + drums[0] + 0.22 * reverb(send_l, 1)
R[:] = mR + drums[1] + 0.22 * reverb(send_r, 2)

mix = np.stack([L, R], 1)
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.6) / np.tanh(1.6) * 0.89  # gentle saturation / limiter
out = sys.argv[1] if len(sys.argv) > 1 else "music_loop.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print(out, N / SR, "s")
