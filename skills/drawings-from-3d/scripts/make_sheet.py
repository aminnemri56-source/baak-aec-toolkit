"""Run AutoCAD's core console to turn compose.py's sheet_data.lsp into a DWG sheet (BAAK cartouche layout) + PDF.

usage: python -I make_sheet.py out_dir base.dwg template.dwg template_layout result.dwg result.pdf
out_dir holds sheet_data.lsp + sheet.json from compose.py. The base DWG is copied, never modified; result files must not exist yet."""
import sys, os, json, shutil, subprocess, glob

OUT, BASE, TPL_DWG, TPL, RES_DWG, RES_PDF = sys.argv[1:7]
for p in (RES_DWG, RES_PDF):
    if os.path.exists(p): sys.exit("exists, not overwriting: " + p)
sh = json.load(open(os.path.join(OUT, "sheet.json"), encoding="utf-8"))
work = os.path.join(OUT, "acc"); os.makedirs(work, exist_ok=True)
base = os.path.join(work, "base.dwg"); shutil.copy2(BASE, base)
tmp_dwg, tmp_pdf = os.path.join(work, "sheet.dwg"), os.path.join(work, "sheet.pdf")
for p in (tmp_dwg, tmp_pdf):
    if os.path.exists(p): os.remove(p)
fw = lambda p: p.replace("\\", "/")
def mt(s):                                    # non-ASCII -> MTEXT unicode escapes (safe whatever the console code page)
    return "".join(c if ord(c) < 128 else "\\U+%04X" % ord(c) for c in s)
def q(s): return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
# text in the data file: escape accents once here
data = open(os.path.join(OUT, "sheet_data.lsp"), encoding="utf-8").read()
data = "".join(c if ord(c) < 128 else "\\\\U+%04X" % ord(c) for c in data)
open(os.path.join(work, "sheet_data_ascii.lsp"), "w", encoding="ascii").write(data)
x1, y1, x2, y2 = sh["vp"]
cfg = f"""(setq bs-data {q(fw(os.path.join(work, 'sheet_data_ascii.lsp')))} bs-tpl-dwg {q(fw(TPL_DWG))} bs-tpl {q(TPL)} bs-name {q(sh['name'])}
      bs-title {q(mt(sh['title']))} bs-doc {q(mt(sh['doc']))} bs-niv {q(mt(sh['niveau']))} bs-date {q(sh['date'])}
      bs-vp (list {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f}) bs-cx {sh['centre'][0]:.4f} bs-cy {sh['centre'][1]:.4f} bs-vh {sh['height']:.4f}
      bs-pdf {q(fw(tmp_pdf))} bs-dwg {q(fw(tmp_dwg))})
"""
open(os.path.join(work, "sheet_cfg.lsp"), "w", encoding="ascii").write(cfg)
here = fw(os.path.dirname(os.path.abspath(__file__)))
scr = os.path.join(work, "sheet.scr")
open(scr, "w", encoding="ascii").write(f'FILEDIA\n0\n(load "{fw(os.path.join(work, "sheet_cfg.lsp"))}")\n(load "{here}/build_sheet.lsp")\n_.QUIT\n_Y\n')
acc = sorted(glob.glob(r"C:\Program Files\Autodesk\AutoCAD 20*\accoreconsole.exe"))[-1]
log = os.path.join(work, "sheet.log")
with open(log, "wb") as lf:
    p = subprocess.run([acc, "/i", base, "/s", scr, "/l", "en-US"], stdout=lf, stderr=subprocess.STDOUT, timeout=1800)
txt = open(log, "rb").read().decode("utf-16-le", "ignore") if open(log, "rb").read(2) == b"\xff\xfe" else open(log, "rb").read().decode("latin1", "ignore")
txt = txt.replace("\x00", "")
for line in txt.splitlines():
    if any(k in line for k in ("MZLOG", "error", "Error", "Invalid", "Unknown command")): print("console:", line.strip()[:200])
if not os.path.exists(tmp_dwg): sys.exit("no DWG written, see " + log)
os.makedirs(os.path.dirname(RES_DWG), exist_ok=True); os.makedirs(os.path.dirname(RES_PDF), exist_ok=True)
shutil.copy2(tmp_dwg, RES_DWG)
if os.path.exists(tmp_pdf): shutil.copy2(tmp_pdf, RES_PDF)
print("dwg", RES_DWG, os.path.getsize(RES_DWG)); print("pdf", RES_PDF, os.path.getsize(RES_PDF) if os.path.exists(RES_PDF) else "MISSING")
