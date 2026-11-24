"""grade_views.py (skill archviz-shots): colour-correct every render view ON ITS OWN and write the image Codex should receive.

usage: grade_views.py <renders dir> <out dir> [--watch N] [--since EPOCH] [--overrides file.json] [--only NAME,NAME]

Per view, in linear light:
  1. white balance from the view's own least-saturated mid/bright surfaces (lamps left out), applied at 65 % and limited to -20/+25 %,
     skipped when the view has no neutral surface at all (an all-terracotta room keeps its colour);
  2. exposure: bright surfaces (90th percentile) to 78 %, the median kept between 26 % and 52 %, never more than +1.4 / -0.7 stop;
  3. highlights rolled off on luminance, never per channel, so a lit orange stays orange instead of turning yellow;
  4. a small toe on very dark views so black machines and lockers keep their shape;
  5. light sharpening.
It then measures the result (clipping, darkness, sharpness, noise, hue of the oranges) and gives each view a verdict.
Writes <out>/<name>.png (what goes to Codex), <out>/grade_report.json and <out>/_SHEETS/GRADE_SHEET_n.jpg (before | after).
--watch N keeps running until N views are graded (renders are taken as soon as their file stops growing), so Codex can be fed from <out>.
overrides.json: {"VIEW": {"ev": 0.3, "warm": -6, "wb": false, "skip": true}}  (ev in stops, warm in % red/blue, wb false = no balance)."""
import json
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
ARGS = sys.argv[3:]


def opt(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


WATCH = int(opt("--watch", 0))
SINCE = float(opt("--since", 0))
OVR = json.load(open(opt("--overrides"), encoding="utf-8")) if opt("--overrides") else {}
ONLY = set(opt("--only", "").split(",")) - {""}
os.makedirs(os.path.join(OUT, "_SHEETS"), exist_ok=True)
REPORT = os.path.join(OUT, "grade_report.json")
report = json.load(open(REPORT, encoding="utf-8")) if os.path.exists(REPORT) else {}
LUM = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def dec(v):  # sRGB -> linear
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4).astype(np.float32)


def enc(v):  # linear -> sRGB
    v = np.clip(v, 0, None)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055).astype(np.float32)


def orange_hue(rgb8):
    """mean hue (degrees) of the saturated oranges of the view, or None"""
    a = rgb8[::4, ::4].astype(np.float32) / 255.0
    mx, mn = a.max(-1), a.min(-1)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where((mx == r) & (mx > mn), 60.0 * (g - b) / (mx - mn), -999.0)
        s = np.where(mx > 0, (mx - mn) / mx, 0)
    m = (h > 2) & (h < 42) & (s > 0.55) & (mx > 0.35)
    return (float(h[m].mean()), float(m.mean())) if m.mean() > 0.004 else (None, 0.0)


def metrics(rgb8):
    a = rgb8.astype(np.float32) / 255.0
    y = a @ LUM
    sub = y[::3, ::3]
    lamp = a.max(-1)[::3, ::3] >= 0.985
    half = y[::2, ::2]
    lap = half[1:-1, 1:-1] * 4 - half[:-2, 1:-1] - half[2:, 1:-1] - half[1:-1, :-2] - half[1:-1, 2:]
    # noise: high-pass energy in the flattest blocks
    hh, ww = (lap.shape[0] // 16) * 16, (lap.shape[1] // 16) * 16
    blk = np.abs(lap[:hh, :ww]).reshape(hh // 16, 16, ww // 16, 16).mean((1, 3))
    return dict(p50=round(float(np.percentile(sub, 50)), 3), p99=round(float(np.percentile(sub, 99)), 3),
                burnt=round(float(lamp.mean()) * 100, 2), black=round(float((sub < 0.02).mean()) * 100, 2),
                sharp=round(float(lap.var()) * 1e4, 2), noise=round(float(np.percentile(blk, 20)) * 1e3, 3))


def grade(path, name):
    o = OVR.get(name, {})
    src8 = np.asarray(Image.open(path).convert("RGB"))
    lin = dec(src8.astype(np.float32) / 255.0)
    disp = src8.astype(np.float32) / 255.0
    lamp = disp.max(-1) >= 0.98
    yd0 = disp @ LUM
    info = dict(before=metrics(src8))
    h0, share = orange_hue(src8)
    # 1. white balance on the view's own neutrals
    gains, wb_note = np.ones(3, dtype=np.float32), "kept"
    strength = 0.65
    if o.get("wb", True):
        mx, mn = disp.max(-1), disp.min(-1)
        sat = (mx - mn) / (mx + 1e-6)
        cand = (yd0 > 0.18) & (yd0 < 0.92) & ~lamp
        if cand.mean() > 0.015:
            thr = max(float(np.percentile(sat[cand][::7], 4)), 0.10)  # the least saturated 4 % (white letters, a pale floor, staff), or all below 10 %
            neu = cand & (sat <= thr)
            if thr <= 0.30 and neu.mean() > 0.002:
                n = lin[neu].mean(0)
                g = (n @ LUM) / np.maximum(n, 1e-6)
                gains = np.clip(g ** strength, 0.80, 1.25).astype(np.float32)
                gains /= float(gains @ LUM)  # keep the brightness
                wb_note = "balanced" + (" (limit reached)" if (np.abs(g ** strength - np.clip(g ** strength, 0.80, 1.25)) > 0.01).any() else "")
            else:
                wb_note = "no neutral surface, colour kept"
    if "warm" in o:
        k = 1 + o["warm"] / 100.0
        gains = gains * np.array([k, 1.0, 1 / k], dtype=np.float32)

    def run(gains):
        x = lin * gains
        y = x @ LUM
        ys = y[~lamp][::11] if (~lamp).any() else y.ravel()[::11]
        p50, p90, p98 = np.percentile(ys, 50), np.percentile(ys, 90), np.percentile(ys, 98)
        g = float(dec(np.float32(0.78)) / max(p90, 1e-4))
        g = min(g, float(dec(np.float32(0.93)) / max(p98, 1e-4)))  # a pale floor or a window must not burn to lift the rest
        if float(enc(np.float32(p50 * g))) > 0.52:
            g *= float(dec(np.float32(0.52)) / max(p50 * g, 1e-5))
        g = float(np.clip(g, 0.62, 2.64)) * 2.0 ** o.get("ev", 0.0)
        med = float(enc(np.float32(p50 * g)))
        gamma = float(np.clip(np.log(0.26) / np.log(max(med, 1e-3)), 0.72, 1.0)) if med < 0.26 else 1.0  # dark view: lift the middle, keep the whites
        x = x * g
        y = np.maximum(x @ LUM, 1e-6)
        # highlight roll-off on luminance
        k = 0.72
        y2 = np.where(y > k, k + (1 - k) * (1 - np.exp(-(y - k) / (1 - k))), y)
        # toe for very dark views
        yd = enc(y2)
        if gamma < 1.0:
            yd = np.power(np.clip(yd, 0, 1), gamma)
        if np.percentile(yd[::9, ::9], 10) < 0.06:
            t = 0.25
            u = np.clip(yd / t, 0, 1)
            yd = yd + 0.6 * t * u * (1 - u) ** 2
        y2 = dec(yd)
        x = x * (y2 / y)[..., None]
        # bring out-of-range colours back along their own hue
        m = x.max(-1)
        over = m > 1.0
        if over.any():
            yy = np.minimum(y2, 0.999)
            tt = np.where(over, (1.0 - yy) / np.maximum(m - yy, 1e-6), 1.0)
            x = yy[..., None] + (x - yy[..., None]) * tt[..., None]
        return (np.clip(enc(x), 0, 1) * 255 + 0.5).astype(np.uint8), g

    out8, g = run(gains)
    h1, _ = orange_hue(out8)
    if h0 is not None and h1 is not None and abs(h1 - h0) > 5.0:  # the balance pulled the brand orange: halve it
        gains = np.sqrt(gains).astype(np.float32)
        gains /= float(gains @ LUM)
        out8, g = run(gains)
        h1, _ = orange_hue(out8)
        wb_note += ", halved to hold the orange"
    im = Image.fromarray(out8).filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
    if max(im.size) > 3072:
        s = 3072 / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    im.save(os.path.join(OUT, name + ".png"), optimize=False)
    info.update(after=metrics(np.asarray(im)), ev=round(float(np.log2(g)), 2), wb=[round(float(v), 3) for v in gains], wb_note=wb_note,
                orange_hue_before=None if h0 is None else round(h0, 1), orange_hue_after=None if h1 is None else round(h1, 1),
                orange_share=round(share * 100, 1), size=list(im.size), source=path.replace("\\", "/"))
    v = []
    b, a = info["before"], info["after"]
    if info["ev"] > 1.15:
        v.append("RE-RENDER BRIGHTER (pushed %+.1f stop, noise and banding rise)" % info["ev"])
    if b["burnt"] > 6.0:
        v.append("BURNT AREAS %.0f %% (window or lamp: lower the exposure of this view)" % b["burnt"])
    if a["black"] > 30.0:
        v.append("TOO BLACK (%.0f %% without detail)" % a["black"])
    if h1 is not None and h1 > 27.0:
        v.append("ORANGE READS YELLOW (hue %.0f, brand 17)" % h1)
    if h1 is not None and h1 < 8.0:
        v.append("ORANGE READS RED (hue %.0f, brand 17)" % h1)
    if "limit reached" in wb_note:
        v.append("STRONG CAST (balance stopped at its limit)")
    info["verdict"] = v or ["OK"]
    return info, Image.fromarray(src8), im


def sheets():
    names = sorted(report)
    for n0 in range(0, len(names), 4):
        rows = []
        for nm in names[n0:n0 + 4]:
            r = report[nm]
            try:
                a = Image.open(r["source"]).convert("RGB")
                b = Image.open(os.path.join(OUT, nm + ".png")).convert("RGB")
            except Exception:
                continue
            w = 640
            h = round(a.height * w / a.width)
            row = Image.new("RGB", (w * 2 + 6, h + 22), (18, 18, 18))
            row.paste(a.resize((w, h)), (0, 22))
            row.paste(b.resize((w, h)), (w + 6, 22))
            ImageDraw.Draw(row).text((6, 5), "%s | render -> Codex input | %+.2f stop | balance R %.2f G %.2f B %.2f (%s) | %s" % (
                nm, r["ev"], r["wb"][0], r["wb"][1], r["wb"][2], r["wb_note"], "; ".join(r["verdict"])), fill=(238, 90, 30))
            rows.append(row)
        if rows:
            s = Image.new("RGB", (rows[0].width, sum(x.height for x in rows) + 6 * (len(rows) - 1)), "white")
            y = 0
            for x in rows:
                s.paste(x, (0, y))
                y += x.height + 6
            s.save(os.path.join(OUT, "_SHEETS", "GRADE_SHEET_%02d.jpg" % (n0 // 4 + 1)), quality=86)


def todo(sizes):
    res = []
    for f in sorted(os.listdir(SRC)) if os.path.isdir(SRC) else []:
        if not f.lower().endswith(".png"):
            continue
        nm, p = f[:-4], os.path.join(SRC, f)
        if ONLY and nm not in ONLY:
            continue
        if OVR.get(nm, {}).get("skip") or os.path.getmtime(p) < SINCE:
            continue
        s = os.path.getsize(p)
        stable = not WATCH or (sizes.get(f) == s and s > 100000)
        sizes[f] = s
        if stable and (nm not in report or report[nm].get("mtime") != os.path.getmtime(p)):
            res.append((nm, p))
    return res


sizes, t0 = {}, time.time()
while True:
    new = todo(sizes)
    for nm, p in new:
        try:
            info, _, _ = grade(p, nm)
        except Exception as e:  # a file still being written: next round
            print(nm, "not readable yet:", type(e).__name__, flush=True)
            continue
        info["mtime"] = os.path.getmtime(p)
        report[nm] = info
        print(time.strftime("%H:%M:%S"), nm, "| %+.2f stop | balance %s (%s) | %s" % (info["ev"], info["wb"], info["wb_note"], "; ".join(info["verdict"])), flush=True)
    if new:
        json.dump(report, open(REPORT, "w", encoding="utf-8"), indent=1)
        sheets()
    if not WATCH or len(report) >= WATCH or time.time() - t0 > 5 * 3600:
        break
    time.sleep(6)
if report:
    sh = np.median([r["after"]["sharp"] for r in report.values()])
    no = np.median([r["after"]["noise"] for r in report.values()])
    for nm, r in report.items():
        if r["after"]["sharp"] < 0.4 * sh and "SOFT" not in " ".join(r["verdict"]):
            r["verdict"] = [x for x in r["verdict"] if x != "OK"] + ["SOFT (sharpness %.1f, batch %.1f)" % (r["after"]["sharp"], sh)]
        if r["after"]["noise"] > 2.2 * no and "NOISY" not in " ".join(r["verdict"]):
            r["verdict"] = [x for x in r["verdict"] if x != "OK"] + ["NOISY (%.2f, batch %.2f): more samples" % (r["after"]["noise"], no)]
    json.dump(report, open(REPORT, "w", encoding="utf-8"), indent=1)
    sheets()
bad = {k: v["verdict"] for k, v in report.items() if v["verdict"] != ["OK"]}
print(len(report), "views graded ->", OUT, "|", len(bad), "to look at:", json.dumps(bad, ensure_ascii=False))
