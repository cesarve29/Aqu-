"""
Procedural soundtrack for NEON RUSH (dark synthwave + sound design).
Everything is synthesized with numpy/scipy and synced to the shot timeline.

    python3 soundtrack.py out.wav
"""
import sys
import numpy as np
from scipy import signal
import wave

SR = 48000
DUR = 65.5
N = int(SR * DUR)
BPM = 120.0
BEAT = 60.0 / BPM
rng = np.random.default_rng(2087)

F = lambda frame: frame / 24.0          # frame -> seconds
T_LED, T_SPIN, T_TAKEOFF = F(236), F(296), F(360)
T_DROP, T_TRACK, T_BRIDGE = F(528), F(672), F(816)
T_SLOW0, T_SLOW1, T_ROLL = F(838), F(946), F(880)
T_HEADON, T_PASS, T_ASCENT = F(960), F(1074), F(1128)
T_SIGN0, T_SIGN1, T_REVEAL, T_END = F(1262), F(1300), F(1344), F(1488)

t = np.arange(N) / SR
L = np.zeros(N)
R = np.zeros(N)


def idx(sec):
    return int(max(0, min(N, sec * SR)))


def add(sig, start, gain=1.0, pan=0.0):
    s = idx(start)
    e = min(N, s + len(sig))
    if e <= s:
        return
    sig = sig[: e - s] * gain
    L[s:e] += sig * np.sqrt(0.5 * (1 - pan))
    R[s:e] += sig * np.sqrt(0.5 * (1 + pan))


def env_adsr(n, a=0.005, d=0.1, s=0.6, r=0.2, sus_len=None):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    sus_n = max(0, n - a_n - d_n - r_n) if sus_len is None else int(sus_len * SR)
    e = np.concatenate([np.linspace(0, 1, max(1, a_n)), np.linspace(1, s, max(1, d_n)),
                        np.full(sus_n, s), np.linspace(s, 0, max(1, r_n))])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def saw(freq, n, detune=0.0, phase=0.0):
    tt = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-detune, 0.0, detune) if detune else (0.0,):
        ph = (tt * freq * (1 + d) + phase + rng.random()) % 1.0
        out += 2 * ph - 1
    return out / (3 if detune else 1)


def square(freq, n, pw=0.5):
    tt = np.arange(n) / SR
    return np.where((tt * freq) % 1.0 < pw, 1.0, -1.0)


def lowpass(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "low")
    return signal.lfilter(b, a, x)


def highpass(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "high")
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(0.99, hi / (SR / 2))], "band")
    return signal.lfilter(b, a, x)


def sweep_lowpass(x, f0, f1, blocks=64):
    """Time-varying low-pass (block-wise, exponential sweep)."""
    out = np.zeros_like(x)
    edges = np.linspace(0, len(x), blocks + 1).astype(int)
    zi = None
    for i in range(blocks):
        fc = f0 * (f1 / f0) ** (i / max(1, blocks - 1))
        b, a = signal.butter(2, min(0.99, fc / (SR / 2)), "low")
        if zi is None:
            zi = signal.lfilter_zi(b, a) * 0
        seg, zi = signal.lfilter(b, a, x[edges[i]:edges[i + 1]], zi=zi)
        out[edges[i]:edges[i + 1]] = seg
    return out


def note(n):  # midi -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def kick(gain=1.0):
    n = int(0.45 * SR)
    tt = np.arange(n) / SR
    f = 45 + 110 * np.exp(-tt * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-tt * 7)
    click = highpass(rng.standard_normal(n), 3000) * np.exp(-tt * 300) * 0.3
    return np.tanh(1.6 * (body + click)) * gain


def snare(gain=1.0):
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 25)
    nz = bandpass(rng.standard_normal(n), 1200, 9000) * np.exp(-tt * 14)
    return (0.5 * tone + 0.9 * nz) * gain


def hat(gain=1.0, open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    tt = np.arange(n) / SR
    return highpass(rng.standard_normal(n), 7000) * np.exp(-tt * (12 if open_ else 70)) * gain


def crash(gain=1.0):
    n = int(2.5 * SR)
    tt = np.arange(n) / SR
    return highpass(rng.standard_normal(n), 4000) * np.exp(-tt * 1.6) * gain


def boom(gain=1.0, length=3.0):
    n = int(length * SR)
    tt = np.arange(n) / SR
    f = 30 + 70 * np.exp(-tt * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 1.3)
    nz = lowpass(rng.standard_normal(n), 900) * np.exp(-tt * 4) * 0.6
    return np.tanh(1.5 * (sub + nz)) * gain


def whoosh(length, f0, f1, gain=1.0, shape="bell"):
    n = int(length * SR)
    nz = rng.standard_normal(n)
    out = np.zeros(n)
    blocks = 48
    edges = np.linspace(0, n, blocks + 1).astype(int)
    for i in range(blocks):
        fc = f0 * (f1 / f0) ** (i / (blocks - 1))
        seg = nz[edges[i]:edges[i + 1]]
        out[edges[i]:edges[i + 1]] = bandpass(seg, fc * 0.6, fc * 1.6, 1)
    x = np.linspace(0, 1, n)
    if shape == "bell":
        e = np.sin(np.pi * x) ** 2
    elif shape == "rise":
        e = x ** 2.5
    else:
        e = (1 - x) ** 2
    return out * e * gain


def riser(length, gain=1.0):
    n = int(length * SR)
    x = np.linspace(0, 1, n)
    nz = whoosh(length, 300, 7000, 1.0, "rise")
    f = 110 * 2 ** (x * 3)
    tone = saw(1, n) * 0
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sign(np.sin(ph)) * 0.25 * x ** 2
    return (nz + lowpass(tone, 3000)) * gain


def reverb(x, seconds=2.5, wet=0.3, damp=3000):
    n = int(seconds * SR)
    tt = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-tt * 6.9 / seconds)
    ir = lowpass(ir, damp)
    ir /= np.sqrt(np.sum(ir ** 2))
    wet_sig = signal.fftconvolve(x, ir)[: len(x)]
    return x * (1 - wet) + wet_sig * wet * 3


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------
CHORDS = [[57, 60, 64], [53, 57, 60], [50, 53, 57], [52, 56, 59]]   # Am F Dm E
BAR = 4 * BEAT


def chord_at(sec):
    return CHORDS[int(sec / (2 * BAR)) % 4]


def pad_track():
    out = np.zeros(N)
    nbar = int(DUR / (2 * BAR)) + 1
    for i in range(nbar):
        s = i * 2 * BAR
        n = int(2 * BAR * SR) + int(0.6 * SR)
        ch = CHORDS[i % 4]
        sig = np.zeros(n)
        for m in ch + [ch[0] - 12]:
            sig += saw(note(m), n, detune=0.004)
        sig = lowpass(sig, 1400) * env_adsr(n, 0.8, 0.5, 0.8, 0.9)
        e = min(N, idx(s) + n)
        out[idx(s):e] += sig[: e - idx(s)] * 0.09
    return out


def bass_track(start, stop, muted=()):
    out = np.zeros(N)
    step = BEAT / 2
    k0 = int(np.ceil(start / step))
    k = k0
    while k * step < stop:
        s = k * step
        if not any(a <= s < b for a, b in muted):
            root = chord_at(s)[0] - 24
            if k % 8 == 7:
                root += 12
            n = int(step * SR * 0.95)
            sig = saw(note(root), n, detune=0.003) + 0.5 * square(note(root - 12), n)
            env = env_adsr(n, 0.003, 0.12, 0.35, 0.05)
            sig = lowpass(sig, 280 + 1600 * env.mean()) * env
            out[idx(s):idx(s) + n] += sig[: max(0, min(n, N - idx(s)))] * 0.32
        k += 1
    return out


def arp_track(start, stop, muted=(), rate=4, octave=0, gain=0.11):
    out = np.zeros(N)
    step = BEAT / rate
    k = int(np.ceil(start / step))
    pattern = [0, 1, 2, 1, 2, 0, 2, 1]
    while k * step < stop:
        s = k * step
        if not any(a <= s < b for a, b in muted):
            ch = chord_at(s)
            m = ch[pattern[k % len(pattern)]] + 12 + octave + (12 if (k // 8) % 2 else 0)
            n = int(step * SR * 1.6)
            sig = square(note(m), n, 0.3) * env_adsr(n, 0.002, 0.08, 0.2, 0.05)
            sig = lowpass(sig, 2600)
            e = min(N, idx(s) + n)
            out[idx(s):e] += sig[: e - idx(s)] * gain
        k += 1
    # ping-pong delay
    d = int(BEAT * 0.75 * SR)
    dl = np.zeros(N)
    dl[d:] = out[:-d] * 0.35
    return out, dl


def drums(start, stop, muted=(), half=False):
    out = np.zeros(N)
    k = int(np.ceil(start / (BEAT / 2)))
    while k * BEAT / 2 < stop:
        s = k * BEAT / 2
        if not any(a <= s < b for a, b in muted):
            beat_in_bar = (k // 2) % 4
            on = k % 2 == 0
            if on and (beat_in_bar in (0, 2) if half else True):
                if not half or beat_in_bar == 0:
                    sig = kick(0.9)
                    out[idx(s):idx(s) + len(sig)] += sig[: max(0, N - idx(s))][:len(sig)]
            if on and beat_in_bar in ((2,) if half else (1, 3)):
                sig = snare(0.55)
                out[idx(s):idx(s) + len(sig)] += sig[: max(0, N - idx(s))][:len(sig)]
            hg = 0.16 if not on else 0.09
            sig = hat(hg, open_=(not on and beat_in_bar == 3))
            out[idx(s):idx(s) + len(sig)] += sig[: max(0, N - idx(s))][:len(sig)]
        k += 1
    return out


# ---------------------------------------------------------------------------
# Arrangement
# ---------------------------------------------------------------------------
def main(path):
    global L, R
    slow = [(T_SLOW0, T_SLOW1 + 0.05)]
    # 1) ambience: rain + city rumble across the whole film
    rain = highpass(rng.standard_normal(N), 1500) * 0.05
    rain += lowpass(rng.standard_normal(N), 400) * 0.06
    amb = np.ones(N)
    amb *= 0.6 + 0.4 * np.clip(1 - (t - 15) / 10, 0, 1)        # louder in the quiet intro
    rain *= amb * np.clip(t / 2.5, 0, 1)
    L += rain * 0.9
    R += np.roll(rain, 997) * 0.9

    # 2) pad throughout, swelling in the intro and the reveal
    pad = pad_track()
    pad_env = np.clip(t / 6, 0, 1) * (0.8 + 1.8 * np.clip((t - T_REVEAL) / 3, 0, 1))
    pad_env *= np.where((t > T_SLOW0) & (t < T_SLOW1), 1.4, 1.0)
    pad_env *= np.clip((T_END + 3.0 - t) / 3.0, 0, 1)
    pad = reverb(pad * pad_env, 3.0, 0.35)
    L += pad
    R += np.roll(pad, 240)

    # 3) intro pulse (heartbeat sub) before takeoff
    for k in range(int(8 / BEAT), int(T_TAKEOFF / BEAT)):
        s = k * BEAT
        add(lowpass(kick(0.35), 200), s, 1.0)

    # 4) bass / arp / drums
    music_start = T_TAKEOFF
    bass = bass_track(music_start, T_REVEAL, muted=slow)
    bass *= np.clip((t - music_start) / (T_DROP - music_start), 0.25, 1.0)
    arp, arp_d = arp_track(T_DROP, T_REVEAL + 2 * BEAT, muted=slow)
    arp2, arp2_d = arp_track(T_ASCENT, T_REVEAL, rate=4, octave=12, gain=0.05)
    dr = drums(T_DROP, T_ASCENT, muted=slow)
    dr += drums(T_ASCENT, T_SIGN1 - 0.01, half=True)
    dr += drums(T_SIGN1, T_REVEAL)
    L += bass + arp + arp_d * 0.3 + arp2 + 0.6 * arp2_d + dr
    R += bass + 0.6 * arp + arp_d + 0.6 * arp2 + arp2_d + dr

    # slow-motion section: muffled, reverb-drenched echo of the groove
    s0, s1 = idx(T_SLOW0 - 0.2), idx(T_SLOW1)
    ghost = drums(T_SLOW0, T_SLOW1, half=True) + bass_track(T_SLOW0, T_SLOW1)
    ghost = reverb(lowpass(ghost, 380), 3.5, 0.6)
    L += ghost * 0.22
    R += ghost * 0.22

    # 5) sound design
    # LED power-on stutter blips
    for dt_, f in ((0.0, 880), (0.09, 1320), (0.21, 1760)):
        n = int(0.12 * SR)
        add(square(f, n, 0.25) * env_adsr(n, 0.002, 0.05, 0.3, 0.04) * 0.08, T_LED + 0.04 + dt_, 1.0, 0.2)
    add(boom(0.25, 1.5), T_LED + 0.25)
    # propeller spin-up whine and motor hum for the flight
    n = idx(T_REVEAL + 4) - idx(T_SPIN)
    tt = np.arange(n) / SR
    spin = np.clip(tt / 2.2, 0, 1) ** 1.5
    f = 70 + 210 * spin
    ph = 2 * np.pi * np.cumsum(f) / SR
    hum = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3.01 * ph)) * (0.5 + 0.5 * np.sin(4 * ph))
    hum = lowpass(hum, 2500) * (0.06 + 0.06 * spin)
    fade = np.clip((idx(T_REVEAL + 4) - idx(T_SPIN) - np.arange(n)) / (3 * SR), 0, 1)
    add(hum * fade, T_SPIN)
    # take-off + edge leap
    add(whoosh(2.2, 200, 1800, 0.35), T_TAKEOFF + 2.0, 1.0, -0.4)
    add(riser(T_DROP - (T_TAKEOFF + 1.0), 0.22), T_TAKEOFF + 1.0)
    add(whoosh(1.8, 2500, 300, 0.5, "bell"), F(455), 1.0, 0.3)
    add(boom(0.9, 3.5), T_DROP)
    add(crash(0.25), T_DROP)
    # chase: passing whooshes on the beat
    for s in np.arange(T_DROP + 2 * BAR, T_SLOW0 - 1, 2 * BAR):
        add(whoosh(1.0, 400, 2500, 0.22), s - 0.5, 1.0, rng.uniform(-0.7, 0.7))
    add(crash(0.18), T_TRACK)
    # bridge: slow-mo drop + deep roll whoosh + re-entry
    add(whoosh(0.6, 3000, 200, 0.4, "fall"), T_SLOW0 - 0.1)
    add(boom(0.5, 4.0), T_SLOW0 + 0.1)
    add(reverb(whoosh(3.0, 150, 900, 0.5), 2.5, 0.3), T_ROLL - 1.6)
    add(riser(1.6, 0.3), T_SLOW1 - 1.6)
    add(boom(0.6, 2.0), T_SLOW1)
    add(crash(0.25), T_SLOW1)
    # head-on pass-by (doppler)
    n = int(2.4 * SR)
    tt = np.arange(n) / SR - 1.2
    fdop = 320 * np.where(tt < 0, 1.25, 0.8)
    fdop = 320 * (1 + 0.25 * np.tanh(-tt * 6))
    ph = 2 * np.pi * np.cumsum(fdop) / SR
    amp = 1 / (1 + (tt * 5) ** 2)
    pass_sig = (np.sin(ph) + 0.4 * np.sin(2 * ph)) * amp * 0.35 + whoosh(2.4, 300, 3000, 0.45)
    pan_curve = np.tanh(tt * 4)
    s = idx(T_PASS - 1.2)
    e = min(N, s + n)
    L[s:e] += (pass_sig * np.sqrt(0.5 * (1 - pan_curve)))[: e - s]
    R[s:e] += (pass_sig * np.sqrt(0.5 * (1 + pan_curve)))[: e - s]
    # ascent riser into the sign power-on
    add(riser(T_SIGN1 - T_ASCENT, 0.18), T_ASCENT)
    for k in range(14):
        s = T_SIGN0 + rng.uniform(0, T_SIGN1 - T_SIGN0)
        n = int(rng.uniform(0.03, 0.12) * SR)
        buzz = np.sign(np.sin(2 * np.pi * 120 * np.arange(n) / SR)) * highpass(rng.standard_normal(n), 2000) * 0.15
        add(buzz, s, 1.0, rng.uniform(-0.5, 0.5))
    add(boom(1.0, 4.5), T_SIGN1)
    add(crash(0.3), T_SIGN1)
    # reveal: final hit for the title card
    add(reverb(boom(1.0, 5.0), 4.0, 0.5), T_END)
    n = int(6.0 * SR)
    final = np.zeros(n)
    for m in (45, 57, 60, 64, 69):
        final += saw(note(m), n, detune=0.005)
    final = lowpass(final, 900) * env_adsr(n, 0.05, 1.0, 0.5, 3.0) * 0.08
    add(reverb(final, 4.0, 0.5), T_END)

    # master: gentle compression, fades, limiting
    mix = np.stack([L, R])
    mix *= np.clip(t / 1.5, 0, 1)
    mix *= np.clip((DUR - t) / 2.0, 0, 1)
    peak = np.max(np.abs(mix))
    mix = np.tanh(mix / peak * 1.6) / np.tanh(1.6)
    mix *= 0.89
    data = (mix.T * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", path, DUR, "s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav")
