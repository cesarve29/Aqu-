"""
Mix the ElevenLabs music + sound effects into the NEON RUSH soundtrack.

The ElevenLabs takes (one per cue) live in a folder as mp3:
  music, rain, led, spinup, hover, flyby, whoosh, boom, riser, slowmo, neon

    python3 mix_audio.py EL_AUDIO_DIR out.wav

The music (120 BPM, drop at 32.02 s) is re-edited on bar boundaries so its drop
lands on the chase cut (22.0 s), the full section is extended with a repeated
6-bar phrase, the bridge slow-motion gets a low-pass "underwater" breakdown and
the outro tail sits under the end title card.
"""
import os, subprocess, sys, wave
import numpy as np
from scipy import signal

SR = 48000
DUR = 65.5
N = int(SR * DUR)
F = lambda frame: frame / 24.0

T_LED, T_SPIN, T_TAKEOFF, T_LEAP = F(236), F(296), F(360), F(452)
T_DROP, T_TRACK, T_BRIDGE = F(528), F(672), F(816)
T_SLOW0, T_SLOW1 = F(838), F(946)
T_HEADON, T_PASS, T_ASCENT = F(960), F(1074), F(1128)
T_SIGN0, T_SIGN1, T_REVEAL, T_END = F(1262), F(1300), F(1344), F(1488)


def load(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float64) / 32768.0


def normalize(x, peak=1.0):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def db(g):
    return 10 ** (g / 20)


def lowpass(x, fc):
    sos = signal.butter(4, fc / (SR / 2), "low", output="sos")
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
        pl, pr = np.sqrt(0.5 * (1 - pan)) * np.sqrt(2), np.sqrt(0.5 * (1 + pan)) * np.sqrt(2)
        self.x[s:e, 0] += sig[: e - s, 0] * g * pl
        self.x[s:e, 1] += sig[: e - s, 1] * g * pr


def music_edit(m):
    """Bar-aligned re-edit: (music_start, music_end, video_start)."""
    drop, bar = 32.02, 2.0
    pieces = [
        (drop - 22.0, drop, 0.0),                       # build: drop lands at 22.0 s
        (drop, drop + 10 * bar, 22.0),                  # 10 bars full energy
        (drop + 4 * bar, drop + 10 * bar, 42.0),        # repeat 6 bars
        (drop + 10 * bar, drop + 14 * bar, 54.0),       # last 4 bars (climax)
        (drop + 14 * bar, len(m) / SR, 62.0),           # outro tail under the title card
    ]
    out = np.zeros((N, 2))
    xf = int(0.012 * SR)
    for i, (a, b, v) in enumerate(pieces):
        seg = m[int(a * SR): int(b * SR)].copy()
        if i > 0:
            seg[:xf] *= np.linspace(0, 1, xf)[:, None]
        if i < len(pieces) - 1:
            seg[-xf:] *= np.linspace(1, 0, xf)[:, None]
        s = int(v * SR)
        e = min(N, s + len(seg))
        out[s:e] += seg[: e - s]
    # slow-motion breakdown: muffle with a low-pass and duck, smooth in/out
    muff = lowpass(out, 320.0) * db(-3)
    t = np.arange(N) / SR
    w = np.clip((t - (T_SLOW0 - 0.15)) / 0.3, 0, 1) * np.clip(((T_SLOW1 + 0.05) - t) / 0.12, 0, 1)
    out = out * (1 - w)[:, None] + muff * w[:, None]
    # reveal: let the score close down toward the final hit
    closing = lowpass(out, 900.0)
    w2 = np.clip((t - T_REVEAL) / (T_END - T_REVEAL), 0, 1) ** 1.5 * (t < T_END)
    out = out * (1 - w2)[:, None] + closing * w2[:, None]
    out *= np.clip(t / 1.0, 0, 1)[:, None]
    return out


def loop_to(x, length):
    reps = int(np.ceil(length * SR / len(x)))
    return np.concatenate([x] * reps)[: int(length * SR)]


def main(src, out_path):
    a = {k: load(os.path.join(src, k + ".mp3")) for k in
         ("music", "rain", "led", "spinup", "hover", "flyby", "whoosh", "boom", "riser", "slowmo", "neon")}
    for k in a:
        if k != "music":
            a[k] = normalize(a[k])
    mus = Bus()
    mus.x = music_edit(normalize(a["music"], 0.9))

    sfx = Bus()
    t = np.arange(N) / SR
    # rain bed, louder in the quiet intro, ducked under the action
    rain = loop_to(a["rain"], DUR)
    renv = (db(-14) + (db(-8) - db(-14)) * np.clip((T_DROP - t) / 4.0, 0, 1)) * np.clip(t / 2.0, 0, 1)
    renv *= np.clip((DUR - t) / 2.5, 0, 1)
    sfx.x += rain * renv[:, None]
    # drone: LED boot, spin-up, flight hum bed
    sfx.add(a["led"], T_LED, -6, 0.15)
    sfx.add(fade(a["spinup"], 0.05, 0.4), T_SPIN, -9, 0.1)
    hover = loop_to(a["hover"], T_REVEAL + 2.0 - (T_SPIN + 3.6))
    hs = T_SPIN + 3.6
    th = hs + np.arange(len(hover)) / SR
    henv = np.full(len(th), db(-20))
    henv[(th >= T_TAKEOFF) & (th < T_DROP)] = db(-15)          # close to the drone
    henv *= np.clip((th - hs) / 0.6, 0, 1) * np.clip((T_REVEAL + 2.0 - th) / 2.0, 0, 1)
    henv = np.where((th > T_SLOW0) & (th < T_SLOW1), henv * db(-8), henv)
    sfx.add(hover * henv[:, None], hs)
    # take-off and the leap over the edge
    sfx.add(fade(a["whoosh"], 0.02, 0.3), T_LEAP - 0.6, -5, -0.3)
    sfx.add(a["riser"], T_DROP - len(a["riser"]) / SR, -9)
    sfx.add(a["boom"], T_DROP, -4)
    # chase: whooshes on cuts and passing signs
    for s, pan in ((T_DROP + 4.0, 0.6), (T_TRACK - 0.4, -0.5), (T_TRACK + 3.0, 0.5), (T_BRIDGE - 0.5, -0.4)):
        sfx.add(fade(a["whoosh"], 0.02, 0.3), s, -10, pan)
    # bridge slow-motion
    sfx.add(a["slowmo"], T_SLOW0 - 0.2, -4)
    sfx.add(fade(a["whoosh"], 0.02, 0.3), T_SLOW1 - 0.9, -6, 0.3)
    sfx.add(a["boom"], T_SLOW1, -10)
    # head-on pass-by and whip pan
    sfx.add(a["flyby"], T_PASS - 1.25, -3)
    # ascent: riser into the sign, neon power-on, impact
    sfx.add(a["riser"], T_SIGN1 - len(a["riser"]) / SR, -8)
    sfx.add(a["neon"], T_SIGN0, -6, -0.1)
    sfx.add(a["boom"], T_SIGN1, -3)
    # final hit on the title card
    sfx.add(a["boom"], T_END, -2)

    mix = mus.x * db(-1.5) + sfx.x
    mix *= np.clip((DUR - t) / 1.5, 0, 1)[:, None]
    # soft limiter
    peak = np.max(np.abs(mix))
    mix = np.tanh(mix / peak * 1.3) / np.tanh(1.3) * db(-1.0)
    data = (mix * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "soundtrack.wav")
