#!/usr/bin/env python3
"""Miniatura de YouTube de "El Jinete de la Calabaza Llameante": thumbnail_1080p.png (1920x1080) y thumbnail.png (1280x720)."""
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
    # fondo: primer plano de la calabaza llameante (escena 8), desplazado a la derecha
    base = frame(float(os.environ.get('T_MAIN', 73.0)))
    base = ImageEnhance.Contrast(base).enhance(1.1)
    img = Image.new('RGB', (W, H))
    img.paste(base.resize((int(W * 1.18), int(H * 1.18))).filter(ImageFilter.GaussianBlur(14)), (-200, -100))
    big = base.resize((int(W * 1.1), int(H * 1.1)))
    img.paste(big, (430, -40))
    img = img.convert('RGBA')
    grad = Image.new('L', (W, H))
    gd = ImageDraw.Draw(grad)
    for x in range(W):
        a = max(0.0, 1 - x / (W * 0.6)) ** 1.2
        gd.line([(x, 0), (x, H)], fill=int(230 * a))
    shade = Image.new('RGBA', (W, H), (14, 4, 2, 255))
    shade.putalpha(grad)
    img.alpha_composite(shade)
    vig = Image.new('L', (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    dark.putalpha(Image.eval(vig, lambda v: 255 - v))
    img.alpha_composite(dark)
    # recuadro: la caverna con fuego azul (escena 15)
    ins = frame(float(os.environ.get('T_INSET', 148.0))).crop((160, 120, 1760, 1020)).resize((520, 293))
    ins = ImageEnhance.Brightness(ins).enhance(1.15)
    img.alpha_composite(Image.new('RGBA', (532, 305), (60, 170, 255, 255)), (78, 722))
    img.paste(ins, (84, 728))
    f_tag = ImageFont.truetype(FONT, 56)
    f_big = ImageFont.truetype(FONT, 190)
    f_mid = ImageFont.truetype(FONT, 96)
    d = ImageDraw.Draw(img)
    tag = 'MINECRAFT · HALLOWEEN'
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle((78, 60, 78 + tw + 56, 148), 18, fill=(255, 122, 20))
    d.text((106, 104), tag, font=f_tag, fill=(20, 8, 0), anchor='lm')
    glow_text(img, (66, 175), 'EL JINETE', f_big, (255, 236, 200), (255, 110, 20, 220))
    glow_text(img, (76, 405), 'DE LA CALABAZA', f_mid, (255, 170, 60), (255, 70, 0, 200))
    glow_text(img, (76, 525), 'LLAMEANTE', f_mid, (255, 170, 60), (255, 70, 0, 200))
    full = img.convert('RGB')
    full.save(os.path.join(HERE, 'thumbnail_1080p.png'), optimize=True)
    full.resize((1280, 720), Image.LANCZOS).save(os.path.join(HERE, 'thumbnail.png'), optimize=True)
    print('ok thumbnail_1080p.png (1920x1080) + thumbnail.png (1280x720)')


if __name__ == '__main__':
    main()
