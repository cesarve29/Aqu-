"""
Sound design for JARDÍN LUMEN (no music): mixes the eight ElevenLabs sound-effect
takes (one take each) against the camera timeline.

    python3 mix_sfx.py audio out.wav

Takes: wind, ambience, flight, shimmer, drips, rustle, golem, stone (mp3).
"""
import os, subprocess, sys, wave
import numpy as np
from scipy import signal

SR = 48000
DUR = 63.5                      # 60 s picture + 3.5 s title card
N = int(SR * DUR)
F = lambda frame: frame / 24.0

T_GORGE_IN = F(150)             # camera drops below the cliff tops
T_ARCH, T_SLAB = F(287), F(400)  # passes under the rock arch / fallen slab
T_EXIT = F(474)                 # bursts out of the gorge
T_WAVE = 21.5                   # glow wave runs across the flowers
T_PEAK = F(620)                 # hanging over the field
T_DIVE = F(690)
T_SKIM0, T_SKIM1 = F(740), F(1100)
T_GOLEM = F(1150)               # slowing down in front of the golem
T_WAKE = F(1330)                # eyes start to glow
T_END = 60.0


def load(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float64) / 32768.0
    return x / (np.max(np.abs(x)) + 1e-9)


def db(g):
    return 10 ** (g / 20)


def env(t, pts):
    """piecewise-linear gain envelope in dB: [(time, dB), ...]"""
    ts, gs = zip(*pts)
    return db(np.interp(t, ts, gs))


def lowpass(x, fc):
    sos = signal.butter(4, fc / (SR / 2), "low", output="sos")
    return signal.sosfiltfilt(sos, x, axis=0)


def highpass(x, fc):
    sos = signal.butter(2, fc / (SR / 2), "high", output="sos")
    return signal.sosfiltfilt(sos, x, axis=0)


def fade(x, fin=0.0, fout=0.0):
    x = x.copy()
    if fin > 0:
        n = min(len(x), int(fin * SR))
        x[:n] *= np.linspace(0, 1, n)[:, None]
    if fout > 0:
        n = min(len(x), int(fout * SR))
        x[-n:] *= np.linspace(1, 0, n)[:, None]
    return x


def loop_to(x, length, xf=1.5):
    """seamless loop with crossfades (the takes were generated as loops)."""
    n = int(length * SR)
    k = int(xf * SR)
    out = np.zeros((n + len(x), 2))
    pos = 0
    first = True
    while pos < n:
        seg = x.copy()
        if not first:
            seg[:k] *= np.linspace(0, 1, k)[:, None]
        seg[-k:] *= np.linspace(1, 0, k)[:, None]
        out[pos:pos + len(seg)] += seg
        pos += len(seg) - k
        first = False
    return out[:n]


def reverb(x, rt=1.6, mix=0.25, seed=1):
    rng = np.random.default_rng(seed)
    n = int(rt * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9 * t / rt)[:, None]
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2, axis=0))
    wet = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - mix) + wet * mix * 2.0


class Bus:
    def __init__(self):
        self.x = np.zeros((N, 2))

    def add(self, sig, start, gain_db=0.0, pan=0.0):
        s = int(round(start * SR))
        if s < 0:
            sig, s = sig[-s:], 0
        e = min(N, s + len(sig))
        if e <= s:
            return
        g = db(gain_db)
        pl, pr = np.sqrt(1 - pan), np.sqrt(1 + pan)
        self.x[s:e, 0] += sig[: e - s, 0] * g * pl
        self.x[s:e, 1] += sig[: e - s, 1] * g * pr


def loudest(x, length):
    """slice of `length` s centred on the loudest moment of x."""
    e = np.convolve(np.abs(x).mean(axis=1), np.ones(int(0.2 * SR)) / (0.2 * SR), mode="same")
    c = int(np.argmax(e))
    n = int(length * SR)
    s = max(0, min(len(x) - n, c - n // 2))
    return x[s:s + n], (c - s) / SR


def main(src, out_path):
    a = {k: load(os.path.join(src, k + ".mp3")) for k in
         ("wind", "ambience", "flight", "shimmer", "drips", "rustle", "golem", "stone")}
    t = np.arange(N) / SR
    bus = Bus()

    # --- beds -------------------------------------------------------------
    wind = loop_to(a["wind"], DUR)
    wind = wind * env(t, [(0, -60), (1.2, -16), (T_GORGE_IN, -11), (T_EXIT - 1.0, -10), (T_EXIT + 1.5, -24),
                          (T_PEAK, -28), (T_GOLEM, -30), (T_END, -32), (DUR, -60)])[:, None]
    bus.x += wind
    drips = reverb(loop_to(a["drips"], DUR), 1.8, 0.35, 3)
    drips = drips * env(t, [(0, -60), (T_GORGE_IN - 2, -40), (T_GORGE_IN + 1, -19), (T_EXIT - 2, -20),
                            (T_EXIT + 1.0, -40), (T_GOLEM - 2, -40), (T_GOLEM + 3, -27), (T_END, -27), (DUR, -60)])[:, None]
    bus.x += drips
    amb = loop_to(a["ambience"], DUR)
    amb = amb * env(t, [(0, -60), (T_EXIT - 4, -36), (T_EXIT + 1.5, -15), (T_SKIM1, -14), (T_GOLEM, -17),
                        (T_END, -19), (DUR - 0.3, -40), (DUR, -80)])[:, None]
    bus.x += amb

    # --- flight air: speed-driven rush built from the FPV take ---------------
    speed_keys = [(0, 11.0), (60, 17.0), (110, 19.5), (420, 19.5), (470, 15.0), (540, 9.0), (590, 5.2), (640, 5.0),
                  (700, 11.0), (760, 12.5), (1060, 11.5), (1110, 8.5), (1180, 5.5), (1260, 3.2), (1340, 1.1), (1439, 0.35)]
    v = np.interp(t, [F(f) for f, _ in speed_keys], [s for _, s in speed_keys])
    rush = loop_to(a["flight"], DUR, 2.0)
    hp = highpass(rush, 250)
    vn = np.clip(v / 19.5, 0, 1)
    rush = (rush * (0.35 + 0.65 * vn[:, None]) + hp * (0.6 * vn[:, None])) * (db(-30) + (db(-10) - db(-30)) * vn ** 1.6)[:, None]
    rush *= np.clip(t / 1.5, 0, 1)[:, None] * np.clip((T_END - t) / 3.0, 0, 1)[:, None]
    bus.x += rush

    # --- whooshes on the close passes -------------------------------------
    whoosh, pk = loudest(a["flight"], 2.6)
    whoosh = fade(whoosh, 0.05, 0.5)
    for tt, g, pan in ((T_GORGE_IN - 0.3, -8, -0.3), (T_ARCH, -5, 0.0), (T_SLAB, -6, 0.2), (T_EXIT, -4, 0.0)):
        bus.add(reverb(whoosh, 1.4, 0.3, 5), tt - pk, g, pan)
    # wall brushes inside the gorge
    for k, tt in enumerate(np.arange(T_GORGE_IN + 1.2, T_EXIT - 1.0, 2.35)):
        bus.add(lowpass(whoosh, 2500), tt - pk, -16, 0.6 if k % 2 else -0.6)
    # flowers rushing under the camera while skimming the field
    rustle = fade(a["rustle"], 0.2, 1.0)
    for k, tt in enumerate((T_DIVE + 1.0, T_SKIM0 + 3.5, T_SKIM0 + 8.0, T_SKIM0 + 12.0)):
        bus.add(rustle, tt, -8 if k else -6, (-0.35, 0.35)[k % 2])
    bus.add(rustle, T_GOLEM + 0.5, -14, 0.0)

    # --- magic -------------------------------------------------------------
    sh = fade(a["shimmer"], 0.4, 1.5)
    bus.add(reverb(sh, 2.6, 0.4, 7), T_WAVE - 0.8, -5, 0.0)
    bus.add(reverb(lowpass(sh, 4000), 3.0, 0.5, 8), T_WAKE - 0.5, -9, 0.0)

    # --- the golem ---------------------------------------------------------
    gol = reverb(a["golem"], 2.2, 0.3, 9)
    bus.add(gol, T_GOLEM + 1.0, -6, 0.0)
    bus.add(gol, T_GOLEM + 1.0 + len(gol) / SR - 0.5, -5, 0.0)
    stone = reverb(fade(a["stone"], 0.05, 1.0), 2.5, 0.35, 11)
    bus.add(stone, T_WAKE + 0.4, -6, 0.0)
    # deep tail under the title card
    bus.add(lowpass(stone, 300), T_END - 0.2, -4, 0.0)

    mix = bus.x
    mix *= np.clip((DUR - t) / 1.2, 0, 1)[:, None]
    peak = np.max(np.abs(mix))
    mix = np.tanh(mix / peak * 1.4) / np.tanh(1.4) * db(-1.0)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "soundtrack.wav")
