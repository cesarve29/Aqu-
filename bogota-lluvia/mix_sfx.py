"""
Sound design for BOGOTÁ BAJO LA LLUVIA (no music): mixes the seven ElevenLabs sound-effect
takes (one take each) against the camera move; street sounds fade with the drone's altitude.

    python3 mix_sfx.py audio out.wav

Takes: rain, traffic, horns, wind, thunder, drips, flyby (mp3).
"""
import os, subprocess, sys, wave
import numpy as np
from scipy import signal

SR = 48000
DUR = 60.0                      # picture length; ends with a fade to black
N = int(SR * DUR)
F = lambda frame: frame / 24.0



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


# camera altitude above the street (m) at frame f, from the control points in build_bogota.py
ALT = [(0, 10), (276, 12), (326, 22), (380, 42), (450, 78), (525, 118), (590, 152), (640, 178), (690, 198),
       (735, 211), (780, 218), (1439, 230)]
T_CLIMB = F(300)       # starts rising along the tower
T_CREST = F(735)       # clears the top
T_REVEAL = F(800)
T_END = 60.0


def main(src, out_path):
    a = {k: load(os.path.join(src, k + ".mp3")) for k in
         ("rain", "traffic", "horns", "wind", "thunder", "drips", "flyby")}
    t = np.arange(N) / SR
    bus = Bus()
    alt = np.interp(t, [F(f) for f, _ in ALT], [z for _, z in ALT])
    street = np.clip(1.0 - (alt - 12.0) / 120.0, 0.0, 1.0)          # 1 at street level -> 0 up high
    high = 1.0 - street

    # --- rain: close & splashy in the street, wider and softer up high -------
    rain = loop_to(a["rain"], DUR, 2.0)
    rain_far = lowpass(rain, 3500)
    bus.x += rain * (db(-9) * (0.35 + 0.65 * street))[:, None] + rain_far * (db(-14) * high)[:, None]
    drips = reverb(loop_to(a["drips"], DUR, 1.5), 1.2, 0.25, 3)
    bus.x += drips * (db(-15) * street ** 2)[:, None]

    # --- traffic: present on Carrera 7, a distant city hum from the top ----------
    tr = loop_to(a["traffic"], DUR, 2.0)
    tr_far = reverb(lowpass(tr, 900), 2.5, 0.5, 4)
    bus.x += tr * (db(-10) * street ** 1.5)[:, None] + tr_far * (db(-17) * high)[:, None]
    hn = fade(a["horns"], 0.05, 1.0)
    bus.add(hn, 3.2, -12, -0.3)
    bus.add(lowpass(reverb(hn, 2.5, 0.5, 6), 1500), 41.0, -22, 0.4)

    # --- wind grows with altitude -------------------------------------------------
    wind = loop_to(a["wind"], DUR, 2.0)
    wenv = db(-30 + 21 * high) * (1 + 0.25 * np.exp(-((t - T_CREST) / 1.6) ** 2))
    bus.x += wind * wenv[:, None]

    # --- drone passes -------------------------------------------------------------
    wh, pk = loudest(a["flyby"], 3.0)
    wh = fade(wh, 0.05, 0.6)
    for tt, g, pan in ((1.0, -10, 0.2), (F(250), -9, -0.3), (T_CREST, -7, 0.0)):
        bus.add(reverb(wh, 1.2, 0.25, 5), tt - pk, g, pan)

    # --- thunder over the hills -----------------------------------------------------
    th = a["thunder"]
    bus.add(reverb(lowpass(th, 2500), 3.0, 0.35, 7), 19.5, -14, 0.5)
    bus.add(reverb(th, 3.5, 0.3, 8), T_REVEAL - 0.5, -6, 0.3)
    bus.add(reverb(lowpass(th, 1200), 4.0, 0.4, 9), 47.0, -12, 0.6)

    mix = bus.x
    mix *= np.clip(t / 1.0, 0, 1)[:, None] * np.clip((DUR - t) / 3.0, 0, 1)[:, None]
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
