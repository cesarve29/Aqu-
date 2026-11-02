"""YouTube thumbnail: a ray-traced still of Tilo with the relit star plus the title."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import render
from render import SceneRenderer, scene_by_name, OUT, FONT_TITLE, shadowed_text

sr = SceneRenderer(1280, 720)
img = Image.fromarray(sr.frame(scene_by_name("s12"), 31.5, {}))
sr.close()
img = img.convert("RGBA")
W, H = img.size
f1 = ImageFont.truetype(FONT_TITLE, 92)
f2 = ImageFont.truetype(FONT_TITLE, 60)
shadowed_text(img, (W * 0.5, H * 0.13), "Tilo y la Estrella", f1, glow=(255, 190, 90, 200), shadow=8)
shadowed_text(img, (W * 0.5, H * 0.88), "Un cuento de Navidad", f2, fill=(255, 255, 255), glow=(120, 180, 255, 160), shadow=6)
img.convert("RGB").save(os.path.join(OUT, "miniatura_youtube.png"))
print("ok")
