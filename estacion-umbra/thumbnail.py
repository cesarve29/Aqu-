#!/usr/bin/env python3
"""Miniatura de YouTube (1280x720) a partir de dos cuadros renderizados en Cycles.

La cara pegada al vidrio escarchado (toma especial 99 de scenes.py) + texto.
Requiere haber renderizado:
    UMBRA_W=1280 UMBRA_H=720 UMBRA_SAMPLES=32 UMBRA_OUT=build/thumb python3 scenes.py --shot 99 --still 0
"""
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, "build", "thumb")
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
W, H = 1280, 720


def grade(im, warm=False):
    im = ImageEnhance.Contrast(im).enhance(1.25)
    im = ImageEnhance.Brightness(im).enhance(1.25)
    return ImageEnhance.Color(im).enhance(1.15)


def outlined(d, xy, text, font, fill, stroke, sw):
    d.text(xy, text, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)


def main():
    im = Image.open(os.path.join(T, "still_99_0.00.png")).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.3)
    im = ImageEnhance.Color(im).enhance(0.85)
    # tinte frio en sombras + oscurecer la mitad izquierda para el texto
    cold = Image.new("RGB", (W, H), (10, 25, 60))
    im = Image.blend(im, cold, 0.18)
    grad = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        v = int(235 * max(0.0, 1 - x / 760) ** 1.3)
        gd.line([(x, 0), (x, H)], fill=v)
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, grad)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-260, -200, W + 260, H + 200), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(110))
    canvas = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), vig)
    d = ImageDraw.Draw(canvas)
    f_big = ImageFont.truetype(FONT, 150)
    f_mid = ImageFont.truetype(FONT, 50)
    f_small = ImageFont.truetype(FONT, 46)
    outlined(d, (46, 300), "ERA MI", f_big, (255, 255, 255), (170, 0, 0), 10)
    outlined(d, (46, 450), "VOZ", f_big, (255, 255, 255), (170, 0, 0), 10)
    outlined(d, (52, 625), "ESTACIÓN UMBRA", f_mid, (200, 220, 255), (0, 0, 0), 4)
    d.rounded_rectangle((44, 40, 330, 112), radius=12, fill=(190, 0, 0))
    d.rounded_rectangle((60, 54, 116, 98), radius=6, outline=(255, 255, 255), width=4)
    d.ellipse((92, 64, 110, 82), outline=(255, 255, 255), width=3)
    d.line((66, 64, 84, 64), fill=(255, 255, 255), width=3)
    d.line((96, 54, 112, 40), fill=(255, 255, 255), width=3)
    d.text((128, 50), "3:00 AM", font=f_small, fill=(255, 255, 255))
    out = os.path.join(HERE, "youtube_thumbnail.png")
    canvas.save(out)
    print(out)


if __name__ == "__main__":
    main()
