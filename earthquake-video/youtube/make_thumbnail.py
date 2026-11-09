# Builds the 1280x720 YouTube thumbnail from clean renders (MODE=h Q=clean node snap.js <dir> 1695 3230)
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
src, out = sys.argv[1], sys.argv[2]
F = '/usr/share/fonts/opentype/inter/'
W, H = 1280, 720
bg = Image.open(f'{src}/f01695.jpg').convert('RGB')
# crop towards the collapsing building (right side)
bg = bg.crop((0, 60, 1440, 870)).resize((W, H), Image.LANCZOS)
bg = ImageEnhance.Contrast(bg).enhance(1.15)
bg = ImageEnhance.Color(bg).enhance(1.15)
# left dark gradient for text + warm tint
grad = Image.new('L', (W, H))
gd = ImageDraw.Draw(grad)
for x in range(W):
    a = max(0, 1 - x / (W * 0.66)) ** 1.1
    gd.line([(x, 0), (x, H)], fill=int(225 * a))
dark = Image.new('RGB', (W, H), (12, 8, 6))
img = Image.composite(dark, bg, grad)
d = ImageDraw.Draw(img)

def text(xy, s, size, fill, font='InterDisplay-Black.otf', stroke=0, sfill=(0, 0, 0), shadow=True):
    f = ImageFont.truetype(F + font, size)
    if shadow:
        sh = Image.new('RGBA', (W, H)); sd = ImageDraw.Draw(sh)
        sd.text((xy[0] + 6, xy[1] + 8), s, font=f, fill=(0, 0, 0, 200), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        img.paste(sh.filter(ImageFilter.GaussianBlur(7)), (0, 0), sh.filter(ImageFilter.GaussianBlur(7)))
    d.text(xy, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return d.textbbox(xy, s, font=f, stroke_width=stroke)

text((58, 40), '¿Y SI HUBIERA UN', 60, (255, 255, 255), 'InterDisplay-ExtraBold.otf')
b = text((50, 102), 'TERREMOTO', 126, (255, 210, 40), stroke=3, sfill=(40, 20, 0))
# big "MAGNITUD 10" with red badge
f = ImageFont.truetype(F + 'InterDisplay-Black.otf', 104)
s = 'MAGNITUD 10?'
bb = d.textbbox((0, 0), s, font=f)
bx, by = 50, 250
d.rounded_rectangle((bx - 6, by + bb[1] - 22, bx + bb[2] + 34, by + bb[3] + 24), 18, fill=(214, 28, 28))
text((bx + 14, by), s, 104, (255, 255, 255), shadow=False)
text((60, 470), '?', 0, (0, 0, 0), shadow=False) if False else None
text((58, 668), 'Lo que nunca ha pasado… todavía', 34, (235, 235, 235), 'InterDisplay-Bold.otf')

# tsunami inset bottom-right
ts = Image.open(f'{src}/f03230.jpg').convert('RGB').crop((380, 180, 1700, 920)).resize((420, 236), Image.LANCZOS)
ts = ImageEnhance.Contrast(ts).enhance(1.15)
ix, iy = 56, 405
sh = Image.new('RGBA', (W, H)); ImageDraw.Draw(sh).rounded_rectangle((ix, iy + 8, ix + 428, iy + 250), 16, fill=(0, 0, 0, 190))
sh = sh.filter(ImageFilter.GaussianBlur(10)); img.paste(sh, (0, 0), sh)
d.rounded_rectangle((ix - 6, iy - 6, ix + 426, iy + 242), 18, fill=(255, 255, 255))
mask = Image.new('L', ts.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, *ts.size), 13, fill=255)
img.paste(ts, (ix, iy), mask)
fb = ImageFont.truetype(F + 'InterDisplay-Black.otf', 34)
lb = d.textbbox((0, 0), 'TSUNAMI', font=fb)
d.rounded_rectangle((ix + 14, iy + 14, ix + 14 + lb[2] + 28, iy + 14 + lb[3] + 18), 10, fill=(214, 28, 28))
d.text((ix + 28, iy + 20), 'TSUNAMI', font=fb, fill=(255, 255, 255))
img.save(out, quality=95)
