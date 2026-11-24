"""Draw the outlines of a same-camera esquisse on top of a photo, so faults against the design are visible at a glance
(for the review) and can be shown to Codex as a comment image. The esquisse must have the render's framing.
usage: esq_overlay.py photo.png esquisse.png out.png [--side out_side.jpg]
out.png: the photo with the esquisse edges in bright green (2 px); --side: esquisse | photo | overlay sheet."""
import sys

import numpy as np
from PIL import Image, ImageFilter

ph_p, es_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
ph = Image.open(ph_p).convert("RGB")
es = Image.open(es_p).convert("RGB").resize(ph.size, Image.LANCZOS)
g = np.asarray(es.convert("L").filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)
gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
edge = (np.maximum(gx, gy) > 22).astype(np.uint8) * 255
m = Image.fromarray(edge).filter(ImageFilter.MaxFilter(3))
arr = np.asarray(ph).copy()
mk = np.asarray(m) > 0
arr[mk] = (0.25 * arr[mk] + 0.75 * np.array([40, 255, 90])).astype(np.uint8)
Image.fromarray(arr).save(out)
if "--side" in sys.argv:
    o = sys.argv[sys.argv.index("--side") + 1]
    w, h = 900, int(900 * ph.size[1] / ph.size[0])
    s = Image.new("RGB", (3 * w + 20, h), (25, 25, 25))
    for i, im in enumerate((es, ph, Image.fromarray(arr))):
        s.paste(im.resize((w, h)), (i * (w + 10), 0))
    s.save(o, quality=88)
print(out)
