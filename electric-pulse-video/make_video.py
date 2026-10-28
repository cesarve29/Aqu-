#!/usr/bin/env python3
"""
EchoBot - ELECTRIC PULSE (lyric video 3D)

Mundo 3D por raymarching en GLSL (OpenGL via moderngl; en servidores sin GPU corre en
llvmpipe bajo Xvfb): una megaciudad viva bajo la tormenta (calles mojadas con reflejos,
miles de ventanas, coches voladores, rayos, torre de energia, ondas expansivas con el
bombo) y un laberinto digital con laseres y estroboscopios para la segunda estrofa.
Las letras son tipografia cinetica 3D animada letra a letra, sincronizada con los
tiempos incrustados en el .m4a. Intro con artista + titulo. Sin ecualizador.

Uso:
    python3 make_video.py                     -> electric_pulse_1080p.mp4 (1920x1080, 30 fps, < 100 MB)
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

W, H, FPS = 1920, 1080, 30
WORLD_W, WORLD_H = 1920, 1080
SKY_W, SKY_H = 960, 540
HERE = os.path.dirname(os.path.abspath(__file__))
SONG = os.path.join(HERE, "electric_pulse.m4a")
BUILD = os.path.join(HERE, "build")
AUDIO = os.path.join(BUILD, "audio_full.wav")
MASTER = os.path.join(BUILD, "master.mp4")
OUT = os.path.join(HERE, "electric_pulse_1080p.mp4")
FONTS = os.path.join(HERE, "fonts")
SR = 22050

ARTIST = "ECHOBOT"
TITLE = "ELECTRIC PULSE"
INTRO = 6.0  # segundos de intro antes de que arranque la cancion

KEYWORDS = {
    "night", "neon", "dreams", "electric", "tides", "lights", "sky", "fly", "pulse",
    "shake", "jolt", "veins", "revolt", "strobe-lit", "digital", "maze", "bassline",
    "circuit", "sparks", "ignite", "right", "collide", "burn",
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


# ----------------------------------------------------------------------------
# audio: intro (extracto filtrado + subida de ruido) + cancion
# ----------------------------------------------------------------------------
def build_audio():
    os.makedirs(BUILD, exist_ok=True)
    fmt = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
    fc = (
        f"[0:a]atrim=30:{30 + INTRO},asetpts=PTS-STARTPTS,lowpass=f=420,lowpass=f=420,"
        f"volume=1.6,afade=t=in:d=2.5,afade=t=out:st={INTRO - 0.35}:d=0.35,{fmt}[m];"
        f"anoisesrc=d={INTRO}:c=pink:a=0.6,highpass=f=1800,"
        f"afade=t=in:st=2.2:d={INTRO - 2.35},afade=t=out:st={INTRO - 0.15}:d=0.15,volume=0.22,{fmt}[n];"
        f"[m][n]amix=inputs=2:normalize=0[intro];"
        f"[0:a]{fmt}[song];[intro][song]concat=n=2:v=0:a=1[out]"
    )
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SONG, "-filter_complex", fc,
                    "-map", "[out]", "-c:a", "pcm_s16le", AUDIO], check=True)


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
        text = " ".join(rows[2:]).strip()
        if text.startswith("["):
            name = text.strip("[]").lower()
            count[name] = count.get(name, 0) + 1
            section = name if count[name] == 1 or name.endswith("2") else f"{name} 2"
            continue
        lines.append({"t0": t0 + INTRO, "t1": t1 + INTRO, "text": text, "section": section})
    return lines


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
    flux = np.maximum(0, np.diff(bass, prepend=bass[0]))
    flux = np.clip(flux / (np.percentile(flux, 98) + 1e-9), 0, 1.5)
    kicks, last = [], -1.0
    for i in range(n):
        t = i / FPS
        if flux[i] > 0.4 and t - last > 0.2 and t > INTRO - 0.05:
            kicks.append(t)
            last = t
    kick = np.zeros(n)
    for i in range(n):
        kick[i] = max(flux[i] if flux[i] > 0.25 else 0, (kick[i - 1] if i else 0) * 0.82)
    return {"bass": np.convolve(bass, np.ones(5) / 5, mode="same"), "kick": np.clip(kick, 0, 1.2),
            "energy": np.convolve(rms, np.ones(45) / 45, mode="same"), "kicks": np.array(kicks)}


# ----------------------------------------------------------------------------
# guion: secciones, paletas, camara
# ----------------------------------------------------------------------------
# neon 1, neon 2, niebla (lineal, para el shader)
PALETTES = {
    "intro":       ((0.0, 0.85, 1.0), (1.0, 0.1, 0.65), (0.035, 0.012, 0.07)),
    "verse":       ((0.0, 0.85, 1.0), (1.0, 0.1, 0.65), (0.045, 0.014, 0.08)),
    "prechorus":   ((1.0, 0.55, 0.08), (1.0, 0.08, 0.3), (0.07, 0.02, 0.045)),
    "chorus":      ((1.0, 0.12, 0.7), (0.1, 1.0, 0.85), (0.06, 0.012, 0.09)),
    "verse 2":     ((1.0, 0.42, 0.04), (1.0, 0.08, 0.45), (0.03, 0.006, 0.02)),
    "prechorus 2": ((0.75, 1.0, 0.1), (1.0, 0.1, 0.2), (0.025, 0.02, 0.012)),
    "chorus 2":    ((0.2, 0.5, 1.0), (1.0, 0.78, 0.1), (0.02, 0.025, 0.08)),
    "outro":       ((0.6, 0.3, 1.0), (0.0, 0.85, 1.0), (0.03, 0.02, 0.08)),
}
HALL = {"verse 2", "prechorus 2"}


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


def cam_pose(name, T, st, en, travel):
    """Posicion/objetivo de la camara para una seccion. Devuelve (x, y, yaw, pitch, roll, fov, speed)."""
    u = T - st
    p = clamp(u / max(en - st, 1e-3))
    if name == "intro":
        k = smooth(T / INTRO)
        return (0.0, lerp(175, 10, k ** 0.8), 0.0, lerp(-1.25, 0.04, smooth(T / (INTRO * 0.95))), 0.0, 1.15, 20)
    if name == "verse":
        return (3 * math.sin(u * 0.21), 7 + 2.5 * math.sin(u * 0.35), 0.12 * math.sin(u * 0.17),
                0.07 + 0.05 * math.sin(u * 0.3), -0.05 * math.cos(u * 0.21), 1.2, 22)
    if name == "prechorus":
        return (2 * math.sin(u * 0.4), 8 + 34 * p ** 1.4, 0.1 * math.sin(u * 0.5),
                0.08 + 0.32 * math.sin(math.pi * min(p * 1.15, 1)), 0.12 * math.sin(u * 0.9), 1.15, lerp(22, 50, p))
    if name in ("chorus", "chorus 2"):
        low_first = name == "chorus 2"
        half = smooth((u - (en - st) * 0.5) / 2.0)
        hi = 28 + 8 * math.sin(u * 0.45)
        lo = 3.2 + 0.8 * math.sin(u * 0.9)
        y = lerp(lo, hi, half) if low_first else lerp(hi, lo, half)
        x = 6.5 * math.sin(u * 0.33)
        pitch = lerp(-0.02, -0.12, half if low_first else 1 - half) + 0.04 * math.sin(u * 0.5)
        spd = lerp(80, 60, half) if low_first else lerp(60, 80, half)
        return (x, y, 0.16 * math.cos(u * 0.33), pitch, -0.33 * math.cos(u * 0.33), 1.0, spd)
    if name == "verse 2":
        return (2.2 * math.sin(u * 0.27), 3.2 + 0.6 * math.sin(u * 0.5), 0.2 * math.sin(u * 0.19),
                0.03, 0.06 * math.sin(u * 0.3), 1.12, 16)
    if name == "prechorus 2":
        return (2.0 * math.sin(u * 0.5), 3.2 + 6 * p ** 2, 0.15 * math.sin(u * 0.4), 0.03 + 0.1 * p,
                0.7 * p ** 2 * math.sin(u * 1.6), 1.1 - 0.15 * p, lerp(16, 45, p))
    # outro
    return (2 * math.sin(u * 0.2), lerp(40, 190, smooth(p * 1.1)), 0.1 * math.sin(u * 0.15),
            lerp(-0.15, -0.75, smooth(p * 1.2)), 0.08 * math.sin(u * 0.25), 1.15, lerp(35, 6, p))


def build_frames(secs, audio, nframes, lines):
    """Precalcula camara + uniforms del mundo por fotograma."""
    kicks = audio["kicks"]
    # rayos: tiempos de descarga
    bolts = [3.05, INTRO]
    for name, st, en in secs:
        ks = [k for k in kicks if st <= k < en]
        if name == "verse":
            bolts += ks[5::14]
        elif name == "prechorus":
            sel, last = [], -9
            for k in ks:
                if k - last > 0.42:
                    sel.append(k)
                    last = k
            bolts += sel
        elif name in ("chorus", "chorus 2"):
            bolts += ks[::4]
        elif name == "outro":
            bolts += ks[2:30:9]
    bolts = sorted(bolts)
    frames = []
    travel = 0.0
    prev_name = None
    for i in range(nframes):
        T = i / FPS
        k, name, st, en = section_at(T, secs)
        pose = cam_pose(name, T, st, en, travel)
        # mezcla suave de camara con la seccion anterior si siguen en el mismo mundo
        if k > 0:
            pname, pst, pen = secs[k - 1]
            if (pname in HALL) == (name in HALL) and T - st < 1.0:
                pp = cam_pose(pname, T, pst, pen, travel)
                a = smooth((T - st) / 1.0)
                pose = tuple(lerp(x, y, a) for x, y in zip(pp, pose))
        x, y, yaw, pitch, roll, fov, spd = pose
        j = min(i, len(audio["bass"]) - 1)
        bass, kick = float(audio["bass"][j]), float(audio["kick"][j])
        travel += spd * (0.85 + 0.35 * bass) / FPS
        fwd = (math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch))
        pos = (x, y, travel)
        tgt = (x + fwd[0], y + fwd[1], travel + fwd[2])
        # paleta con fundido corto entre secciones
        pal = PALETTES[name]
        if k > 0 and T - st < 0.6:
            pal = tuple(lerp3(a, b, smooth((T - st) / 0.6)) for a, b in zip(PALETTES[secs[k - 1][0]], pal))
        # bombo mas reciente
        ki = np.searchsorted(kicks, T, side="right") - 1
        kt = kicks[ki] if ki >= 0 else -99
        chorus = name in ("chorus", "chorus 2")
        hall = name in HALL
        # rayos
        bi = np.searchsorted(bolts, T, side="right") - 1
        flash = 0.0
        if bi >= 0:
            age = T - bolts[bi]
            if age < 0.6:
                flash = math.exp(-age * 10) + (0.7 * math.exp(-(age - 0.09) * 14) if age > 0.09 else 0)
        flash *= 0 if hall else 1
        cut = T - st
        frames.append({
            "T": T, "section": name, "k": k, "hall": hall,
            "pos": pos, "tgt": tgt, "roll": roll, "fov": fov - (0.06 * kick if chorus else 0.0),
            "bass": bass, "kick": kick, "pal": pal, "flash": flash,
            "pulseR": (T - kt) * 95.0, "pulseA": math.exp(-(T - kt) * 2.0) * (1.0 if chorus else 0.0),
            "kt": kt,
            "win": smooth((T - 0.4) / 4.2) if name == "intro" else 1.0,
            "strobe": (math.exp(-(T - kt) * 13) * (0.6 if name == "verse 2" else 1.0)) if hall else 0.0,
            "laser": (0.55 + 0.9 * kick) if hall else 0.0,
            "cars": 0.0 if hall else 1.0,
            "rain": 0.0 if hall else (0.45 if chorus else 0.9),
            "flash_scr": (0.6 * math.exp(-cut * 8) if k > 0 else 0.0) + (0.05 * kick if chorus else 0.0) + 0.12 * flash,
            "glitch": clamp(1 - cut / 0.25) if k > 0 else 0.0,
            "chroma": (1.2 * kick if chorus else 0.4 * kick),
        })
    # el centro de cada onda expansiva queda fijo donde estaba la camara al sonar el bombo
    tz = {round(f["T"] * FPS): f["pos"][2] for f in frames}
    for f in frames:
        z0 = tz.get(round(f["kt"] * FPS), f["pos"][2])
        f["pulseC"] = (0.0, 0.0, z0 + 70.0)
    return frames, bolts


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
    "verse 2":     ("orbitron", 120, ["glitch", "spin"], "glitchout"),
    "prechorus 2": ("orbitron", 130, ["slam"], "scatter"),
    "chorus 2":    ("bungee", 190, ["slam"], "zoom"),
}
CHORUS_FX = {
    "electric pulse": ("slam", "zoom", "pulse"),
    "feel it shake": ("pop", "fall", "shake"),
    "feel it jolt": ("glitch", "glitchout", "jolt"),
    "it's in our veins": ("drop", "zoom", "flow"),
    "we can't revolt": ("slam", "scatter", "pulse"),
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
        {"t0": 2.95, "t1": 5.55, "text": TITLE, "font": "orbitron", "size": 112, "in": "slam", "out": "zoom",
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


def lightning_layer(bolts, T, pal):
    act = [b for b in bolts if 0 <= T - b < 0.32]
    if not act:
        return None
    im = Image.new("RGBA", (SKY_W, SKY_H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c1 = to255(pal[0])
    for b in act:
        age = T - b
        k = math.exp(-age * 9) * (0.6 + 0.4 * (int(age * 60) % 2))
        rng = random.Random(int(b * 1000))
        for _ in range(1 + rng.randint(0, 1)):
            x, y = rng.uniform(SKY_W * 0.12, SKY_W * 0.88), 0.0
            pts = [(x, y)]
            ymax = rng.uniform(0.45, 0.7) * SKY_H
            while y < ymax:
                y += rng.uniform(10, 26)
                x += rng.uniform(-24, 24)
                pts.append((x, y))
            col = tuple(int(v * k) for v in (230, 235, 255))
            dr.line(pts, fill=(*col, int(255 * k)), width=3)
            for j in range(2, len(pts) - 2, 3):
                bx, by = pts[j]
                br = [(bx, by)]
                for _ in range(4):
                    bx += rng.uniform(-22, 22)
                    by += rng.uniform(8, 18)
                    br.append((bx, by))
                dr.line(br, fill=(*[int(v * k) for v in c1], int(200 * k)), width=2)
    glow = im.filter(ImageFilter.GaussianBlur(7))
    out = Image.alpha_composite(glow, im)
    out = Image.alpha_composite(out, glow)
    return out


# ----------------------------------------------------------------------------
# trabajo por fotograma en procesos auxiliares (texto + rayos)
# ----------------------------------------------------------------------------
G = {}


def init_worker(items, frames_meta, bolts):
    G.update(items=items, meta=frames_meta, bolts=bolts)


def text_job(i):
    T, kick, pal = G["meta"][i]
    pal255 = pal
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glitch = 0.0
    for it in G["items"]:
        glitch = max(glitch, render_item(layer, it, T, kick, pal255))
    sky = lightning_layer(G["bolts"], T, pal)
    return layer.tobytes(), (sky.tobytes() if sky is not None else b""), glitch


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
    if not os.environ.get("DISPLAY") and not os.environ.get("EP_XVFB"):
        os.environ["EP_XVFB"] = "1"
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
        self.stex = ctx.texture((SKY_W, SKY_H), 4)
        self.stex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.empty_sky = bytes(SKY_W * SKY_H * 4)
        self.otex = ctx.texture((W, H), 3)
        self.ofbo = ctx.framebuffer([self.otex])

    @staticmethod
    def _set(prog, name, val):
        if name in prog:
            prog[name].value = val

    def render(self, f, text_bytes, sky_bytes, text_glitch, fade):
        s = self._set
        pw = self.world
        self.stex.write(sky_bytes or self.empty_sky)
        self.stex.use(1)
        s(pw, "uSkyFx", 1)
        s(pw, "uRes", (WORLD_W, WORLD_H))
        s(pw, "uTime", f["T"])
        s(pw, "uScene", 1 if f["hall"] else 0)
        s(pw, "uCamPos", f["pos"])
        s(pw, "uCamTgt", f["tgt"])
        s(pw, "uRoll", f["roll"])
        s(pw, "uFov", f["fov"])
        s(pw, "uBass", f["bass"])
        s(pw, "uKick", f["kick"])
        s(pw, "uFlash", f["flash"])
        s(pw, "uCol1", f["pal"][0])
        s(pw, "uCol2", f["pal"][1])
        s(pw, "uFog", f["pal"][2])
        s(pw, "uPulseR", f["pulseR"])
        s(pw, "uPulseA", f["pulseA"])
        s(pw, "uPulseC", f["pulseC"])
        s(pw, "uWin", f["win"])
        s(pw, "uStrobe", f["strobe"])
        s(pw, "uLaser", f["laser"])
        s(pw, "uCars", f["cars"])
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
        s(pp, "uChroma", f["chroma"] + 2.0 * text_glitch)
        s(pp, "uGlitch", clamp(f["glitch"] + 0.5 * text_glitch))
        s(pp, "uFlashScr", f["flash_scr"])
        s(pp, "uFade", fade)
        s(pp, "uRain", f["rain"])
        s(pp, "uGlow", 0.75)
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
    secs = build_sections(lines, dur)
    print("secciones:", [(n, round(a, 2), round(b, 2)) for n, a, b in secs], flush=True)
    audio = analyze_audio(dur)
    nframes = int(dur * FPS)
    frames, bolts = build_frames(secs, audio, nframes, lines)
    items = make_items(lines) + intro_outro_items(secs[-1][1], dur)
    meta = [(f["T"], f["kick"], f["pal"]) for f in frames]

    def fade(T):
        return smooth(T / 0.7) * (1 - smooth((T - (dur - 2.6)) / 2.4))

    rend = Renderer()
    if "--stills" in sys.argv:
        secs_req = [float(x) for x in sys.argv[sys.argv.index("--stills") + 1:]]
        os.makedirs(os.path.join(HERE, "stills"), exist_ok=True)
        init_worker(items, meta, bolts)
        for sT in secs_req:
            i = min(int(sT * FPS), nframes - 1)
            tb, sb, g = text_job(i)
            buf = rend.render(frames[i], tb, sb, g, fade(frames[i]["T"]))
            Image.frombytes("RGB", (W, H), buf).transpose(Image.FLIP_TOP_BOTTOM).save(
                os.path.join(HERE, "stills", f"t{sT:06.2f}.png"))
            print("still", sT, flush=True)
        return

    os.makedirs(BUILD, exist_ok=True)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-vf", "vflip", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", MASTER], stdin=subprocess.PIPE)
    batch = 16
    with Pool(2, initializer=init_worker, initargs=(items, meta, bolts)) as pool:
        nxt = pool.map_async(text_job, range(0, min(batch, nframes)))
        for b0 in range(0, nframes, batch):
            res = nxt.get()
            b1 = b0 + batch
            if b1 < nframes:
                nxt = pool.map_async(text_job, range(b1, min(b1 + batch, nframes)))
            for k, (tb, sb, g) in enumerate(res):
                i = b0 + k
                ff.stdin.write(rend.render(frames[i], tb, sb, g, fade(frames[i]["T"])))
            if (b0 // batch) % 10 == 0:
                print(f"frame {b0}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    # codificacion final en dos pasadas para quedar por debajo de 100 MB (limite de GitHub)
    vbit = int((92 * 8 * 1024) / dur - 192)
    common = ["-c:v", "libx264", "-preset", "slow", "-b:v", f"{vbit}k", "-pix_fmt", "yuv420p"]
    plog = os.path.join(BUILD, "x264pass")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", MASTER] + common +
                   ["-pass", "1", "-passlogfile", plog, "-an", "-f", "null", "-"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", MASTER, "-i", AUDIO, "-map", "0:v", "-map", "1:a"] +
                   common + ["-pass", "2", "-passlogfile", plog, "-c:a", "aac", "-b:a", "192k",
                             "-movflags", "+faststart", "-shortest", OUT], check=True)
    print("listo:", OUT, flush=True)


if __name__ == "__main__":
    main()
