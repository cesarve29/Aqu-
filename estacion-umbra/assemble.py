#!/usr/bin/env python3
"""Montaje final de ESTACION UMBRA.

1. Cada toma (cuadros PNG de Cycles) se interpola por movimiento a 60 fps de forma
   independiente (asi los cortes nunca se mezclan), se escala a 1920x1080 y se etalona.
2. Se concatenan las tomas y se mezcla el audio (build/mix.wav).

Salida: estacion_umbra_1080p60.mp4
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
FRAMES = os.path.join(BUILD, "frames")
FPS = 15
SHOT_FPS = {8: 30, 13: 30}
DUR = {1: 10.0, 2: 10.0, 3: 11.0, 4: 13.0, 5: 9.0, 6: 12.0, 7: 9.0, 8: 2.5,
       9: 12.5, 10: 13.0, 11: 13.0, 12: 11.0, 13: 3.0, 14: 14.5, 15: 13.0, 16: 10.0}

# etalonaje: sombras frias, altas luces calidas, grano de pelicula, vinieta
GRADE = ("scale=1920:1080:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,"
         "colorbalance=rs=-0.04:gs=0.0:bs=0.05:rh=0.04:gh=0.01:bh=-0.03,"
         "eq=contrast=1.06:saturation=0.92:gamma=0.98,"
         "noise=c0s=7:c0f=t+u:c1s=3:c1f=t+u:c2s=3:c2f=t+u,"
         "vignette=angle=PI/4.6")


def run(cmd):
    print(" ".join(cmd[:6]), "...", flush=True)
    subprocess.run(cmd, check=True)


def shot_clip(i):
    fps = SHOT_FPS.get(i, FPS)
    out = os.path.join(BUILD, f"clip{i:02d}.mp4")
    if os.path.exists(out) and os.environ.get("UMBRA_REBUILD") != "1":
        return out
    n = int(round(DUR[i] * fps))
    src = os.path.join(FRAMES, f"shot{i:02d}", "f_%04d.png")
    missing = [k for k in range(n) if not os.path.exists(os.path.join(FRAMES, f"shot{i:02d}", f"f_{k:04d}.png"))]
    if missing:
        raise SystemExit(f"toma {i}: faltan {len(missing)} cuadros (primero {missing[0]})")
    interp = ("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:me=epzs:vsbmc=1:scd=none"
              if fps < 60 else "fps=60")
    vf = f"{interp},tpad=stop_mode=clone:stop_duration=0.5,{GRADE}"
    # los ultimos cuadros interpolados necesitan el cuadro final: se recorta a la duracion exacta
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-start_number", "0", "-i", src,
         "-vf", vf, "-t", f"{DUR[i]}", "-r", "60", "-c:v", "libx264", "-preset", "medium", "-crf", "12",
         "-pix_fmt", "yuv420p", out])
    return out


def main():
    only = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else sorted(DUR)
    clips = [shot_clip(i) for i in only]
    if len(only) != len(DUR):
        return
    lst = os.path.join(BUILD, "clips.txt")
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    master = os.path.join(HERE, "estacion_umbra_1080p60_master.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", os.path.join(BUILD, "mix.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "grain",
         "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "60", "-c:a", "aac", "-b:a", "320k",
         "-movflags", "+faststart", "-shortest", master])
    # version ligera (< 100 MB) para el repositorio
    small = os.path.join(HERE, "estacion_umbra_1080p60.mp4")
    common = ["-c:v", "libx264", "-preset", "slow", "-b:v", "4200k", "-maxrate", "6000k", "-bufsize", "8400k",
              "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "60"]
    run(["ffmpeg", "-v", "error", "-y", "-i", master, "-map", "0:v"] + common +
        ["-pass", "1", "-passlogfile", os.path.join(BUILD, "x264"), "-an", "-f", "mp4", os.devnull])
    run(["ffmpeg", "-v", "error", "-y", "-i", master] + common +
        ["-pass", "2", "-passlogfile", os.path.join(BUILD, "x264"), "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", small])
    print("listo:", master, small)


if __name__ == "__main__":
    main()
