"""
Analisis del audio para sincronizar el video con el piano.

Extrae (a la tasa de cuadros del video):
  - energia (RMS suavizado y normalizado)
  - onsets (flujo espectral) y pulsos de golpe
  - pulsos (beats) mediante seguimiento por programacion dinamica
  - activacion de cada tecla del piano (61 teclas, C2..C7) a partir del espectro
  - eventos de nota (tecla, tiempo, fuerza) para las particulas de luz
  - calendario de cambios de escena alineado con golpes fuertes
Requiere: numpy y ffmpeg.
"""
import subprocess

import numpy as np

SR = 22050
HOP = 512
AFPS = SR / HOP  # ~43 cuadros de analisis por segundo
LOW_MIDI, HIGH_MIDI = 36, 96  # C2..C7, las 61 teclas visibles


def load_mono(path):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-ac', '1', '-ar', str(SR),
                          '-f', 'f32le', '-'], check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def frames(x, n):
    pad = np.concatenate([np.zeros(n // 2, np.float32), x, np.zeros(n // 2, np.float32)])
    count = 1 + (len(pad) - n) // HOP
    return pad, count


def stft_features(x):
    """Flujo espectral (n=2048) y energia por tecla (n=8192, resolucion ~2.7 Hz)."""
    pad, count = frames(x, 2048)
    win = np.hanning(2048).astype(np.float32)
    flux = np.zeros(count, np.float32)
    rms = np.zeros(count, np.float32)
    prev = None
    for s in range(0, count, 2048):
        e = min(count, s + 2048)
        idx = np.arange(2048)[None, :] + HOP * np.arange(s, e)[:, None]
        seg = pad[idx]
        rms[s:e] = np.sqrt((seg ** 2).mean(1))
        L = np.log1p(30 * np.abs(np.fft.rfft(seg * win, axis=1)))
        cat = np.vstack([L[:1] if prev is None else prev[None], L])
        flux[s:e] = np.maximum(cat[1:] - cat[:-1], 0).sum(1)
        prev = L[-1]

    n = 8192
    pad, count2 = frames(x, n)
    count2 = min(count, count2)
    win = np.hanning(n).astype(np.float32)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    midis = np.arange(21, 109)
    bands = []
    for m in midis:
        f = 440 * 2 ** ((m - 69) / 12)
        lo, hi = f * 2 ** (-0.45 / 12), f * 2 ** (0.45 / 12)
        b = np.where((freqs >= lo) & (freqs <= hi))[0]
        if len(b) == 0:
            b = np.array([np.argmin(np.abs(freqs - f))])
        bands.append(b)
    keys = np.zeros((count, len(midis)), np.float32)
    for s in range(0, count2, 512):
        e = min(count2, s + 512)
        idx = np.arange(n)[None, :] + HOP * np.arange(s, e)[:, None]
        S = np.abs(np.fft.rfft(pad[idx] * win, axis=1))
        for j, b in enumerate(bands):
            keys[s:e, j] = S[:, b].max(1)
    return flux, rms, keys, midis


def smooth(v, w):
    if w <= 1:
        return v
    k = np.hanning(w * 2 + 1)
    k /= k.sum()
    return np.convolve(np.pad(v, w, mode='edge'), k, mode='valid')


def norm01(v, lo=2, hi=98):
    a, b = np.percentile(v, lo), np.percentile(v, hi)
    return np.clip((v - a) / (b - a + 1e-9), 0, 1)


def track_beats(onset, bpm_range=(70, 140)):
    """Seguimiento de pulsos estilo Ellis (2007): tempo global por autocorrelacion + PD."""
    o = onset - onset.mean()
    ac = np.correlate(o, o, 'full')[len(o) - 1:]
    lags = np.arange(len(ac))
    lo, hi = int(AFPS * 60 / bpm_range[1]), int(AFPS * 60 / bpm_range[0])
    # ponderar hacia ~100 BPM para evitar elegir el doble tempo
    w = np.exp(-0.5 * (np.log2(lags[lo:hi] / (AFPS * 60 / 100)) / 0.9) ** 2)
    period = lo + np.argmax(ac[lo:hi] * w)
    n = len(onset)
    score = onset.astype(np.float64).copy()
    back = np.full(n, -1)
    offs = np.arange(-2 * period, -period // 2 + 1)
    pen = -100 * np.log(-offs / period) ** 2 / 100.0
    for t in range(2 * period, n):
        cand = score[t + offs] + pen * 1.2
        k = np.argmax(cand)
        score[t] = onset[t] + cand[k]
        back[t] = t + offs[k]
    t = int(np.argmax(score[-period * 2:]) + n - period * 2)
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return np.array(beats[::-1]) / AFPS, 60 * AFPS / period


def note_events(keys, midis, onset_env, rms_n):
    """Eventos de nota: en cada pico de onset, las teclas cuya energia mas sube."""
    E = keys.copy()
    # supresion simple de armonicos: restar parte de la octava y la duodecima de abajo
    E[:, 12:] -= 0.55 * keys[:, :-12]
    E[:, 19:] -= 0.35 * keys[:, :-19]
    E = np.maximum(E, 0)
    L = np.log1p(E / (np.percentile(E, 99) + 1e-9) * 50)
    W = np.maximum(L - np.median(L, axis=1, keepdims=True), 0)  # blanqueo por cuadro
    n = len(L)
    o = onset_env
    peaks = np.where((o[1:-1] > o[:-2]) & (o[1:-1] >= o[2:]) & (o[1:-1] > 0.12))[0] + 1
    ev = []
    lastt = np.full(L.shape[1], -99.0)
    for t in peaks:
        if t < 3 or t > n - 4:
            continue
        rise = L[t + 2] - L[t - 2]
        score = rise * (W[t + 2] > 0)
        order = np.argsort(-score)
        top = score[order[0]]
        if top <= 0:
            continue
        nmax = 1 + int(o[t] > 0.35) + int(o[t] > 0.7)
        for k in order[:nmax]:
            if score[k] < top * 0.45 or t / AFPS - lastt[k] < 0.15:
                continue
            lastt[k] = t / AFPS
            m = midis[k]
            while m < LOW_MIDI:
                m += 12
            while m > HIGH_MIDI:
                m -= 12
            v = float(np.clip(0.35 + 0.65 * min(1.0, o[t]), 0, 1)) * (0.7 + 0.3 * rms_n[t])
            ev.append((t / AFPS, m - LOW_MIDI, v))
    ev.sort()
    return ev, W


def press_curves(events, nframes, fps):
    """Envolvente de pulsacion por tecla a la tasa del video: ataque rapido, liberacion suave."""
    K = HIGH_MIDI - LOW_MIDI + 1
    P = np.zeros((nframes, K), np.float32)
    for t0, k, v in events:
        f0 = int(t0 * fps)
        if f0 >= nframes:
            continue
        dur = int(fps * (0.35 + 0.6 * v))
        f1 = min(nframes, f0 + dur + int(fps * 0.6))
        tt = (np.arange(f0, f1) - f0) / fps
        env = np.where(tt < 0.03, tt / 0.03, np.where(tt < 0.35 + 0.6 * v, 1.0,
                       np.exp(-(tt - 0.35 - 0.6 * v) / 0.12)))
        P[f0:f1, k] = np.maximum(P[f0:f1, k], env * v)
    return P


def scene_schedule(t_beats, energy_f, onset_f, fps, dur, n_scenes):
    """Cambios de escena en pulsos fuertes: cada ~8 compases en calma, ~2-4 en el climax."""
    changes = [0.0]
    t = 0.0
    while True:
        e = energy_f[min(len(energy_f) - 1, int(t * fps))]
        gap = 19.0 - 13.0 * e
        target = t + gap
        if target > dur - 6:
            break
        win = t_beats[(t_beats > target - 2.5) & (t_beats < target + 2.5)]
        if len(win):
            strength = [onset_f[min(len(onset_f) - 1, int(b * fps))] for b in win]
            target = float(win[int(np.argmax(strength))])
        changes.append(target)
        t = target
    scenes = [i % n_scenes for i in range(len(changes))]
    return np.array(changes), np.array(scenes)


def analyze(path, fps, n_scenes):
    x = load_mono(path)
    dur = len(x) / SR
    flux, rms, keys, midis = stft_features(x)
    onset = flux - smooth(flux, 8)
    onset = np.maximum(onset, 0)
    onset /= np.percentile(onset, 99.5) + 1e-9
    rms_n = norm01(smooth(rms, 10))
    t_beats, bpm = track_beats(onset)
    events, _ = note_events(keys, midis, onset, rms_n)

    nf = int(dur * fps)
    tf = np.arange(nf) / fps
    ta = np.arange(len(rms)) / AFPS
    energy = np.interp(tf, ta, norm01(smooth(rms, 40)))
    energy_fast = np.interp(tf, ta, rms_n)
    # golpe: maximo del onset en la ventana de cada cuadro de video
    ai = np.clip((tf * AFPS).astype(int), 0, len(onset) - 1)
    onset_f = np.array([onset[max(0, i - 1):i + 2].max() for i in ai])
    hit = np.zeros(nf, np.float32)
    for i in range(nf):
        hit[i] = max(min(1.0, onset_f[i]), hit[i - 1] * 0.82 if i else 0)
    # fase de pulso: 1 en cada beat y decae
    beat_pulse = np.zeros(nf, np.float32)
    beat_idx = np.zeros(nf, np.int32)
    for j, b in enumerate(t_beats):
        f0 = int(b * fps)
        if f0 >= nf:
            break
        tt = np.arange(nf - f0) / fps
        seg = np.exp(-tt / 0.18)
        beat_pulse[f0:] = np.maximum(beat_pulse[f0:], seg)
        beat_idx[f0:] = j
    press = press_curves(events, nf, fps)
    changes, scenes = scene_schedule(t_beats, energy, onset_f, fps, dur, n_scenes)
    return dict(dur=dur, bpm=bpm, energy=energy.astype(np.float32), energy_fast=energy_fast.astype(np.float32),
                hit=hit, beat_pulse=beat_pulse, beat_idx=beat_idx, beats=t_beats,
                press=press, events=np.array(events, np.float32).reshape(-1, 3),
                changes=changes, scenes=scenes)


if __name__ == '__main__':
    import sys
    a = analyze(sys.argv[1], 24, 5)
    print('dur %.1f  bpm %.1f  beats %d  notas %d' % (a['dur'], a['bpm'], len(a['beats']), len(a['events'])))
    print('cambios:', np.round(a['changes'], 1))
    for s in range(0, int(a['dur']), 15):
        m = (a['events'][:, 0] >= s) & (a['events'][:, 0] < s + 15)
        print(s, 'notas', int(m.sum()), 'energia %.2f' % a['energy'][s * 24])
