#!/usr/bin/env python3
"""
EchoBot - ELECTRIC HEARTBEAT (video musical 3D, 1920x1080 a 60 fps)

Mundo 3D por raymarching en GLSL (OpenGL via moderngl; en servidores sin GPU corre en
llvmpipe bajo Xvfb) con acabado de render tipo Blender/Cycles: oclusion ambiental,
reflejos con Fresnel, sombras suaves, cromo y metal liquido, profundidad de campo con bokeh,
bloom, destellos anamorficos, aberracion de lente y grano de pelicula.

Guion visual (todo reacciona al bombo, los graves y la energia de la cancion):
  intro      monitor cardiaco (ECG) + descenso sobre la ciudad; artista y titulo
  verse      vuelo por la avenida de neon atravesando portales de cromo que se encienden
             con cada golpe; laseres que barren el cielo desde las azoteas
  prechorus  la camara acelera y sube entre los laseres
  chorus     tunel fractal de cromo que se repliega con cada golpe; cortes cada 4 golpes
  verse 2    la ciudad se apaga y se vuelve gris... hasta que una chispa la atraviesa
  prechorus2 el tunel fractal otra vez, acelerando ("voltage rising")
  chorus 2   el reactor: nucleo de metal liquido, anillos giroscopicos, laseres, arcos
             y cortes de camara cada 4 golpes con cambio de color
  outro      la camara se aleja del reactor; titulo, artista y el trazo del ECG

Las letras son tipografia cinetica 3D animada letra a letra, sincronizada con los tiempos
incrustados en el .m4a, y ademas se incluyen como pista de subtitulos (SRT/mov_text).
Sin ecualizador.

Uso:
    python3 make_video.py                     -> electric_heartbeat_1080p60.mp4 (< 100 MB)
    python3 make_video.py --stills 3 8 30 ...  -> PNGs en stills/ (segundos del video, intro incluida)
Requiere: numpy, Pillow, moderngl, ffmpeg (y xvfb-run si no hay pantalla/EGL).
"""
import math
import os
import random
import re
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 60
WORLD_W, WORLD_H = int(os.environ.get("EH_WORLD_W", 1920)), int(os.environ.get("EH_WORLD_H", 1080))
HERE = os.path.dirname(os.path.abspath(__file__))
SONG = os.path.join(HERE, "electric_heartbeat.m4a")
BUILD = os.path.join(HERE, "build")
AUDIO = os.path.join(BUILD, "audio_full.wav")
MASTER = os.path.join(BUILD, "master.mp4")
OUT = os.path.join(HERE, "electric_heartbeat_1080p60.mp4")
SRT_OUT = os.path.join(HERE, "electric_heartbeat.srt")
FONTS = os.path.join(HERE, "fonts")
SR = 22050

ARTIST = "ECHOBOT"
TITLE = "ELECTRIC HEARTBEAT"
INTRO = 6.0  # segundos de intro antes de que arranque la cancion
HB_PERIOD = 0.8  # latido sintetico de la intro (audio + trazo ECG)

KEYWORDS = {
    "neon", "burns", "night", "echoes", "pulse", "rising", "fire", "electric", "heartbeat",
    "shock", "current", "flow", "collide", "static", "alive", "shadows", "decay", "signals",
    "spark", "gray", "voltage", "surge", "ignite",
}


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t ** 3


def back_out(t, k=2.0):
    t = clamp(t) - 1
    return 1 + (k + 1) * t ** 3 + k * t ** 2


def bounce_out(t):
    t = clamp(t)
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(a, b, t):
    return tuple(lerp(x, y, t) for x, y in zip(a, b))


def ecg(x):
    """Trazo de electrocardiograma (mismo que en world.frag): picos P-QRS-T por periodo."""
    f = x - math.floor(x)
    return (0.12 * math.exp(-((f - 0.18) * 28) ** 2) - 0.18 * math.exp(-((f - 0.30) * 70) ** 2)
            + 1.0 * math.exp(-((f - 0.335) * 60) ** 2) - 0.32 * math.exp(-((f - 0.37) * 60) ** 2)
            + 0.22 * math.exp(-((f - 0.58) * 16) ** 2))


def t_path(z):
    """Eje de la arteria (mismo que tPath en world.frag)."""
    return (7.0 * math.sin(z * 0.021) + 3.0 * math.sin(z * 0.047), 2.5 * math.sin(z * 0.017))


# ----------------------------------------------------------------------------
# audio: intro (latido sintetico + extracto filtrado del estribillo) + cancion
# ----------------------------------------------------------------------------
def build_audio():
    os.makedirs(BUILD, exist_ok=True)
    fmt = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
    P = HB_PERIOD
    # "lub" en el pico QRS del trazo (fase 0.335) y "dub" 0.17 s despues
    ph = f"mod(t-{0.335 * P:.4f}+{P},{P})"
    beat = (f"0.9*sin(2*PI*52*t)*exp(-{ph}*22)+0.6*sin(2*PI*44*t)*exp(-({ph}-0.17)*26)*gte({ph},0.17)")
    fc = (
        f"aevalsrc='{beat}':s=44100:d={INTRO},lowpass=f=160,volume=0.9,"
        f"afade=t=out:st={INTRO - 0.4}:d=0.4,{fmt}[hb];"
        f"[0:a]atrim=29:{29 + INTRO},asetpts=PTS-STARTPTS,lowpass=f=380,lowpass=f=380,"
        f"volume=1.4,afade=t=in:st=1.5:d=3.0,afade=t=out:st={INTRO - 0.3}:d=0.3,{fmt}[m];"
        f"[hb][m]amix=inputs=2:normalize=0[intro];"
        f"[0:a]{fmt}[song];[intro][song]concat=n=2:v=0:a=1[out]"
    )
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SONG, "-filter_complex", fc,
                    "-map", "[out]", "-c:a", "pcm_s16le", AUDIO], check=True)


def clean(text):
    return text.replace("’", "'").replace("‘", "'")


def load_lyrics():
    srt = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", SONG, "-map", "0:s:0", "-f", "srt", "-"],
                         capture_output=True, text=True, check=True).stdout
    lines, section, count = [], "verse", {}
    for block in srt.strip().split("\n\n"):
        rows = block.strip().splitlines()
        if len(rows) < 3:
            continue
        a, b = re.findall(r"(\d+):(\d+):(\d+),(\d+)", rows[1])
        t0 = int(a[0]) * 3600 + int(a[1]) * 60 + int(a[2]) + int(a[3]) / 1000
        t1 = int(b[0]) * 3600 + int(b[1]) * 60 + int(b[2]) + int(b[3]) / 1000
        text = clean(" ".join(rows[2:]).strip())
        if text.startswith("["):
            name = text.strip("[]").lower()
            count[name] = count.get(name, 0) + 1
            section = name if count[name] == 1 or name.endswith("2") else f"{name} 2"
            continue
        lines.append({"t0": t0 + INTRO, "t1": t1 + INTRO, "text": text, "section": section})
    return lines


def write_srt(lines):
    def ts(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    rows = [(0.7, INTRO - 0.3, f"{ARTIST.title()} - Electric Heartbeat")]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["t0"] if i + 1 < len(lines) else ln["t1"] + 3
        rows.append((ln["t0"], min(max(ln["t1"], ln["t0"] + 1.2), nxt), ln["text"]))
    with open(SRT_OUT, "w", encoding="utf-8") as f:
        for k, (a, b, t) in enumerate(rows, 1):
            f.write(f"{k}\n{ts(a)} --> {ts(b)}\n{t}\n\n")


def analyze_audio(dur):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", AUDIO, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    n = int(dur * FPS) + 2
    win = 2048
    pad = np.concatenate([np.zeros(win), a, np.zeros(win)])
    hann = np.hanning(win)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    lo = (freqs > 30) & (freqs < 150)
    bass, rms = np.zeros(n), np.zeros(n)
    for i in range(n):
        c = int(i / FPS * SR) + win
        seg = pad[c - win // 2:c + win // 2]
        if len(seg) < win:
            continue
        bass[i] = np.abs(np.fft.rfft(seg * hann))[lo].sum()
        rms[i] = math.sqrt(float(np.mean(seg ** 2)))
    bass = np.clip(bass / (np.percentile(bass, 97) + 1e-9), 0, 1.3)
    rms = np.clip(rms / (np.percentile(rms, 97) + 1e-9), 0, 1.3)
    # flujo espectral medido sobre 2 fotogramas (equivale al de 30 fps)
    flux = np.maximum(0, bass - np.concatenate([bass[:2], bass[:-2]]))
    flux = np.clip(flux / (np.percentile(flux, 98) + 1e-9), 0, 1.5)
    kicks, last = [], -1.0
    for i in range(n):
        t = i / FPS
        if flux[i] > 0.4 and t - last > 0.2 and t > INTRO - 0.05:
            kicks.append(t)
            last = t
    kick = np.zeros(n)
    for i in range(n):
        kick[i] = max(flux[i] if flux[i] > 0.25 else 0, (kick[i - 1] if i else 0) * 0.905)
    return {"bass": np.convolve(bass, np.ones(9) / 9, mode="same"), "kick": np.clip(kick, 0, 1.2),
            "energy": np.convolve(rms, np.ones(90) / 90, mode="same"), "kicks": np.array(kicks)}


# ----------------------------------------------------------------------------
# guion: secciones, escenas, paletas, camara
# ----------------------------------------------------------------------------
# neon 1, neon 2, niebla (lineal, para el shader)
PALETTES = {
    "intro":       ((1.0, 0.08, 0.32), (0.0, 0.8, 1.0), (0.035, 0.01, 0.05)),
    "verse":       ((1.0, 0.08, 0.32), (0.0, 0.8, 1.0), (0.045, 0.012, 0.07)),
    "prechorus":   ((1.0, 0.15, 0.55), (1.0, 0.55, 0.1), (0.07, 0.015, 0.05)),
    "chorus":      ((1.0, 0.06, 0.25), (0.15, 0.9, 1.0), (0.09, 0.008, 0.04)),
    "verse 2":     ((0.9, 0.2, 0.35), (0.45, 0.55, 0.7), (0.035, 0.035, 0.042)),
    "prechorus 2": ((1.0, 0.3, 0.05), (1.0, 0.05, 0.45), (0.08, 0.02, 0.02)),
    "chorus 2":    ((1.0, 0.05, 0.3), (0.55, 0.3, 1.0), (0.03, 0.008, 0.06)),
    "outro":       ((1.0, 0.1, 0.4), (0.0, 0.8, 1.0), (0.025, 0.01, 0.05)),
}
SCENE = {"intro": 0, "verse": 0, "prechorus": 0, "chorus": 1, "verse 2": 0,
         "prechorus 2": 1, "chorus 2": 2, "outro": 2}
CORE = (0.0, 26.0, 0.0, 13.0)


def build_sections(lines, dur):
    secs = [("intro", 0.0)]
    for ln in lines:
        if secs[-1][0] != ln["section"]:
            secs.append((ln["section"], ln["t0"] if len(secs) > 1 else INTRO))
    secs.append(("outro", lines[-1]["t1"] + 0.8))
    out = []
    for i, (name, st) in enumerate(secs):
        en = secs[i + 1][1] if i + 1 < len(secs) else dur
        out.append((name, st, en))
    return out


def section_at(T, secs):
    for k, (name, st, en) in enumerate(secs):
        if T < en or k == len(secs) - 1:
            return k, name, st, en
    return len(secs) - 1, *secs[-1]


def city_pose(name, T, st, en):
    """(x, y, yaw, pitch, roll, fov, speed)"""
    u = T - st
    p = clamp(u / max(en - st, 1e-3))
    if name == "intro":
        k = smooth((T - 2.4) / (INTRO - 2.4))
        return (0.0, lerp(190, 7, k ** 0.8), 0.0, lerp(-1.2, 0.08, smooth((T - 2.4) / (INTRO - 2.6))), 0.0, 1.15, 26)
    if name == "verse":
        return (3 * math.sin(u * 0.21), 7 + 2.0 * math.sin(u * 0.35), 0.12 * math.sin(u * 0.17),
                0.08 + 0.04 * math.sin(u * 0.3), -0.06 * math.cos(u * 0.21), 1.15, 30)
    if name == "prechorus":
        return (2 * math.sin(u * 0.4), 7 + 45 * p ** 1.6, 0.1 * math.sin(u * 0.5),
                0.08 + 0.2 * math.sin(math.pi * min(p * 1.1, 1)), 0.12 * math.sin(u * 0.9), lerp(1.15, 0.9, p),
                lerp(30, 70, p))
    # verse 2: calle baja, lenta, ciudad muriendo
    return (2.2 * math.sin(u * 0.27), 5.0 + 0.8 * math.sin(u * 0.5), 0.15 * math.sin(u * 0.19),
            0.08, 0.05 * math.sin(u * 0.3), 1.12, 18)


def fold_for(ki):
    """Pliegue del fractal: un valor nuevo en cada golpe."""
    return 0.25 + 0.3 * math.sin(ki * 1.71) + 0.12 * math.sin(ki * 0.37)


def build_frames(secs, audio, nframes, lines):
    """Precalcula camara + uniforms del mundo por fotograma."""
    kicks = audio["kicks"]
    sec_d = {n: (a, b) for n, a, b in secs}
    spark_t = next((l["t0"] for l in lines if l["text"].lower().startswith("but your spark")), sec_d["verse 2"][0] + 6)
    frames = []
    travel = 0.0      # avance de la camara en la ciudad
    tz = 0.0          # avance en el tunel
    rings = [0.0, 1.0, 2.0]
    for i in range(nframes):
        T = i / FPS
        k, name, st, en = section_at(T, secs)
        u = T - st
        p = clamp(u / max(en - st, 1e-3))
        scene = SCENE[name]
        j = min(i, len(audio["bass"]) - 1)
        bass, kick = float(audio["bass"][j]), float(audio["kick"][j])
        energy = float(audio["energy"][j])
        ki = int(np.searchsorted(kicks, T, side="right") - 1)
        kt = kicks[ki] if ki >= 0 else -99
        age = T - kt
        beat = math.exp(-age * 6.0)
        if name == "intro":
            ph = ((T - 0.335 * HB_PERIOD) % HB_PERIOD)
            beat = math.exp(-ph * 7.0) + (0.55 * math.exp(-(ph - 0.17) * 9.0) if ph > 0.17 else 0.0)
        beat = clamp(beat, 0, 1.2)
        # golpes dentro de la seccion -> planos (un corte cada 4 golpes)
        k0 = int(np.searchsorted(kicks, st, side="left"))
        nk = max(0, ki - k0 + 1)
        shot = nk // 4
        shot_t = kicks[k0 + shot * 4 - 1] if shot > 0 else st
        decay, spark, spark_pos = 0.0, 0.0, (0.0, 0.0, 0.0)
        arcs, lasers = 0.0, 0.0
        flash = 0.0
        cutflash = 0.0
        tint = (1.0, 1.0, 1.0)
        if name == "intro":
            wf = 0.03 + 0.97 * smooth((T - 1.9) / 2.2)
            tint = (wf, wf, wf)
        focus, aperture = 60.0, 1.0
        roll = 0.0
        # anillos del reactor: giran mas rapido con la energia y dan un tiron en cada golpe
        for r in range(3):
            rings[r] += (0.25 + 0.9 * energy + 2.5 * kick) * (1.0 + 0.35 * r) * (1 if r != 1 else -1) / FPS
        fold = lerp(fold_for(ki - 1), fold_for(ki), smooth(age / 0.16))
        if scene == 0:
            pose = city_pose(name, T, st, en)
            if name == "verse" and u < 1.0:
                pose = tuple(lerp(a, b, smooth(u)) for a, b in zip(city_pose("intro", T, secs[0][1], secs[0][2]), pose))
            x, y, yaw, pitch, roll, fov, spd = pose
            travel += spd * (0.85 + 0.35 * bass + 0.5 * kick) / FPS
            fwd = (math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch))
            pos = (x, y, travel)
            tgt = (x + fwd[0], y + fwd[1], travel + fwd[2])
            lasers = {"intro": 0.5 * smooth((T - 3.0) / 2.0), "verse": 0.55 + 0.6 * kick,
                      "prechorus": 0.8 + 1.0 * kick, "verse 2": 0.0}[name]
            if name == "verse 2":
                ts = spark_t
                decay = 0.9 * smooth(u / 4.0) * (1 - smooth((T - ts - 0.9) / 1.6))
                beat *= 1 - 0.75 * decay
                lasers = (0.8 + 1.0 * kick) * smooth((T - ts - 0.8) / 0.8)
                if ts - 0.6 < T < ts + 2.2:
                    a = (T - (ts - 0.6)) / 2.8
                    spark = smooth(a / 0.1) * (1 - smooth((a - 0.85) / 0.15))
                    spark_pos = (x + 6 * math.sin(a * 5), y + 1.5 + 2 * math.sin(a * 3), travel + lerp(140, -10, a))
                    flash = 0.35 * math.exp(-max(0.0, T - ts - 0.9) * 4) if T > ts + 0.9 else 0.0
                tint = lerp3((0.82, 0.86, 0.95), (1.0, 1.0, 1.0), 1 - decay)
            focus = 40.0
            aperture = 0.6 if name == "intro" else 0.9
        elif scene == 1:
            accel = name == "prechorus 2"
            spd = (lerp(22, 60, p ** 1.5) if accel else 38) * (0.85 + 0.35 * bass + 0.6 * kick)
            tz += spd / FPS
            cx, cy = t_path(tz)
            ax, ay = t_path(tz + 9)
            # en el estribillo cada plano cambia de giro y posicion dentro del tunel
            rng = random.Random(shot * 31 + k * 7)
            ph = rng.uniform(0, 6.28) if not accel else 0.0
            orb = 0.9 + 0.4 * math.sin(u * 0.7)
            ox, oy = orb * math.cos(u * 0.45 + ph), orb * math.sin(u * 0.45 + ph) * 0.6
            pos = (cx + ox, cy + oy, tz)
            tgt = (ax + ox * 0.3, ay + oy * 0.3, tz + 9)
            roll = (rng.uniform(-0.9, 0.9) if not accel else 0.0) + 0.25 * math.sin(u * 0.33)
            roll += 0.8 * p ** 2 * math.sin(u * 1.4) if accel else 0.0
            fov = (0.95 - 0.25 * p) if accel else 0.9
            fov -= 0.1 * kick
            if not accel and shot > 0:
                cutflash = 0.3 * math.exp(-(T - shot_t) * 10)
            focus, aperture = 12.0, 0.7
        else:
            hx, hy, hz, hs = CORE
            lasers = 0.6 + 1.2 * kick
            arcs = 0.3 + 1.0 * kick
            if name == "chorus 2":
                # cortes de camara cada 4 golpes: angulo, distancia y altura nuevas
                rng = random.Random(shot * 97 + 13)
                ang = rng.uniform(0, 6.28) + (T - shot_t) * rng.choice((-0.25, 0.25))
                rad = rng.uniform(34, 62) - (T - shot_t) * 2.0
                cyy = rng.choice((4.0, 14.0, 30.0, 48.0)) + 2 * math.sin(u)
                fov = rng.uniform(0.9, 1.25) - 0.08 * kick
                roll = rng.uniform(-0.25, 0.25)
                if shot > 0:
                    cutflash = 0.35 * math.exp(-(T - shot_t) * 10)
            else:
                ang = 0.8 + u * 0.07
                rad = lerp(45, 64, smooth(p * 1.1))
                cyy = lerp(20, 105, smooth(p * 1.15))
                fov = 1.15
                roll = 0.05 * math.sin(u * 0.2)
                lasers *= 1 - smooth(p * 1.2)
                arcs *= 1 - smooth(p * 1.4)
            pos = (hx + rad * math.cos(ang), cyy, hz + rad * math.sin(ang))
            tgt = (hx, hy, hz)
            focus = math.dist(pos, (hx, hy, hz)) - hs * 0.5
            aperture = 2.0
        # paleta con fundido corto entre secciones; en los estribillos los colores se intercambian en cada corte
        pal = PALETTES[name]
        if name in ("chorus", "chorus 2") and shot % 2 == 1:
            pal = (pal[1], pal[0], pal[2])
        if k > 0 and u < 0.6:
            pal = tuple(lerp3(a, b, smooth(u / 0.6)) for a, b in zip(PALETTES[secs[k - 1][0]], pal))
        chorus = name in ("chorus", "chorus 2")
        cut = u
        frames.append({
            "T": T, "section": name, "k": k, "scene": scene,
            "pos": pos, "tgt": tgt, "roll": roll, "fov": fov,
            "bass": bass, "kick": kick, "beat": beat, "pal": pal, "flash": flash,
            "pulseR": age * (95.0 if scene == 0 else (70.0 if scene == 1 else 60.0)),
            "pulseA": math.exp(-age * 2.0) * (1.0 if (chorus or name in ("prechorus", "prechorus 2", "outro")) else 0.45),
            "kt": kt, "decay": decay, "spark": spark, "spark_pos": spark_pos,
            "arcs": arcs, "lasers": lasers, "fold": fold, "rings": tuple(rings), "core": CORE,
            "seed": float(ki % 97), "tint": tint, "focus": focus, "aperture": aperture,
            "win": smooth((T - 2.6) / 3.0) if name == "intro" else 1.0,
            "flash_scr": (0.55 * math.exp(-cut * 8) if k > 1 else 0.0) + (0.05 * kick if chorus else 0.0) + 0.3 * flash + cutflash,
            "glitch": max(clamp(1 - cut / 0.25) if k > 1 else 0.0,
                          clamp(1 - (T - shot_t) / 0.12) if chorus and shot > 0 else 0.0),
            "chroma": (1.3 * kick if chorus else 0.5 * kick),
        })
    # el centro de cada onda expansiva queda fijo donde estaba la camara al sonar el bombo
    zmap = {round(f["T"] * FPS): f["pos"][2] for f in frames}
    for f in frames:
        z0 = zmap.get(round(f["kt"] * FPS), f["pos"][2])
        f["pulseC"] = (0.0, 0.0, z0 + (70.0 if f["scene"] == 0 else 0.0))
    return frames


# ----------------------------------------------------------------------------
# tipografia cinetica
# ----------------------------------------------------------------------------
FONT_FILES = {
    "anton": "Anton-Regular.ttf",
    "bungee": "Bungee-Regular.ttf",
    "monoton": "Monoton-Regular.ttf",
    "orbitron": "Orbitron[wght].ttf",
}


@lru_cache(maxsize=64)
def font(key, size):
    f = ImageFont.truetype(os.path.join(FONTS, FONT_FILES[key]), size)
    if key == "orbitron":
        try:
            f.set_variation_by_name("Black")
        except Exception:
            pass
    return f


@lru_cache(maxsize=256)
def cap(key, size):
    return -font(key, size).getbbox("H", anchor="ls")[1]


def to255(c, k=1.0):
    return tuple(int(clamp(v * k, 0, 1) * 255) for v in c)


def text_colors(pal, accent):
    c1, c2 = pal[0], pal[1]
    if accent:
        face_a = to255(tuple(0.55 * v + 0.45 for v in c1))
        face_b = to255(c1)
        side = to255(c2, 0.55)
    else:
        face_a = (255, 255, 255)
        face_b = to255(tuple(0.75 + 0.25 * v for v in c1))
        side = to255(c2, 0.45)
    return face_a, face_b, side


def _shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    out[dy:, dx:] = m[:h - dy, :w - dx]
    return out


@lru_cache(maxsize=6000)
def glyph(ch, fkey, size, colors):
    """Letra 3D: extrusion, contorno, cara con degradado y bisel. Centrada en la imagen."""
    face_a, face_b, side = colors
    f = font(fkey, size)
    adv = f.getlength(ch)
    l, t, r, b = f.getbbox(ch, anchor="ls")
    cap = -f.getbbox("H", anchor="ls")[1]
    depth = max(3, int(size * 0.09))
    stroke = max(2, size // 30)
    cx0, cy0 = adv / 2, -cap / 2
    hw = max(cx0 - l, r - cx0) + stroke + depth + 6
    hh = max(cy0 - t, b - cy0) + stroke + depth + 6
    w, h = int(2 * hw) + 2, int(2 * hh) + 2
    ox, oy = w / 2 - cx0, h / 2 - cy0

    def mask(sw):
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((ox, oy), ch, font=f, anchor="ls", fill=255, stroke_width=sw, stroke_fill=255)
        return np.asarray(im, np.float32) / 255.0

    m_face, m_out = mask(0), mask(stroke)
    rgb = np.zeros((h, w, 3), np.float32)
    al = np.zeros((h, w), np.float32)
    sideA = np.array(side, np.float32)
    sideB = sideA * 0.25
    for k in range(depth, 0, -1):
        u = k / depth
        a = _shift(m_out, int(round(k * 0.35)), int(round(k * 0.9)))[..., None]
        rgb = rgb * (1 - a) + (sideB * u + sideA * (1 - u)) * a
        al = np.maximum(al, a[..., 0])
    a = m_out[..., None]
    rgb = rgb * (1 - a) + np.array((10, 0, 24), np.float32) * a
    al = np.maximum(al, m_out)
    yy = np.linspace(0, h, h)[:, None, None]
    g = np.clip((yy - (oy - cap)) / max(cap, 1), 0, 1)
    face = np.array(face_a, np.float32) * (1 - g) + np.array(face_b, np.float32) * g
    a = m_face[..., None]
    rgb = rgb * (1 - a) + face * a
    rim = np.clip(m_face - _shift(m_face, 0, max(2, size // 45)), 0, 1)[..., None] * 0.85
    rgb = rgb * (1 - rim) + 255 * rim
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al * 255]).astype(np.uint8), "RGBA")


SCRAMBLE = "#$%&@!?<>/\\01ABCDEFXYZ"

# fuente, tamano, estilo de entrada, salida, efecto por seccion
SECTION_STYLE = {
    "verse":       ("anton", 190, ["glitch", "pop", "drop", "spin"], "zoom"),
    "prechorus":   ("orbitron", 130, ["slam"], "scatter"),
    "chorus":      ("bungee", 190, ["slam"], "zoom"),
    "verse 2":     ("anton", 170, ["glitch", "spin", "drop", "pop"], "glitchout"),
    "prechorus 2": ("orbitron", 130, ["slam"], "scatter"),
    "chorus 2":    ("bungee", 190, ["slam"], "zoom"),
}
CHORUS_FX = {
    "electric heartbeat": ("slam", "zoom", "pulse"),
    "it's all i know": ("pop", "fall", "none"),
    "shock me once": ("glitch", "glitchout", "jolt"),
    "let the current flow": ("drop", "zoom", "flow"),
    "feel it collide": ("slam", "scatter", "shake"),
    "in the static": ("glitch", "glitchout", "jolt"),
    "we come alive": ("slam", "zoom", "pulse"),
}


def make_items(lines):
    items = []
    count = {}
    for idx, ln in enumerate(lines):
        sec = ln["section"]
        fkey, size, styles, exit_ = SECTION_STYLE[sec]
        n = count.get(sec, 0)
        count[sec] = n + 1
        sin, fx = styles[n % len(styles)], "none"
        if sec.startswith("chorus"):
            sin, exit_, fx = CHORUS_FX.get(ln["text"].lower(), ("slam", "zoom", "pulse"))
        if sec.startswith("prechorus"):
            fx = "pulse"
        t1 = lines[idx + 1]["t0"] if idx + 1 < len(lines) and lines[idx + 1]["t0"] - ln["t1"] < 1.0 else ln["t1"]
        items.append({
            "t0": ln["t0"], "t1": t1, "text": ln["text"].upper(), "font": fkey, "size": size,
            "in": sin, "out": exit_, "fx": fx, "cy": H * 0.48, "tracking": 0.0,
            "chorus": sec.startswith("chorus"), "section": sec, "seed": idx * 7 + 3,
            "wordtime": True,
        })
    return items


def intro_outro_items(outro_start, dur):
    return [
        {"t0": 0.7, "t1": 5.55, "text": ARTIST, "font": "monoton", "size": 210, "in": "glitch", "out": "glitchout",
         "fx": "none", "cy": H * 0.40, "tracking": 0.12, "chorus": False, "section": "intro", "seed": 1,
         "wordtime": False, "accent_all": True, "stagger": 0.09},
        {"t0": 2.95, "t1": 5.55, "text": TITLE, "font": "orbitron", "size": 104, "in": "slam", "out": "zoom",
         "fx": "pulse", "cy": H * 0.66, "tracking": 0.04, "chorus": False, "section": "intro", "seed": 2,
         "wordtime": False, "stagger": 0.05},
        {"t0": outro_start + 0.6, "t1": dur + 5, "text": TITLE, "font": "orbitron", "size": 118, "in": "slam",
         "out": "zoom", "fx": "pulse", "cy": H * 0.43, "tracking": 0.04, "chorus": False, "section": "outro",
         "seed": 5, "wordtime": False, "stagger": 0.05},
        {"t0": outro_start + 2.0, "t1": dur + 5, "text": ARTIST, "font": "monoton", "size": 150, "in": "glitch",
         "out": "glitchout", "fx": "none", "cy": H * 0.66, "tracking": 0.12, "chorus": False, "section": "outro",
         "seed": 6, "wordtime": False, "accent_all": True, "stagger": 0.08},
    ]


@lru_cache(maxsize=256)
def layout(text, fkey, base, tracking, maxw=1640):
    """Reparte en 1-2 filas y devuelve [(char, x, y, size, word_idx, accent)] centrado en (0,0)."""
    words = text.split()
    size = base
    while True:
        sizes = [int(size * (1.22 if re.sub(r"[^a-z\-]", "", w.lower()) in KEYWORDS else 1.0)) for w in words]

        def wlen(w, s):
            f = font(fkey, s)
            return f.getlength(w) + tracking * s * (len(w) - 1)
        rows, cur, cw = [], [], 0.0
        for wi, wd in enumerate(words):
            wl = wlen(wd, sizes[wi])
            sp = font(fkey, sizes[wi]).getlength(" ") * 0.9
            if cur and cw + sp + wl > maxw:
                rows.append(cur)
                cur, cw = [], 0.0
            cw += (sp if cur else 0) + wl
            cur.append(wi)
        rows.append(cur)
        widths = [sum(wlen(words[i], sizes[i]) for i in r) + sum(font(fkey, sizes[i]).getlength(" ") * 0.9 for i in r[1:]) for r in rows]
        if (len(rows) <= 2 and max(widths) <= maxw) or size < 70:
            break
        size -= 8
    out = []
    row_h = [max(sizes[i] for i in r) for r in rows]
    total = sum(h * 1.05 for h in row_h)
    y = -total / 2
    for r, rw, rh in zip(rows, widths, row_h):
        y += rh * 1.05
        x = -rw / 2
        for wi in r:
            s = sizes[wi]
            f = font(fkey, s)
            wd = words[wi]
            accent = s != size
            for ci, ch in enumerate(wd):
                out.append((ch, x + f.getlength(wd[:ci]) + tracking * s * ci, y - cap(fkey, s) / 2, s, wi, accent))
            x += f.getlength(wd) + tracking * s * (len(wd) - 1) + f.getlength(" ") * 0.9
    return tuple(out), size


def homography(src, dst):
    A, bv = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        bv += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(bv, float)).tolist()


def rot_mat(ax, ay, az):
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    return (np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @
            np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]))


def place(layer, canvas, cx, cy, z, yaw, pitch, roll, alpha, f=1800.0):
    cw, ch = canvas.size
    R = rot_mat(pitch, yaw, roll)
    dst = []
    for (x, y) in ((0, 0), (cw, 0), (cw, ch), (0, ch)):
        P = R @ np.array([x - cw / 2, y - ch / 2, 0.0])
        zz = max(P[2] + z + f, 60)
        dst.append((cx + f * P[0] / zz, cy + f * P[1] / zz))
    if alpha < 0.999:
        canvas = canvas.copy()
        canvas.putalpha(canvas.getchannel("A").point(lambda v: int(v * alpha)))
    coeffs = homography([(0, 0), (cw, 0), (cw, ch), (0, ch)], dst)
    layer.alpha_composite(canvas.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BILINEAR))


def glyph_in(style, a, rnd, T):
    """(dx, dy, scale, rot, alpha, scramble)"""
    if a < 0:
        return None
    if style == "pop":
        p = clamp(a / 0.38)
        return (0, (1 - ease_out(p)) * 70, max(0.01, back_out(p)), (1 - ease_out(p)) * rnd[0] * 35, clamp(a / 0.1), False)
    if style == "slam":
        p = clamp(a / 0.15)
        sc = lerp(3.4, 1.0, ease_in(p) ** 0.7)
        if p >= 1:
            sc = 1 + 0.14 * math.exp(-(a - 0.15) * 12) * math.cos((a - 0.15) * 34)
        return (0, 0, sc, (1 - p) * rnd[1] * 12, clamp(a / 0.07), False)
    if style == "glitch":
        if a < 0.26:
            fl = 0.35 + 0.65 * ((int(T * 30) + int(rnd[2] * 7)) % 2)
            return (rnd[0] * 30 * (1 - a / 0.26) * math.sin(T * 90), 0, 1.0, 0, fl * clamp(a / 0.05), True)
        return (0, 0, 1.0, 0, 1.0, False)
    if style == "drop":
        p = clamp(a / 0.55)
        return (0, -(1 - bounce_out(p)) * 420, 1.0, (1 - p) * rnd[1] * 25, clamp(a / 0.08), False)
    if style == "spin":
        p = clamp(a / 0.45)
        return (0, 0, max(0.01, ease_out(p)), (1 - ease_out(p)) * 300 * (1 if rnd[2] > 0.5 else -1), clamp(a / 0.15), False)
    return (0, 0, 1.0, 0, 1.0, False)


def render_item(layer, it, T, kick, pal):
    t0, t1 = it["t0"], it["t1"]
    if T < t0 - 0.35 or T > t1 + 0.6:
        return 0.0
    glyphs, base = layout(it["text"], it["font"], it["size"], it["tracking"])
    nwords = max(g[4] for g in glyphs) + 1
    # tiempos de entrada por palabra (proporcionales a su longitud dentro del 55% inicial)
    words = it["text"].split()
    if it["wordtime"]:
        span = min((t1 - t0) * 0.55, 0.45 * nwords)
        lens = np.array([len(w) + 2 for w in words], float)
        wstart = t0 - 0.08 + np.concatenate([[0], np.cumsum(lens)[:-1]]) / lens.sum() * span
        stag = 0.028
    else:
        wstart = [t0] * nwords
        stag = it.get("stagger", 0.05)
    exit_t = t1 - 0.28
    e = clamp((T - exit_t) / 0.45)
    xs = [g[1] for g in glyphs]
    ys = [g[2] for g in glyphs]
    margin = int(base * 2.2)
    cw = int(max(abs(min(xs)), abs(max(xs))) * 2 + 2 * margin)
    ch = int(max(abs(min(ys)), abs(max(ys))) * 2 + 2 * margin)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    glitch = 0.0
    wi_count = {}
    for gi, (c, x, y, s, wi, accent) in enumerate(glyphs):
        k = wi_count.get(wi, 0)
        wi_count[wi] = k + 1
        rng = random.Random(it["seed"] * 1000 + gi)
        rnd = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random())
        st = it["in"]
        state = glyph_in(st, T - (wstart[wi] + k * stag), rnd, T)
        if state is None:
            continue
        dx, dy, sc, rot, al, scr = state
        if scr:
            glitch = max(glitch, 0.6)
        # vida en reposo: ola suave
        dy += 5 * math.sin(T * 2.3 + gi * 0.5)
        fx = it["fx"]
        if fx == "shake":
            jr = random.Random(int(T * FPS) * 31 + gi)
            amp = 4 + 22 * kick
            dx += jr.uniform(-amp, amp)
            dy += jr.uniform(-amp, amp)
            rot += jr.uniform(-4, 4) * kick
        elif fx == "jolt" and kick > 0.45:
            jr = random.Random(int(T * FPS) * 17 + gi)
            dx += jr.uniform(-40, 40) * kick
            scr = scr or jr.random() < 0.25
            glitch = max(glitch, kick)
        if (accent or fx == "pulse") and it["chorus"] or (fx == "pulse" and accent):
            sc *= 1 + 0.10 * kick
        # salida
        out = it["out"]
        if e > 0:
            if out == "scatter":
                dx += rnd[0] * 700 * e
                dy += rnd[1] * 300 * e + 700 * e * e
                rot += rnd[0] * 300 * e
                al *= 1 - e
            elif out == "fall":
                dy += 1000 * e * e * (0.7 + 0.6 * rnd[2])
                rot += rnd[1] * 90 * e
                al *= 1 - e ** 2
            elif out == "glitchout":
                scr = scr or random.Random(int(T * 30) + gi).random() < 0.6
                dx += rnd[0] * 50 * e * math.sin(T * 80)
                al *= (1 - e) * (0.4 + 0.6 * ((int(T * 30) + gi) % 2))
                glitch = max(glitch, 0.7 * (1 - e))
        if al <= 0.01:
            continue
        accent2 = accent or it.get("accent_all", False)
        if fx == "flow":
            accent2 = math.sin(T * 7 - gi * 0.7) > 0
        c0 = c
        if scr:
            c = SCRAMBLE[(int(T * 30) + gi * 7) % len(SCRAMBLE)]
        cols = text_colors(pal, accent2)
        g = glyph(c, it["font"], s, cols)
        if abs(sc - 1) > 0.01 or abs(rot) > 0.5:
            g = g.resize((max(1, int(g.width * sc)), max(1, int(g.height * sc))), Image.BILINEAR)
            if abs(rot) > 0.5:
                g = g.rotate(rot, Image.BILINEAR, expand=True)
        if al < 0.999:
            g = g.copy()
            g.putalpha(g.getchannel("A").point(lambda v, al=al: int(v * al)))
        px = cw / 2 + x + font(it["font"], s).getlength(c0) / 2 + dx - g.width / 2
        py = ch / 2 + y + dy - g.height / 2
        canvas.alpha_composite(g, (int(px), int(py)))
    # transformacion 3D de toda la frase
    enter = ease_out((T - (t0 - 0.35)) / 0.45)
    dur = max(t1 - t0, 0.5)
    z = (1 - enter) * 900 - 160 * clamp((T - t0) / dur)
    alpha = clamp(enter * 1.6)
    if it["out"] == "zoom" and e > 0:
        z -= 1500 * ease_in(e)
        alpha *= 1 - clamp(e * 1.3)
    if alpha <= 0.01:
        return glitch
    sd = it["seed"]
    yaw = 0.22 * math.sin(T * 0.55 + sd) + (1 - enter) * 0.5 * (1 if sd % 2 else -1)
    pitch = 0.10 * math.sin(T * 0.43 + sd * 0.7) - 0.03
    roll = 0.035 * math.sin(T * 0.31 + sd)
    cx, cy = W / 2, it["cy"]
    if it["chorus"] and kick > 0.15:
        # eco que se expande con cada golpe
        place(layer, canvas, cx, cy, z - 420 * (1.2 - kick), yaw, pitch, roll, alpha * 0.4 * kick)
    place(layer, canvas, cx, cy, z - 70 * kick * (1 if it["chorus"] else 0.3), yaw, pitch, roll, alpha)
    return glitch



def ecg_layer(layer, T, dur, pal):
    """Monitor cardiaco 2D: en la intro y al final del outro."""
    if T < INTRO:
        a = smooth(T / 0.6) * (1 - smooth((T - (INTRO - 1.4)) / 1.2))
        cy, amp = H * 0.53, 150
    elif T > dur - 7.5:
        a = smooth((T - (dur - 7.5)) / 1.2) * (1 - smooth((T - (dur - 1.8)) / 1.2))
        cy, amp = H * 0.85, 70
    else:
        return
    if a <= 0.01:
        return
    sweep = HB_PERIOD * 2.4  # el cabezal barre la pantalla en 2.4 latidos
    head = (T % sweep) / sweep
    im = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c1 = to255(pal[0])
    n = 480
    # cada x muestra el valor escrito cuando el cabezal paso por ella (fase alineada con el audio)
    pts = [(s / n * W / 2, (cy - amp * ecg((T - ((head - s / n) % 1.0) * sweep) / HB_PERIOD)) / 2)
           for s in range(n + 1)]
    hi = int(head * n)
    for s in range(n):
        if s == hi:
            continue
        # el trazo se desvanece detras del cabezal, como en un monitor real
        d = (head - s / n) % 1.0
        k = math.exp(-d * 3.2) * a
        if k < 0.02:
            continue
        dr.line([pts[s], pts[s + 1]], fill=(*c1, int(255 * k)), width=3)
    glow = im.filter(ImageFilter.GaussianBlur(6))
    hx, hy = pts[hi]
    dr.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=(255, 235, 240, int(255 * a)))
    out = Image.alpha_composite(glow, im)
    out = Image.alpha_composite(out, glow).resize((W, H), Image.BILINEAR)
    layer.alpha_composite(out)


# ----------------------------------------------------------------------------
# trabajo por fotograma en procesos auxiliares (texto)
# ----------------------------------------------------------------------------
G = {}


def init_worker(items, frames_meta, dur):
    G.update(items=items, meta=frames_meta, dur=dur)


def text_job(i):
    T, kick, pal = G["meta"][i]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ecg_layer(layer, T, G["dur"], pal)
    glitch = 0.0
    for it in G["items"]:
        glitch = max(glitch, render_item(layer, it, T, kick, pal))
    return layer.tobytes(), glitch


# ----------------------------------------------------------------------------
# OpenGL
# ----------------------------------------------------------------------------
VS = """#version 330
in vec2 in_pos; out vec2 vUV;
void main(){ gl_Position = vec4(in_pos, 0.0, 1.0); vUV = in_pos * 0.5 + 0.5; }"""


def gl_context():
    import moderngl
    try:
        return moderngl.create_standalone_context(backend="egl")
    except Exception:
        pass
    if not os.environ.get("DISPLAY") and not os.environ.get("EH_XVFB"):
        os.environ["EH_XVFB"] = "1"
        os.execvp("xvfb-run", ["xvfb-run", "-a", "-s", "-screen 0 640x480x24", sys.executable] + sys.argv)
    return moderngl.create_standalone_context()


class Renderer:
    def __init__(self):
        import moderngl
        self.mgl = moderngl
        ctx = self.ctx = gl_context()
        rd = lambda n: open(os.path.join(HERE, n)).read()
        self.world = ctx.program(vertex_shader=VS, fragment_shader=rd("world.frag"))
        self.post = ctx.program(vertex_shader=VS, fragment_shader=rd("post.frag"))
        vbo = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        self.vw = ctx.vertex_array(self.world, [(vbo, "2f", "in_pos")])
        self.vp = ctx.vertex_array(self.post, [(vbo, "2f", "in_pos")])
        self.wtex = ctx.texture((WORLD_W, WORLD_H), 4, dtype="f2")
        self.wtex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.wtex.repeat_x = self.wtex.repeat_y = False
        self.wfbo = ctx.framebuffer([self.wtex])
        self.ttex = ctx.texture((W, H), 4)
        self.ttex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.ttex.repeat_x = self.ttex.repeat_y = False
        self.otex = ctx.texture((W, H), 3)
        self.ofbo = ctx.framebuffer([self.otex])

    @staticmethod
    def _set(prog, name, val):
        if name in prog:
            prog[name].value = val

    def render(self, f, text_bytes, text_glitch, fade):
        s = self._set
        pw = self.world
        s(pw, "uRes", (WORLD_W, WORLD_H))
        s(pw, "uTime", f["T"])
        s(pw, "uScene", f["scene"])
        s(pw, "uCamPos", f["pos"])
        s(pw, "uCamTgt", f["tgt"])
        s(pw, "uRoll", f["roll"])
        s(pw, "uFov", f["fov"])
        s(pw, "uBass", f["bass"])
        s(pw, "uKick", f["kick"])
        s(pw, "uBeat", f["beat"])
        s(pw, "uFlash", f["flash"])
        s(pw, "uCol1", f["pal"][0])
        s(pw, "uCol2", f["pal"][1])
        s(pw, "uFog", f["pal"][2])
        s(pw, "uPulseR", f["pulseR"])
        s(pw, "uPulseA", f["pulseA"])
        s(pw, "uPulseC", f["pulseC"])
        s(pw, "uWin", f["win"])
        s(pw, "uDecay", f["decay"])
        s(pw, "uSpark", f["spark"])
        s(pw, "uSparkPos", f["spark_pos"])
        s(pw, "uCore", f["core"])
        s(pw, "uRingRot", f["rings"])
        s(pw, "uFold", f["fold"])
        s(pw, "uLasers", f["lasers"])
        s(pw, "uArcs", f["arcs"])
        s(pw, "uSeed", f["seed"])
        self.wfbo.use()
        self.vw.render(self.mgl.TRIANGLE_STRIP)
        self.wtex.build_mipmaps()
        self.ttex.write(text_bytes)
        self.ttex.build_mipmaps()
        self.wtex.use(0)
        self.ttex.use(2)
        pp = self.post
        s(pp, "uWorld", 0)
        s(pp, "uText", 2)
        s(pp, "uRes", (W, H))
        s(pp, "uTime", f["T"])
        s(pp, "uKick", f["kick"])
        s(pp, "uBeat", f["beat"])
        s(pp, "uChroma", f["chroma"] + 2.0 * text_glitch)
        s(pp, "uGlitch", clamp(f["glitch"] + 0.5 * text_glitch))
        s(pp, "uFlashScr", f["flash_scr"])
        s(pp, "uFade", fade)
        s(pp, "uGlow", 0.75)
        s(pp, "uFocus", f["focus"])
        s(pp, "uAperture", f["aperture"])
        s(pp, "uTint", f["tint"])
        self.ofbo.use()
        self.vp.render(self.mgl.TRIANGLE_STRIP)
        return self.ofbo.read(components=3)


# ----------------------------------------------------------------------------
def main():
    gl_context()  # si hace falta, se relanza bajo xvfb-run antes del trabajo pesado
    build_audio()
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", AUDIO],
                               capture_output=True, text=True, check=True).stdout)
    lines = load_lyrics()
    write_srt(lines)
    secs = build_sections(lines, dur)
    print("secciones:", [(n, round(a, 2), round(b, 2)) for n, a, b in secs], flush=True)
    audio = analyze_audio(dur)
    nframes = int(dur * FPS)
    frames = build_frames(secs, audio, nframes, lines)
    items = make_items(lines) + intro_outro_items(secs[-1][1], dur)
    meta = [(f["T"], f["kick"], f["pal"]) for f in frames]

    def fade(T):
        return smooth(T / 0.5) * (1 - smooth((T - (dur - 2.0)) / 1.9))

    rend = Renderer()
    if "--stills" in sys.argv:
        secs_req = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1:]]
        os.makedirs(os.path.join(HERE, "stills"), exist_ok=True)
        init_worker(items, meta, dur)
        for sT in secs_req:
            i = min(int(sT * FPS), nframes - 1)
            tb, g = text_job(i)
            buf = rend.render(frames[i], tb, g, fade(frames[i]["T"]))
            Image.frombytes("RGB", (W, H), buf).transpose(Image.FLIP_TOP_BOTTOM).save(
                os.path.join(HERE, "stills", f"t{sT:06.2f}.png"))
            print("still", sT, frames[i]["section"], flush=True)
        return

    start = int(os.environ.get("EH_START", 0))
    end = min(int(os.environ.get("EH_END", nframes)), nframes)
    part = os.environ.get("EH_PART")
    master = os.path.join(BUILD, f"part_{part}.mp4") if part else MASTER
    os.makedirs(BUILD, exist_ok=True)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-vf", "vflip", "-c:v", "libx264", "-preset", "medium", "-crf", "15",
         "-pix_fmt", "yuv420p", master], stdin=subprocess.PIPE)
    batch = 16
    with Pool(int(os.environ.get("EH_TEXT_WORKERS", 2)), initializer=init_worker, initargs=(items, meta, dur)) as pool:
        nxt = pool.map_async(text_job, range(start, min(start + batch, end)))
        for b0 in range(start, end, batch):
            res = nxt.get()
            b1 = b0 + batch
            if b1 < end:
                nxt = pool.map_async(text_job, range(b1, min(b1 + batch, end)))
            for k, (tb, g) in enumerate(res):
                i = b0 + k
                ff.stdin.write(rend.render(frames[i], tb, g, fade(frames[i]["T"])))
            if ((b0 - start) // batch) % 10 == 0:
                print(f"frame {b0}/{end}", flush=True)
    ff.stdin.close()
    ff.wait()
    if part:
        print("parte lista:", master, flush=True)
        return
    finish(dur)


def finish(dur):
    """Codificacion final en dos pasadas (< 100 MB, limite de GitHub) + audio + subtitulos."""
    vbit = int((93 * 8 * 1024) / dur - 192)
    common = ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-b:v", f"{vbit}k",
              "-maxrate", f"{int(vbit * 1.6)}k", "-bufsize", f"{vbit * 3}k", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    plog = os.path.join(BUILD, "x264pass")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", MASTER] + common +
                   ["-pass", "1", "-passlogfile", plog, "-an", "-f", "null", "-"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", MASTER, "-i", AUDIO, "-i", SRT_OUT,
                    "-map", "0:v", "-map", "1:a", "-map", "2:s"] + common +
                   ["-pass", "2", "-passlogfile", plog, "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=Lyrics",
                    "-metadata", f"title={ARTIST.title()} - Electric Heartbeat", "-metadata", "artist=EchoBot",
                    "-movflags", "+faststart", "-t", f"{dur:.3f}", OUT], check=True)
    print("listo:", OUT, flush=True)


if __name__ == "__main__":
    if "--finish" in sys.argv:
        build_audio()
        lines = load_lyrics()
        write_srt(lines)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  AUDIO], capture_output=True, text=True, check=True).stdout)
        finish(d)
    else:
        main()
