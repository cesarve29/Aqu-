"""Procedurally synthesises the promo soundtrack (no samples, no external services).
Needs numpy + scipy. Run from the project root:
    python3 audio/make_soundtrack.py   ->  public/soundtrack.wav
Timings mirror the Remotion timeline (30 fps)."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
FPS = 30
TOTAL = 904 / FPS
N = int(TOTAL * SR)
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N)

BEAT = 20 / FPS            # carousel step = one beat (90 BPM)
T_CAR, T_SHOW, T_PROC, T_OUT = 108 / FPS, 308 / FPS, 596 / FPS, 734 / FPS

def t_(d): return np.arange(int(d * SR)) / SR
def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, kind, fs=SR, output="sos"), x)
def add(x, at, gain=1.0, pan=0.0):
    i = int(max(at, 0) * SR)
    if i >= N: return
    x = x[: N - i] * gain
    L[i:i + len(x)] += x * (1 - max(pan, 0)); R[i:i + len(x)] += x * (1 + min(pan, 0))

def kick():
    t = t_(0.45); f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) + 0.3 * filt(rng.standard_normal(len(t)), "high", 3000) * np.exp(-t * 200)
def bass(freq, dur):
    t = t_(dur); f = freq * (1 + 0.6 * np.exp(-t * 40))
    x = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(f) / SR))
    return x * np.minimum(1, t * 200) * np.exp(-t * 1.6) * np.minimum(1, (dur - t) * 40)
def clap():
    t = t_(0.3); n = filt(rng.standard_normal(len(t)), "band", [900, 4500])
    env = sum(np.exp(-np.maximum(t - d, 0) * 38) * (t >= d) for d in (0, 0.011, 0.023))
    return n * env * 0.5
def hat(open_=False):
    t = t_(0.25 if open_ else 0.06)
    return filt(rng.standard_normal(len(t)), "high", 7500) * np.exp(-t * (14 if open_ else 80))
def bell(freq, dur=1.6):
    t = t_(dur)
    x = np.sin(2 * np.pi * freq * t + 2.5 * np.exp(-t * 6) * np.sin(2 * np.pi * freq * 3.01 * t))
    return x * np.exp(-t * 3.2) * np.minimum(1, t * 400)
def whoosh(dur=0.55, lo=400, hi=5000):
    t = t_(dur); n = rng.standard_normal(len(t)); out = np.zeros(len(t)); k = 12
    for j in range(k):                       # swept band-pass in chunks
        a, b = j * len(t) // k, (j + 1) * len(t) // k
        fc = lo * (hi / lo) ** np.sin(np.pi * (j + 0.5) / k)
        out[a:b] = filt(n, "band", [fc * 0.6, min(fc * 1.6, 18000)])[a:b]
    return out * np.sin(np.pi * t / dur) ** 2
def impact(dur=2.2):
    t = t_(dur); f = 38 + 70 * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    crash = filt(rng.standard_normal(len(t)), "band", [300, 9000]) * np.exp(-t * 3.5) * 0.35
    return np.tanh(1.6 * sub) + crash
def riser(dur):
    t = t_(dur); n = filt(rng.standard_normal(len(t)), "high", 1500)
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (2 * t / dur)) / SR)
    return (n * 0.5 + tone * 0.3) * (t / dur) ** 2.5
def pad(freqs, dur):
    t = t_(dur); x = np.zeros(len(t))
    for f in freqs:
        for det in (-0.4, 0, 0.5):
            ph = 2 * np.pi * (f + det) * t + rng.uniform(0, 6.28)
            x += sum(np.sin(k * ph) / k for k in range(1, 9))
    x = filt(x, "low", 650) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.2 * t))
    return x / np.max(np.abs(x))
def buzz(dur):                               # tattoo machine
    t = t_(dur); ph = 2 * np.pi * 118 * t + 0.3 * np.sin(2 * np.pi * 5 * t)
    x = np.sign(np.sin(ph)) * 0.6 + sum(np.sin(k * ph) / k for k in range(1, 14))
    x = filt(x, "band", [180, 3800]) * (0.8 + 0.2 * np.sin(2 * np.pi * 1.3 * t))
    gate = np.ones(len(t))
    for a, b in ((1.55, 1.85), (3.2, 3.45)):  # needle lifts off the skin
        gate[(t > a) & (t < b)] = 0.12
    gate = filt(gate, "low", 25)
    return x / np.max(np.abs(x)) * gate * np.minimum(1, t * 6) * np.minimum(1, (dur - t) * 4)

# ---- bed: dark D-minor pad for the whole piece
D2, F2, A2, C2, F3 = 73.42, 87.31, 110.0, 65.41, 174.61
p = pad([D2, A2, F3], TOTAL)
add(p * np.minimum(1, t_(TOTAL) * 0.8), 0, 0.10)

# ---- intro: riser into the logo landing, then letter ticks
add(riser(55 / FPS), 0, 0.5)
add(whoosh(1.2, 200, 3000), 0.5, 0.5)
add(impact(), 55 / FPS - 0.03, 0.85)
for i in range(10):
    add(hat(), (44 + i * 3) / FPS, 0.12, pan=(i - 4.5) / 9)
add(riser(1.0), T_CAR - 1.0, 0.35)

# ---- beat: 90 BPM half-time trap, bars aligned to the carousel steps
roots = [D2, D2, F2, C2]
mel = [293.66, 349.23, 440.0, 349.23, 293.66, 261.63, 220.0, 261.63]
nbeats = int((TOTAL - T_CAR) / BEAT)
for b in range(nbeats):
    t0 = T_CAR + b * BEAT
    bar, pos = divmod(b, 4)
    in_proc = T_PROC <= t0 < T_OUT - 0.01
    if t0 > TOTAL - 1.4: break
    g = 0.45 if in_proc else 1.0              # pull the drums back under the footage
    if pos == 0 or (pos == 2 and bar % 2 == 1):
        add(kick(), t0, 0.95 * g)
    if pos == 3 and bar % 2 == 0:
        add(kick(), t0 + BEAT / 2, 0.8 * g)
    if pos == 0: add(bass(roots[bar % 4], BEAT * 2.4), t0, 0.5 * g)
    if pos == 2 and not in_proc:
        add(clap(), t0, 0.8)
    for s in range(4):                        # 16th hats with occasional rolls
        if in_proc and s % 2: continue
        add(hat(), t0 + s * BEAT / 4, (0.16 if s % 2 == 0 else 0.09) * g, pan=0.25 if s % 2 else -0.15)
    if pos == 3 and bar % 2 == 1 and not in_proc:
        for s in range(6): add(hat(), t0 + BEAT / 2 + s * BEAT / 12, 0.07 + 0.02 * s, pan=0.3)
    if pos == 1 and bar % 2 == 0: add(hat(True), t0 + BEAT / 2, 0.10 * g, pan=-0.3)
    if not in_proc and pos % 2 == 0:          # bell motif + echo
        n = bell(mel[(b // 2) % 8])
        add(n, t0, 0.13, pan=-0.3); add(n, t0 + BEAT * 0.75, 0.05, pan=0.4)

# ---- movement sounds
for k in range(1, 10):                        # carousel whips
    add(whoosh(0.4, 500, 4500), T_CAR + k * BEAT - 0.05, 0.16, pan=0.5 if k % 2 else -0.5)
for k in range(6):                            # showcase card flips
    add(whoosh(0.6, 300, 6000), T_SHOW + k * 50 / FPS - 0.12, 0.30, pan=-0.4 if k % 2 else 0.4)
add(impact(1.6), T_SHOW, 0.45)

# ---- process scene: machine buzz over a thinned-out beat
add(whoosh(0.9, 200, 3000), T_PROC - 0.2, 0.35)
add(buzz(T_OUT - T_PROC - 0.5), T_PROC + 0.3, 0.16)
add(riser(1.4), T_OUT - 1.4, 0.45)

# ---- outro: hit on the logo, hit on the call to action, final tail
add(impact(), T_OUT + 0.1, 0.8)
add(impact(1.8), T_OUT + 40 / FPS, 0.6)
add(impact(3.0), TOTAL - 1.4, 0.9)
add(bell(146.83, 2.5), TOTAL - 1.4, 0.25)

# ---- master: light room echo, soft clip, fades
mix = np.stack([L, R], 1)
for d, g in ((0.11, 0.12), (0.23, 0.07)):
    k = int(d * SR); mix[k:] += mix[:-k][:, ::-1] * g
mix = filt(mix.T, "high", 30).T
mix = np.tanh(mix * 1.5) / np.tanh(1.5)
mix /= np.max(np.abs(mix)) / 0.94
n_out = int(0.9 * SR); mix[-n_out:] *= np.linspace(1, 0, n_out)[:, None] ** 1.5
mix[: int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))[:, None]
wavfile.write("public/soundtrack.wav", SR, (mix * 32767).astype(np.int16))
for name, a, b in (("intro", 0, T_CAR), ("carousel", T_CAR, T_SHOW), ("showcase", T_SHOW, T_PROC), ("process", T_PROC, T_OUT), ("outro", T_OUT, TOTAL)):
    seg = mix[int(a * SR):int(b * SR)]
    print(f"{name:9s} rms {20*np.log10(np.sqrt(np.mean(seg**2))):6.1f} dB  peak {20*np.log10(np.max(np.abs(seg))):5.1f} dB")
