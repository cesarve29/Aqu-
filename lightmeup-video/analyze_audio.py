"""Audio analysis for the Light Me Up video.

Decodes the song, then writes per-video-frame features (energy bands, a
32-band log spectrum, onsets and a beat grid) to audio_features.json so the
WebGL renderer can react to the music deterministically.
"""
import json
import subprocess
import sys

import numpy as np

FPS = 30
SR = 48000
NBANDS = 32


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def norm(x, pct=98):
    hi = np.percentile(x, pct) + 1e-9
    return np.clip(x / hi, 0, 1.5)


def smooth(x, a_up, a_down):
    y = np.zeros_like(x)
    v = 0.0
    for i, s in enumerate(x):
        a = a_up if s > v else a_down
        v = v + (s - v) * a
        y[i] = v
    return y


def main(path, out):
    y = decode(path)
    hop = SR // FPS
    win = 4096
    nframes = int(np.ceil(len(y) / hop))
    pad = np.concatenate([np.zeros(win // 2, np.float32), y, np.zeros(win, np.float32)])
    window = np.hanning(win).astype(np.float32)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    edges = np.geomspace(30, 16000, NBANDS + 1)
    band_idx = [(freqs >= edges[i]) & (freqs < edges[i + 1]) for i in range(NBANDS)]

    spec = np.zeros((nframes, NBANDS), np.float32)
    bass = np.zeros(nframes); mid = np.zeros(nframes); high = np.zeros(nframes); rms = np.zeros(nframes)
    flux = np.zeros(nframes)
    prev = None
    mb = (freqs >= 20) & (freqs < 150)
    mm = (freqs >= 150) & (freqs < 2000)
    mh = (freqs >= 2000) & (freqs < 12000)
    for i in range(nframes):
        seg = pad[i * hop: i * hop + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        mag = np.abs(np.fft.rfft(seg * window))
        rms[i] = np.sqrt(np.mean(seg ** 2))
        bass[i] = mag[mb].mean(); mid[i] = mag[mm].mean(); high[i] = mag[mh].mean()
        for b in range(NBANDS):
            spec[i, b] = mag[band_idx[b]].mean() if band_idx[b].any() else 0
        lm = np.log1p(mag)
        if prev is not None:
            flux[i] = np.maximum(lm - prev, 0).sum()
        prev = lm

    spec = np.log1p(spec * 10)
    spec = spec / (np.percentile(spec, 99, axis=0, keepdims=True) + 1e-9)
    spec = np.clip(spec, 0, 1.2)

    flux = flux - np.convolve(flux, np.ones(15) / 15, mode="same")
    flux = np.maximum(flux, 0)
    onset = norm(flux, 99)

    # Tempo via autocorrelation of onset envelope (60-180 BPM)
    oc = onset - onset.mean()
    ac = np.correlate(oc, oc, mode="full")[len(oc) - 1:]
    lags = np.arange(len(ac))
    lo, hi = int(FPS * 60 / 180), int(FPS * 60 / 60)
    best_lag = lo + int(np.argmax(ac[lo:hi]))
    # refine with sub-frame precision using longer lags (multiples)
    period = best_lag
    cands = np.linspace(best_lag - 1, best_lag + 1, 201)
    def score(p, phase):
        t = np.arange(phase, nframes, p)
        return onset[np.round(t).astype(int).clip(0, nframes - 1)].sum()
    best = (0, period, 0)
    for p in cands:
        for ph in np.linspace(0, p, 40, endpoint=False):
            s = score(p, ph)
            if s > best[0]:
                best = (s, p, ph)
    _, period, phase = best
    bpm = 60 * FPS / period
    beats = np.arange(phase, nframes, period) / FPS

    energy = smooth(norm(rms), 0.08, 0.02)
    out_d = {
        "fps": FPS,
        "duration": len(y) / SR,
        "nframes": nframes,
        "bpm": float(bpm),
        "beat_period": float(period / FPS),
        "beat_phase": float(phase / FPS),
        "beats": [round(float(b), 4) for b in beats],
        "rms": np.round(norm(rms), 3).tolist(),
        "energy": np.round(energy, 3).tolist(),
        "bass": np.round(smooth(norm(bass), 0.6, 0.15), 3).tolist(),
        "mid": np.round(smooth(norm(mid), 0.5, 0.15), 3).tolist(),
        "high": np.round(smooth(norm(high), 0.6, 0.2), 3).tolist(),
        "onset": np.round(onset, 3).tolist(),
        "spec": np.round(spec, 2).tolist(),
    }
    json.dump(out_d, open(out, "w"))
    print(f"frames={nframes} dur={len(y)/SR:.2f}s bpm={bpm:.2f} phase={phase/FPS:.3f}s")
    # coarse energy profile every 2 s for section planning
    step = FPS * 2
    for i in range(0, nframes, step):
        e = energy[i:i + step].mean(); b = out_d["bass"][i]
        print(f"{i/FPS:6.1f}s energy={e:.2f} bass={np.mean(out_d['bass'][i:i+step]):.2f} " + "#" * int(e * 40))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
