"""Deterministic photographic grade measured on reference photographs (08/11/2026: "over exposed, bad contrast, colours bad").
Matches each image's luminance distribution (exposure + contrast, by percentiles) and its colour balance and
saturation (Lab a/b mean and spread) to the references, partially (strength), with a soft highlight roll-off.
Same settings for every image of a set = one consistent look; no AI re-interpretation.
usage: photo_grade.py out_dir --ref r1 r2 ... --in a.png b.png ... [--lum 0.8] [--col 0.5] [--sat 1.0] [--suffix _graded]"""
import argparse
import os

import numpy as np
from PIL import Image


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lab_to_srgb(lab):
    fy = (lab[..., 0] + 16) / 116
    fx, fz = fy + lab[..., 1] / 500, fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    Mi = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    c = xyz @ Mi.T
    c = np.where(c > 0.0031308, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055, 12.92 * c)
    return np.clip(c * 255, 0, 255)


def load(p, maxw=1200):
    im = Image.open(p).convert("RGB")
    if im.size[0] > maxw:
        im = im.resize((maxw, int(maxw * im.size[1] / im.size[0])))
    return srgb_to_lab(np.asarray(im, dtype=np.float64))


PCT = [1, 5, 15, 30, 50, 70, 85, 95, 99]


def stats(labs):
    L = np.concatenate([l[..., 0].ravel() for l in labs])
    a = np.concatenate([l[..., 1].ravel() for l in labs])
    b = np.concatenate([l[..., 2].ravel() for l in labs])
    return np.percentile(L, PCT), (a.mean(), a.std(), b.mean(), b.std())


ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--ref", nargs="+", required=True)
ap.add_argument("--in", dest="inp", nargs="+", required=True)
ap.add_argument("--lum", type=float, default=0.8)
ap.add_argument("--col", type=float, default=0.5)
ap.add_argument("--sat", type=float, default=1.0)
ap.add_argument("--suffix", default="")
ap.add_argument("--gain", type=float, default=1.0)   # 08/11 "THIS BUT MORE LIGHTED": exposure gain with a soft shoulder
A = ap.parse_args()
os.makedirs(A.out, exist_ok=True)
rp, (ram, ras, rbm, rbs) = stats([load(p) for p in A.ref])
print("ref L percentiles", np.round(rp, 1), "a/b", round(ram, 1), round(ras, 1), round(rbm, 1), round(rbs, 1))
for p in A.inp:
    im = Image.open(p).convert("RGB")
    lab = srgb_to_lab(np.asarray(im, dtype=np.float64))
    ip, (am, as_, bm, bs) = stats([lab])
    L = lab[..., 0]
    Lm = np.interp(L, ip, rp)                                   # luminance curve: this image's percentiles -> the refs'
    Lm = np.where(Lm > 88, 88 + (Lm - 88) * 0.55, Lm)           # soft highlight roll-off (no blown sun patches)
    L2 = L + A.lum * (Lm - L)
    a2 = lab[..., 1] + A.col * (((lab[..., 1] - am) / max(as_, 1e-3) * ras + ram) - lab[..., 1])
    b2 = lab[..., 2] + A.col * (((lab[..., 2] - bm) / max(bs, 1e-3) * rbs + rbm) - lab[..., 2])
    if A.col == 0:
        # hue-preserving: scale LINEAR rgb by the luminance ratio (darkening in Lab turns orange red; this keeps orange orange)
        rgb = np.asarray(im, dtype=np.float64) / 255.0
        lin = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
        Y1 = lin @ np.array([0.2126, 0.7152, 0.0722])
        f2 = (L2 + 16) / 116
        Y2 = np.where(f2 ** 3 > 0.008856, f2 ** 3, (f2 - 16 / 116) / 7.787)
        if A.gain != 1.0:
            Yg = Y2 * A.gain
            k = 0.7
            Y2 = np.where(Yg > k, k + (Yg - k) / (1 + (Yg - k) / (1 - k)), Yg)   # soft shoulder: no blown whites
        lin2 = lin * (Y2 / np.maximum(Y1, 1e-5))[..., None]
        Yn = lin2 @ np.array([0.2126, 0.7152, 0.0722])
        lin2 = Yn[..., None] + A.sat * (lin2 - Yn[..., None])          # saturation around the pixel's own luminance
        lin2 = np.clip(lin2, 0, 1)
        out = (np.where(lin2 > 0.0031308, 1.055 * lin2 ** (1 / 2.4) - 0.055, 12.92 * lin2) * 255).astype(np.uint8)
    else:
        out = lab_to_srgb(np.stack([L2, a2 * A.sat, b2 * A.sat], -1)).astype(np.uint8)
    name = os.path.splitext(os.path.basename(p))[0] + A.suffix + ".png"
    if os.path.basename(os.path.dirname(p)).startswith("CU_"):
        name = os.path.basename(os.path.dirname(os.path.dirname(p))) + "_" + os.path.basename(os.path.dirname(p)) + A.suffix + ".png"
    elif name.startswith("photo"):
        name = os.path.basename(os.path.dirname(p)) + "_hero" + A.suffix + ".png"
    Image.fromarray(out).save(os.path.join(A.out, name))
    print(name, "L p50 %.1f -> %.1f" % (ip[4], np.median(L2)))
