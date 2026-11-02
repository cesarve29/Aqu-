import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from PIL import Image, ImageDraw
import render, story
names = sys.argv[1:] or [s[0] for s in story.SCENES]
sr = render.SceneRenderer(320, 180)
tl, _ = story.timeline()
out = os.path.join(render.OUT, "qa_new"); os.makedirs(out, exist_ok=True)
imgs = []
for sc in tl:
    if sc["name"] not in names: continue
    t = 0.5
    while t < sc["dur"]:
        imgs.append((sc["start"] + t, Image.fromarray(sr.frame(sc, t, {}))))
        t += 1.0
sr.close()
C, R = 8, 6
for s in range(0, len(imgs), C * R):
    sheet = Image.new("RGB", (C * 320, R * 180)); d = ImageDraw.Draw(sheet)
    for i, (T, im) in enumerate(imgs[s:s + C * R]):
        x, y = (i % C) * 320, (i // C) * 180
        sheet.paste(im, (x, y)); d.text((x + 3, y + 3), "%d:%04.1f" % (T // 60, T % 60), fill=(255, 255, 0))
    sheet.save(os.path.join(out, "sheet_%s_%02d.jpg" % ("_".join(names) if len(names) < 4 else "all", s // (C * R))))
print("sheets", (len(imgs) + C * R - 1) // (C * R))
