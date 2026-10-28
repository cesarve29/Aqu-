#!/usr/bin/env python3
"""
Banda sonora de BLOCKCRAFT sintetizada desde cero con numpy:
musica por capitulos + efectos sincronizados con events.json (generado por render.cjs --events).

Uso: python3 audio.py  -> soundtrack.wav (44.1 kHz estereo)
"""
import json
import math
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUR = 335.0
N = int(SR * DUR)
R = np.random.default_rng(7)

music = np.zeros((2, N))
sfx = np.zeros((2, N))
amb = np.zeros((2, N))


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=0.05, d=None):
    e = np.ones(n)
    na, nr = min(n, max(1, int(a * SR))), min(n, max(1, int(r * SR)))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


def put(buf, t0, x, amp=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i + len(x) <= 0:
        return
    if i < 0:
        x = x[-i:]
        i = 0
    x = x[:N - i]
    l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    buf[0, i:i + len(x)] += x * amp * l * 1.414
    buf[1, i:i + len(x)] += x * amp * r * 1.414


def band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def noise(d):
    return R.standard_normal(int(d * SR))


# ------------------------------------------------------------------ instrumentos
def piano(f, d=2.5):
    t = tt(d)
    x = np.zeros_like(t)
    for k in range(1, 7):
        x += np.sin(2 * np.pi * f * k * t * (1 + 0.0004 * k)) / k ** 1.6 * np.exp(-t * (1.2 + k * 0.9))
    return x * env(len(t), 0.004, 0.2)


def pluck(f, d=0.6):
    t = tt(d)
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.2 * np.exp(-t * (5 + k * 3)) for k in range(1, 8))
    return x * env(len(t), 0.002, 0.05)


def saw(f, t, nh=14):
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, nh) if f * k < 9000)


def pad(f, d, a=0.8, r=1.2, bright=8):
    t = tt(d)
    x = saw(f * 0.997, t, bright) + saw(f * 1.003, t, bright) + 0.5 * np.sin(2 * np.pi * f / 2 * t)
    lfo = 1 + 0.15 * np.sin(2 * np.pi * 0.3 * t)
    return x * lfo * env(len(t), a, r) * 0.25


def choir(f, d, a=1.0, r=1.5):
    t = tt(d)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    x = np.zeros_like(t)
    for k, amp in [(1, 1.0), (2, 0.5), (3, 0.35), (4, 0.25), (5, 0.12), (7, 0.08)]:
        form = 1.0 + 0.8 * math.exp(-((f * k - 700) / 300) ** 2) + 0.5 * math.exp(-((f * k - 1150) / 250) ** 2)
        x += np.sin(ph * k) * amp * form
    return x * env(len(t), a, r) * 0.3


def brass(f, d):
    t = tt(d)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t * 2, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    bright = np.clip(t * 8, 0, 1) * 0.7 + 0.3
    x = sum(np.sin(ph * k) / k * bright ** (k * 0.4) for k in range(1, 12) if f * k < 8000)
    return np.tanh(x * 1.2) * env(len(t), 0.03, 0.15) * 0.5


def bass(f, d):
    t = tt(d)
    x = saw(f, t, 8) * np.exp(-t * 3) + 0.6 * np.sin(2 * np.pi * f * t)
    return x * env(len(t), 0.003, 0.05) * 0.5


def kick(d=0.5, f0=120, f1=42):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * 25)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7) + band(noise(d), 1000, 6000) * np.exp(-t * 90) * 0.3


def snare(d=0.3):
    t = tt(d)
    return band(noise(d), 800, 9000) * np.exp(-t * 18) * 0.6 + np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25) * 0.6


def hat(d=0.08):
    t = tt(d)
    return band(noise(d), 6000, 16000) * np.exp(-t * 60) * 0.5


def tom(f=90, d=0.6):
    t = tt(d)
    ff = f * (1 + 0.5 * np.exp(-t * 20))
    return np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 5) + band(noise(d), 200, 2000) * np.exp(-t * 30) * 0.2


def bell(f, d=1.6):
    t = tt(d)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 3) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 9)
    return x * env(len(t), 0.002, 0.1)


# ------------------------------------------------------------------ musica
C_CALM = [[48, 55, 60, 64, 71], [45, 52, 57, 60, 67], [41, 48, 53, 57, 64], [43, 50, 55, 59, 62]]
C_DAWN2 = [[41, 48, 53, 57, 64], [48, 55, 60, 64, 67], [43, 50, 55, 59, 62], [45, 52, 57, 60, 64]]
C_DUSK = [[45, 52, 57, 60, 64], [41, 48, 53, 57, 60], [38, 45, 50, 53, 57], [40, 47, 52, 56, 59]]
C_NIGHT = [[38, 45, 50, 53, 57], [34, 41, 46, 50, 53], [36, 43, 48, 52, 55], [33, 40, 45, 49, 52]]
C_END = [[40, 47, 52, 55, 59], [41, 48, 53, 57, 60], [40, 47, 52, 55, 59], [38, 45, 50, 53, 57]]
C_BOSS = [[40, 47, 52, 55, 59], [36, 43, 48, 52, 55], [38, 45, 50, 54, 57], [35, 42, 47, 51, 54]]
C_WIN = [[40, 47, 52, 56, 59], [37, 44, 49, 52, 56], [33, 45, 49, 52, 57], [35, 47, 51, 54, 59]]


def calm_section(t0, t1, bpm, prog, melody=False, amp=1.0, seed=1):
    beat = 60 / bpm
    bar = beat * 4
    rr = np.random.default_rng(seed)
    pat = [0, 2, 3, 4, 3, 2, 1, 2]
    mel = 72
    scale = [60, 62, 64, 67, 69, 72, 74, 76, 79, 81]
    t, b = t0, 0
    while t < t1 - 0.5:
        ch = prog[b % len(prog)]
        put(music, t, pad(mf(ch[0] + 12), bar + 0.5, 1.0, 1.0, 5), 0.1 * amp)
        put(music, t, piano(mf(ch[0] - 12), 3.5), 0.22 * amp)
        for i, k in enumerate(pat):
            put(music, t + i * beat / 2, piano(mf(ch[k] + 12)), 0.13 * amp, pan=-0.3 + 0.15 * (k % 3))
        if melody and b % 2 == 1:
            for j in range(4):
                idx = int(np.argmin([abs(s - mel) for s in scale]))
                idx = int(np.clip(idx + rr.integers(-2, 3), 0, len(scale) - 1))
                mel = scale[idx]
                put(music, t + j * beat, piano(mf(mel + 12), 2.0), 0.16 * amp, pan=0.25)
        t += bar
        b += 1


def pads(t0, t1, bar, prog, amp, voice=pad, oct_=12):
    t, b = t0, 0
    while t < t1 - 0.1:
        ch = prog[b % len(prog)]
        d = min(bar + 1.0, t1 - t + 1.0)
        for m in ch[1:]:
            put(music, t, voice(mf(m + oct_ - 12), d), amp / 4, pan=(m % 5 - 2) * 0.2)
        put(music, t, voice(mf(ch[0]), d), amp / 3)
        t += bar
        b += 1


def battle(t0, t1, bpm, prog, amp=1.0, drums=True, hats=True, arp=False, stabs=False, snr=False):
    beat = 60 / bpm
    s16 = beat / 4
    t, b = t0, 0
    while t < t1 - 0.05:
        ch = prog[(b // 4) % len(prog)]
        for i in range(4):
            tb = t + i * beat
            if tb >= t1:
                break
            if drums:
                if i in (0, 2) or (b % 4 == 3 and i == 3):
                    put(music, tb, kick(), 0.55 * amp)
                if snr and i in (1, 3):
                    put(music, tb, snare(), 0.3 * amp, pan=0.1)
                if not snr and i == 3 and b % 2 == 1:
                    put(music, tb, tom(110), 0.3 * amp, pan=-0.2)
            for j in range(2):
                put(music, tb + j * beat / 2, bass(mf(ch[0] + (12 if (i * 2 + j) % 4 == 2 else 0)), beat / 2), 0.32 * amp)
                if hats:
                    put(music, tb + j * beat / 2, hat(), 0.12 * amp, pan=0.35)
            if arp:
                for j in range(4):
                    m = ch[1 + (i * 4 + j) % 4] + 12
                    put(music, tb + j * s16, pluck(mf(m), 0.25), 0.1 * amp, pan=-0.35 + 0.7 * ((i * 4 + j) % 2))
        if stabs and b % 4 == 0:
            for m in ch[1:4]:
                put(music, t, brass(mf(m + 12), beat * 1.5), 0.16 * amp)
        t += beat * 4
        b += 1


def compose():
    calm_section(0.5, 40, 72, C_CALM, melody=False, amp=0.9, seed=1)
    calm_section(40, 75, 84, C_CALM, melody=True, amp=0.9, seed=2)
    pads(75, 92, 4.2, C_DUSK, 0.5)
    calm_section(76, 92, 60, C_DUSK, amp=0.5, seed=3)
    # noche: suspenso y combate
    pads(92, 100, 4.0, C_NIGHT[:1], 0.45)
    for k in range(8):
        put(music, 92 + k * 1.0, kick(0.4, 70, 38), 0.35)
        put(music, 92.28 + k * 1.0, kick(0.4, 60, 36), 0.22)
    battle(100, 140.6, 112, C_NIGHT, amp=0.85, arp=True)
    pads(100, 140.6, 60 / 112 * 16, C_NIGHT, 0.25, voice=pad)
    pads(141, 143.5, 2.5, [[38, 39, 50, 51, 62]], 0.3)
    battle(145, 158, 112, C_NIGHT, amp=0.8, arp=True)
    pads(158.4, 168, 4.8, [[50, 57, 62, 66, 69], [43, 55, 59, 62, 67]], 0.4, voice=choir)
    calm_section(168, 196, 76, C_DAWN2, melody=True, amp=0.85, seed=4)
    # el Fin
    pads(200, 240, 60 / 90 * 8, C_END, 0.5)
    pads(200, 240, 60 / 90 * 8, C_END, 0.35, voice=choir, oct_=24)
    beat = 60 / 90
    t = 212.0
    while t < 239.5:
        put(music, t, tom(70, 0.9), 0.5)
        put(music, t + beat * 2, tom(85, 0.7), 0.32)
        t += beat * 4
    battle(240, 275.2, 140, C_BOSS, amp=0.9, arp=True, stabs=True, snr=True)
    pads(240, 275.2, 60 / 140 * 16, C_BOSS, 0.3, voice=choir, oct_=24)
    # muerte de la dragona: crescendo
    for i, ch in enumerate([[40, 47, 52, 55, 59], [36, 48, 52, 55, 60], [43, 50, 55, 59, 62], [35, 47, 51, 54, 59]]):
        t0 = 275.6 + i * 3.6
        for m in ch:
            put(music, t0, choir(mf(m + 12), 4.4, 0.8, 1.0), 0.12 + 0.05 * i)
            put(music, t0, pad(mf(m), 4.4, 0.6, 1.0), 0.07 + 0.03 * i)
    # victoria
    beat = 60 / 100
    t = 291.2
    for i, ch in enumerate(C_WIN + [C_WIN[0]]):
        d = beat * (4 if i < 4 else 8)
        for m in ch[1:]:
            put(music, t, brass(mf(m + 12), d), 0.13)
        put(music, t, brass(mf(ch[0]), d), 0.2)
        put(music, t, tom(60, 1.2), 0.5)
        for j in range(4):
            put(music, t + j * beat, piano(mf(ch[1 + j % 4] + 24), 2.0), 0.1)
        t += d
    calm_section(303.5, 333, 72, C_CALM, melody=True, amp=0.95, seed=5)
    put(music, 331.5, piano(mf(48), 4.0), 0.3)
    put(music, 331.5, piano(mf(60), 4.0), 0.2)
    put(music, 331.5, piano(mf(64), 4.0), 0.2)
    put(music, 331.5, piano(mf(67), 4.0), 0.2)


# ------------------------------------------------------------------ efectos
def chirp_noise(d, f0, f1, bw=600):
    t = tt(d)
    n = band(noise(d), 1, bw)
    f = f0 * (f1 / f0) ** (t / d)
    return n * np.cos(2 * np.pi * np.cumsum(f) / SR)


def growl(f0, d, rough=0.6, f1=None):
    t = tt(d)
    f1 = f1 or f0
    f = np.linspace(f0, f1, len(t)) * (1 + 0.03 * np.sin(2 * np.pi * 7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum(np.sin(ph * k) / k for k in range(1, 20))
    x *= 1 + rough * np.sin(2 * np.pi * 31 * t)
    x = band(x, 80, 2500) + band(noise(d), 200, 1500) * rough * 0.4
    return np.tanh(x * 1.5)


def boom(d=2.5, big=1.0):
    t = tt(d)
    x = band(noise(d), 30, 3000) * np.exp(-t * (2.2 / big)) * 1.2
    x += kick(d, 90, 28) * 0.9
    x += band(noise(d), 2000, 9000) * np.exp(-t * 14) * 0.5
    return np.tanh(x * 1.3)


def fx(kind, ev):
    if kind == 'punch':
        t = tt(0.12)
        return band(noise(0.12), 200, 2500) * np.exp(-t * 40) * 0.6 + np.sin(2 * np.pi * 90 * t) * np.exp(-t * 30), 0.35
    if kind == 'break':
        t = tt(0.35)
        return band(noise(0.35), 300, 3500) * np.exp(-t * 10) + np.sin(2 * np.pi * 140 * t) * np.exp(-t * 20) * 0.5, 0.45
    if kind == 'sparkle':
        x = np.zeros(int(2.5 * SR))
        for i, m in enumerate([84, 88, 91, 96, 100]):
            b = bell(mf(m), 1.5)
            s = int(i * 0.12 * SR)
            x[s:s + len(b)] += b[:len(x) - s]
        return x, 0.18
    if kind == 'toast':
        x = np.zeros(int(2 * SR))
        for i, m in enumerate([79, 84, 88]):
            b = bell(mf(m), 1.4)
            s = int(i * 0.1 * SR)
            x[s:s + len(b)] += b[:len(x) - s]
        return x, 0.2
    if kind == 'groan':
        return growl(95 + R.random() * 25, 1.3, 0.8, 75) * env(int(1.3 * SR), 0.15, 0.4), 0.22
    if kind == 'zombie_hurt':
        return growl(150, 0.45, 0.5, 110) * env(int(0.45 * SR), 0.02, 0.15), 0.25
    if kind == 'skeleton_hurt':
        d = 0.45
        t = tt(d)
        clicks = (np.sin(2 * np.pi * 28 * t) > 0.6).astype(float)
        return band(noise(d), 1500, 7000) * clicks * np.exp(-t * 4), 0.3
    if kind in ('spider_hurt', 'spider_hiss'):
        d = 0.9 if kind == 'spider_hiss' else 0.4
        t = tt(d)
        return band(noise(d), 2500, 9000) * (0.6 + 0.4 * np.sin(2 * np.pi * 18 * t)) * env(len(t), 0.05, 0.2), 0.25
    if kind == 'creeper_hurt':
        return np.zeros(10), 0
    if kind == 'hit':
        t = tt(0.25)
        return band(noise(0.25), 150, 4000) * np.exp(-t * 30) + np.sin(2 * np.pi * 70 * t) * np.exp(-t * 18), 0.42
    if kind == 'whoosh':
        return chirp_noise(0.28, 500, 1600, 500) * env(int(0.28 * SR), 0.06, 0.15), 0.25
    if kind == 'poof':
        t = tt(0.6)
        return band(noise(0.6), 100, 1200) * np.exp(-t * 6), 0.4
    if kind == 'bow':
        t = tt(0.4)
        return pluck(180, 0.4) * 0.8 + chirp_noise(0.4, 2500, 900, 800) * np.exp(-t * 8) * 0.5, 0.35
    if kind == 'bow_draw':
        t = tt(0.9)
        return band(noise(0.9), 400, 1800) * np.linspace(0.1, 1, len(t)) * (0.7 + 0.3 * np.sin(2 * np.pi * 40 * t)) * env(len(t), 0.05, 0.1), 0.08
    if kind == 'arrow_hit':
        t = tt(0.15)
        return np.sin(2 * np.pi * 220 * t) * np.exp(-t * 35) + band(noise(0.15), 500, 3000) * np.exp(-t * 50) * 0.5, 0.35
    if kind == 'hiss':
        d = 2.5
        t = tt(d)
        return band(noise(d), 3000, 12000) * np.linspace(0.2, 1.0, len(t)) ** 2 * env(len(t), 0.1, 0.05), 0.5
    if kind == 'explode':
        return boom(3.0, 1.2), 1.0
    if kind == 'hurt':
        t = tt(0.25)
        f = 330 - 120 * t / 0.25
        ph = 2 * np.pi * np.cumsum(f) / SR
        return sum(np.sin(ph * k) / k for k in range(1, 6)) * env(len(t), 0.01, 0.08), 0.3
    if kind == 'place':
        t = tt(0.15)
        return band(noise(0.15), 150, 2000) * np.exp(-t * 35) + np.sin(2 * np.pi * 110 * t) * np.exp(-t * 30) * 0.6, 0.35
    if kind == 'ignite':
        t = tt(0.3)
        return band(noise(0.3), 2000, 10000) * np.exp(-t * 14), 0.4
    if kind == 'portal_open':
        d = 4.0
        t = tt(d)
        x = sum(np.sin(2 * np.pi * f * t * (1 + 0.003 * np.sin(2 * np.pi * 0.7 * t))) for f in (110, 165.5, 220.8, 331))
        x *= (0.6 + 0.4 * np.sin(2 * np.pi * 6 * t)) * env(len(t), 0.6, 1.5) * 0.3
        return x + chirp_noise(d, 200, 3000, 800) * env(len(t), 0.05, 2.5) * 0.4, 0.4
    if kind == 'warp':
        d = 4.0
        t = tt(d)
        x = chirp_noise(d, 150, 5000, 1500) * (t / d) ** 1.5
        x += sum(np.sin(2 * np.pi * np.cumsum(f * (1 + 3 * (t / d) ** 2)) / SR) for f in (110, 165)) * 0.3 * (t / d)
        return x * env(len(t), 0.2, 0.05), 0.55
    if kind == 'roar':
        d = 2.6
        return growl(80, d, 0.9, 52) * env(int(d * SR), 0.25, 0.8), 0.7
    if kind == 'crystal':
        d = 2.0
        x = boom(d, 0.6) * 0.8
        for i in range(25):
            s = int(R.random() * 0.4 * SR)
            b = bell(1500 + R.random() * 4000, 0.6)
            x[s:s + len(b)] += b[:len(x) - s] * 0.25
        return x, 0.65
    if kind == 'breath':
        d = 3.5
        t = tt(d)
        return band(noise(d), 100, 1800) * env(len(t), 0.3, 1.2) + growl(60, d, 0.4, 50) * env(len(t), 0.3, 1.0) * 0.3, 0.45
    if kind == 'dragon_hit':
        d = 0.7
        x = fx('hit', ev)[0]
        g = growl(120, d, 0.7, 85) * env(int(d * SR), 0.02, 0.3)
        g[:len(x)] += x
        return g, 0.45
    if kind == 'crit':
        x = fx('dragon_hit', ev)[0]
        s = fx('sparkle', ev)[0]
        y = np.zeros(max(len(x), len(s)))
        y[:len(x)] += x
        y[:len(s)] += s * 1.5
        return y, 0.6
    if kind == 'land':
        return kick(1.2, 70, 30) + band(noise(1.2), 40, 600) * np.exp(-tt(1.2) * 4) * 0.6, 0.7
    if kind == 'dragon_death':
        d = 14.0
        t = tt(d)
        x = growl(90, d, 0.9, 40) * env(len(t), 0.5, 3) * 0.7
        x += chirp_noise(d, 300, 6000, 2000) * (t / d) ** 2 * 0.5
        return x, 0.6
    if kind == 'boom_big':
        return boom(5.0, 2.5), 1.0
    if kind == 'victory':
        return fx('toast', ev)[0], 0.25
    if kind == 'xp':
        return bell(mf(84 + int(R.random() * 12)), 0.25), 0.08
    if kind == 'step':
        t = tt(0.09)
        return band(noise(0.09), 150, 2200) * np.exp(-t * 45), 0.12
    if kind == 'step_end':
        t = tt(0.09)
        return band(noise(0.09), 300, 3500) * np.exp(-t * 50), 0.12
    if kind == 'flap':
        d = 0.7
        t = tt(d)
        dist = ev.get('d', 30)
        return band(noise(d), 60, 600) * np.sin(np.pi * t / d) ** 2, 0.5 * min(1.0, 18 / max(dist, 6))
    return None, 0


def ambience():
    t = tt(DUR)
    # viento suave
    w = band(noise(DUR), 80, 700) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 23))
    amb[0] += w * 0.012
    amb[1] += np.roll(w, 3000) * 0.012
    # pajaros de dia
    for a, b in [(10, 75), (170, 196), (306, 333)]:
        tc = a
        while tc < b:
            d = 0.12 + R.random() * 0.1
            x = tt(d)
            f = 2600 + 1400 * R.random()
            ch = np.sin(2 * np.pi * np.cumsum(f + 900 * np.sin(2 * np.pi * 14 * x)) / SR) * env(len(x), 0.01, 0.05)
            for k in range(1 + int(R.random() * 3)):
                put(amb, tc + k * (d + 0.05), ch, 0.03, pan=R.random() * 1.6 - 0.8)
            tc += 1.5 + R.random() * 3
    # grillos de noche
    for a, b in [(84, 168)]:
        x = tt(b - a)
        cr = np.sin(2 * np.pi * 4300 * x) * (np.sin(2 * np.pi * 30 * x) > 0.3) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.9 * x) > 0.5)
        fade = np.clip((x) / 4, 0, 1) * np.clip((b - a - x) / 4, 0, 1)
        put(amb, a, cr * fade, 0.008, pan=-0.4)
        put(amb, a + 0.37, cr * fade, 0.006, pan=0.5)
    # dron del Fin
    a, b = 200, 303
    x = tt(b - a)
    dr = (np.sin(2 * np.pi * 41 * x) + 0.5 * np.sin(2 * np.pi * 61.7 * x)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * x))
    dr += band(noise(b - a), 100, 900) * 0.6
    put(amb, a, dr * np.clip(x / 2, 0, 1) * np.clip((b - a - x) / 2, 0, 1), 0.03)


def reverb(x, secs=2.4, wet=0.25, seed=3):
    n = int(secs * SR)
    rr = np.random.default_rng(seed)
    out = np.zeros_like(x)
    L = 1 << int(math.ceil(math.log2(x.shape[1] + n)))
    for c in range(2):
        ir = rr.standard_normal(n) * np.exp(-np.arange(n) / SR * (6.9 / secs))
        ir = band(ir, 150, 7000)
        ir /= np.sqrt(np.sum(ir ** 2))
        y = np.fft.irfft(np.fft.rfft(x[c], L) * np.fft.rfft(ir, L), L)[:x.shape[1]]
        out[c] = x[c] + y * wet
    return out


def main():
    ev = json.load(open(os.path.join(HERE, 'events.json')))
    print('componiendo...')
    compose()
    print('efectos:', len(ev))
    for e in ev:
        x, a = fx(e['type'], e)
        if x is None or a == 0:
            continue
        pan = 0.0
        if e['type'] in ('groan', 'zombie_hurt', 'skeleton_hurt', 'spider_hurt', 'arrow_hit', 'flap'):
            pan = R.random() * 0.8 - 0.4
        put(sfx, e['t'], x, a, pan)
    ambience()
    # la musica baja durante el silencio del explosivo y la explosion
    t = np.arange(N) / SR
    duck = 1 - 0.6 * np.clip((t - 140.6) / 0.4, 0, 1) * np.clip((146 - t) / 1.5, 0, 1)
    duck *= np.clip(t / 0.8, 0, 1)
    duck *= np.where(t > 333.5, np.clip((335 - t) / 1.5, 0, 1), 1)
    print('reverb...')
    mix = reverb(music, 2.8, 0.45) * 0.9 * duck + reverb(sfx, 1.6, 0.25, 5) + reverb(amb, 2.0, 0.3, 9)
    mix = np.tanh(mix / np.percentile(np.abs(mix), 99.95) * 1.15) * 0.95
    pcm = (mix.T * 32767).astype(np.int16)
    out = os.path.join(HERE, 'soundtrack.wav')
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(out)


if __name__ == '__main__':
    main()
