#!/usr/bin/env python3
"""Miniatura de YouTube a partir de cuadros del render: thumbnail.png (1280x720) y thumbnail_1080p.png (1920x1080)"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'


def frame(t):
    s = int(t // 10) + 1
    out = os.path.join(tempfile.gettempdir(), f'thumb_{t}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t - (s - 1) * 10), '-i',
                    os.path.join(HERE, 'renders', f'scene_{s:02d}.mp4'), '-frames:v', '1', out], check=True)
    return Image.open(out).convert('RGB')


def glow_text(img, xy, text, font, fill, glow, stroke=10, blur=18, anchor='la'):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=font, fill=glow, stroke_width=stroke + 8, stroke_fill=glow, anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(5, 6, 14), anchor=anchor)


def main():
    # fondo: la mascara con ojos brillantes entre el fuego azul (escena 22), desplazada a la derecha
    base = frame(219.5)
    base = ImageEnhance.Contrast(base).enhance(1.12)
    img = Image.new('RGB', (W, H))
    img.paste(base.resize((int(W * 1.18), int(H * 1.18))).filter(ImageFilter.GaussianBlur(14)), (-200, -100))
    big = base.resize((int(W * 1.08), int(H * 1.08)))
    img.paste(big, (500, -20))
    img = img.convert('RGBA')
    # degradado oscuro a la izquierda para el texto
    grad = Image.new('L', (W, H))
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        a = max(0.0, 1 - x / (W * 0.58)) ** 1.2
        gd.line([(x, 0), (x, H)], fill=int(235 * a))
    shade = Image.new('RGBA', (W, H), (3, 6, 20, 255))
    shade.putalpha(grad)
    img.alpha_composite(shade)
    # vineta
    vig = Image.new('L', (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    dark.putalpha(Image.eval(vig, lambda v: 255 - v))
    img.alpha_composite(dark)
    # recuadro de un esqueleto/fuego azul (escena 16) abajo a la izquierda
    ins = frame(158).crop((180, 250, 1500, 1000)).resize((520, 296))
    ins = ImageEnhance.Brightness(ins).enhance(1.25)
    box = Image.new('RGBA', (532, 308), (255, 140, 30, 255))
    img.alpha_composite(box, (78, 722))
    img.paste(ins, (84, 728))

    f_tag = ImageFont.truetype(FONT, 58)
    f_big = ImageFont.truetype(FONT, 168)
    f_mid = ImageFont.truetype(FONT, 132)
    d = ImageDraw.Draw(img)
    # etiqueta superior naranja
    tag = 'MINECRAFT · HALLOWEEN'
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle((78, 60, 78 + tw + 56, 150), 18, fill=(255, 122, 20))
    d.text((106, 105), tag, font=f_tag, fill=(20, 8, 0), anchor='lm')
    glow_text(img, (70, 190), 'LA MÁSCARA', f_big, (255, 255, 255), (80, 170, 255, 210))
    glow_text(img, (78, 400), 'DEL ECO', f_mid, (120, 205, 255), (30, 120, 255, 200))
    glow_text(img, (78, 540), 'AZUL', f_mid, (120, 205, 255), (30, 120, 255, 200))
    full = img.convert('RGB')
    full.save(os.path.join(HERE, 'thumbnail_1080p.png'), optimize=True)
    full.resize((1280, 720), Image.LANCZOS).save(os.path.join(HERE, 'thumbnail.png'), optimize=True)
    print('ok thumbnail.png (1280x720) + thumbnail_1080p.png (1920x1080)')


if __name__ == '__main__':
    main()
