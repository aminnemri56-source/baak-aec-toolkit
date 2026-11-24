"""Bulk review: render | photo pairs, 4 views per sheet, for every view folder under out_dir that has the photo.
usage: pairs_sheet.py out_dir [photo relative path, default photo.png] -> out_dir/_PAIRS_<n>.jpg (prints the files)"""
import os
import sys

from PIL import Image, ImageDraw

OUT = sys.argv[1]
REL = sys.argv[2] if len(sys.argv) > 2 else "photo.png"
W = 760
views = sorted(d for d in os.listdir(OUT) if os.path.exists(os.path.join(OUT, d, REL)))
rows = []
for v in views:
    pr = []
    for p, t in ((os.path.join(OUT, v, "render.png"), "render"), (os.path.join(OUT, v, REL), REL)):
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        im = im.resize((W, int(im.height * W / im.width)))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 260, 22], fill=(0, 0, 0))
        d.text((6, 5), f"{v[9:]}  {t}", fill=(238, 90, 30))
        pr.append(im)
    rows.append(pr)
for n in range(0, len(rows), 4):
    chunk = rows[n:n + 4]
    h = max(i.height for r in chunk for i in r)
    s = Image.new("RGB", (2 * W + 10, len(chunk) * (h + 10)), (20, 20, 20))
    for k, r in enumerate(chunk):
        for c, im in enumerate(r):
            s.paste(im, (c * (W + 10), k * (h + 10)))
    f = os.path.join(OUT, "_PAIRS_%d.jpg" % (n // 4 + 1))
    s.save(f, quality=85)
    print(f, [v[9:] for v in views[n:n + 4]])
