#!/usr/bin/env python3
"""Mezcla final de ESTACION UMBRA: voz en off + efectos (ElevenLabs) sincronizados con las tomas.

Salida: build/mix.wav (48 kHz estereo, -14 LUFS).
Requiere numpy y ffmpeg.
"""
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "audio", "raw")
BUILD = os.path.join(HERE, "build")
SR = 48000
TOTAL = 166.5

# inicio de cada toma (s) -> mismo orden y duraciones que scenes.py
SHOT_START = {1: 0.0, 2: 10.0, 3: 20.0, 4: 31.0, 5: 44.0, 6: 53.0, 7: 65.0, 8: 74.0, 9: 76.5,
              10: 89.0, 11: 102.0, 12: 115.0, 13: 126.0, 14: 129.0, 15: 143.5, 16: 156.5}

# segmentos de la narracion (inicio, fin dentro de narration.mp3) -> momento en el video
NARRATION = [
    ((0.00, 7.04), 11.0),    # Dicen que en la Estacion Umbra...
    ((8.38, 14.57), 21.0),   # La noche del 31 de octubre...
    ((15.71, 21.50), 36.0),  # Era una voz pidiendo ayuda...
    ((22.76, 26.89), 46.0),  # La transmision tenia fecha...
    ((27.96, 35.17), 54.5),  # Afuera, en la nieve...
    ((36.26, 38.85), 65.5),  # Entonces escuche un golpe...
    ((39.77, 46.34), 79.0),  # Cuando volvi a mirar...
    ((47.36, 52.73), 90.0),  # Grabe la senal...
    ((53.73, 57.48), 103.0), # Eran tres palabras. Ya estoy adentro.
    ((58.52, 63.55), 116.0), # Senti su respiracion...
    ((64.59, 71.25), 131.0), # A la manana siguiente...
    ((72.30, 74.19), 145.0), # Pero yo no la envie.
]


def ff_load(path, start=None, end=None, af=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start}"]
    if end is not None:
        cmd += ["-to", f"{end}"]
    cmd += ["-i", path]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def fade(x, fin=0.01, fout=0.05):
    n = len(x)
    a = int(fin * SR)
    b = int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, min(a, n))[:, None]
    if b:
        x[-b:] *= np.linspace(1, 0, min(b, n))[:, None]
    return x


class Bus:
    def __init__(self):
        self.buf = np.zeros((int(TOTAL * SR) + SR, 2), dtype=np.float32)

    def add(self, x, at, gain_db=0.0, dur=None, fin=0.01, fout=0.05):
        if dur is not None:
            x = x[: int(dur * SR)]
        x = fade(x.copy(), fin, fout) * (10 ** (gain_db / 20))
        i = int(at * SR)
        j = min(len(self.buf), i + len(x))
        self.buf[i:j] += x[: j - i]

    def loop(self, x, a, b, gain_db=0.0, fin=1.0, fout=1.0):
        n = int((b - a) * SR)
        reps = int(np.ceil(n / len(x))) + 1
        y = np.tile(x, (reps, 1))[:n]
        self.add(y, a, gain_db, fin=fin, fout=fout)


def env_automation(points, n):
    """points: [(t, dB), ...] -> ganancia lineal por muestra."""
    t = np.arange(n) / SR
    ts = [p[0] for p in points]
    ds = [p[1] for p in points]
    return (10 ** (np.interp(t, ts, ds) / 20)).astype(np.float32)[:, None]


def main():
    os.makedirs(BUILD, exist_ok=True)
    narr = os.path.join(RAW, "narration.mp3")
    crea = os.path.join(RAW, "creature.mp3")
    R = lambda n: os.path.join(RAW, n)  # noqa: E731

    # --- voz: un semitono mas grave, calidez y una cola de sala pequena
    deep = ("asetrate=44100*0.944,aresample=44100,atempo=1.0593,"
            "highpass=f=55,equalizer=f=120:t=q:w=1:g=3,equalizer=f=3500:t=q:w=1.5:g=2,"
            "acompressor=threshold=0.1:ratio=3:attack=10:release=200,"
            "aecho=0.8:0.6:35|61:0.12|0.08")
    voice = Bus()
    for (a, b), at in NARRATION:
        voice.add(ff_load(narr, a, b + 0.25, deep), at, 0.0, fin=0.02, fout=0.25)

    # voz de la radio (misma voz del narrador, filtrada y distorsionada)
    radio_v = ("asetrate=44100*0.97,aresample=44100,atempo=1.031,highpass=f=350,lowpass=f=2800,"
               "acrusher=bits=8:mix=0.35,volume=1.6,aecho=0.6:0.4:18:0.3")
    voice.add(ff_load(crea, 0.0, 3.2, radio_v), 31.5, -2.0)
    # "Ya... estoy... adentro" demoniaco: -4 semitonos + capa invertida
    demon = "asetrate=44100*0.79,aresample=44100,atempo=1.26,aecho=0.8:0.7:60|120:0.35|0.2"
    c2 = ff_load(crea, 4.1, 7.3, demon)
    voice.add(c2, 108.6, 0.0, fin=0.05, fout=0.4)
    voice.add(c2[::-1].copy(), 108.2, -10.0, fin=0.3, fout=0.3)
    # "Ahora es tu turno" (susurro final)
    voice.add(ff_load(crea, 8.05, 10.2, "asetrate=44100*0.86,aresample=44100,atempo=1.163,aecho=0.8:0.6:45|90:0.3|0.15"),
              152.9, 1.0, fin=0.05, fout=0.5)

    # --- efectos puntuales
    fx = Bus()
    fx.add(ff_load(R("radio.mp3")), 25.8, -4.0, fout=1.5)
    fx.add(ff_load(R("radio.mp3"), af="highpass=f=400"), 31.0, -10.0, fout=2.0)
    fx.add(ff_load(R("printer.mp3")), 44.3, -6.0, fout=0.8)
    fx.add(ff_load(R("snowsteps.mp3")), 55.0, -3.0, fout=1.0)
    fx.add(ff_load(R("knock.mp3")), 68.9, 0.0)
    fx.add(ff_load(R("riser.mp3")), 69.4, -5.0, dur=74.25 - 69.4, fin=1.5, fout=0.02)
    fx.add(ff_load(R("js1.mp3")), 74.25, 2.0, fin=0.0, fout=0.4)
    fx.add(ff_load(R("js1.mp3"), af="lowpass=f=200,volume=2"), 74.25, 0.0, fin=0.0, fout=0.6)
    fx.add(ff_load(R("tape.mp3")), 95.6, -5.0, fout=1.0)
    fx.add(ff_load(R("breath.mp3")), 115.3, -3.0, fout=1.5)
    fx.add(ff_load(R("riser.mp3")), 120.6, -4.0, dur=126.95 - 120.6, fin=2.0, fout=0.02)
    fx.add(ff_load(R("js2.mp3")), 126.95, 3.0, fin=0.0, fout=0.6)
    fx.add(ff_load(R("js2.mp3"), af="lowpass=f=150,volume=2.5"), 126.95, 0.0, fin=0.0, fout=1.0)
    fx.add(ff_load(R("radio.mp3"), af="highpass=f=500,lowpass=f=3000"), 133.5, -12.0, fout=3.0)
    fx.add(ff_load(R("heartbeat.mp3")), 147.0, -6.0, fin=2.0, fout=2.0)
    fx.add(ff_load(R("js1.mp3"), af="lowpass=f=900"), 153.05, -8.0, fin=0.0, fout=0.6)
    fx.add(ff_load(R("heartbeat.mp3")), 158.0, -8.0, fin=1.0, fout=3.0)
    fx.add(ff_load(R("js2.mp3"), af="lowpass=f=120,volume=2"), 156.5, -2.0, fin=0.0, fout=2.5)

    # --- camas: viento (exterior abierto / interior apagado) y drone
    beds = Bus()
    wind = ff_load(R("wind.mp3"))
    wind_in = ff_load(R("wind.mp3"), af="lowpass=f=650")
    drone = ff_load(R("drone.mp3"))
    beds.loop(wind, 0.0, 10.6, -2.0, fin=1.5, fout=0.6)
    beds.loop(wind_in, 9.8, 53.2, -9.0, fin=0.5, fout=0.4)
    beds.loop(wind, 53.0, 65.2, -4.0, fin=0.3, fout=0.4)
    beds.loop(wind_in, 65.0, 143.6, -11.0, fin=0.4, fout=0.4)
    beds.loop(wind, 143.5, 166.5, -5.0, fin=0.4, fout=4.0)
    beds.loop(drone, 8.0, 166.5, -9.0, fin=4.0, fout=5.0)
    beds.add(ff_load(R("heartbeat.mp3")), 100.5, -9.0, fin=2.0, fout=2.0)
    # silencios antes de cada jumpscare (las camas desaparecen)
    n = len(beds.buf)
    auto = env_automation([(0, 0), (71.5, 0), (73.8, -30), (74.2, -30), (74.6, 0),
                           (123.0, 0), (126.0, -30), (127.0, -30), (128.6, -40), (129.4, 0)], n)
    beds.buf *= auto

    # ducking de camas bajo la voz
    v = np.abs(voice.buf).mean(1)
    k = int(0.25 * SR)
    cs = np.concatenate([[0.0], np.cumsum(v, dtype=np.float64)])
    idx = np.arange(len(v))
    lo = np.clip(idx - k // 2, 0, len(v))
    hi = np.clip(idx + k // 2, 0, len(v))
    venv = (cs[hi] - cs[lo]) / k
    duck = 1.0 - 0.6 * np.clip(venv / 0.04, 0, 1)
    beds.buf *= duck[:, None].astype(np.float32)

    mix = voice.buf * 1.0 + fx.buf * 0.9 + beds.buf * 0.85
    mix = mix[: int(TOTAL * SR)]
    peak = np.abs(mix).max()
    if peak > 0.98:
        mix *= 0.98 / peak
    tmp = os.path.join(BUILD, "mix_pre.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", tmp], input=mix.astype(np.float32).tobytes(), check=True)
    out = os.path.join(BUILD, "mix.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
                    "loudnorm=I=-14:TP=-1.0:LRA=18:linear=false", "-ar", str(SR), "-c:a", "pcm_s16le", out], check=True)
    print("mix ->", out)


if __name__ == "__main__":
    main()
