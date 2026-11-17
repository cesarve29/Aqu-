"""Procedurally synthesised soundtrack (no samples): forest bed, footfall,
growls and the roar, all timed to the same envelopes that drive the animation."""
import sys, numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
DUR = 15.0
rng = np.random.default_rng(3)
t = np.arange(int(SR * DUR)) / SR

def env(points):
    p = np.array(points, float); return np.interp(t, p[:, 0], p[:, 1])
def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos"); return signal.sosfilt(sos, x)
def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="low", fs=SR, output="sos"), x)
def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="high", fs=SR, output="sos"), x)
def slow_noise(rate, seed):
    r = np.random.default_rng(seed); n = int(DUR * rate) + 3
    return np.interp(t, np.arange(n) / rate, r.normal(0, 1, n))

def voice(f0, amp, rough=0.5, seed=0):
    """glottal-ish pulse train with jitter, pushed through animal formants."""
    f = f0 * (1 + 0.035 * slow_noise(40, seed) + 0.02 * slow_noise(9, seed + 1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    src = np.zeros_like(t)
    for k in range(1, 26):                                   # bright sawtooth-like source
        src += np.sin(k * ph + 0.3 * k) / k ** 0.85
    sub = np.sin(ph * 0.5) * 0.9                             # sub-harmonic growl
    n = rng.normal(0, 1, len(t))
    fry = 0.5 + 0.5 * np.sign(np.sin(ph * 0.5)) * rough      # vocal-fry gating at half pitch
    x = (src * fry + sub) * amp + 0.55 * n * amp * (0.6 + 0.4 * np.sin(ph))
    out = 1.0 * bp(x, 90, 320) + 1.3 * bp(x, 380, 760) + 0.9 * bp(x, 900, 1500) + 0.45 * bp(x, 2000, 3400) + 0.6 * lp(x, 90)
    return out

roar_e = env([(0, 0), (4.5, 0), (4.72, 0.25), (4.95, 1.0), (6.0, 0.92), (7.6, 1.0), (8.8, 0.85), (9.5, 0.4), (10.2, 0.05), (10.5, 0), (15, 0)])
roar_f = env([(0, 80), (4.5, 62), (4.95, 118), (5.6, 104), (7.5, 96), (8.8, 84), (9.6, 62), (10.4, 44), (15, 44)])
roar = voice(roar_f, roar_e, 0.55, 1)
scream = bp(rng.normal(0, 1, len(t)), 520, 1900) * (0.6 + 0.4 * np.sin(2 * np.pi * 31 * t + 2 * np.sin(2 * np.pi * 3.1 * t)))
fs = roar_f * 4.03 * (1 + 0.02 * slow_noise(30, 5))
scream = scream * 0.8 + 0.6 * np.sign(np.sin(2 * np.pi * np.cumsum(fs) / SR)) * (0.5 + 0.5 * slow_noise(55, 6))
roar += 0.5 * bp(scream, 300, 2600) * roar_e ** 1.5
roar *= 1 + 0.18 * np.sin(2 * np.pi * 6.3 * t) * roar_e

bark_e = env([(0, 0), (12.8, 0), (13.02, 1.0), (13.45, 0.8), (13.95, 0.05), (14.1, 0), (15, 0)])
bark = voice(env([(0, 90), (12.8, 78), (13.05, 125), (13.5, 98), (14.0, 60), (15, 60)]), bark_e, 0.5, 11) * 0.85

growl_e = env([(0, 0.0), (0.3, 0.10), (1.2, 0.22), (2.1, 0.12), (3.2, 0.2), (4.2, 0.30), (4.6, 0.1), (10.2, 0), (10.8, 0.25), (11.6, 0.32), (12.6, 0.22), (12.9, 0.05), (14.0, 0.06), (14.4, 0.26), (15, 0.2)])
breath = 0.5 + 0.5 * np.sin(2 * np.pi * t / 2.6)
growl = lp(voice(env([(0, 34), (4.4, 40), (10.5, 36), (15, 31)]), growl_e * (0.55 + 0.45 * breath), 0.9, 21), 900) * 1.3

def thud(t0, amp):
    tt = np.clip(t - t0, 0, None); on = (t >= t0)
    f = 28 + 45 * np.exp(-tt / 0.05)
    body = np.sin(2 * np.pi * np.cumsum(f * on) / SR) * np.exp(-tt / 0.22)
    crunch = lp(rng.normal(0, 1, len(t)), 700) * np.exp(-tt / 0.07) + 0.4 * hp(rng.normal(0, 1, len(t)), 2500) * np.exp(-tt / 0.03)
    return amp * on * (body + 0.6 * crunch)
steps = thud(3.02, 1.0) + thud(13.1, 0.55)

# forest bed: wind in the leaves, insects, birds that fall silent when the animal turns
wind = bp(rng.normal(0, 1, len(t)), 250, 2600, 1) * (0.5 + 0.3 * slow_noise(0.7, 31)) * 0.035
wind += hp(rng.normal(0, 1, len(t)), 5200) * 0.010 * (0.6 + 0.4 * np.sin(2 * np.pi * 17 * t))
leaves = hp(rng.normal(0, 1, len(t)), 1800) * (roar_e ** 2 * 0.06 + bark_e * 0.03)       # foliage rattled by the roar
birds = np.zeros_like(t)
for t0 in (0.25, 0.62, 0.95, 1.5, 1.72, 11.9, 14.3):
    d = rng.uniform(0.07, 0.14); f1, f2 = rng.uniform(2600, 4300), rng.uniform(3000, 5200)
    m = (t >= t0) & (t < t0 + d); u = (t[m] - t0) / d
    birds[m] += np.sin(2 * np.pi * (f1 * u + (f2 - f1) * u * u / 2) * d + 3 * np.sin(40 * u)) * np.sin(np.pi * u) ** 2 * (0.05 if t0 < 3 else 0.02)

dry = np.tanh(2.6 * (roar * 0.55 + bark * 0.55)) * 0.9 + np.tanh(1.5 * growl) * 0.5 + steps * 0.9
def reverb(x, seed, decay=1.5, pre=0.03):
    r = np.random.default_rng(seed); n = int(SR * decay * 2)
    ir = r.normal(0, 1, n) * np.exp(-np.arange(n) / (SR * decay / 4.5)); ir = lp(ir, 3800); ir[: int(pre * SR)] = 0
    for dly, g in ((0.31, 0.5), (0.47, 0.32), (0.83, 0.2)):                  # echoes off the tree line
        i = int(dly * SR); ir[i:i + 200] += g * r.normal(0, 1, 200) * 6
    y = signal.fftconvolve(x, ir)[: len(x)]
    return y / (np.abs(ir).sum() ** 0.5 * 9)
L = dry + 0.55 * reverb(dry, 1) + wind + leaves + birds
R = dry + 0.55 * reverb(dry, 2) + np.roll(wind, 900) + np.roll(leaves, 400) + np.roll(birds, 30) * 0.7
st = np.stack([L, R], 1)
st = hp(st.T, 24).T
st /= np.abs(st).max() * 1.02
st = np.tanh(st * 1.6) / np.tanh(1.6)                                         # gentle limiter
fade = np.minimum(1, np.minimum(t / 0.15, (DUR - t) / 0.4))[:, None]
wavfile.write(sys.argv[1] if len(sys.argv) > 1 else "trex_roar.wav", SR, (st * fade * 0.97 * 32767).astype(np.int16))
print("audio ok", st.shape, "rms roar", float(np.sqrt((st[int(5 * SR):int(9 * SR)] ** 2).mean())), "rms bed", float(np.sqrt((st[int(1 * SR):int(2 * SR)] ** 2).mean())))
