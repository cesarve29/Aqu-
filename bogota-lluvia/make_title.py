"""Opening title (1920x1080 RGBA): 'COLOMBIA' filled with the flag's bands
(yellow top half, blue, red) + a white subtitle.   python3 make_title.py title.png"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FONT_B = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_L = "/usr/share/fonts/opentype/inter/InterDisplay-Light.otf"
YEL, BLU, RED = (252, 209, 22), (0, 56, 147), (206, 17, 38)

word = "COLOMBIA"
fb = ImageFont.truetype(FONT_B, 150)
fl = ImageFont.truetype(FONT_L, 34)
# text mask, letter-spaced
spacing = 22
widths = [fb.getbbox(c)[2] - fb.getbbox(c)[0] for c in word]
total = sum(widths) + spacing * (len(word) - 1)
asc = fb.getbbox("COLOMBIA")
th = asc[3] - asc[1]
x0, y0 = (W - total) // 2, 430
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)
x = x0
for c, w in zip(word, widths):
    bb = fb.getbbox(c)
    md.text((x - bb[0], y0 - asc[1]), c, font=fb, fill=255)
    x += w + spacing
# flag bands over the glyph height: yellow 1/2, blue 1/4, red 1/4
fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(fill)
fd.rectangle([0, 0, W, y0 + th * 0.5], fill=YEL + (255,))
fd.rectangle([0, y0 + th * 0.5, W, y0 + th * 0.75], fill=BLU + (255,))
fd.rectangle([0, y0 + th * 0.75, W, H], fill=RED + (255,))
out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
# soft shadow for legibility over the rainy street
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.75)))
out = Image.alpha_composite(out, shadow)
txt = fill.copy()
txt.putalpha(mask)
out = Image.alpha_composite(out, txt)
# subtitle
sub = "BOGOTÁ   ·   CENTRO DE LA CIUDAD   ·   TORRE COLPATRIA"
sd = ImageDraw.Draw(out)
sb = sd.textbbox((0, 0), sub, font=fl)
sx, sy = (W - (sb[2] - sb[0])) // 2, y0 + th + 48
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(sh).text((sx, sy), sub, font=fl, fill=(0, 0, 0, 200))
out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(6)))
ImageDraw.Draw(out).text((sx, sy), sub, font=fl, fill=(255, 255, 255, 235))
out.save(sys.argv[1] if len(sys.argv) > 1 else "title.png")
print("title", total, th)
