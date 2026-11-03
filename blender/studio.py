"""Vista de estudio del personaje (espalda, perfil, 3/4 frontal, primer plano)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, math
import film
from PIL import Image
out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp/studio.png'
pct = int(sys.argv[sys.argv.index('--') + 2]) if '--' in sys.argv and len(sys.argv) > sys.argv.index('--') + 2 else 40
s = film.reset()
film.world_color((0.035, 0.04, 0.055), 1)
fig = film.Figure(hood_up=False)
tgt = film.empty('T', (0, 0, 1.05)); tgh = film.empty('TH', (0, 0.03, 1.66))
film.area_light('Key', (2.5, -2.5, 3), tgt, (1, 0.95, 0.9), 900, 2)
film.area_light('RimC', (-2, 2.5, 2.5), tgt, (0.3, 0.85, 1), 700, 1.5)
film.area_light('RimM', (2, 2.5, 2.2), tgt, (1, 0.3, 0.7), 500, 1.5)
film.area_light('Fill', (-3, -2, 1.5), tgt, (0.6, 0.7, 1), 150, 3)
s.render.resolution_x, s.render.resolution_y = 1000, 1400
s.render.resolution_percentage = pct; s.eevee.taa_render_samples = 16
views = [((0.4, -4.6, 1.2), tgt, 45), ((4.6, 0.2, 1.2), tgt, 45), ((-2.6, 3.8, 1.3), tgt, 45),
         ((0.55, -1.1, 1.72), tgh, 60)]
ims = []
for i, (loc, t, lens) in enumerate(views):
    cam = film.camera('C%d' % i, loc, t, lens=lens, fstop=16)
    s.camera = cam
    p = out.replace('.png', '_%d.png' % i)
    s.render.filepath = p
    bpy.ops.render.render(write_still=True)
    ims.append(Image.open(p))
W = sum(i.width for i in ims); H = ims[0].height
sheet = Image.new('RGB', (W, H)); x = 0
for im in ims:
    sheet.paste(im, (x, 0)); x += im.width
sheet.save(out)
print('SHEET', out)
