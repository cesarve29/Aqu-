"""Procedural soundtrack: original music, synthesized sound effects, voice-over mix."""
import json
import math
import os
import subprocess
import numpy as np
from scipy import signal

from engine import BUILD, ROOT

SR = 48000
rng = np.random.default_rng(12345)
VOZ = os.path.join(ROOT, "voz")
OUT = os.path.join(ROOT, "out")


# ===================================================================== DSP helpers
def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(n - a_n - d_n - r_n, 0)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False), np.linspace(1, s, d_n, endpoint=False),
                        np.full(s_n, s), np.linspace(s, 0, r_n)])
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def expdec(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, f, order=2):
    sos = signal.butter(order, f, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def hp(x, f, order=2):
    sos = signal.butter(order, f, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def noise(n):
    return rng.standard_normal(n)


def pink(n):
    w = rng.standard_normal(n)
    X = np.fft.rfft(w)
    f = np.arange(len(X))
    f[0] = 1
    X = X / np.sqrt(f)
    y = np.fft.irfft(X, n)
    return y / (np.std(y) + 1e-9)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pan(x, p):
    """p in [-1,1] -> stereo"""
    l = math.cos((p + 1) * math.pi / 4)
    r = math.sin((p + 1) * math.pi / 4)
    return np.stack([x * l, x * r], 1)


class Bus:
    def __init__(self, dur):
        self.n = int(dur * SR) + SR * 4
        self.buf = np.zeros((self.n, 2), np.float32)

    def add(self, t, x, gain=1.0, p=0.0):
        if x.ndim == 1:
            x = pan(x, p)
        i = int(t * SR)
        if i < 0:
            x = x[-i:]
            i = 0
        j = min(i + len(x), self.n)
        if j > i:
            self.buf[i:j] += (x[:j - i] * gain).astype(np.float32)


def make_ir(dur=3.0, predelay=0.02, damp=4000, seed=1):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 6.9 / dur)
    irl = r.standard_normal(n) * env
    irr = r.standard_normal(n) * env
    irl = lp(irl, damp); irr = lp(irr, damp)
    pd = np.zeros(int(predelay * SR))
    ir = np.stack([np.concatenate([pd, irl]), np.concatenate([pd, irr])], 1)
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def reverb(buf, ir, wet=0.3):
    out = np.zeros_like(buf)
    for c in range(2):
        out[:, c] = signal.oaconvolve(buf[:, c], ir[:, c], mode="full")[:len(buf)]
    return buf * (1 - wet * 0.5) + out * wet


# ===================================================================== instruments
def fm_bell(f, dur, ratio=3.5, index=2.5, tau=1.2, amp=0.3):
    t = t_arr(dur)
    ie = index * np.exp(-t / (tau * 0.5))
    y = np.sin(2 * np.pi * f * t + ie * np.sin(2 * np.pi * f * ratio * t))
    e = np.exp(-t / tau) * np.minimum(1, t / 0.003)
    return amp * y * e


def celesta(f, dur, amp=0.25):
    t = t_arr(dur)
    y = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6) + 0.12 * np.sin(2 * np.pi * 4.01 * f * t) * np.exp(-t * 12)
    e = np.exp(-t / 0.9) * np.minimum(1, t / 0.002)
    return amp * y * e


def pluck(f, dur, amp=0.35, damp=0.996):
    """Karplus-Strong"""
    n = int(dur * SR)
    N = max(int(SR / f), 2)
    buf = rng.uniform(-1, 1, N)
    buf = lp(buf, min(4000, SR / 2 - 100))
    out = np.zeros(n)
    idx = 0
    b = buf.copy()
    for i in range(n):
        v = b[idx]
        nxt = b[(idx + 1) % N]
        b[idx] = damp * 0.5 * (v + nxt)
        out[i] = v
        idx = (idx + 1) % N
    return amp * out * np.minimum(1, np.arange(n) / 40)


def pluck_fast(f, dur, amp=0.35):
    """cheaper pluck: decaying harmonic stack"""
    t = t_arr(dur)
    y = np.zeros_like(t)
    for h in range(1, 8):
        y += np.sin(2 * np.pi * f * h * t) * np.exp(-t * (3 + h * 2.5)) / h
    return amp * y * np.minimum(1, t / 0.003)


def strings(f, dur, amp=0.12, attack=0.4, release=0.6, vib=0.004, bright=8):
    t = t_arr(dur)
    ph = 2 * np.pi * f * (t + vib / (2 * np.pi * 5.2) * np.sin(2 * np.pi * 5.2 * t) * 0)
    vibr = 1 + vib * np.sin(2 * np.pi * 5.2 * t + rng.random() * 6)
    phase = 2 * np.pi * np.cumsum(f * vibr) / SR
    y = np.zeros_like(t)
    for h in range(1, bright + 1):
        y += np.sin(h * phase + rng.random() * 6) / h
    for det in (0.997, 1.003):
        y += 0.5 * np.sin(phase * det)
    e = env_adsr(len(t), attack, 0.2, 0.85, release)
    return amp * y * e


def pad(f, dur, amp=0.10, attack=1.2, release=1.5):
    t = t_arr(dur)
    y = np.zeros_like(t)
    for det in (0.995, 1.0, 1.005):
        for h, w in ((1, 1.0), (2, 0.4), (3, 0.2), (4, 0.1)):
            y += w * np.sin(2 * np.pi * f * det * h * t + rng.random() * 6)
    y *= 1 + 0.15 * np.sin(2 * np.pi * 0.2 * t)
    return amp * y * env_adsr(len(t), attack, 0.3, 0.9, release) / 3


def choir(f, dur, amp=0.08, attack=1.0, release=1.2, vowel="a"):
    t = t_arr(dur)
    formants = {"a": [(800, 1.0), (1150, 0.5), (2900, 0.2)], "o": [(450, 1.0), (800, 0.4), (2830, 0.1)]}[vowel]
    vibr = 1 + 0.006 * np.sin(2 * np.pi * 5.0 * t + rng.random() * 6)
    y = np.zeros_like(t)
    for v in range(3):
        det = 1 + (v - 1) * 0.004
        phase = 2 * np.pi * np.cumsum(f * det * vibr) / SR
        for h in range(1, 24):
            fh = f * h
            if fh > 5000:
                break
            g = sum(a * math.exp(-((fh - fc) / (fc * 0.18)) ** 2) for fc, a in formants) + 0.02
            y += g * np.sin(h * phase + rng.random() * 6)
    return amp * y * env_adsr(len(t), attack, 0.3, 0.9, release) / 3


def timpani(f, dur=2.0, amp=0.5):
    t = t_arr(dur)
    fr = f * (1 + 0.15 * np.exp(-t * 30))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    y = np.sin(ph) * np.exp(-t * 1.8) + 0.3 * lp(noise(len(t)), 400) * np.exp(-t * 20)
    return amp * y


def sleigh(dur=0.25, amp=0.12):
    t = t_arr(dur)
    y = np.zeros_like(t)
    for k in range(5):
        f = 2600 + rng.random() * 3800
        y += np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t * (18 + rng.random() * 10))
    y += 0.4 * hp(noise(len(t)), 6000) * np.exp(-t * 30)
    return amp * y


def bell_tone(f, dur=5.0, amp=0.3):
    t = t_arr(dur)
    partials = [(0.5, 0.5, 2.5), (1.0, 1.0, 1.6), (1.19, 0.6, 1.2), (1.5, 0.45, 1.0), (2.0, 0.4, 0.8), (2.52, 0.25, 0.6),
                (3.0, 0.2, 0.45), (4.07, 0.1, 0.3)]
    y = np.zeros_like(t)
    for r, a, d in partials:
        y += a * np.sin(2 * np.pi * f * r * t + rng.random() * 6) * np.exp(-t / (d * dur / 3))
    y *= np.minimum(1, t / 0.002)
    return amp * y / 2


# ===================================================================== music
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11],
          "dorian": [0, 2, 3, 5, 7, 9, 10]}
THEME = [(5, 1), (3, 1), (4, 1), (5, 1), (6, 2), (5, 2), (4, 1), (3, 1), (2, 1), (3, 1), (1, 4),
         (3, 1), (5, 1), (8, 1), (7, 1), (6, 2), (5, 2), (4, 1), (6, 1), (5, 1), (2, 1), (1, 4)]
THEME_CHORDS = [1, 4, 2, 1, 1, 4, 5, 1]


def deg2midi(root, scale, deg, octave=0):
    sc = SCALES[scale]
    d = deg - 1
    o = d // 7
    return root + 12 * (o + octave) + sc[d % 7]


def chord_notes(root, scale, deg, octave=0):
    return [deg2midi(root, scale, deg + k, octave) for k in (0, 2, 4)]


MOODS = {
    # key root midi, scale, bpm, progression (scale degrees), instruments, theme?, intensity
    "intro": dict(root=62, scale="major", bpm=70, prog=[1, 6, 4, 5], inst=["pad", "celesta_theme", "choir"], level=0.9),
    "village": dict(root=62, scale="major", bpm=92, prog=THEME_CHORDS, inst=["pad", "celesta_theme", "pizz", "sleigh"], level=0.75),
    "tension": dict(root=62, scale="minor", bpm=72, prog=[1, 6, 4, 5], inst=["pad", "strings_trem", "low_drone"], level=0.8),
    "resolve": dict(root=59, scale="minor", bpm=84, prog=[1, 6, 3, 7], inst=["pad", "pizz", "celesta_arp"], level=0.7),
    "forest": dict(root=64, scale="minor", bpm=66, prog=[1, 6, 3, 7], inst=["pad", "celesta_sparse", "low_drone"], level=0.7),
    "wonder": dict(root=67, scale="lydian", bpm=76, prog=[1, 2, 6, 4], inst=["pad", "celesta_arp", "choir"], level=0.75),
    "cave": dict(root=57, scale="minor", bpm=70, prog=[1, 6, 3, 7], inst=["pad", "glass_arp", "low_drone"], level=0.75),
    "forge": dict(root=50, scale="minor", bpm=60, prog=[1, 4, 5, 1], inst=["strings_low", "timpani", "low_drone"], level=0.8),
    "golem": dict(root=53, scale="major", bpm=68, prog=[6, 4, 1, 5], inst=["pad", "strings", "celesta_sparse"], level=0.75),
    "storm": dict(root=60, scale="minor", bpm=96, prog=[1, 6, 4, 5], inst=["strings_trem", "timpani", "choir", "low_drone"], level=0.85),
    "release": dict(root=56, scale="major", bpm=70, prog=[1, 5, 6, 4], inst=["pad", "choir", "celesta_arp", "strings"], level=0.85),
    "triumph": dict(root=62, scale="major", bpm=84, prog=THEME_CHORDS, inst=["pad", "strings", "choir", "celesta_theme", "timpani_soft"], level=0.9),
    "celebrate": dict(root=62, scale="major", bpm=116, prog=THEME_CHORDS, inst=["pad", "celesta_theme", "pizz", "sleigh", "strings"], level=0.8),
    "outro": dict(root=62, scale="major", bpm=72, prog=THEME_CHORDS, inst=["pad", "celesta_theme", "choir"], level=0.85),
}


def render_mood(mood, dur, seed=0, start_bar=0):
    m = MOODS[mood]
    r = np.random.default_rng(seed)
    beat = 60.0 / m["bpm"]
    bar = beat * 4
    n = int((dur + 4) * SR)
    out = np.zeros((n, 2))
    root, scale = m["root"], m["scale"]
    prog = m["prog"]
    nbars = int(math.ceil(dur / bar)) + 1

    def put(t, x, g=1.0, p=0.0):
        i = int(t * SR)
        if i >= n:
            return
        x = pan(x, p) if x.ndim == 1 else x
        j = min(n, i + len(x))
        out[i:j] += x[:j - i] * g
    theme_beats = []
    tb = 0
    for d, L in THEME:
        theme_beats.append((tb, d, L))
        tb += L
    for b in range(nbars):
        t0 = b * bar
        deg = prog[(b + start_bar) % len(prog)]
        ch = chord_notes(root, scale, deg, -1)
        insts = m["inst"]
        if "pad" in insts:
            for k, mn in enumerate(ch):
                put(t0, pad(mtof(mn), bar + 1.2, amp=0.05), p=(k - 1) * 0.4)
            put(t0, pad(mtof(ch[0] - 12), bar + 1.2, amp=0.05))
        if "strings" in insts:
            for k, mn in enumerate(ch):
                put(t0, strings(mtof(mn + 12), bar + 0.4, amp=0.035, attack=0.5), p=(k - 1) * 0.5)
        if "strings_low" in insts:
            put(t0, strings(mtof(ch[0] - 12), bar + 0.5, amp=0.07, attack=0.8, bright=10))
            put(t0, strings(mtof(ch[2] - 12), bar + 0.5, amp=0.04, attack=0.8), p=0.3)
        if "strings_trem" in insts:
            for k, mn in enumerate(ch):
                s = strings(mtof(mn), bar + 0.3, amp=0.05, attack=0.2, bright=10)
                tt = np.arange(len(s)) / SR
                s *= 0.6 + 0.4 * np.abs(np.sin(np.pi * tt * 6.0))
                put(t0, s, p=(k - 1) * 0.6)
        if "low_drone" in insts:
            put(t0, pad(mtof(root - 24), bar + 1.5, amp=0.06, attack=1.5), p=0)
        if "pizz" in insts:
            for k in range(4):
                mn = ch[0] - 12 if k % 2 == 0 else ch[2] - 12
                put(t0 + k * beat, pluck_fast(mtof(mn), 0.8, amp=0.16), p=-0.2)
        if "sleigh" in insts:
            for k in range(8):
                if k % 2 == 1 or r.random() < 0.3:
                    put(t0 + k * beat / 2, sleigh(amp=0.04 if k % 2 else 0.025), p=0.5)
        if "timpani" in insts and b % 1 == 0:
            put(t0, timpani(mtof(root - 24), amp=0.35))
            if m["bpm"] > 90:
                put(t0 + 2.5 * beat, timpani(mtof(root - 24), amp=0.2))
        if "timpani_soft" in insts and b % 2 == 0:
            put(t0, timpani(mtof(root - 24), amp=0.18))
        if "choir" in insts and (b % 2 == 0):
            for k, mn in enumerate(ch):
                put(t0, choir(mtof(mn), bar * 2 + 0.8, amp=0.03, vowel="a" if k else "o"), p=(k - 1) * 0.5)
        if "celesta_arp" in insts:
            arp = ch + [ch[0] + 12, ch[1] + 12, ch[0] + 12, ch[2], ch[1]]
            for k in range(8):
                put(t0 + k * beat / 2, celesta(mtof(arp[k % len(arp)] + 12), 1.4, amp=0.07), p=0.3 * math.sin(k))
        if "glass_arp" in insts:
            arp = ch + [ch[0] + 12, ch[2] + 12, ch[1] + 12]
            for k in range(6):
                if r.random() < 0.8:
                    put(t0 + k * bar / 6, fm_bell(mtof(arp[k % len(arp)] + 12), 2.5, ratio=2.0, index=1.2, tau=1.4, amp=0.06),
                        p=r.uniform(-0.7, 0.7))
        if "celesta_sparse" in insts:
            for k in range(4):
                if r.random() < 0.45:
                    mn = r.choice(ch) + 24
                    put(t0 + k * beat + r.uniform(0, 0.1), celesta(mtof(mn), 1.6, amp=0.06), p=r.uniform(-0.6, 0.6))
        if "celesta_theme" in insts:
            # 8-bar theme phrase
            tb0 = ((b + start_bar) % 8) * 4
            for (bb, d, L) in theme_beats:
                if tb0 <= bb < tb0 + 4:
                    mn = deg2midi(root, scale, d, 1)
                    put(t0 + (bb - tb0) * beat, celesta(mtof(mn), max(1.2, L * beat + 0.6), amp=0.11), p=0.15)
                    put(t0 + (bb - tb0) * beat, fm_bell(mtof(mn + 12), 1.0, amp=0.02), p=-0.2)
    out = out[:int(dur * SR)]
    # fades
    fi = int(min(1.5, dur / 4) * SR)
    fo = int(min(2.0, dur / 4) * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return out * m["level"]


# ===================================================================== sound effects
def sfx_step(surface):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    if surface == "snow":
        x = bp(noise(n), 800, 5000) * np.exp(-t * 28)
        crackle = (rng.random(n) < 0.02) * rng.standard_normal(n) * np.exp(-t * 20)
        x = x * 0.5 + hp(crackle, 2000) * 1.2
        x += 0.3 * lp(noise(n), 300) * np.exp(-t * 40)
        return x * 0.12
    if surface == "ice":
        x = bp(noise(n), 2000, 8000) * np.exp(-t * 45) + 0.2 * np.sin(2 * np.pi * 3100 * t) * np.exp(-t * 60)
        return x * 0.10
    if surface in ("stone", "cave"):
        x = bp(noise(n), 300, 3000) * np.exp(-t * 60) + 0.5 * np.sin(2 * np.pi * 110 * t) * np.exp(-t * 50)
        return x * 0.14
    if surface == "wood":
        x = np.sin(2 * np.pi * 170 * t) * np.exp(-t * 30) + 0.4 * bp(noise(n), 400, 2500) * np.exp(-t * 50)
        return x * 0.16
    return bp(noise(n), 500, 4000) * np.exp(-t * 40) * 0.1


def sfx_golem_step():
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 45 * t * (1 + 0.3 * np.exp(-t * 10))) * np.exp(-t * 5) + 0.5 * lp(noise(n), 250) * np.exp(-t * 8)
    x += 0.15 * bp(noise(n), 1500, 5000) * (rng.random(n) < 0.01) * np.exp(-t * 4) * 8
    return x * 0.35


def sfx_hammer():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 950 * t) + 0.6 * np.sin(2 * np.pi * 1530 * t) + 0.3 * np.sin(2 * np.pi * 420 * t)) * np.exp(-t * 35)
    x += 0.5 * bp(noise(n), 1000, 6000) * np.exp(-t * 120)
    return x * 0.12


def sfx_chime_rise(n_notes=7, base=84, step=0.07, amp=0.12):
    out = np.zeros(int((n_notes * step + 2.5) * SR))
    scale = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]
    for k in range(n_notes):
        x = celesta(mtof(base + scale[k % len(scale)]), 2.0, amp=amp)
        i = int(k * step * SR)
        out[i:i + len(x)] += x
    return out


def sfx_shimmer(dur, amp=0.05, density=12, lo=80, hi=100):
    out = np.zeros(int((dur + 2) * SR))
    for k in range(int(dur * density)):
        tt = rng.random() * dur
        x = fm_bell(mtof(rng.integers(lo, hi)), 1.5, ratio=2.01, index=0.8, tau=0.4, amp=amp * rng.uniform(0.4, 1))
        i = int(tt * SR)
        out[i:i + len(x)] += x
    return out


def sfx_whoosh(dur=1.6, f0=300, f1=3000, amp=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = noise(n)
    out = np.zeros(n)
    seg = 2048
    for i in range(0, n, seg):
        u = i / n
        fc = f0 * (f1 / f0) ** u
        y = bp(x[i:i + seg + 512], max(fc * 0.6, 40), min(fc * 1.6, SR / 2 - 100))[:seg]
        out[i:i + len(y)] = y
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return out * e * amp


def sfx_wind(dur, level=0.5, gust=0.5, whistle=0.0, seed=0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = lp(pink(n), 900) * 0.6 + bp(pink(n), 300, 2500) * 0.3
    r = np.random.default_rng(seed)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t + r.random() * 6) * np.sin(2 * np.pi * 0.047 * t + r.random() * 6)
    lfo += gust * np.maximum(0, np.sin(2 * np.pi * 0.07 * t + r.random() * 6)) ** 3
    y = x * lfo
    if whistle > 0:
        f = 700 + 250 * np.sin(2 * np.pi * 0.09 * t) + 120 * np.sin(2 * np.pi * 0.23 * t)
        ph = 2 * np.pi * np.cumsum(f) / SR
        y += whistle * 0.15 * np.sin(ph) * lfo * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t))
    fade = int(min(2.0, dur / 4) * SR)
    y[:fade] *= np.linspace(0, 1, fade)
    y[-fade:] *= np.linspace(1, 0, fade)
    return y * level * 0.3


def sfx_star_out():
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    out = sfx_whoosh(1.5, 4000, 200, 0.2)
    out = np.pad(out, (0, n - len(out)))
    rev = celesta(mtof(96), 2.5, 0.15)[::-1][:n]
    out[:len(rev)] += rev * np.linspace(0, 1, len(rev)) * 0.5
    out += np.sin(2 * np.pi * 55 * t) * np.exp(-np.maximum(t - 1.3, 0) * 3) * (t > 1.3) * 0.3
    return out


def sfx_ignite(amp=0.4, big=False):
    n = int(5.0 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    if big:
        out += np.sin(2 * np.pi * 50 * t * (1 + 0.5 * np.exp(-t * 8))) * np.exp(-t * 1.5) * 0.6
        out += lp(noise(n), 800) * np.exp(-t * 3) * 0.4
    for k, mn in enumerate([74, 78, 81, 86, 90, 93]):
        x = fm_bell(mtof(mn), 4.0, ratio=2.0, index=1.0, tau=1.5, amp=0.12)
        i = int(k * 0.05 * SR)
        out[i:i + len(x)] += x[:n - i]
    sh = sfx_shimmer(3.0, amp=0.05, density=20)
    out[:len(sh)] += sh[:n]
    return out * amp


def sfx_lantern_grab():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((2300, 18), (3410, 22), (5200, 30))) * 0.1
    return x + bp(noise(n), 2000, 8000) * np.exp(-t * 80) * 0.1


def sfx_lantern_light():
    n = int(1.5 * SR)
    t = np.arange(n) / SR
    x = lp(noise(n), 1200) * np.exp(-t * 4) * np.minimum(1, t / 0.05) * 0.3
    x += hp((rng.random(n) < 0.004) * noise(n), 1500) * np.exp(-t * 2) * 0.6
    return x


def sfx_heartbeat(dur):
    out = np.zeros(int((dur + 1) * SR))
    k = 0.0
    while k < dur:
        for off, a in ((0, 1.0), (0.22, 0.7)):
            n = int(0.25 * SR)
            t = np.arange(n) / SR
            x = np.sin(2 * np.pi * 52 * t) * np.exp(-t * 18) * a * 0.5
            i = int((k + off) * SR)
            out[i:i + n] += x
        k += 0.85
    return out


def sfx_owl():
    out = np.zeros(int(2.0 * SR))
    for (st, d, f) in ((0, 0.35, 390), (0.55, 0.6, 360)):
        n = int(d * SR)
        t = np.arange(n) / SR
        fr = f * (1 - 0.06 * t / d)
        x = np.sin(2 * np.pi * np.cumsum(fr) / SR) + 0.25 * np.sin(4 * np.pi * np.cumsum(fr) / SR)
        x *= np.sin(np.pi * t / d) ** 1.5
        x += 0.1 * bp(noise(n), 300, 900) * np.sin(np.pi * t / d)
        i = int(st * SR)
        out[i:i + n] += x * 0.12
    return out


def sfx_breath():
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    e = np.sin(np.pi * t / 2.6) ** 2
    return bp(noise(n), 400, 3500) * e * 0.06


def sfx_rub(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = (0.5 + 0.5 * np.sin(2 * np.pi * 2.9 * t)) ** 2
    return bp(noise(n), 1500, 7000) * e * 0.05


def sfx_ice_crack():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(7):
        tt = rng.random() * 0.8
        m = int(0.15 * SR)
        tk = np.arange(m) / SR
        x = hp(noise(m), 1500) * np.exp(-tk * 60) + 0.5 * np.sin(2 * np.pi * rng.uniform(1800, 4200) * tk) * np.exp(-tk * 25)
        i = int(tt * SR)
        out[i:i + m] += x * rng.uniform(0.3, 1)
    return out * 0.15


def sfx_giggle():
    out = np.zeros(int(2.0 * SR))
    for k in range(9):
        x = celesta(mtof(96 + (k % 3) * 2 + rng.integers(0, 3)), 0.6, amp=0.06)
        i = int(k * 0.09 * SR)
        out[i:i + len(x)] += x
    return out


def sfx_lumi_talk(dur):
    out = np.zeros(int((dur + 1) * SR))
    tt = 0.0
    while tt < dur:
        syl = rng.integers(3, 7)
        for s in range(syl):
            x = fm_bell(mtof(rng.integers(88, 99)), 0.25, ratio=1.0, index=0.6, tau=0.08, amp=0.05)
            i = int((tt + s * 0.11) * SR)
            out[i:i + len(x)] += x
        tt += syl * 0.11 + rng.uniform(0.25, 0.6)
    return out


def sfx_drips(dur, rate=0.8):
    out = np.zeros(int((dur + 1) * SR))
    k = 0.0
    while k < dur:
        k += rng.exponential(1 / rate)
        n = int(0.4 * SR)
        t = np.arange(n) / SR
        f = rng.uniform(900, 2200)
        fr = f * (1 + 0.6 * np.exp(-t * 40))
        x = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 14) * 0.06
        i = int(k * SR)
        if i + n < len(out):
            out[i:i + n] += x
    return out


def sfx_rumble(dur, f=40, amp=0.25, bubbles=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = lp(pink(n), 160) * amp
    if bubbles > 0:
        k = 0.0
        while k < dur:
            k += rng.exponential(0.35)
            m = int(0.12 * SR)
            tk = np.arange(m) / SR
            fb = rng.uniform(80, 220)
            b = np.sin(2 * np.pi * np.cumsum(fb * (1 + 1.5 * tk / 0.12)) / SR) * np.sin(np.pi * tk / 0.12)
            i = int(k * SR)
            if i + m < n:
                x[i:i + m] += b * bubbles
        x += hp((rng.random(n) < 0.0015) * noise(n), 2000) * 0.2 * bubbles
    fade = int(min(2, dur / 4) * SR)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x


def sfx_golem_voice(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    syll = 0.5 + 0.5 * np.sin(2 * np.pi * 2.6 * t + np.sin(2 * np.pi * 0.7 * t) * 2)
    f = 62 + 6 * np.sin(2 * np.pi * 0.5 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = sum(np.sin(h * ph) / h for h in range(1, 12))
    grind = bp(noise(n), 80, 600)
    x = (tone * 0.5 + grind * 0.6) * syll ** 2
    x = lp(x, 900)
    e = env_adsr(n, 0.2, 0.1, 1.0, 0.5)
    return x * e * 0.22


def sfx_gravel(dur, amp=0.07):
    n = int(dur * SR)
    x = hp((rng.random(n) < 0.03) * noise(n), 1500)
    x = lp(x, 6000)
    e = env_adsr(n, 0.3, 0.1, 1.0, 0.6)
    return x * e * amp * 3


def sfx_cloth():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    return bp(noise(n), 800, 5000) * np.sin(np.pi * t / 0.9) ** 2 * 0.07


def sfx_swell(amp=0.5, root=62):
    out = np.zeros(int(5 * SR))
    for k, mn in enumerate([root, root + 4, root + 7, root + 12]):
        x = choir(mtof(mn), 4.5, amp=0.05, attack=1.6, release=2.0)
        out[:len(x)] += x
    return out * amp * 2


def sfx_roar(dur=2.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    f = 70 + 25 * np.sin(2 * np.pi * 3 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    growl = sum(np.sin(h * ph + rng.random()) / h for h in range(1, 20)) * (1 + 0.5 * np.sin(2 * np.pi * 23 * t))
    x = lp(growl, 1400) * 0.5 + bp(noise(n), 200, 3000) * 0.8
    return x * e * 0.3


def sfx_vortex_rise(dur=5.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = sfx_whoosh(dur, 100, 1200, 0.4)
    out += np.sin(2 * np.pi * np.cumsum(40 + 40 * t / dur) / SR) * (t / dur) * 0.2
    return out


def sfx_sigh(dur=4.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    seg = 2048
    x = noise(n)
    for i in range(0, n, seg):
        u = i / n
        fc = 1800 * (1 - u) + 300 * u
        y = bp(x[i:i + seg + 512], fc * 0.5, fc * 1.5)[:seg]
        out[i:i + len(y)] = y
    return out * np.sin(np.pi * t / dur) * 0.12


def sfx_crowd(dur, cheer=False, amp=0.1):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    voices = 14 if cheer else 8
    for v in range(voices):
        f0 = rng.uniform(120, 300)
        vib = 1 + 0.03 * np.sin(2 * np.pi * rng.uniform(4, 7) * t)
        ph = 2 * np.pi * np.cumsum(f0 * vib * (1 + (0.3 if cheer else 0.05) * np.sin(2 * np.pi * rng.uniform(0.3, 1.5) * t))) / SR
        tone = sum(np.sin(h * ph) * (1.0 / h) for h in range(1, 14))
        fc = rng.uniform(500, 1200)
        y = bp(tone, fc * 0.6, fc * 1.8) + 0.3 * bp(noise(n), fc * 0.8, fc * 2)
        syl = np.clip(np.sin(2 * np.pi * rng.uniform(2, 4) * t + rng.random() * 6), 0, 1) ** 1.5 if not cheer else \
            np.clip(np.sin(2 * np.pi * rng.uniform(0.3, 0.8) * t + rng.random() * 6) + 0.4, 0, 1.2)
        out += y * syl * rng.uniform(0.5, 1.0)
    out /= np.max(np.abs(out)) + 1e-9
    e = env_adsr(n, 0.5, 0.2, 1.0, 1.5)
    return out * e * amp


def sfx_fire(dur):
    n = int(dur * SR)
    x = lp(pink(n), 400) * 0.25
    pops = (rng.random(n) < 0.0012) * noise(n) * 3
    x += hp(pops, 1500)
    fade = int(min(2, dur / 4) * SR)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x * 0.05


def sfx_firework_launch():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    f = 900 + 1600 * t / 1.2
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.05 + bp(noise(n), 1500, 6000) * 0.03
    return x * np.sin(np.pi * t / 1.2)


def sfx_firework_boom():
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    x = lp(noise(n), 500) * np.exp(-t * 4) * 0.7 + np.sin(2 * np.pi * 48 * t) * np.exp(-t * 5) * 0.5
    crack = hp((rng.random(n) < 0.004) * noise(n), 2500) * np.clip((t - 0.3) / 0.3, 0, 1) * np.exp(-t * 1.2)
    return (x + crack * 0.8) * 0.3


def sfx_rustle():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    return bp(noise(n), 1500, 8000) * np.sin(np.pi * t / 0.5) * 0.05


def sfx_bells_peal(dur):
    out = np.zeros(int((dur + 6) * SR))
    notes = [62, 66, 69, 74, 69, 66]
    k = 0
    tt = 0.0
    while tt < dur:
        x = bell_tone(mtof(notes[k % len(notes)]), 5.0, amp=0.18)
        i = int(tt * SR)
        out[i:i + len(x)] += x
        tt += 0.55
        k += 1
    return out


def sfx_crystal_open():
    out = sfx_ignite(amp=0.3)
    n = len(out)
    t = np.arange(n) / SR
    out += np.sin(2 * np.pi * 1320 * t) * np.exp(-t * 0.8) * 0.03 * np.sin(2 * np.pi * 5 * t)
    return out


def sfx_beam_hit(idx):
    x = fm_bell(mtof(86 + idx * 2), 2.5, ratio=2.0, index=1.5, tau=1.0, amp=0.12)
    n = len(x)
    t = np.arange(n) / SR
    x += np.sin(2 * np.pi * 220 * (1 + idx * 0.12) * t) * np.exp(-t * 1.5) * 0.04
    return x


def movavg(x, w):
    c = np.cumsum(np.concatenate([[0.0], x]))
    h = w // 2
    idx = np.arange(len(x))
    lo = np.clip(idx - h, 0, len(x)); hi = np.clip(idx + h, 0, len(x))
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


# ===================================================================== assembly
def build():
    meta = json.load(open(os.path.join(BUILD, "timeline.json")))
    total = meta["total"]
    scenes = meta["scenes"]
    music = Bus(total)
    sfx = Bus(total)
    sfx_wet = Bus(total)   # reverberant effects (cave / magic)
    amb = Bus(total)
    voice = Bus(total)
    # ---- music per scene with crossfades
    for k, sc in enumerate(scenes):
        mood = sc["mood"]
        start = sc["start"] - (0.6 if k > 0 else 0)
        dur = sc["dur"] + (1.2 if k < len(scenes) - 1 else 0) + 0.6
        if sc["name"] == "s03":
            # village joy, then tension once the wind arrives
            a = render_mood("village", 17.5, seed=k)
            music.add(start, a)
            b = render_mood("tension", dur - 15.5, seed=k + 100)
            music.add(start + 15.5, b)
        elif sc["name"] == "s09":
            a = render_mood("forge", 23.0, seed=k)
            music.add(start, a, gain=0.8)
            b = render_mood("golem", dur - 21.5, seed=k + 100)
            music.add(start + 21.5, b)
        elif sc["name"] == "s12":
            a = render_mood("resolve", 31.0, seed=k)
            music.add(start, a)
            b = render_mood("triumph", dur - 29.5, seed=k + 100)
            music.add(start + 29.5, b, gain=1.1)
        else:
            music.add(start, render_mood(mood, dur, seed=k))
        print("music", sc["name"], mood, flush=True)
    # ---- voice
    for sc in scenes:
        if sc["narr"]:
            p = os.path.join(VOZ, sc["narr"] + ".mp3")
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                                 capture_output=True).stdout
            x = np.frombuffer(raw, np.float32).astype(np.float64)
            x = hp(x, 70)
            voice.add(sc["start"] + sc["lead"], x, gain=1.0)
    # ---- events
    for e in meta["events"]:
        T = e["t"]
        nm = e["name"]
        if nm == "step":
            surf = e.get("surface", "snow")
            x = sfx_step(surf)
            (sfx_wet if surf == "cave" else sfx).add(T, x, gain=e.get("vol", 1.0), p=rng.uniform(-0.15, 0.15))
        elif nm == "golem_step":
            sfx.add(T, sfx_golem_step(), gain=0.9)
        elif nm == "hammer":
            sfx.add(T, sfx_hammer(), p=0.2)
        elif nm == "bell":
            sfx_wet.add(T, bell_tone(mtof(55), 6.0, amp=0.35), p=-0.3)
        elif nm == "bells_peal":
            sfx_wet.add(T, sfx_bells_peal(e.get("dur", 8)), p=-0.2)
        elif nm in ("chime_big",):
            sfx_wet.add(T, sfx_chime_rise(9, 79, 0.09, 0.08))
        elif nm == "chime_small":
            sfx_wet.add(T, sfx_chime_rise(5, 84, 0.07, 0.06))
        elif nm == "chime_rise":
            sfx_wet.add(T, sfx_chime_rise(8, 84, 0.06, 0.09))
        elif nm == "shimmer":
            sfx_wet.add(T, sfx_shimmer(e.get("dur", 5), amp=0.04))
        elif nm == "glimmer":
            sfx_wet.add(T, sfx_shimmer(4, amp=0.035, density=6))
        elif nm == "whoosh3":
            for k in range(3):
                sfx.add(T + k * 0.22, sfx_whoosh(1.6, 300, 3500, 0.18), p=(k - 1) * 0.7)
            sfx_wet.add(T, sfx_chime_rise(6, 88, 0.05, 0.05))
        elif nm == "wind":
            amb.add(T, sfx_wind(e["dur"], level=e.get("level", 0.5), seed=int(T)))
        elif nm == "cold_wind":
            amb.add(T, sfx_wind(e["dur"], level=0.6, gust=0.8, whistle=0.5, seed=7))
        elif nm == "blizzard":
            amb.add(T, sfx_wind(e["dur"], level=1.3 * e.get("level", 1.0), gust=0.8, whistle=0.25, seed=int(T)))
        elif nm == "ignite_soft":
            sfx_wet.add(T, sfx_ignite(amp=0.35))
        elif nm == "star_out":
            sfx_wet.add(T - 1.2, sfx_star_out())
        elif nm == "star_ignite":
            sfx_wet.add(T, sfx_ignite(amp=0.6, big=True))
        elif nm == "lantern_grab":
            sfx.add(T, sfx_lantern_grab(), p=0.2)
        elif nm == "lantern_light":
            sfx.add(T, sfx_lantern_light(), p=0.2)
        elif nm == "lantern_open":
            sfx.add(T, sfx_lantern_grab())
            sfx_wet.add(T + 0.4, sfx_chime_rise(6, 86, 0.05, 0.06))
        elif nm == "heartbeat":
            sfx.add(T, sfx_heartbeat(e.get("dur", 3)), gain=1.0)
        elif nm == "owl":
            sfx_wet.add(T, sfx_owl(), p=-0.5)
        elif nm == "breath":
            sfx.add(T, sfx_breath())
        elif nm == "rub":
            sfx.add(T, sfx_rub(e.get("dur", 4)))
        elif nm == "ice_crack":
            sfx_wet.add(T, sfx_ice_crack())
        elif nm == "giggle":
            sfx_wet.add(T, sfx_giggle(), p=0.3)
        elif nm == "lumi_talk":
            sfx_wet.add(T, sfx_lumi_talk(e.get("dur", 5)), gain=0.5, p=0.2)
        elif nm == "cave_ambience":
            amb.add(T, sfx_rumble(e["dur"], amp=0.12) + sfx_drips(e["dur"])[:int(e["dur"] * SR)])
        elif nm == "whisper":
            sfx_wet.add(T, bp(noise(int(2.5 * SR)), 2000, 8000) * np.sin(np.pi * np.arange(int(2.5 * SR)) / (2.5 * SR)) * 0.02)
        elif nm == "beam_hit":
            sfx_wet.add(T, sfx_beam_hit(e.get("idx", 0)))
        elif nm == "crystal_open":
            sfx_wet.add(T, sfx_crystal_open())
        elif nm == "forge_ambience":
            amb.add(T, sfx_rumble(e["dur"], amp=0.22, bubbles=0.05))
        elif nm == "golem_voice":
            sfx.add(T, sfx_golem_voice(e.get("dur", 4)), gain=0.8)
        elif nm == "stone_shiver":
            sfx.add(T, sfx_gravel(e.get("dur", 10)))
        elif nm == "cloth":
            sfx.add(T, sfx_cloth())
        elif nm == "warm_swell":
            sfx_wet.add(T, sfx_swell(0.5))
        elif nm == "vortex_rise":
            sfx.add(T, sfx_vortex_rise(5.0), gain=0.6)
        elif nm == "roar":
            sfx.add(T, sfx_roar(2.2), gain=0.6)
        elif nm == "inner_light":
            sfx_wet.add(T, sfx_swell(0.6, root=56))
            sfx_wet.add(T + 3, sfx_shimmer(6, amp=0.04))
        elif nm == "sigh":
            sfx_wet.add(T, sfx_sigh(4.5))
        elif nm == "dissolve":
            sfx_wet.add(T, sfx_shimmer(e.get("dur", 8), amp=0.05, density=25, lo=84, hi=104))
        elif nm == "cheer":
            sfx.add(T, sfx_crowd(e.get("dur", 8), cheer=True, amp=0.12))
        elif nm == "murmur":
            sfx.add(T, sfx_crowd(1.6, amp=0.05), p=rng.uniform(-0.4, 0.4))
        elif nm == "party_ambience":
            amb.add(T, sfx_crowd(e["dur"], amp=0.035))
        elif nm == "fire_crackle":
            amb.add(T, sfx_fire(e["dur"]))
        elif nm == "firework_launch":
            sfx.add(T, sfx_firework_launch(), gain=0.8, p=rng.uniform(-0.5, 0.5))
        elif nm == "firework_boom":
            sfx_wet.add(T, sfx_firework_boom(), gain=0.7, p=rng.uniform(-0.6, 0.6))
        elif nm == "rustle":
            sfx.add(T, sfx_rustle())
    print("events placed", flush=True)
    # ---- reverbs
    ir_music = make_ir(3.2, 0.03, 5000, seed=2)
    ir_fx = make_ir(2.4, 0.02, 6000, seed=3)
    mus = reverb(music.buf.astype(np.float64), ir_music, wet=0.35)
    fxw = reverb(sfx_wet.buf.astype(np.float64), ir_fx, wet=0.45)
    fx = sfx.buf.astype(np.float64)
    ambb = amb.buf.astype(np.float64)
    vo = voice.buf.astype(np.float64)
    # ducking music under voice
    venv = np.abs(vo[:, 0]) + np.abs(vo[:, 1])
    win = int(0.25 * SR)
    venv = movavg(venv, win)
    duck = 1.0 - 0.45 * np.clip(venv / 0.04, 0, 1)
    duck = movavg(duck, int(0.3 * SR))
    mus *= duck[:, None]
    mix = vo * 1.0 + mus * 0.55 + fx * 0.85 + fxw * 0.9 + ambb * 0.6
    n_total = int(total * SR)
    mix = mix[:n_total]
    # final fade
    fo = int(2.5 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    # soft limiter
    pk = np.max(np.abs(mix))
    mix = np.tanh(mix / max(pk, 1e-9) * 1.2) / math.tanh(1.2) * 0.95
    path = os.path.join(BUILD, "mix_raw.wav")
    import wave
    data = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    # stems for checking
    print("wrote", path, "%.1fs" % (len(mix) / SR))
    # loudness normalisation for YouTube (-14 LUFS)
    final = os.path.join(BUILD, "mix_final.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), final], check=True)
    print("wrote", final)


if __name__ == "__main__":
    build()
