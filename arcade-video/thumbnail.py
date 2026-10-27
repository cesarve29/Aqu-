#!/usr/bin/env python3
"""Miniatura de YouTube (1280x720) con el estilo del video."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw

import make_video as mv

HERE = os.path.dirname(os.path.abspath(__file__))


def compose():
    arr = mv.synth_bg(0.35, hor=138, sun_r=40)
    im = Image.fromarray(arr)
    dr = ImageDraw.Draw(im)
    mv.draw_dragon(dr, 240, 96, 20.6, jaw=1.0, s=1.05)
    # rafaga de balas desde la boca
    mx, my = 200, 112
    for k in range(3):
        for j in range(12):
            a = j * 2 * math.pi / 12 + k * 0.25
            r = 22 + k * 20
            px, py = mx + math.cos(a) * r, my + math.sin(a) * r
            if px < 215:
                dr.ellipse([px - 2, py - 2, px + 2, py + 2], fill=mv.MAG)
                dr.point((px, py), fill=mv.WHITE)
    # heroe saltando con la espada cargada y estela
    hx, hy = 92, 150
    for k in range(3, 0, -1):
        mv.put(im, mv.sprite('ninja_b', 3, mv.PAL_GHOST), hx - k * 20, hy + k * 9)
    dr.line([hx + 6, hy - 24, hx + 62, hy - 78], fill=mv.CYAN, width=9)
    dr.line([hx + 6, hy - 24, hx + 62, hy - 78], fill=mv.WHITE, width=3)
    mv.burst(dr, hx + 62, hy - 78, 0.25, n=40, speed=90, seed=2, life=1.0,
             colors=[mv.WHITE, mv.CYAN, mv.MAG], grav=0)
    mv.put(im, mv.sprite('ninja_b', 3), hx, hy)
    mv.explosion(dr, 250, 150, 0.18, 1.2, seed=4)
    mv.explosion(dr, 300, 60, 0.12, 0.8, seed=6)
    # titulo
    logo = mv.text_rgba("LAST GAME", 5, mv.chrome, outline=mv.INK)
    im.paste(logo, (160 - logo.width // 2, 6), logo)
    mv.draw_text(im, "LA ULTIMA PARTIDA", 160, 48, 2, mv.PINK)
    # insignias
    dr.rectangle([6, 160, 106, 174], fill=mv.INK, outline=mv.YELLOW)
    mv.draw_text(im, "BOSS FIGHT!", 56, 164, 1, mv.YELLOW)
    return np.array(im)


def main():
    frame = mv.post(compose(), 1, 5.0, 0, (0, 0), 0.0)
    full = Image.fromarray(frame)
    out = os.path.join(HERE, 'youtube_thumbnail.png')
    full.resize((1280, 720), Image.LANCZOS).save(out, optimize=True)
    print(out, os.path.getsize(out) // 1024, "KB")


if __name__ == '__main__':
    main()
