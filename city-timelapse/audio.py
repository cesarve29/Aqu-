#!/usr/bin/env python3
"""Banda sonora del timelapse (3:00): piano ambiental que crece con la ciudad + clics de bloques.
Usa los instrumentos sintetizados de voxel-video/audio.py. Requiere events.json (render.cjs --events)."""
import json
import math
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'voxel-video'))
import audio as A  # noqa: E402

SR = A.SR
DUR = 180.0
N = int(SR * DUR)
R = np.random.default_rng(11)
music = np.zeros((2, N))
sfx = np.zeros((2, N))
amb = np.zeros((2, N))


def put(buf, t0, x, amp=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i + len(x) <= 0:
        return
    x = x[:N - i]
    l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    buf[0, i:i + len(x)] += x * amp * l * 1.414
    buf[1, i:i + len(x)] += x * amp * r * 1.414


mf = A.mf
PROG_A = [[48, 55, 60, 64, 71], [45, 52, 57, 60, 67], [41, 48, 53, 57, 64], [43, 50, 55, 59, 62]]
PROG_B = [[41, 48, 53, 57, 64], [48, 55, 60, 64, 67], [43, 50, 55, 59, 62], [45, 52, 57, 60, 64]]
PROG_N = [[45, 52, 57, 60, 64], [41, 48, 53, 57, 60], [43, 50, 55, 59, 62], [40, 47, 52, 56, 59]]


def section(t0, t1, bpm, prog, amp=1.0, melody=False, drums=0.0, bassl=0.0, choir=0.0, seed=1):
    beat = 60 / bpm
    bar = beat * 4
    rr = np.random.default_rng(seed)
    scale = [60, 62, 64, 67, 69, 72, 74, 76, 79]
    mel = 72
    pat = [0, 2, 3, 4, 3, 2, 1, 2]
    t, b = t0, 0
    while t < t1 - 0.3:
        ch = prog[b % len(prog)]
        put(music, t, A.pad(mf(ch[0] + 12), bar + 0.6, 1.0, 1.0, 5), 0.09 * amp)
        put(music, t, A.piano(mf(ch[0] - 12), 3.5), 0.2 * amp)
        for i, k in enumerate(pat):
            put(music, t + i * beat / 2, A.piano(mf(ch[k] + 12)), 0.12 * amp, pan=-0.3 + 0.15 * (k % 3))
        if melody:
            for j in range(4):
                if rr.random() < 0.7:
                    idx = int(np.argmin([abs(s - mel) for s in scale]))
                    mel = scale[int(np.clip(idx + rr.integers(-2, 3), 0, len(scale) - 1))]
                    put(music, t + j * beat, A.piano(mf(mel + 12), 2.2), 0.15 * amp, pan=0.25)
        if choir:
            for m in ch[1:4]:
                put(music, t, A.choir(mf(m + 12), bar + 0.8, 0.8, 1.0), choir * 0.06)
        for i in range(4):
            tb = t + i * beat
            if drums:
                if i in (0, 2):
                    put(music, tb, A.kick(0.4, 90, 40), 0.35 * drums)
                if i in (1, 3):
                    put(music, tb, A.snare(0.2), 0.08 * drums, pan=0.15)
                for j in range(2):
                    put(music, tb + j * beat / 2, A.hat(), 0.06 * drums, pan=0.35)
            if bassl:
                put(music, tb, A.bass(mf(ch[0]), beat * 0.9), 0.25 * bassl)
        t += bar
        b += 1


def compose():
    section(0.4, 24, 76, PROG_A, amp=0.9, seed=1)
    section(24, 66, 96, PROG_B, amp=0.9, melody=True, drums=0.6, bassl=0.6, seed=2)
    section(66, 80, 72, PROG_N, amp=0.7, seed=3)
    section(80, 124, 100, PROG_A, amp=0.95, melody=True, drums=0.8, bassl=0.8, seed=4)
    section(124, 132, 72, PROG_N, amp=0.7, seed=5)
    section(132, 168, 100, PROG_B, amp=1.0, melody=True, drums=0.85, bassl=0.9, choir=1.0, seed=6)
    section(168, 177, 66, PROG_A[:2], amp=0.9, choir=1.2, seed=7)
    for m in (48, 55, 60, 64, 67, 72):
        put(music, 176.0, A.piano(mf(m), 4.0), 0.18)


def blocks(ev):
    ts = np.array(ev['placements'])
    step = 1 / 14
    for k in range(int(DUR / step)):
        a, b = k * step, (k + 1) * step
        n = np.searchsorted(ts, b) - np.searchsorted(ts, a)
        if n == 0:
            continue
        t = A.tt(0.07)
        f = 300 + R.random() * 500
        x = A.band(A.noise(0.07), 300, 3500) * np.exp(-t * 60) + np.sin(2 * np.pi * f * t) * np.exp(-t * 45) * 0.4
        put(sfx, a + R.random() * step * 0.5, x, 0.05 + 0.02 * min(1.0, n / 6), pan=R.random() * 1.2 - 0.6)


def ambience():
    t = A.tt(DUR)
    w = A.band(A.noise(DUR), 80, 700) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 19))
    amb[0] += w * 0.012
    amb[1] += np.roll(w, 3000) * 0.012
    for a, b in [(2, 64), (82, 122), (134, 166)]:
        tc = a
        while tc < b:
            d = 0.12 + R.random() * 0.1
            x = A.tt(d)
            f = 2600 + 1400 * R.random()
            ch = np.sin(2 * np.pi * np.cumsum(f + 900 * np.sin(2 * np.pi * 14 * x)) / SR) * A.env(len(x), 0.01, 0.05)
            for k in range(1 + int(R.random() * 3)):
                put(amb, tc + k * (d + 0.05), ch, 0.028, pan=R.random() * 1.6 - 0.8)
            tc += 1.2 + R.random() * 2.5
    for a, b in [(64, 82), (122, 134), (166, 180)]:
        x = A.tt(b - a)
        cr = np.sin(2 * np.pi * 4300 * x) * (np.sin(2 * np.pi * 30 * x) > 0.3) * ((0.5 + 0.5 * np.sin(2 * np.pi * 0.9 * x)) > 0.5)
        fade = np.clip(x / 3, 0, 1) * np.clip((b - a - x) / 3, 0, 1)
        put(amb, a, cr * fade, 0.007, pan=-0.4)
        put(amb, a + 0.37, cr * fade, 0.005, pan=0.5)


def main():
    ev = json.load(open(os.path.join(HERE, 'events.json')))
    compose()
    blocks(ev)
    ambience()
    t = np.arange(N) / SR
    fade = np.clip(t / 1.0, 0, 1) * np.clip((DUR - t) / 2.5, 0, 1)
    mix = (A.reverb(music, 2.8, 0.45) * 0.9 + A.reverb(sfx, 1.2, 0.2, 5) + A.reverb(amb, 2.0, 0.3, 9)) * fade
    mix = np.tanh(mix / np.percentile(np.abs(mix), 99.95) * 1.1) * 0.93
    out = os.path.join(HERE, 'soundtrack.wav')
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
    print(out)


if __name__ == '__main__':
    main()
