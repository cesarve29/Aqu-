"""Mixes the ElevenLabs sound effects in sfx/ into a 15 s stereo track timed to
the animation (same timings as animate.roar_env / bark_env / the footfalls).

    python3 mix_sfx.py out.wav
"""
import os, sys, subprocess, numpy as np
from scipy import signal
from scipy.io import wavfile

SR, DUR = 44100, 15.0
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(SR * DUR)

def load(name):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(HERE, "sfx", name), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)

def fade(x, fin=0.0, fout=0.0):
    x = x.copy(); n = len(x)
    if fin > 0: k = min(n, int(fin * SR)); x[:k] *= np.linspace(0, 1, k)[:, None]
    if fout > 0: k = min(n, int(fout * SR)); x[n - k:] *= np.linspace(1, 0, k)[:, None]
    return x

def place(bus, clip, t0, gain=1.0, src0=0.0, length=None):
    """put clip[src0 : src0+length] at time t0 (seconds) on the bus."""
    a = int(src0 * SR); b = len(clip) if length is None else min(len(clip), a + int(length * SR))
    c = clip[a:b] * gain; i = int(t0 * SR); j = min(N, i + len(c))
    bus[i:j] += c[: j - i]

def db(x): return 10 ** (x / 20)

roar, bark, growl, step, forest = (load(f) for f in ("roar.mp3", "bark.mp3", "growl.mp3", "step.mp3", "forest.mp3"))
mix = np.zeros((N, 2))

# forest bed: quiet, gently ducked under the roar; the clip fades out at its end, so hold its level
amb = np.zeros((N, 2)); place(amb, forest, 0.0)
t = np.arange(N) / SR
duck = 1 - 0.85 * np.clip((t - 4.4) / 0.3, 0, 1) * np.clip((10.6 - t) / 0.6, 0, 1)
mix += amb * db(-12) * duck[:, None]

# low growl + breathing before the roar and in the pause before the bark
place(mix, fade(growl, 0.4, 0.6), 0.2, db(-9), src0=0.0, length=4.25)
place(mix, fade(growl, 0.5, 0.4), 10.15, db(-11), src0=2.2, length=2.75)

# heavy footstep when the foot lands (3.02 s) and a lighter one on the second step (13.1 s)
place(mix, step, 2.98, db(-4))
place(mix, step, 13.06, db(-10))

# main roar: jaw snaps open 4.45-4.95 s, held to ~8.8 s, closes by 10.3 s
def monster(x):
    """make the roar huge and harsh: octave-down sub layer, a detuned double for width,
    upper-mid bite, parallel saturation and heavy compression."""
    x = x / np.abs(x).max()
    sos_lp = signal.butter(4, 180, "low", fs=SR, output="sos")
    sub = signal.resample_poly(x, 2, 1, axis=0)[: len(x)]          # one octave down (played at half speed)
    sub = signal.sosfilt(sos_lp, sub, axis=0)
    sub /= np.abs(sub).max() + 1e-9
    dbl = signal.resample_poly(x, 100, 97, axis=0)[: len(x)]       # ~0.5 semitone lower double
    dbl = np.pad(dbl, ((0, len(x) - len(dbl)), (0, 0)))[:, ::-1]   # swap sides -> wide
    body = x + 0.55 * dbl
    bite = signal.sosfilt(signal.butter(2, [900, 3200], "band", fs=SR, output="sos"), body, axis=0)
    y = body + 0.9 * bite + 0.85 * sub
    y /= np.abs(y).max()
    dist = np.tanh(4.0 * y) / np.tanh(4.0)                         # grit
    y = 0.55 * y + 0.65 * dist
    # compressor: flatten the envelope so the whole roar stays at full force
    env = np.sqrt(signal.sosfilt(signal.butter(1, 12, "low", fs=SR, output="sos"), (y ** 2).mean(1)).clip(1e-9))
    target = np.percentile(env, 92)
    gain = np.clip(target / env, 0.25, 4.0) ** 0.75
    y = y * gain[:, None]
    return y / np.abs(y).max()
place(mix, fade(monster(roar), 0.03, 0.45), 4.45, db(0))
# short bark-roar with the second jaw snap at 13.08 s
place(mix, fade(bark, 0.02, 0.15), 12.86, db(-11))

# a touch of forest reverb (sparse early reflections + diffuse tail) on everything but the bed
rng = np.random.default_rng(1)
n = int(SR * 1.6); ir = rng.normal(0, 1, (n, 2)) * np.exp(-np.arange(n) / (SR * 0.35))[:, None]
ir = signal.sosfilt(signal.butter(2, 3500, "low", fs=SR, output="sos"), ir, axis=0)
ir[: int(0.025 * SR)] = 0
for d, g in ((0.11, 0.5), (0.23, 0.35), (0.41, 0.22)):
    k = int(d * SR); ir[k:k + 64] += g * rng.normal(0, 1, (64, 2)) * 4
ir /= np.sqrt((ir ** 2).sum(0)) * 4.5
dry = mix - amb * db(-12) * duck[:, None]
wet = np.stack([signal.fftconvolve(dry[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * 0.45

# master: clean low end, gentle limiter, fades
out = signal.sosfilt(signal.butter(2, 25, "high", fs=SR, output="sos"), out, axis=0)
out /= np.abs(out).max() / 0.98
out = np.tanh(out * 2.2) / np.tanh(2.2)
f = np.minimum(1, np.minimum(t / 0.1, (DUR - t) / 0.35))[:, None]
out = out * f * 0.97
wavfile.write(sys.argv[1] if len(sys.argv) > 1 else "trex_roar.wav", SR, (out * 32767).astype(np.int16))
print("mixed", out.shape, "peak", float(np.abs(out).max()))
