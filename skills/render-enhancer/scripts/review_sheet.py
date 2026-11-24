"""Review sheet for one Codex job: render and photo side by side on top, then the photo's four quarters at full detail
(people, hands, machines and edges are judged there). usage: review_sheet.py job_dir [photo file name] -> job_dir/_REVIEW_<photo>.jpg"""
import os
import sys

from PIL import Image, ImageDraw

D = sys.argv[1]
P = sys.argv[2] if len(sys.argv) > 2 else "photo.png"
W = 1600
ph = Image.open(os.path.join(D, P)).convert("RGB")
rp = os.path.join(D, "render.png")
top = []
for im, t in ([(Image.open(rp).convert("RGB"), "RENDER")] if os.path.exists(rp) else []) + [(ph, P)]:
    im = im.resize((W // 2 - 5, int(im.height * (W // 2 - 5) / im.width)))
    ImageDraw.Draw(im).text((10, 10), t, fill=(238, 90, 30))
    top.append(im)
th = max(i.height for i in top)
w, h = ph.size
quads = [ph.crop((x, y, x + w // 2, y + h // 2)) for y in (0, h // 2) for x in (0, w // 2)]
qw = W // 2 - 5
quads = [q.resize((qw, int(q.height * qw / q.width))) for q in quads]
qh = quads[0].height
s = Image.new("RGB", (W, th + 10 + 2 * (qh + 10)), (20, 20, 20))
for i, im in enumerate(top):
    s.paste(im, (i * (W // 2 + 5), 0))
for i, q in enumerate(quads):
    s.paste(q, ((i % 2) * (qw + 10), th + 10 + (i // 2) * (qh + 10)))
out = os.path.join(D, "_REVIEW_%s.jpg" % os.path.splitext(P)[0])
s.save(out, quality=88)
print(out)
