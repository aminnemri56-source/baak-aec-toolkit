"""Contact sheet to READ each camera before writing its note: renders brightened x1.6, 3x3 grid, view name.
usage: render_read_sheet.py renders_dir_or_view_dirs out.jpg [filter substring]
- renders_dir: a folder of <VIEW>.png, or a Codex out dir with <VIEW>/render.png subfolders."""
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance

SRC, OUT = sys.argv[1], sys.argv[2]
FLT = sys.argv[3] if len(sys.argv) > 3 else ""
items = []
for f in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, f)
    if f.lower().endswith(".png"):
        items.append((os.path.splitext(f)[0], p))
    elif os.path.isdir(p) and os.path.exists(os.path.join(p, "render.png")):
        items.append((f, os.path.join(p, "render.png")))
items = [(n, p) for n, p in items if FLT in n]
W = 760
ims = []
for n, p in items:
    im = ImageEnhance.Brightness(Image.open(p).convert("RGB")).enhance(1.6)
    im = im.resize((W, int(W * im.height / im.width)))
    d = ImageDraw.Draw(im)
    for k in (1, 2):
        d.line([(W * k // 3, 0), (W * k // 3, im.height)], fill=(0, 255, 255), width=1)
        d.line([(0, im.height * k // 3), (W, im.height * k // 3)], fill=(0, 255, 255), width=1)
    d.rectangle([0, 0, 200, 24], fill=(0, 0, 0))
    d.text((6, 6), n, fill=(255, 140, 60))
    ims.append(im)
if not ims:
    sys.exit("no renders")
h = max(i.height for i in ims)
cols = 2
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (cols * W + 10, rows * (h + 10)), (20, 20, 20))
for i, im in enumerate(ims):
    S.paste(im, ((i % cols) * (W + 10), (i // cols) * (h + 10)))
S.save(OUT, quality=86)
print(OUT, [n for n, _ in items])
