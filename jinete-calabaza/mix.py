#!/usr/bin/env python3
"""Mezcla final de "El Jinete de la Calabaza Llameante" (260 s, 44.1 kHz, estereo).

- Musica: 5 piezas generadas con ElevenLabs Music (una por acto), con fundidos cruzados.
- Voz en off: narracion de ElevenLabs (voz "Alejandro - Horror y Misterio", eleven_v4) generada
  en una sola toma y cortada en sus 12 frases (pausas + programacion dinamica por longitud).
  La linea del Rey va mas grave y con eco.
- Efectos: 30 clips de ElevenLabs Sound Effects colocados por escena; reverberacion de caverna
  en las escenas de la cueva.
- "Ducking": la musica baja cuando habla el narrador.  Salida: audio/mezcla.wav
"""
import os
import re
import subprocess
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUR = 260.0
N = int(SR * DUR)
rng = np.random.default_rng(7)


def decode(src, ch=2):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-ac', str(ch), '-ar', str(SR), '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(out, np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch) if ch > 1 else a


def db(x):
    return 10 ** (x / 20)


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-12)


def place(buf, t, sig, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig * gain


def fade(sig, a=0.02, r=0.3):
    sig = sig.copy()
    na, nr = min(len(sig), int(a * SR)), min(len(sig), int(r * SR))
    if na:
        sig[:na] *= np.linspace(0, 1, na)[:, None] if sig.ndim > 1 else np.linspace(0, 1, na)
    if nr:
        sig[-nr:] *= np.linspace(1, 0, nr)[:, None] if sig.ndim > 1 else np.linspace(1, 0, nr)
    return sig


def resample(sig, factor):
    """factor < 1 => mas lento y grave (camara lenta)."""
    idx = np.arange(0, len(sig) - 1, factor)
    return np.stack([np.interp(idx, np.arange(len(sig)), sig[:, c]) for c in range(sig.shape[1])], 1).astype(np.float32)


def reverb(x, seconds=2.6, damp=0.55, wet=0.45, seed=3):
    """Reverberacion de convolucion (ruido decreciente filtrado), estereo."""
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros((len(x) + n, 2), np.float32)
    for c in range(2):
        ir = r.standard_normal(n).astype(np.float32) * np.exp(-t * 6.9 / seconds)
        # mas apagado con el tiempo (filtro simple)
        k = int(SR * 0.0006 * (1 + damp * 4))
        ir = np.convolve(ir, np.ones(k) / k, mode='same')
        ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        L = len(x) + n
        nfft = 1 << (L - 1).bit_length()
        y = np.fft.irfft(np.fft.rfft(x[:, c], nfft) * np.fft.rfft(ir, nfft), nfft)[:L]
        out[:, c] = y * wet
    out[: len(x)] += x * (1 - wet * 0.5)
    return out


# ----------------------------------------------------------------------------
# MUSICA
# ----------------------------------------------------------------------------
music = np.zeros((N, 2), np.float32)
CUES = [('acto1', 0.0), ('acto2', 60.0), ('acto3', 110.0), ('acto4', 180.0), ('acto5', 229.0)]
XF = 1.6
for k, (name, t0) in enumerate(CUES):
    m = decode(os.path.join(HERE, 'music', name + '.mp3'))
    nxt = CUES[k + 1][1] if k + 1 < len(CUES) else DUR
    length = int((nxt - t0 + XF) * SR)
    m = m[:length]
    m = fade(m, a=0.05 if k == 0 else XF, r=XF if k + 1 < len(CUES) else 3.0)
    m *= db(-20) / rms(m)  # cada pieza ~ -20 dBFS RMS
    place(music, t0 - (XF if k else 0) * 0.5, m)
music[: int(2.5 * SR)] *= np.linspace(0.2, 1, int(2.5 * SR))[:, None]

# ----------------------------------------------------------------------------
# EFECTOS
# ----------------------------------------------------------------------------
sfx = np.zeros((N, 2), np.float32)
cave = np.zeros((N, 2), np.float32)
_cache = {}


def S(name):
    if name not in _cache:
        a = decode(os.path.join(HERE, 'sfx', name + '.mp3'))
        a /= np.max(np.abs(a)) + 1e-9
        _cache[name] = a * db(-6)
    return _cache[name]


def ev(t, name, g=0.0, speed=1.0, dur=None, cav=False, pan=0.0):
    a = S(name)
    if speed != 1.0:
        a = resample(a, speed)
    if dur:
        a = a[: int(dur * SR)]
    a = fade(a, 0.01, min(0.4, len(a) / SR * 0.3))
    a = a * np.array([[np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414]], np.float32)
    place(cave if cav else sfx, t, a, db(g))


def loop(t0, t1, name, g=0.0, cav=False, speed=1.0, fin=1.0, fout=1.0):
    a = S(name)
    if speed != 1.0:
        a = resample(a, speed)
    n = int((t1 - t0) * SR)
    reps = int(np.ceil(n / len(a))) + 1
    xf = int(0.5 * SR)
    seg = np.zeros((reps * len(a), 2), np.float32)
    pos = 0
    for _ in range(reps):
        b = fade(a, 0.5, 0.5)
        seg[pos:pos + len(b)] += b
        pos += len(b) - xf
    seg = seg[:n]
    seg = fade(seg, fin, fout)
    place(cave if cav else sfx, t0, seg, db(g))


# ambientes
loop(0, 21, 'fiesta', -13, fin=3)
loop(8, 31, 'crepitar', -14)
loop(36, 50, 'crepitar', -12)
loop(60, 92, 'crepitar', -18)
loop(58, 70, 'viento_bosque', -18)
loop(100, 110, 'viento_bosque', -12)
loop(110, 124, 'viento_bosque', -15)
loop(122, 230, 'fuego_almas', -15, fin=4, fout=3)
loop(130, 230, 'gotas_cueva', -14, cav=True, fin=3, fout=3)
loop(230.5, 260, 'pajaros_amanecer', -11, fin=3, fout=3)

# Acto I
ev(4.0, 'buho', -12)
ev(13.0, 'fiesta', -14)
ev(24.2, 'whoosh', -9)
loop(24.2, 28.6, 'cascos_lentos', -16)
ev(26.0, 'relincho', -16, speed=0.9)
ev(28.6, 'whoosh', -10)
ev(31.95, 'trueno', 0)
ev(33.0, 'tierra_grieta', -3)
ev(35.9, 'rugido_fuego', -1)
ev(37.6, 'calabaza_grieta', -12)
ev(40.4, 'tierra_grieta', -5)
ev(44.5, 'relincho', 0)
ev(45.1, 'trueno', -7)
loop(50, 60.5, 'galope', -4, speed=0.8, fin=0.3)
ev(52.2, 'gritos', -5)
ev(54.6, 'puertas', -4)
ev(57.2, 'puertas', -7)
# Acto II
loop(60, 65.4, 'cascos_lentos', -8, fout=1.5)
ev(76.4, 'cristal', -18, speed=0.7)
ev(83.4, 'brisa_despedida', -9)
ev(84.0, 'cristal', -12)
loop(94.2, 100.5, 'galope', -4, fin=0.6)
loop(100, 110.4, 'galope', -3)
ev(104.0, 'buho', -12)
ev(105.0, 'whoosh', -7)
# Acto III
loop(110, 120, 'cascos_lentos', -9)
ev(110.8, 'zombis', -3)
ev(113.6, 'zombis', -6)
ev(115.2, 'rugido_fuego', -5)
loop(120, 125.2, 'galope', -6)
ev(125.0, 'relincho', -2)
ev(144.0, 'whoosh', -12, cav=True)
ev(153.3, 'huesos', -2, cav=True)
ev(154.4, 'huesos', -6, cav=True)
ev(160.7, 'arcos', -3, cav=True)
ev(173.6, 'huesos', -7, cav=True)
ev(176.5, 'rey_rugido', -5, cav=True)
# Acto IV
ev(181.5, 'huesos', -3, cav=True)
ev(182.3, 'flechas', -2, cav=True)
ev(183.2, 'espada_enciende', -1, cav=True)
ev(184.4, 'whoosh', -3, cav=True)
ev(185.2, 'flechas', -6, cav=True, speed=0.8)
ev(186.3, 'espada_choque', -7, cav=True)
ev(187.8, 'espada_choque', -9, cav=True)
for t in (190.6, 192.6, 195.0, 197.4):
    ev(t, 'espada_choque', -3, cav=True)
ev(192.2, 'derrumbe', -7, cav=True)
ev(196.2, 'huesos', -8, cav=True)
ev(201.6, 'baculo_onda', 0, cav=True)
ev(202.6, 'calabaza_grieta', -2, cav=True)
ev(210.3, 'whoosh', -6, cav=True)
ev(212.0, 'cristal', -3, cav=True)
ev(214.5, 'whoosh', -5, cav=True)
ev(214.6, 'cristal', -6, cav=True)
ev(215.2, 'brisa_despedida', -9, cav=True)
ev(220.9, 'cristal', -4, cav=True)
ev(222.1, 'explosion_dorada', 0, cav=True)
ev(224.0, 'derrumbe', -2, cav=True)
ev(224.2, 'corona_rompe', -1, cav=True)
ev(226.2, 'derrumbe', -7, cav=True)
# Acto V
loop(236, 240, 'cascos_lentos', -15)
loop(240, 245.6, 'galope', -6, fout=1.2)
loop(243, 250, 'fiesta', -11, fin=1.5, fout=2)
ev(254.2, 'brisa_despedida', -3)
ev(256.4, 'cristal', -10)

sfx += reverb(cave, 3.2, 0.5, 0.55)[:N] * db(-6)

# ----------------------------------------------------------------------------
# VOZ EN OFF
# ----------------------------------------------------------------------------
LINES = open(os.path.join(HERE, 'voz', 'lineas.txt'), encoding='utf-8').read().strip().split('\n')
STARTS = [1.0, 30.4, 50.6, 70.4, 80.4, 100.4, 130.4, 170.4, 180.15, 210.4, 230.4, 250.3]
KING = 8


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


def align(S_):
    chars = np.array([len(re.sub(r'[^\wáéíóúñ]', '', l)) for l in LINES], float)
    k = sum(b - a for a, b in S_) / chars.sum()
    n, m = len(S_), len(LINES)
    D = np.full((n + 1, m + 1), np.inf)
    P = np.zeros((n + 1, m + 1), int)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            for p in range(j - 1, i):
                if not np.isfinite(D[p, j - 1]):
                    continue
                dur = S_[i - 1][1] - S_[p][0]
                gap = S_[p][0] - S_[p - 1][1] if p > 0 else 2.0
                c = D[p, j - 1] + ((dur - k * chars[j - 1]) / (k * chars[j - 1] + 1)) ** 2 - 0.8 * min(gap, 2)
                if c < D[i, j]:
                    D[i, j], P[i, j] = c, p
    out, i = [], n
    for j in range(m, 0, -1):
        p = P[i, j]
        out.append((S_[p][0], S_[i - 1][1]))
        i = p
    return out[::-1]


def monster(x):
    """Voz del Rey: mas grave (casi una cuarta), con un doble una octava abajo y eco de caverna."""
    idx = np.arange(0, len(x), 0.78)
    y = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    idx2 = np.arange(0, len(x), 0.5)
    sub = np.interp(idx2, np.arange(len(x)), x).astype(np.float32)[: len(y)]
    y = y + 0.35 * np.pad(sub, (0, len(y) - len(sub)))
    out = np.zeros(len(y) + int(1.8 * SR), np.float32)
    out[: len(y)] += y
    for d, g in ((0.21, 0.5), (0.44, 0.32), (0.7, 0.2), (1.0, 0.12), (1.35, 0.07)):
        o = int(d * SR)
        out[o:o + len(y)] += y * g
    return out


os.makedirs(os.path.join(HERE, "audio"), exist_ok=True)
take = decode(os.path.join(HERE, 'voz', 'narracion_take1.mp3'), ch=1)
groups = align(speech_segments(take))
voice = np.zeros(N, np.float32)
subs = []
for k, ((a, b), t0) in enumerate(zip(groups, STARTS)):
    seg = take[max(0, int((a - 0.12) * SR)): int((b + 0.35) * SR)].copy()
    seg[:400] *= np.linspace(0, 1, 400)
    seg[-2000:] *= np.linspace(1, 0, 2000)
    if k == KING:
        seg = monster(seg) * 1.1
    place(voice, t0, seg)
    d = (b - a) / (0.78 if k == KING else 1.0)
    subs.append((t0, t0 + d + 0.3))
    print(f'{t0:6.1f}s ({d:4.1f}s) {LINES[k][:60]}')
with open(os.path.join(HERE, 'audio', 'tiempos_voz.txt'), 'w') as f:
    for a, b in subs:
        f.write(f'{a:.2f} {b:.2f}\n')

act = np.abs(voice) > 0.01
voice *= db(-16) / np.sqrt(np.mean(voice[act] ** 2))
# voz del narrador con un poco de "sala"
v2 = reverb(np.stack([voice, voice], 1), 1.2, 0.7, 0.12, seed=9)[:N]

# ducking
blk = SR // 50
env = np.sqrt(np.mean(np.pad(voice, (0, -N % blk)).reshape(-1, blk) ** 2, 1))
on = (env > 0.008).astype(np.float32)
on = np.convolve(on, np.ones(25) / 25, mode='same')
duck = 1 - 0.55 * np.clip(on * 1.5, 0, 1)
duck = np.repeat(duck, blk)[:N, None]

mix = music * duck + sfx * (0.6 + 0.4 * duck) + v2
mix[-int(2.0 * SR):] *= np.linspace(1, 0, int(2.0 * SR))[:, None]
# limitador suave
peak = np.max(np.abs(mix))
print('pico antes del limitador', round(float(peak), 3))
# limitador con envolvente (ataque 5 ms, relajacion 250 ms), techo -1 dBFS
ceil = db(-1.0)
lvl = np.max(np.abs(mix), 1)
need = np.minimum(1.0, ceil / np.maximum(lvl, 1e-9))
blk = 220
g = need[: len(need) // blk * blk].reshape(-1, blk).min(1)
g = np.minimum(g, np.concatenate([g[1:], g[-1:]]))  # mirar un bloque adelante
rel = np.exp(-blk / (0.25 * SR))
for i in range(1, len(g)):
    g[i] = min(g[i], g[i - 1] * rel + (1 - rel))
g = np.repeat(g, blk)
g = np.concatenate([g, np.ones(len(mix) - len(g))])
mix = mix * g[:, None]
mix = np.clip(mix, -ceil, ceil)
print('RMS musica %.1f dB | voz %.1f dB | mezcla %.1f dB | pico %.2f' % (
    20 * np.log10(rms(music)), 20 * np.log10(np.sqrt(np.mean(voice[act] ** 2))), 20 * np.log10(rms(mix)), np.max(np.abs(mix))))
os.makedirs(os.path.join(HERE, 'audio'), exist_ok=True)
out = os.path.join(HERE, 'audio', 'mezcla.wav')
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
print('ok', out)
