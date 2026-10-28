"""
Banda sonora lofi sintetizada para "夜のカフェへ".
Piano electrico con acordes de jazz, bajo redondo, bateria boom-bap con swing,
melodia pentatonica, crepitar de vinilo y efectos sincronizados con las escenas
(bacon chisporroteando, tostadora, chispas magicas, pasos, grillos, tren,
campanilla de la cafeteria y lluvia).
"""
import math
import wave

import numpy as np
from scipy import signal

SR = 44100
BPM = 78.0
BEAT = 60.0 / BPM
BAR = BEAT * 4

rng = np.random.default_rng(29)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n, a=0.005, d=0.3, s=0.6, r=0.2, total=None):
    t = np.arange(n) / SR
    total = total or n / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-3)))
    rel = np.clip((total - t) / r, 0, 1)
    return e * rel


def lp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), 'low')
    return signal.lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), 'high')
    return signal.lfilter(b, a, x)


def bp(x, f0, f1, order=2):
    b, a = signal.butter(order, [f0 / (SR / 2), f1 / (SR / 2)], 'band')
    return signal.lfilter(b, a, x)


def add(buf, start, snd, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= buf.shape[1] or i + len(snd) <= 0:
        return
    j0 = max(0, -i)
    snd = snd[j0:]
    i = max(0, i)
    n = min(len(snd), buf.shape[1] - i)
    l = math.cos((pan + 1) * math.pi / 4)
    r = math.sin((pan + 1) * math.pi / 4)
    buf[0, i:i + n] += snd[:n] * gain * l * 1.414
    buf[1, i:i + n] += snd[:n] * gain * r * 1.414


# ----------------------------------------------------------------------------
# instrumentos
# ----------------------------------------------------------------------------
def epiano(f, dur, vel=1.0):
    n = int((dur + 0.6) * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * f * 1.0 * t) * 1.2 * np.exp(-t * 4)
    x = np.sin(2 * np.pi * f * t + mod)
    x += 0.25 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 3)
    x += 0.08 * np.sin(2 * np.pi * f * 4.01 * t) * np.exp(-t * 8)
    e = np.exp(-t * 1.1) * np.clip(t / 0.004, 0, 1) * np.clip((dur + 0.5 - t) / 0.5, 0, 1)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
    return x * e * trem * vel


def bass(f, dur, vel=1.0):
    n = int((dur + 0.1) * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    x = np.tanh(x * 1.4)
    e = np.clip(t / 0.01, 0, 1) * np.exp(-t * 1.2) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    return x * e * vel


def flute(f, dur, vel=1.0):
    n = int((dur + 0.3) * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.4, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    x = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    breath = lp(rng.standard_normal(n), 3000) * 0.04
    e = np.clip(t / 0.08, 0, 1) * np.clip((dur + 0.25 - t) / 0.25, 0, 1) * (0.8 + 0.2 * np.exp(-t * 2))
    return (x + breath) * e * vel


def bell(f, dur=2.5, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 3)
         + 0.3 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 6))
    return x * np.exp(-t * 2.2) * np.clip(t / 0.002, 0, 1) * vel


def kick():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 80 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    x += 0.3 * lp(rng.standard_normal(n), 1500) * np.exp(-t * 80)
    return np.tanh(x * 1.6)


def snare():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n), 900, 5000) * np.exp(-t * 14)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25)
    return (nz * 0.9 + tone * 0.6) * 0.8


def rim():
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 820 * t) + 0.5 * bp(rng.standard_normal(n), 1500, 6000)) * np.exp(-t * 70) * 0.5


def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 70)) * 0.5


# ----------------------------------------------------------------------------
# armonia
# ----------------------------------------------------------------------------
PROG_A = [  # Dm9  G13  Cmaj9  A7b9
    ([50, 53, 57, 60, 64], 38), ([53, 59, 64, 67], 43), ([52, 55, 59, 62, 67], 36), ([55, 61, 64, 70], 45)]
PROG_B = [  # Fmaj9  Em7  Ebmaj7  Dm7 (G7)
    ([53, 57, 60, 64, 67], 41), ([52, 55, 59, 62], 40), ([51, 55, 58, 62], 39), ([50, 53, 57, 60], 38)]
PENTA = [60, 62, 64, 67, 69, 72, 74, 76]


def section(t):
    """Devuelve (progresion, bateria, melodia, nivel de teclas) segun el tiempo."""
    if t < 14:
        return PROG_A, 0, 0, 0.8
    if t < 68:
        return PROG_A, 2, 1 if t > 36 else 0, 1.0
    if t < 84:
        return PROG_B, 1, 0, 0.9
    if t < 142:
        return PROG_B, 2, 1 if (t > 96) else 0, 1.0
    if t < 160:
        return PROG_A, 2, 1, 0.95
    return PROG_A, 0, 0, 0.8


def build_music(dur):
    N = int(dur * SR) + SR
    keys = np.zeros((2, N))
    bas = np.zeros((2, N))
    drm = np.zeros((2, N))
    mel = np.zeros((2, N))
    kick_env = np.zeros(N)
    K, Sn, R = kick(), snare(), rim()
    Hc, Ho = hat(), hat(True)
    nb = int(dur / BAR) + 1
    mrng = np.random.default_rng(5)
    for b in range(nb):
        t0 = b * BAR
        prog, dlev, mlev, klev = section(t0 + 0.01)
        notes, root = prog[b % 4]
        # acordes: golpe en 1 y anticipacion en el "y" del 3
        for (pos, ln, vel) in ((0.0, 2.4, 0.9), (2.5, 1.4, 0.6)):
            if pos > 0 and b % 2 == 1 and dlev == 0:
                continue
            for k, m in enumerate(notes):
                add(keys, t0 + pos * BEAT + k * 0.018, epiano(mtof(m), ln * BEAT, vel * klev),
                    0.09, pan=-0.3 + 0.15 * k)
        if dlev >= 1 or t0 > 8:
            add(bas, t0, bass(mtof(root), 1.8 * BEAT), 0.5)
            add(bas, t0 + 2.5 * BEAT, bass(mtof(root + 7 if b % 2 == 0 else root + 12), 1.2 * BEAT), 0.4)
        # bateria
        sw = 0.13 * BEAT
        if dlev >= 2:
            for p in (0.0, 1.75, 2.5):
                if p == 1.75 and b % 2 == 0:
                    continue
                add(drm, t0 + p * BEAT, K, 0.85)
                i = int((t0 + p * BEAT) * SR)
                kick_env[i:i + int(0.25 * SR)] = np.maximum(kick_env[i:i + int(0.25 * SR)],
                                                            np.exp(-np.arange(min(int(0.25 * SR), N - i)) / SR * 9))
            for p in (1.0, 3.0):
                add(drm, t0 + p * BEAT + 0.012, Sn, 0.55, pan=0.05)
        elif dlev == 1:
            for p in (1.0, 3.0):
                add(drm, t0 + p * BEAT, R, 0.35, pan=0.1)
        if dlev >= 1:
            for e in range(8):
                tt = t0 + e * BEAT / 2 + (sw if e % 2 else 0)
                op = (e == 7 and b % 4 == 3)
                add(drm, tt, Ho if op else Hc, (0.22 if e % 2 else 0.32) * (0.8 + 0.2 * mrng.random()), pan=0.3)
        # melodia
        if mlev:
            pos = 0.0
            while pos < 4.0:
                ln = mrng.choice([0.5, 1.0, 1.5, 2.0], p=[0.3, 0.35, 0.15, 0.2])
                if mrng.random() < 0.62:
                    cand = [m for m in PENTA if (m % 12) in [n % 12 for n in notes] + [2, 9]]
                    m = mrng.choice(cand if cand else PENTA)
                    add(mel, t0 + pos * BEAT + (sw if (pos * 2) % 2 else 0), flute(mtof(m + 12), ln * BEAT * 0.9),
                        0.07, pan=0.25)
                pos += ln
    # sidechain y mezcla de la musica
    duck = 1 - 0.35 * kick_env
    keys *= duck
    bas *= duck
    keys = np.vstack([lp(keys[0], 4500), lp(keys[1], 4500)])
    drm = np.vstack([lp(drm[0], 9000), lp(drm[1], 9000)])
    music = keys + bas * 0.9 + drm * 0.8 + mel
    # intro filtrada (se abre poco a poco)
    t = np.arange(N) / SR
    open_ = np.clip((t - 2) / 12, 0, 1)
    dull = np.vstack([lp(music[0], 900), lp(music[1], 900)])
    music = dull * (1 - open_) + music * open_
    # wow & flutter de cinta
    wob = 0.0022 * np.sin(2 * np.pi * 0.45 * t) + 0.0005 * np.sin(2 * np.pi * 5.3 * t)
    idx = np.clip(np.arange(N) - wob * SR, 0, N - 1)
    music = np.vstack([np.interp(idx, np.arange(N), music[0]), np.interp(idx, np.arange(N), music[1])])
    return music[:, :int(dur * SR)]


# ----------------------------------------------------------------------------
# ambiente y efectos
# ----------------------------------------------------------------------------
def noise(n):
    return rng.standard_normal(n)


def build_fx(dur):
    N = int(dur * SR)
    fx = np.zeros((2, N))
    t = np.arange(N) / SR
    # vinilo: siseo + crepitar
    hiss = hp(noise(N), 3000) * 0.006
    crk = np.zeros(N)
    pos = rng.integers(0, N, int(dur * 9))
    crk[pos] = rng.uniform(-1, 1, len(pos)) * rng.uniform(0.1, 0.5, len(pos))
    crk = bp(crk, 800, 6000)
    pops = np.zeros(N)
    pos = rng.integers(0, N, int(dur * 0.6))
    pops[pos] = rng.choice([-1, 1], len(pos)) * 0.7
    pops = lp(pops, 2000)
    vinyl = hiss + crk * 0.5 + pops * 0.25
    fx += np.vstack([vinyl, np.roll(vinyl, 37)])

    def seg(a, b):
        return int(a * SR), int(b * SR)

    def fade(n, fi, fo):
        e = np.ones(n)
        k = int(fi * SR)
        e[:k] = np.linspace(0, 1, k)
        k = int(fo * SR)
        e[-k:] = np.linspace(1, 0, k)
        return e

    # pajaritos al principio
    for k in range(7):
        st = 1.5 + k * 1.6 + rng.uniform(0, 0.6)
        n = int(0.12 * SR)
        tt = np.arange(n) / SR
        f = 3200 + 1200 * np.sin(np.pi * tt / 0.12) + rng.uniform(-300, 300)
        ch = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.12) ** 2
        for r in range(2):
            add(fx, st + r * 0.16, ch, 0.05, pan=rng.uniform(-0.7, 0.7))
    # bacon chisporroteando (14 - 35)
    a, b = seg(14.0, 35.0)
    n = b - a
    sz = bp(noise(n), 2500, 9000) * (0.5 + 0.5 * np.abs(lp(noise(n), 6)))
    cr = np.zeros(n)
    pos = rng.integers(0, n, int(n / SR * 40))
    cr[pos] = rng.uniform(0.3, 1, len(pos))
    cr = hp(cr, 2000)
    s_ = (sz * 0.05 + cr * 0.12) * fade(n, 1.5, 2.5)
    fx[0, a:b] += s_ * 0.9
    fx[1, a:b] += s_ * 1.1
    # huevos al sarten
    for st in (23.6, 25.2):
        n = int(0.9 * SR)
        tt = np.arange(n) / SR
        crack = hp(noise(n), 1500) * np.exp(-tt * 60) * 0.3
        sizz = bp(noise(n), 3000, 9000) * np.clip(tt / 0.1, 0, 1) * np.exp(-tt * 2.5) * 0.18
        add(fx, st, crack + sizz, 1.0, pan=0.3)
    # tostadora: pop + muelle
    n = int(0.5 * SR)
    tt = np.arange(n) / SR
    clk = hp(noise(n), 1000) * np.exp(-tt * 90) * 0.5
    boing = np.sin(2 * np.pi * np.cumsum(500 + 300 * np.exp(-tt * 10)) / SR) * np.exp(-tt * 9) * 0.12
    add(fx, 29.5, clk + boing, 1.0, pan=-0.5)
    # cubiertos / plato
    for st in (37.0, 55.2, 58.6, 62.0):
        add(fx, st, bell(2400, 0.6, 0.06) + bell(3100, 0.6, 0.04), 1.0, pan=0.2)
    # maullido
    for st in (46.6, 62.5):
        n = int(0.55 * SR)
        tt = np.arange(n) / SR
        f = 520 + 260 * np.sin(np.pi * np.clip(tt / 0.5, 0, 1)) ** 0.7 - 180 * tt
        ph = 2 * np.pi * np.cumsum(f) / SR
        m = (np.sin(ph) + 0.6 * np.sin(2 * ph) + 0.35 * np.sin(3 * ph)) * np.sin(np.pi * np.clip(tt / 0.55, 0, 1))
        m = bp(m, 400, 3500)
        add(fx, st, m, 0.06, pan=0.4)
    # chispas magicas (arpegio de campanitas)
    for k in range(12):
        add(fx, 71.2 + k * 0.09, bell(mtof(84 + [0, 2, 4, 7, 9][k % 5] + 12 * (k // 5)), 1.8), 0.05,
            pan=-0.6 + k * 0.1)
    # puerta de casa
    n = int(1.2 * SR)
    tt = np.arange(n) / SR
    creak = bp(noise(n), 300, 1400) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * tt)) * np.sin(np.pi * tt / 1.2) * 0.06
    add(fx, 79.0, creak, 1.0, pan=0.6)
    # exterior nocturno: grillos (84 - 142)
    a, b = seg(80.0, 142.5)
    n = b - a
    tt = np.arange(n) / SR
    cr = np.sin(2 * np.pi * 4300 * tt) * (np.sin(2 * np.pi * 28 * tt) > 0.2) * (np.sin(2 * np.pi * 0.9 * tt) > -0.1)
    cr2 = np.sin(2 * np.pi * 5100 * tt) * (np.sin(2 * np.pi * 31 * tt + 1) > 0.3) * (np.sin(2 * np.pi * 0.7 * tt + 2) > 0)
    amb = lp(noise(n), 400) * 0.02
    e = fade(n, 4.0, 1.5)
    fx[0, a:b] += (cr * 0.012 + cr2 * 0.006 + amb) * e
    fx[1, a:b] += (cr * 0.006 + cr2 * 0.012 + amb) * e
    # pasos (calle, rio y cafeteria)
    step = 1 / (2 * 0.9)
    for (a_, b_) in ((75.8, 81.2), (84.0, 112.5), (112.0, 116.0), (123.5, 128.5), (128.0, 137.2)):
        st = a_
        k = 0
        while st < b_:
            n = int(0.09 * SR)
            tt = np.arange(n) / SR
            s_ = lp(noise(n), 900) * np.exp(-tt * 55) * 0.35
            add(fx, st, s_, 0.5, pan=-0.1 if k % 2 else 0.1)
            st += step
            k += 1
    # tren por el viaducto (de derecha a izquierda)
    a, b = seg(113.0, 124.5)
    n = b - a
    tt = np.arange(n) / SR
    rum = lp(noise(n), 260) * 0.25
    clack = np.zeros(n)
    for k in range(int(n / SR / 0.42)):
        for dd in (0.0, 0.11):
            i = int((k * 0.42 + dd) * SR)
            if i < n - 2000:
                clack[i:i + 2000] += lp(noise(2000), 1200) * np.exp(-np.arange(2000) / SR * 60)
    tr = (rum + clack * 0.35) * np.sin(np.pi * np.clip(tt / (n / SR), 0, 1)) ** 1.5
    panp = np.linspace(0.9, -0.9, n)
    fx[0, a:b] += tr * 0.12 * np.cos((panp + 1) * np.pi / 4) * 1.4
    fx[1, a:b] += tr * 0.12 * np.sin((panp + 1) * np.pi / 4) * 1.4
    add(fx, 114.2, flute(mtof(79), 0.5) + flute(mtof(76), 0.5), 0.04, pan=0.7)
    # campanilla de la cafeteria
    for k, f in enumerate((2093, 2637, 3136, 2637, 2093)):
        add(fx, 136.0 + k * 0.07, bell(f, 2.0), 0.06, pan=0.3)
    # lluvia + murmullo de la cafeteria
    a, b = seg(141.0, dur)
    n = b - a
    tt = np.arange(n) / SR
    rn = bp(noise(n), 600, 8000) * 0.05
    drops = np.zeros(n)
    pos = rng.integers(0, n, int(n / SR * 25))
    drops[pos] = rng.uniform(0.2, 0.8, len(pos))
    drops = bp(drops, 1500, 5000)
    murm = bp(noise(n), 200, 900) * (0.6 + 0.4 * np.abs(lp(noise(n), 3))) * 0.015
    k = np.clip((tt - 1.5) / 6, 0, 1)
    fx[0, a:b] += (rn * k + drops * 0.15 * k + murm)
    fx[1, a:b] += (np.roll(rn, 113) * k + np.roll(drops, 401) * 0.15 * k + murm)
    return fx


def build(dur):
    music = build_music(dur)
    fx = build_fx(dur)
    t = np.arange(music.shape[1]) / SR
    # la musica baja un poco al final
    mfade = np.clip((dur - t) / 6.0, 0, 1)
    mix_ = music * 0.75 * mfade + fx
    mix_ = np.tanh(mix_ * 1.1) / np.tanh(1.1)
    fade = np.clip(t / 1.5, 0, 1) * np.clip((dur - t) / 3.0, 0, 1)
    mix_ *= fade
    mix_ /= max(1e-6, np.max(np.abs(mix_))) / 0.89
    return mix_


def write_wav(path, x):
    data = (np.clip(x.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == '__main__':
    import sys
    write_wav(sys.argv[1] if len(sys.argv) > 1 else 'soundtrack.wav', build(166.0))
