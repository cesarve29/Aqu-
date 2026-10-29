#!/usr/bin/env python3
"""Voz en off (ElevenLabs, voz "Alejandro - Horror y Misterio") mezclada con la banda sonora.

Corta la narracion en sus 25 frases (pausas + duracion esperada por frase), coloca cada
frase en su escena, baja la musica mientras habla el narrador y deja la voz del Rey
mas grave y con eco.  Salida: audio/mezcla.wav
"""
import os
import re
import subprocess
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
TAKE = os.path.join(HERE, 'voz', 'narracion_take1.mp3')
LINES = open(os.path.join(HERE, 'voz', 'lineas.txt'), encoding='utf-8').read().strip().split('\n')
# segundo del video en que empieza cada frase (escenas de 10 s)
STARTS = [1.4, 10.8, 20.8, 30.6, 41.0, 50.6, 60.6, 70.8, 80.8, 90.8, 100.6, 110.8, 120.8,
          130.8, 140.8, 150.8, 160.8, 170.6, 180.3, 203.4, 214.8, 230.8, 240.6, 250.4, 258.5]
KING = 18  # "Que no salga vivo!"


def read_wav(p):
    w = wave.open(p)
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, w.getnchannels())


def decode(src):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768


def speech_segments(a, thr_db=-40, gap=0.7):
    blk = SR // 100
    e = np.sqrt(np.mean(a[: len(a) // blk * blk].reshape(-1, blk) ** 2, 1)) + 1e-9
    on = 20 * np.log10(e) > thr_db
    out, i, n = [], 0, len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = last = i
        while j < n and (j - last) < gap * 100:
            if on[j]:
                last = j
            j += 1
        out.append((i / 100, (last + 1) / 100))
        i = j
    return out


def align(S):
    """Agrupa segmentos consecutivos en len(LINES) frases (programacion dinamica)."""
    chars = np.array([len(re.sub(r'[^\wáéíóúñ]', '', l)) for l in LINES], float)
    k = sum(b - a for a, b in S) / chars.sum()
    n, m = len(S), len(LINES)
    D = np.full((n + 1, m + 1), np.inf)
    P = np.zeros((n + 1, m + 1), int)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            for p in range(j - 1, i):
                if not np.isfinite(D[p, j - 1]):
                    continue
                dur = S[i - 1][1] - S[p][0]
                gap = S[p][0] - S[p - 1][1] if p > 0 else 2.0
                c = D[p, j - 1] + ((dur - k * chars[j - 1]) / (k * chars[j - 1] + 1)) ** 2 - 0.8 * min(gap, 2)
                if c < D[i, j]:
                    D[i, j], P[i, j] = c, p
    out, i = [], n
    for j in range(m, 0, -1):
        p = P[i, j]
        out.append((S[p][0], S[i - 1][1]))
        i = p
    return out[::-1]


def monster(x):
    """Voz del Rey: un tono y medio mas grave + eco de caverna."""
    idx = np.arange(0, len(x), 0.82)
    y = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    out = np.zeros(len(y) + int(1.6 * SR), np.float32)
    out[: len(y)] += y
    for d, g in ((0.23, 0.45), (0.47, 0.28), (0.74, 0.16), (1.05, 0.09)):
        o = int(d * SR)
        out[o:o + len(y)] += y * g
    return out * 1.15


def main():
    take = decode(TAKE)
    groups = align(speech_segments(take))
    music = read_wav(os.path.join(HERE, 'audio', 'soundtrack.wav'))
    N = len(music)
    voice = np.zeros(N, np.float32)
    for k, ((a, b), t0) in enumerate(zip(groups, STARTS)):
        seg = take[max(0, int((a - 0.12) * SR)): int((b + 0.35) * SR)].copy()
        seg[:400] *= np.linspace(0, 1, 400)
        seg[-2000:] *= np.linspace(1, 0, 2000)
        if k == KING:
            seg = monster(seg)
        i = int(t0 * SR)
        j = min(N, i + len(seg))
        voice[i:j] += seg[: j - i]
        print(f'{t0:6.1f}s  ({b - a:4.1f}s)  {LINES[k][:60]}')
    # nivel de la voz (~ -16 dBFS RMS mientras habla)
    act = np.abs(voice) > 0.01
    rms = np.sqrt(np.mean(voice[act] ** 2))
    voice *= 10 ** (-16 / 20) / rms
    # "ducking": la musica baja ~7 dB cuando habla el narrador
    blk = SR // 50
    env = np.sqrt(np.mean(np.pad(voice, (0, -N % blk)).reshape(-1, blk) ** 2, 1))
    on = (env > 0.01).astype(np.float32)
    on = np.convolve(on, np.ones(25) / 25, mode='same')  # suaviza 0.5 s
    duck = 1 - 0.55 * np.clip(on * 1.5, 0, 1)
    duck = np.repeat(duck, blk)[:N]
    mix = music * duck[:, None] + voice[:, None] * np.array([[0.98, 0.98]])
    mix = np.tanh(mix * 1.05) * 0.95
    out = os.path.join(HERE, 'audio', 'mezcla.wav')
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print('ok', out)


if __name__ == '__main__':
    main()
