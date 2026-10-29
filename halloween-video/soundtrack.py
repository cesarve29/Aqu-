#!/usr/bin/env python3
"""Banda sonora procedural de "La Mascara del Eco Azul" (260 s, 44.1 kHz, estereo).

Musica (caja de musica, pads, coro, batalla) + efectos sincronizados con el guion.
Uso: python3 soundtrack.py  -> audio/soundtrack.wav
"""
import os
import wave

import numpy as np

SR = 44100
DUR = 260.0
N = int(SR * DUR)
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(1031)

music = np.zeros((N, 2), np.float32)
sfx = np.zeros((N, 2), np.float32)
cave = np.zeros((N, 2), np.float32)  # efectos con reverberacion de caverna


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def note_name(n):
    names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    k = names[n[0]]
    i = 1
    if n[i] in '#b':
        k += 1 if n[i] == '#' else -1
        i += 1
    return midi(12 * (int(n[i:]) + 1) + k)


def env(n, a, r, sustain=1.0, curve=1.0):
    e = np.ones(n, np.float32) * sustain
    a = max(1, int(a * SR))
    r = max(1, int(r * SR))
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a) ** curve * sustain
    r = min(r, n)
    e[n - r:] *= np.linspace(1, 0, r) ** curve
    return e


def add(buf, t, sig, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0:
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    sig = sig[: N - i]
    l = np.cos((pan + 1) * np.pi / 4) * gain
    r = np.sin((pan + 1) * np.pi / 4) * gain
    buf[i:i + len(sig), 0] += sig * l
    buf[i:i + len(sig), 1] += sig * r


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def fft_filter(x, lo=None, hi=None):
    """Filtro pasa-banda suave en frecuencia (x mono)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        g *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, n).astype(np.float32)


def noise(dur):
    return rng.standard_normal(int(dur * SR)).astype(np.float32)


def saw(freq, t, detune=0.0):
    ph = (freq * (1 + detune)) * t
    return (2 * (ph - np.floor(ph + 0.5))).astype(np.float32)


def soft_saw(freq, t, harm=10):
    s = np.zeros_like(t, dtype=np.float32)
    for k in range(1, harm + 1):
        s += np.sin(2 * np.pi * freq * k * t) / k * (0.85 ** k)
    return s


def seg(a, b):
    return int(a * SR), int(b * SR)


# ----------------------------------------------------------------------------
# instrumentos
# ----------------------------------------------------------------------------
def music_box(t0, freq, dur=1.6, gain=0.18, pan=0.0, buf=None, detune_drop=0.0):
    t = tt(dur)
    f = freq * (1 - detune_drop * t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = (np.sin(ph) + 0.35 * np.sin(2 * ph) * np.exp(-t * 8) + 0.2 * np.sin(4.2 * ph) * np.exp(-t * 14)) * np.exp(-t * 3.2)
    s[:80] *= np.linspace(0, 1, 80)
    add(buf if buf is not None else music, t0, s.astype(np.float32), pan, gain)


def bell(t0, freq, dur=7.0, gain=0.25, pan=0.0, buf=None):
    t = tt(dur)
    partials = [(0.5, 1.0, 0.9), (1.0, 0.8, 1.5), (1.19, 0.5, 2.0), (1.5, 0.45, 2.5), (2.0, 0.35, 3.0), (2.74, 0.2, 4.5), (3.76, 0.12, 6.0)]
    s = np.zeros_like(t, dtype=np.float32)
    for r, a, d in partials:
        s += a * np.sin(2 * np.pi * freq * r * t + r) * np.exp(-t * d / 1.5)
    s[:60] *= np.linspace(0, 1, 60)
    add(buf if buf is not None else sfx, t0, s, pan, gain)


def pad(t0, notes, dur, gain=0.06, bright=1800, attack=2.0, release=2.5, buf=None):
    t = tt(dur)
    s = np.zeros_like(t, dtype=np.float32)
    for k, n in enumerate(notes):
        f = note_name(n) if isinstance(n, str) else n
        for d in (-0.004, 0.0, 0.005):
            s += saw(f, t + k * 0.13, d) * 0.33
    s = fft_filter(s, lo=40, hi=bright)
    s *= env(len(t), attack, release)
    l = s * (1 + 0.15 * np.sin(2 * np.pi * 0.11 * t))
    r = s * (1 + 0.15 * np.cos(2 * np.pi * 0.13 * t))
    i = int(t0 * SR)
    b = buf if buf is not None else music
    j = min(N, i + len(t))
    b[i:j, 0] += l[: j - i] * gain
    b[i:j, 1] += r[: j - i] * gain


def choir(t0, notes, dur, gain=0.05, vowel='a', attack=2.5, release=3.0, buf=None):
    """Coro 'aah' por sintesis de formantes sobre armonicos."""
    form = {'a': [(800, 1.0, 80), (1150, 0.5, 90), (2900, 0.25, 120)], 'o': [(450, 1.0, 70), (800, 0.4, 80), (2830, 0.1, 100)]}[vowel]
    t = tt(dur)
    s = np.zeros_like(t, dtype=np.float32)
    for k, n in enumerate(notes):
        f0 = note_name(n) if isinstance(n, str) else n
        for voice in range(3):
            vib = 1 + 0.006 * np.sin(2 * np.pi * (5.0 + voice * 0.4) * t + voice * 2 + k)
            f = f0 * (1 + (voice - 1) * 0.004) * vib
            ph = 2 * np.pi * np.cumsum(f) / SR
            for h in range(1, 28):
                fh = f0 * h
                if fh > 5000:
                    break
                a = sum(g * np.exp(-((fh - fc) / bw) ** 2 / 2) for fc, g, bw in form) + 0.02
                s += np.sin(h * ph).astype(np.float32) * a / (h ** 0.4)
    s *= env(len(t), attack, release) / max(1, len(notes))
    add(buf if buf is not None else music, t0, s, 0.0, gain)


def drum(t0, freq=60, dur=0.9, gain=0.5, pan=0.0, buf=None, click=0.3):
    t = tt(dur)
    f = freq * (1 + 1.6 * np.exp(-t * 25))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 5)
    nz = fft_filter(noise(dur), lo=200, hi=3000) * np.exp(-t * 40) * click
    add(buf if buf is not None else music, t0, (s + nz).astype(np.float32), pan, gain)


def pluck(t0, freq, dur=0.35, gain=0.12, pan=0.0, buf=None, bright=2500):
    t = tt(dur)
    s = saw(freq, t) * np.exp(-t * 9)
    s = fft_filter(s, hi=bright)
    add(buf if buf is not None else music, t0, s, pan, gain)


def whoosh(t0, dur=0.8, lo=300, hi=3000, gain=0.2, pan=0.0, buf=None, rise=True):
    t = tt(dur)
    s = fft_filter(noise(dur), lo=lo, hi=hi)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** (1.5 if rise else 0.7)
    add(buf if buf is not None else sfx, t0, s * e, pan, gain)


def thud(t0, gain=0.5, freq=55, pan=0.0, buf=None):
    t = tt(0.6)
    s = np.sin(2 * np.pi * freq * t * (1 + np.exp(-t * 30))) * np.exp(-t * 9)
    s += fft_filter(noise(0.6), hi=900) * np.exp(-t * 25) * 0.6
    add(buf if buf is not None else sfx, t0, s.astype(np.float32), pan, gain)


def clatter(t0, dur=0.6, density=60, gain=0.15, pan=0.0, buf=None, pitch=1.0):
    """Huesos que chocan: granos de clic resonantes."""
    t = tt(dur)
    s = np.zeros_like(t, dtype=np.float32)
    k = int(density * dur)
    for _ in range(k):
        i = rng.integers(0, len(t) - 2000)
        f = rng.uniform(900, 2600) * pitch
        g = tt(0.04)
        grain = np.sin(2 * np.pi * f * g) * np.exp(-g * 140) * rng.uniform(0.4, 1)
        s[i:i + len(grain)] += grain
    add(buf if buf is not None else sfx, t0, s, pan, gain)


def crackle(a, b, gain=0.05, buf=None, density=25):
    dur = b - a
    t = tt(dur)
    hiss = fft_filter(noise(dur), lo=2000, hi=9000) * 0.25
    s = hiss * (0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t))
    for _ in range(int(density * dur)):
        i = rng.integers(0, len(t) - 600)
        c = tt(0.012)
        s[i:i + len(c)] += np.exp(-c * 400) * rng.uniform(-1, 1) * 3
    s *= env(len(t), 0.5, 0.8)
    add(buf if buf is not None else cave, a, s, rng.uniform(-0.4, 0.4), gain)


def wind(a, b, gain=0.08, lo=150, hi=900):
    dur = b - a
    t = tt(dur)
    s = fft_filter(noise(dur), lo=lo, hi=hi)
    m = 0.55 + 0.3 * np.sin(2 * np.pi * 0.07 * t) + 0.15 * np.sin(2 * np.pi * 0.23 * t + 1)
    s = s * m * env(len(t), 2.0, 2.0)
    s2 = fft_filter(noise(dur), lo=lo * 1.2, hi=hi * 1.1) * m[::-1]
    i, j = int(a * SR), int(a * SR) + len(t)
    j = min(j, N)
    sfx[i:j, 0] += s[: j - i] * gain
    sfx[i:j, 1] += s2[: j - i] * gain * env(len(t), 2.0, 2.0)[: j - i]


def heartbeat(t0, bpm, gain=0.35):
    for k, off in enumerate((0.0, 0.18)):
        t = tt(0.3)
        s = np.sin(2 * np.pi * (48 - k * 6) * t) * np.exp(-t * 18) * (1.0 if k == 0 else 0.7)
        add(sfx, t0 + off, s.astype(np.float32), 0.0, gain)


def growl(t0, dur=2.2, gain=0.35):
    t = tt(dur)
    f = 70 * (1 + 0.25 * np.sin(np.pi * t / dur)) * (1 + 0.04 * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sign(np.sin(ph)) * 0.5 + np.sin(2 * ph) * 0.3
    s = fft_filter(s.astype(np.float32), lo=60, hi=1400)
    s += fft_filter(noise(dur), lo=300, hi=1500) * 0.35
    # formantes tipo "aaar"
    s = s * env(len(t), 0.15, 0.6) * (0.7 + 0.3 * np.sin(2 * np.pi * 3 * t))
    add(cave, t0, s.astype(np.float32), 0.0, gain)


def scream(t0, dur=3.2, gain=0.55):
    """El grito: tono deslizante con vibrato + formantes de ruido + ecos."""
    t = tt(dur)
    f = 620 * np.exp(-t * 0.25) * (1 + 0.035 * np.sin(2 * np.pi * 6.5 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.zeros_like(t, dtype=np.float32)
    for h in range(1, 14):
        s += np.sin(h * ph).astype(np.float32) / h ** 0.9 * np.exp(-((h * 620 - 1100) / 1400) ** 2)
    s += fft_filter(noise(dur), lo=900, hi=4200) * 0.5
    s = s * env(len(t), 0.05, 1.4, curve=0.7) * 0.6
    for k, (dt, g) in enumerate([(0, 1.0), (0.32, 0.55), (0.66, 0.36), (1.02, 0.22), (1.4, 0.13), (1.8, 0.08)]):
        add(cave, t0 + dt, fft_filter(s, hi=6000 - k * 800), (-1) ** k * 0.4 * min(k, 1), gain * g)


def boom(t0, gain=0.7, dur=3.0):
    t = tt(dur)
    f = 45 * (1 + 2.5 * np.exp(-t * 6))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 1.4)
    s += fft_filter(noise(dur), hi=700) * np.exp(-t * 3) * 0.7
    add(sfx, t0, s.astype(np.float32), 0.0, gain)


def chime_run(t0, notes, step=0.12, gain=0.12, buf=None):
    for k, n in enumerate(notes):
        music_box(t0 + k * step, note_name(n), dur=2.0, gain=gain, pan=np.sin(k) * 0.5, buf=buf)


def shatter(t0, gain=0.25):
    for k in range(40):
        f = rng.uniform(2500, 7000)
        t = tt(0.4)
        s = np.sin(2 * np.pi * f * t) * np.exp(-t * rng.uniform(15, 40))
        add(cave, t0 + rng.uniform(0, 0.5), s.astype(np.float32), rng.uniform(-0.8, 0.8), gain * rng.uniform(0.3, 1))


# ----------------------------------------------------------------------------
# PARTITURA
# ----------------------------------------------------------------------------
# --- ACTO I: el pueblo (0-60)
# vals de caja de musica en re menor, 108 bpm 3/4
beat = 60 / 108
melody = ['D5', 'F5', 'A5', 'G5', 'F5', 'E5', 'D5', 'A4', 'D5', 'C#5', 'E5', 'A4',
          'Bb4', 'D5', 'F5', 'E5', 'D5', 'C#5', 'D5', 'F5', 'A5', 'D6', 'A5', 'F5']
bass = ['D3', 'D3', 'Bb2', 'A2', 'G2', 'A2', 'D3', 'A2']
t = 0.6
k = 0
while t < 20.3:
    n = melody[k % len(melody)]
    drop = 0.0
    if t > 18.0:
        drop = (t - 18.0) * 0.06  # la caja de musica "se muere" al llegar la figura
    music_box(t, note_name(n) * (1 - drop * 0.3), dur=1.8, gain=0.16, pan=0.2 * np.sin(k), detune_drop=drop)
    if k % 3 == 0:
        b = bass[(k // 3) % len(bass)]
        pluck(t, note_name(b), dur=0.9, gain=0.07)
    t += beat
    k += 1
pad(0, ['D3', 'F3', 'A3'], 10.5, gain=0.035, bright=1400)
pad(10, ['Bb2', 'D3', 'F3'], 10.5, gain=0.035, bright=1400)
# la llegada: drone grave
pad(20, ['D2', 'A2'], 22, gain=0.05, bright=700, attack=3)
pad(40, ['D2', 'G#2', 'D3'], 21, gain=0.05, bright=800, attack=3)
choir(22, ['D4', 'F4'], 9, gain=0.04, vowel='o')
choir(41, ['C#4', 'E4', 'Bb4'], 9, gain=0.04, vowel='a')
bell(20.6, note_name('D3'), gain=0.32)
bell(26.6, note_name('D3'), gain=0.2)
wind(18, 62, gain=0.05)
# faroles que se apagan (escena 4: t=30..40)
for lt in (2.7, 8.6):
    for side in (-0.6, 0.6):
        whoosh(30 + lt, 0.35, lo=500, hi=2500, gain=0.12, pan=side, rise=False)
    thud(30 + lt + 0.05, gain=0.08, freq=90)
for lt in np.arange(0.3, 10, 2.2):
    thud(30 + lt, gain=0.05, freq=45)  # pasos pesados
# puertas que se cierran (escena 5)
for i in range(8):
    thud(40 + 4.75 + i * 0.18 + rng.uniform(0, 0.1), gain=0.22, freq=70, pan=rng.uniform(-0.7, 0.7))
whoosh(41, 5, lo=100, hi=500, gain=0.12)  # la hoguera se encoge
# la mascara intenta gritar (escena 6)
for k in range(3):
    t0 = 51.6 + k * 0.55
    tt_ = tt(1.4)
    s = np.sin(2 * np.pi * 330 * tt_ * (1 + 0.02 * np.sin(2 * np.pi * 9 * tt_))) * np.sin(np.pi * tt_ / 1.4) ** 2
    s += fft_filter(noise(1.4), lo=1500, hi=5000) * 0.3 * np.sin(np.pi * tt_ / 1.4)
    add(sfx, t0, s.astype(np.float32), 0, 0.05)
music_box(57.6, note_name('A5'), dur=3, gain=0.12)
music_box(58.1, note_name('F5'), dur=3, gain=0.1)

# --- ACTO II: bosque, pantano, cementerio (60-110)
pad(60, ['D2', 'A2', 'F3'], 26, gain=0.045, bright=900, attack=3)
pad(85, ['G2', 'D3', 'Bb3'], 12, gain=0.045, bright=900)
pad(96, ['A2', 'E3', 'C#4'], 15, gain=0.045, bright=1000)
choir(62, ['D4', 'A4'], 12, gain=0.035, vowel='o')
choir(76, ['F4', 'A4', 'D5'], 9, gain=0.03, vowel='o')
wind(60, 112, gain=0.06, lo=120, hi=700)
for t0 in (63.5, 64.2, 71.0, 71.7):  # buho
    tt_ = tt(0.5)
    s = np.sin(2 * np.pi * 380 * tt_ * (1 - 0.05 * tt_)) * np.sin(np.pi * tt_ / 0.5) ** 2
    add(sfx, t0, s.astype(np.float32), -0.6, 0.06)
for lt in np.arange(0, 10, 1.3):  # pasos en el bosque / tablones
    thud(60 + lt, gain=0.04, freq=60)
    thud(80 + lt, gain=0.05, freq=110)
for k in range(26):  # ranas del pantano
    t0 = 80 + rng.uniform(0, 9.5)
    tt_ = tt(0.25)
    f = rng.uniform(140, 220)
    s = np.sign(np.sin(2 * np.pi * f * tt_)) * (np.sin(2 * np.pi * 28 * tt_) > 0) * np.exp(-tt_ * 6)
    add(sfx, t0, fft_filter(s.astype(np.float32), hi=1200), rng.uniform(-0.8, 0.8), 0.03)
for k in range(12):  # burbujas del caldero
    tt_ = tt(0.12)
    f = rng.uniform(300, 700)
    s = np.sin(2 * np.pi * f * tt_ * (1 + tt_ * 6)) * np.exp(-tt_ * 30)
    add(sfx, 80 + rng.uniform(0, 9), s.astype(np.float32), 0.5, 0.05)
whoosh(87, 1.2, lo=600, hi=3000, gain=0.05, pan=0.6)  # cortina
# cementerio
bell(90.4, note_name('C#3'), gain=0.28)
for i in range(6):  # zombis que se levantan
    t0 = 90 + i * 0.9
    tt_ = tt(1.8)
    f = 85 + i * 6
    s = fft_filter(np.sign(np.sin(2 * np.pi * f * tt_ * (1 + 0.1 * np.sin(2 * np.pi * 2 * tt_)))).astype(np.float32), lo=80, hi=900)
    s *= np.sin(np.pi * tt_ / 1.8) ** 2
    add(sfx, t0 + 0.3, s, (-1) ** i * 0.5, 0.05)
    whoosh(t0, 0.9, lo=80, hi=400, gain=0.08, pan=(-1) ** i * 0.5)  # tierra
# runas (escena 11)
chime_run(102.8, ['D5', 'F5', 'A5', 'D6', 'F6', 'A6', 'D7'], step=0.36, gain=0.09)
choir(103, ['D4', 'A4', 'D5', 'F5'], 8, gain=0.05, vowel='a', attack=2)
boom(106.5, gain=0.25)

# --- ACTO III: la montana y la caverna (110-180)
pad(110, ['D2', 'A2'], 22, gain=0.06, bright=600, attack=3)
choir(111, ['D3', 'A3', 'F4'], 10, gain=0.05, vowel='o')
wind(110, 132, gain=0.06, lo=100, hi=600)
crackle(110, 132, gain=0.03, buf=sfx)
for k in range(30):  # gotas del tunel
    tt_ = tt(0.15)
    f = rng.uniform(1200, 2400)
    s = np.sin(2 * np.pi * f * tt_ * (1 - tt_ * 2)) * np.exp(-tt_ * 35)
    add(cave, 120 + rng.uniform(0, 10), s.astype(np.float32), rng.uniform(-0.7, 0.7), 0.05)
for lt in np.arange(0.2, 10, 0.9):
    thud(120 + lt, gain=0.05, freq=70, buf=cave)
# revelacion
choir(130.2, ['D3', 'A3', 'D4', 'F4', 'A4'], 10.5, gain=0.08, vowel='a', attack=3)
pad(130, ['D1', 'D2', 'A2'], 50, gain=0.07, bright=500, attack=3)
crackle(130, 230, gain=0.06)
for k in range(30):  # latidos 2:20-3:00
    bpm = 58 + k * 1.1
    t0 = 140 + sum(60 / (58 + j * 1.1) for j in range(k))
    if t0 > 180:
        break
    heartbeat(t0, bpm, gain=0.3)
clatter(141.8, 1.9, density=120, gain=0.14, pan=-0.3, buf=cave)  # craneos que giran
clatter(142.0, 1.8, density=120, gain=0.14, pan=0.3, buf=cave)
pad(143.8, ['D4', 'G#4', 'D5'], 4, gain=0.03, bright=4000, attack=0.4)  # ojos
whoosh(144.4, 1.2, lo=200, hi=2000, gain=0.2)  # fuego que se aviva
for k in range(14):  # arcos tensandose
    t0 = 151.2 + rng.uniform(0, 1.6)
    tt_ = tt(0.7)
    f = rng.uniform(140, 260) * (1 + tt_ * 0.6)
    s = fft_filter(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)).astype(np.float32), lo=200, hi=2500) * np.sin(np.pi * tt_ / 0.7)
    add(cave, t0, s, rng.uniform(-0.9, 0.9), 0.025)
for lt in np.arange(0.2, 10, 1.1):
    thud(150 + lt, gain=0.05, freq=65, buf=cave)
    thud(160 + lt, gain=0.05, freq=95, buf=cave)
whoosh(160, 10, lo=80, hi=400, gain=0.12)  # rugido de la fosa
pad(170, ['D2', 'Ab2', 'D3'], 11, gain=0.06, bright=800, attack=2)
growl(174.3, dur=2.8, gain=0.12)  # el rey se levanta
boom(176.2, gain=0.3)
clatter(174.2, 2.6, density=50, gain=0.12, buf=cave, pitch=0.7)

# --- ACTO IV: la batalla (180-230)
growl(180.2, dur=2.4, gain=0.3)  # "Que no salga vivo!"
bpm = 140
b = 60 / bpm
ost = ['D2', 'D2', 'F2', 'D2', 'G2', 'D2', 'A2', 'G#2']
t = 181.5
k = 0
while t < 220.0:
    pluck(t, note_name(ost[k % 8]), dur=0.22, gain=0.16, bright=1800)
    pluck(t, note_name(ost[k % 8]) * 2, dur=0.18, gain=0.06, bright=2400)
    if k % 4 == 0:
        drum(t, 55, gain=0.38)
    if k % 8 == 6:
        drum(t, 80, gain=0.22, click=0.8)
    if k % 2 == 1:
        drum(t, 180, dur=0.2, gain=0.06, click=1.2)
    if k % 16 == 0:
        pad(t, ['D3', 'F3', 'A3'] if (k // 16) % 2 == 0 else ['Bb2', 'D3', 'F3'], 16 * b, gain=0.05, bright=2200, attack=0.05, release=0.6)
    t += b
    k += 1
for i in range(40):  # flechas
    t0 = 182.6 + 0.25 + (i % 7) * 0.06 / 0.35 + rng.uniform(0, 1.5)
    tt_ = tt(0.6)
    f = 2200 * (1 - tt_ * 0.5)
    s = fft_filter(noise(0.6), lo=1500, hi=5000) * np.sin(np.pi * tt_ / 0.6) * 0.5 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.1 * np.sin(np.pi * tt_ / 0.6)
    add(sfx, t0, s.astype(np.float32), rng.uniform(-0.9, 0.9), 0.05)
whoosh(184.6, 0.8, lo=100, hi=1200, gain=0.25)  # humo
whoosh(186.4, 0.7, lo=100, hi=1200, gain=0.22)
for k in range(9):  # colapsos al paso
    clatter(190.6 + k * 1.0 + rng.uniform(0, 0.4), 0.7, density=90, gain=0.16, pan=rng.uniform(-0.7, 0.7), buf=cave)
whoosh(190, 10, lo=150, hi=1200, gain=0.06)
# golpe del baculo
boom(202.05, gain=0.85)
whoosh(202.1, 1.4, lo=300, hi=4000, gain=0.25)
thud(202.6, gain=0.5, freq=80)
shatter(202.75, gain=0.12)  # la mascara se agrieta
# el orbe
pad(210, ['D5', 'A5', 'E6'], 6.5, gain=0.025, bright=6000, attack=1.5)
whoosh(210.9, 1.2, lo=200, hi=2500, gain=0.12)  # salto
chime_run(214.5, ['A5', 'D6', 'E6', 'A6'], step=0.35, gain=0.08)
bell(216.05, note_name('D5'), gain=0.18, dur=4)
choir(216.0, ['D4', 'A4', 'D5'], 4.5, gain=0.05, vowel='a', attack=0.5)
# silencio tenso y grito
tt_ = tt(1.5)
add(music, 220.0, (np.sin(2 * np.pi * (200 + 300 * tt_ / 1.5) * tt_) * (tt_ / 1.5) ** 2).astype(np.float32), 0, 0.03)
scream(221.5, gain=0.5)
boom(221.55, gain=0.9, dur=4)
whoosh(221.8, 4.0, lo=100, hi=2000, gain=0.25)  # ola de fuego
for k in range(12):
    clatter(222.2 + k * 0.25 + rng.uniform(0, 0.2), 0.8, density=100, gain=0.12, pan=rng.uniform(-0.9, 0.9), buf=cave)
shatter(224.0, gain=0.25)  # la corona
clatter(224.2, 2.0, density=60, gain=0.18, buf=cave, pitch=0.6)  # el rey cae
thud(226.0, gain=0.4, freq=50)
choir(224.5, ['D3', 'A3', 'D4', 'F#4', 'A4'], 7, gain=0.07, vowel='a', attack=1.5)  # resolucion mayor
pad(224.5, ['D2', 'A2', 'F#3'], 8, gain=0.05, bright=1500, attack=1.5)

# --- ACTO V: amanecer (230-260)
pad(229.5, ['D3', 'F#3', 'A3'], 9, gain=0.04, bright=2200, attack=2.5)
pad(238, ['B2', 'D3', 'F#3'], 8, gain=0.04, bright=2200)
pad(245.5, ['G2', 'B2', 'D3'], 8, gain=0.04, bright=2200)
pad(253, ['A2', 'D3', 'F#3'], 7, gain=0.04, bright=2200, release=4)
choir(250, ['D4', 'F#4', 'A4', 'D5'], 10, gain=0.04, vowel='o', release=4)
melody_major = ['F#5', 'A5', 'D6', 'C#6', 'A5', 'F#5', 'G5', 'B5', 'E6', 'D6', 'A5', 'F#5', 'E5', 'G5', 'A5', 'D5']
t = 231.0
k = 0
while t < 257.5:
    music_box(t, note_name(melody_major[k % len(melody_major)]), dur=2.2, gain=0.12, pan=0.25 * np.sin(k))
    t += 0.62
    k += 1
for k in range(16):  # pajaros al amanecer
    t0 = 231 + rng.uniform(0, 26)
    tt_ = tt(0.18)
    f = rng.uniform(2800, 4200) * (1 + 0.3 * np.sin(2 * np.pi * 18 * tt_))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt_ / 0.18)
    add(sfx, t0, s.astype(np.float32), rng.uniform(-0.8, 0.8), 0.025)
chime_run(240.6, ['D5', 'E5', 'F#5', 'A5', 'B5', 'D6', 'E6', 'F#6', 'A6'], step=0.4, gain=0.07)  # faroles en ola
whoosh(242, 2.5, lo=200, hi=1500, gain=0.08)  # hoguera
music_box(253.5, note_name('D6'), dur=4, gain=0.12)  # la sonrisa
bell(258.0, note_name('D4'), gain=0.15, dur=4)

# ----------------------------------------------------------------------------
# reverberacion y mezcla
# ----------------------------------------------------------------------------
def reverb(x, seconds, damp, seed):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = r.standard_normal(n).astype(np.float32) * np.exp(-np.arange(n) / SR * (6.9 / seconds))
    ir = fft_filter(ir, hi=damp)
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    L = 1 << int(np.ceil(np.log2(len(x) + n)))
    out = np.zeros_like(x)
    I = np.fft.rfft(ir, L)
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], L) * I, L)[: len(x)]
    return out


print('reverberando...')
mix = music * 0.9 + reverb(music, 2.8, 5000, 1) * 0.35
mix += sfx + reverb(sfx, 1.8, 4000, 2) * 0.25
mix += cave + reverb(cave, 4.5, 3500, 3) * 0.6
# fundido de entrada/salida
fade = np.ones(N, np.float32)
fade[: int(1.5 * SR)] = np.linspace(0, 1, int(1.5 * SR))
fade[-int(2.5 * SR):] = np.linspace(1, 0, int(2.5 * SR))
mix *= fade[:, None]
# compresion lenta + limitador suave: sube las partes tranquilas sin aplastar el climax
blk = SR // 10
lev = np.sqrt(np.mean(mix[: len(mix) // blk * blk].reshape(-1, blk, 2) ** 2, axis=(1, 2))) + 1e-6
lev = np.convolve(lev, np.ones(15) / 15, mode='same')
target = 10 ** (-19 / 20)
g = np.clip((target / lev) ** 0.6, 0.3, 6.0)
g = np.repeat(g, blk)
g = np.concatenate([g, np.full(len(mix) - len(g), g[-1])])
mix *= g[:, None]
mix = np.tanh(mix * 1.7) * 0.93
os.makedirs(os.path.join(HERE, 'audio'), exist_ok=True)
out = os.path.join(HERE, 'audio', 'soundtrack.wav')
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
print('ok', out)
