#!/usr/bin/env python3
"""Miniatura de YouTube (1280x720) a partir de dos cuadros renderizados en Cycles.

Izquierda: el hombre encapuchado iluminado por el verde de la radio.
Derecha: la cara pegada al vidrio escarchado.
Requiere haber renderizado:
    UMBRA_W=1280 UMBRA_H=720 UMBRA_SAMPLES=48 UMBRA_OUT=build/thumb python3 scenes.py --shot 4 --still 12.0
    UMBRA_W=1280 UMBRA_H=720 UMBRA_SAMPLES=48 UMBRA_OUT=build/thumb python3 scenes.py --shot 8 --still 1.3
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
    left = grade(Image.open(os.path.join(T, "still_04_12.00.png")).convert("RGB"))
    right = grade(Image.open(os.path.join(T, "still_08_1.30.png")).convert("RGB"))
    # recortes: la cara ocupa la mitad derecha, ampliada
    rw, rh = right.size
    right = right.crop((int(rw * 0.28), int(rh * 0.05), int(rw * 0.98), int(rh * 0.95))).resize((800, 720), Image.LANCZOS)
    lw, lh = left.size
    left = left.crop((int(lw * 0.1), 0, int(lw * 0.75), lh)).resize((640, 720), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(left, (0, 0))
    # mascara diagonal para la mitad derecha
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(560, 0), (W, 0), (W, H), (440, H)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(6))
    rlayer = Image.new("RGB", (W, H))
    rlayer.paste(right, (480, 0))
    canvas = Image.composite(rlayer, canvas, mask)
    # grieta luminosa en el corte
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line([(560, 0), (440, H)], fill=(255, 60, 30), width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(5))
    canvas = Image.blend(canvas, Image.composite(glow, canvas, glow.convert("L")), 0.85)
    # vinieta
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-200, -160, W + 200, H + 160), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    canvas = Image.composite(canvas, Image.new("RGB", (W, H), (0, 0, 0)), vig)

    d = ImageDraw.Draw(canvas)
    f_big = ImageFont.truetype(FONT, 132)
    f_small = ImageFont.truetype(FONT, 46)
    outlined(d, (40, 470), "ERA MI", f_big, (255, 255, 255), (170, 0, 0), 9)
    outlined(d, (40, 590), "VOZ", f_big, (255, 255, 255), (170, 0, 0), 9)
    # etiqueta 3:00 AM con una pequena radio dibujada
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
