"""AutoCAD (COM) and DCE file tools for the BAAK DCE agent.

Rules enforced here, not only in the prompt:
  * nothing is ever written to G: (Google Drive) - drawings on G: open read-only;
  * files and drawings are saved only under D:\\DCE SITE;
  * geometry is drawn as LWPOLYLINE on layers that already exist in the drawing;
  * every change to a drawing asks the user first (unless the agent runs with --auto) and is logged.
"""

import csv
import datetime
import json
import os
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT
from anthropic import beta_tool
from anthropic.lib.tools import ToolError

WRITE_ROOT = Path(r"D:\DCE SITE")
READ_ROOTS = [WRITE_ROOT, Path(r"G:\Mon Drive\@@BAAK CLOUD 2026"), Path(r"D:\PROJECT_models")]
REVIT_COMPARE_CSV = WRITE_ROOT / "ARCHITECTURE" / "REVIT_REF" / "_compare" / "revit_elements_vs_max_categorised.csv"
LOG_DIR = Path.home() / ".dce-agent" / "logs"
AUTO_APPROVE = False   # set by agent.py --auto


# ---------- helpers ----------

def _log(action, detail):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_DIR / f"journal_{datetime.date.today():%Y-%m-%d}.txt", "a", encoding="utf-8") as f:
        f.write(f"{stamp} | {action} | {detail}\n")


def _confirm(what):
    """Ask the user before any change to a drawing or a file."""
    if AUTO_APPROVE:
        return True
    print(f"\n  >> L'agent veut : {what}")
    return input("     Appliquer ? [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


def _check_write_path(path):
    p = Path(path).resolve()
    if str(p).upper().startswith("G:"):
        raise ToolError("Refusé : rien ne s'écrit sur G:. Enregistrez sous D:\\DCE SITE.")
    if WRITE_ROOT.resolve() not in p.parents and p != WRITE_ROOT.resolve():
        raise ToolError(f"Refusé : écriture autorisée seulement sous {WRITE_ROOT}.")
    return p


def _check_read_path(path):
    p = Path(path).resolve()
    if not any(r.resolve() == p or r.resolve() in p.parents for r in READ_ROOTS):
        raise ToolError("Lecture autorisée seulement dans : " + ", ".join(str(r) for r in READ_ROOTS))
    return p


def _pt3(x, y, z=0.0):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)])


def _flat2d(points):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(c) for p in points for c in (p[0], p[1])])


_DXF_NAMES = {"AcDbPolyline": "LWPOLYLINE", "AcDbText": "TEXT", "AcDbMText": "MTEXT", "AcDbBlockReference": "INSERT",
              "AcDbLine": "LINE", "AcDbCircle": "CIRCLE", "AcDbArc": "ARC", "AcDbHatch": "HATCH"}

_acad = None


def _app():
    """Attach to the running AutoCAD (never starts a new one)."""
    global _acad
    if _acad is None:
        try:
            _acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except pythoncom.com_error:
            raise ToolError("AutoCAD n'est pas ouvert. Ouvrez AutoCAD puis relancez la demande.")
    return _acad


def _doc():
    try:
        return _app().ActiveDocument
    except pythoncom.com_error:
        raise ToolError("Aucun dessin actif dans AutoCAD.")


def _layer_names(doc):
    return [doc.Layers.Item(i).Name for i in range(doc.Layers.Count)]


def _require_layer(doc, layer):
    names = _layer_names(doc)
    if layer not in names:
        close = [n for n in names if layer.lower() in n.lower() or n.lower() in layer.lower()][:10]
        raise ToolError(f"Le calque '{layer}' n'existe pas (charte BAAK : on n'invente pas de calque). Calques proches : {close}")


def _entity_summary(ent):
    kind = ent.ObjectName
    info = {"handle": ent.Handle, "type": kind, "layer": ent.Layer}
    try:
        if kind == "AcDbPolyline":
            c = list(ent.Coordinates)
            pts = [[round(c[i], 3), round(c[i + 1], 3)] for i in range(0, len(c), 2)]
            info.update(closed=bool(ent.Closed), vertices=len(pts), points=pts[:40])
        elif kind in ("AcDbText", "AcDbMText"):
            p = ent.InsertionPoint
            info.update(text=ent.TextString[:200], at=[round(p[0], 3), round(p[1], 3)], height=round(ent.Height, 3))
        elif kind == "AcDbBlockReference":
            p = ent.InsertionPoint
            info.update(block=ent.EffectiveName, at=[round(p[0], 3), round(p[1], 3)], rotation_deg=round(ent.Rotation * 57.29578, 2))
        elif kind == "AcDbLine":
            s, e = ent.StartPoint, ent.EndPoint
            info.update(start=[round(s[0], 3), round(s[1], 3)], end=[round(e[0], 3), round(e[1], 3)])
        elif kind in ("AcDbCircle", "AcDbArc"):
            c = ent.Center
            info.update(center=[round(c[0], 3), round(c[1], 3)], radius=round(ent.Radius, 3))
    except pythoncom.com_error:
        pass
    return info


# ---------- read-only tools ----------

@beta_tool
def acad_list_documents() -> str:
    """List the drawings open in AutoCAD (name, full path, read-only flag) and which one is active."""
    app = _app()
    docs = []
    for i in range(app.Documents.Count):
        d = app.Documents.Item(i)
        docs.append({"name": d.Name, "path": d.FullName, "read_only": bool(d.ReadOnly)})
    return json.dumps({"active": _doc().Name, "documents": docs}, ensure_ascii=False)


@beta_tool
def acad_open_document(path: str) -> str:
    """Open a DWG in AutoCAD and make it active. Files on G: always open read-only.

    Args:
        path: Full path of the .dwg file.
    """
    p = _check_read_path(path)
    if not p.exists():
        raise ToolError(f"Fichier introuvable : {p}")
    app = _app()
    for i in range(app.Documents.Count):
        d = app.Documents.Item(i)
        if Path(d.FullName).resolve() == p:
            d.Activate()
            return f"Déjà ouvert, activé : {d.Name} (lecture seule : {bool(d.ReadOnly)})"
    read_only = str(p).upper().startswith("G:")
    d = app.Documents.Open(str(p), read_only)
    d.Activate()
    _log("open", f"{p} read_only={read_only}")
    return f"Ouvert : {d.Name} (lecture seule : {read_only})"


@beta_tool
def acad_document_info() -> str:
    """Summary of the active drawing: path, units, layer count, block definitions, layouts, model-space entity count."""
    d = _doc()
    blocks = [d.Blocks.Item(i).Name for i in range(d.Blocks.Count)]
    blocks = [b for b in blocks if not b.startswith("*")]
    layouts = [d.Layouts.Item(i).Name for i in range(d.Layouts.Count)]
    return json.dumps({
        "name": d.Name, "path": d.FullName, "read_only": bool(d.ReadOnly),
        "insunits": d.GetVariable("INSUNITS"), "layers": d.Layers.Count,
        "model_space_entities": d.ModelSpace.Count, "layouts": layouts,
        "blocks": blocks[:300], "block_count": len(blocks),
    }, ensure_ascii=False)


@beta_tool
def acad_list_layers(contains: str = "") -> str:
    """List the layers of the active drawing with on/frozen/locked state and colour.

    Args:
        contains: Optional text filter on the layer name (case-insensitive).
    """
    d = _doc()
    out = []
    for i in range(d.Layers.Count):
        l = d.Layers.Item(i)
        if contains and contains.lower() not in l.Name.lower():
            continue
        out.append({"name": l.Name, "on": bool(l.LayerOn), "frozen": bool(l.Freeze), "locked": bool(l.Lock), "color": l.color})
    return json.dumps(out, ensure_ascii=False)


@beta_tool
def acad_query_entities(layer: str = "", entity_type: str = "", x_min: float = -1e12, y_min: float = -1e12,
                        x_max: float = 1e12, y_max: float = 1e12, limit: int = 200) -> str:
    """Find model-space entities by layer, type and/or plan window; returns handle, type, layer and geometry.

    Args:
        layer: Exact layer name to filter on (empty = all layers).
        entity_type: Type to filter on, as AutoCAD object name (AcDbPolyline, AcDbText, AcDbMText, AcDbBlockReference, AcDbLine) or DXF name (LWPOLYLINE, TEXT, INSERT...); empty = all.
        x_min: Window minimum X in drawing units (metres in the BAAK drawings).
        y_min: Window minimum Y.
        x_max: Window maximum X.
        y_max: Window maximum Y.
        limit: Maximum number of entities returned (default 200).
    """
    d = _doc()
    # let AutoCAD filter by type and layer (a selection set), then check the window here
    dxf = _DXF_NAMES.get(entity_type, entity_type.upper()) if entity_type else "*"
    name = "DCEAGENT_QUERY"
    try:
        d.SelectionSets.Item(name).Delete()
    except pythoncom.com_error:
        pass
    ss = d.SelectionSets.Add(name)
    found, scanned = [], 0
    try:
        empty = VARIANT(pythoncom.VT_EMPTY, None)
        codes, values = [0], [dxf]
        if layer:
            codes.append(8); values.append(layer)
        ss.Select(5, empty, empty, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, codes), VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, values))
        for i in range(ss.Count):
            scanned += 1
            info = _entity_summary(ss.Item(i))
            pts = info.get("points") or [info.get(k) for k in ("at", "start", "center") if info.get(k)]
            if pts and not any(x_min <= p[0] <= x_max and y_min <= p[1] <= y_max for p in pts):
                continue
            found.append(info)
            if len(found) >= limit:
                break
        matched = ss.Count
    finally:
        ss.Delete()
    return json.dumps({"matched_type_and_layer": matched, "checked": scanned, "returned": len(found), "entities": found}, ensure_ascii=False)


@beta_tool
def dce_list_files(folder: str, pattern: str = "*") -> str:
    """List files in a DCE folder (read-only), e.g. D:\\DCE SITE\\ARCHITECTURE or the project folder on G:.

    Args:
        folder: Folder to list.
        pattern: Glob pattern such as *.dwg or *.pdf (default all files).
    """
    p = _check_read_path(folder)
    items = [{"name": f.name, "size_kb": round(f.stat().st_size / 1024), "modified": f"{datetime.datetime.fromtimestamp(f.stat().st_mtime):%Y-%m-%d %H:%M}"}
             for f in sorted(p.glob(pattern)) if f.is_file()]
    return json.dumps(items[:500], ensure_ascii=False)


@beta_tool
def dce_read_text_file(path: str, max_chars: int = 20000) -> str:
    """Read a text/CSV file from the DCE folders (read-only).

    Args:
        path: Full path of the file.
        max_chars: Maximum number of characters returned.
    """
    p = _check_read_path(path)
    return p.read_text(encoding="utf-8", errors="replace")[:max_chars]


@beta_tool
def revit_differences(category: str = "", status: str = "", z_min: float = -1e9, z_max: float = 1e9, limit: int = 60) -> str:
    """Revit APS V2 elements compared with the 3D model, with their extent in DWG metres (mezzanine-sheet coordinates).

    Args:
        category: Filter on category, e.g. Walls, Slabs, Columns, Curtain glazing, Doors (substring, case-insensitive).
        status: OK, PARTIAL or MISSING_IN_MAX (empty = all).
        z_min: Minimum element height in cm (e.g. 300 for the mezzanine).
        z_max: Maximum element base height in cm.
        limit: Maximum rows returned.
    """
    if not REVIT_COMPARE_CSV.exists():
        raise ToolError(f"Comparaison Revit introuvable : {REVIT_COMPARE_CSV}")
    rows = []
    with open(REVIT_COMPARE_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if category and category.lower() not in r.get("cat", "").lower():
                continue
            if status and r["status"] != status:
                continue
            if not (float(r["z1"]) >= z_min and float(r["z0"]) <= z_max):
                continue
            rows.append({k: r[k] for k in ("element", "cat", "status", "coverage_pct", "z0", "z1", "dwg_x0_m", "dwg_y0_m", "dwg_x1_m", "dwg_y1_m") if k in r})
            if len(rows) >= limit:
                break
    return json.dumps({"note": "DWG = mezzanine sheet; RDC/site sheet: y - 100 m", "rows": rows}, ensure_ascii=False)


# ---------- tools that change a drawing or write a file (ask first) ----------

@beta_tool
def acad_draw_polyline(points: list[list[float]], layer: str, closed: bool = False) -> str:
    """Draw a lightweight polyline (LWPOLYLINE) in model space on an existing layer.

    Args:
        points: Vertices as [[x, y], ...] in drawing units.
        layer: Existing layer name (never a new one).
        closed: Close the polyline.
    """
    d = _doc()
    _require_layer(d, layer)
    if len(points) < 2:
        raise ToolError("Il faut au moins 2 points.")
    if not _confirm(f"dessiner une polyligne de {len(points)} sommets sur '{layer}' (fermée={closed})"):
        return "Annulé par l'utilisateur."
    pl = d.ModelSpace.AddLightWeightPolyline(_flat2d(points))
    pl.Layer = layer
    pl.Closed = closed
    _log("polyline", f"{d.Name} {layer} {points}")
    return f"Polyligne créée, handle {pl.Handle}"


@beta_tool
def acad_add_text(text: str, x: float, y: float, height: float, layer: str) -> str:
    """Add single-line text in model space on an existing layer.

    Args:
        text: Text content.
        x: Insertion X.
        y: Insertion Y.
        height: Text height in drawing units.
        layer: Existing layer name.
    """
    d = _doc()
    _require_layer(d, layer)
    if not _confirm(f"écrire « {text} » sur '{layer}' en ({x}, {y})"):
        return "Annulé par l'utilisateur."
    t = d.ModelSpace.AddText(text, _pt3(x, y), height)
    t.Layer = layer
    _log("text", f"{d.Name} {layer} {text!r} at {x},{y}")
    return f"Texte créé, handle {t.Handle}"


@beta_tool
def acad_insert_block(block_name: str, x: float, y: float, layer: str, scale: float = 1.0, rotation_deg: float = 0.0) -> str:
    """Insert an existing block definition (e.g. LEGENDE, cartouche BAAK) in model space.

    Args:
        block_name: Name of a block already defined in the drawing.
        x: Insertion X.
        y: Insertion Y.
        layer: Existing layer name.
        scale: Uniform scale.
        rotation_deg: Rotation in degrees.
    """
    d = _doc()
    _require_layer(d, layer)
    names = [d.Blocks.Item(i).Name for i in range(d.Blocks.Count)]
    if block_name not in names:
        raise ToolError(f"Bloc '{block_name}' absent du dessin. Blocs proches : {[n for n in names if block_name.lower() in n.lower()][:10]}")
    if not _confirm(f"insérer le bloc '{block_name}' sur '{layer}' en ({x}, {y}), échelle {scale}, rotation {rotation_deg}°"):
        return "Annulé par l'utilisateur."
    b = d.ModelSpace.InsertBlock(_pt3(x, y), block_name, scale, scale, scale, rotation_deg / 57.29578)
    b.Layer = layer
    _log("block", f"{d.Name} {block_name} {layer} at {x},{y}")
    return f"Bloc inséré, handle {b.Handle}"


@beta_tool
def acad_move_entity(handle: str, dx: float, dy: float) -> str:
    """Move an entity by (dx, dy).

    Args:
        handle: Entity handle (from acad_query_entities).
        dx: Displacement in X.
        dy: Displacement in Y.
    """
    d = _doc()
    ent = d.HandleToObject(handle)
    if not _confirm(f"déplacer {ent.ObjectName} {handle} (calque {ent.Layer}) de ({dx}, {dy})"):
        return "Annulé par l'utilisateur."
    ent.Move(_pt3(0, 0), _pt3(dx, dy))
    _log("move", f"{d.Name} {handle} by {dx},{dy}")
    return "Déplacé."


@beta_tool
def acad_set_polyline_points(handle: str, points: list[list[float]]) -> str:
    """Replace all vertices of an existing LWPOLYLINE (to correct its geometry).

    Args:
        handle: Polyline handle.
        points: New vertices as [[x, y], ...].
    """
    d = _doc()
    ent = d.HandleToObject(handle)
    if ent.ObjectName != "AcDbPolyline":
        raise ToolError(f"{handle} n'est pas une polyligne ({ent.ObjectName}).")
    if not _confirm(f"modifier la polyligne {handle} (calque {ent.Layer}) : {len(points)} sommets"):
        return "Annulé par l'utilisateur."
    ent.Coordinates = _flat2d(points)
    _log("edit_polyline", f"{d.Name} {handle} {points}")
    return "Polyligne modifiée."


@beta_tool
def acad_delete_entity(handle: str) -> str:
    """Delete one entity by handle.

    Args:
        handle: Entity handle.
    """
    d = _doc()
    ent = d.HandleToObject(handle)
    desc = f"{ent.ObjectName} {handle} (calque {ent.Layer})"
    if not _confirm(f"supprimer {desc}"):
        return "Annulé par l'utilisateur."
    ent.Delete()
    _log("delete", f"{d.Name} {desc}")
    return "Supprimé."


@beta_tool
def acad_save_copy(path: str) -> str:
    """Save the active drawing as a new DWG under D:\\DCE SITE (never on G:, never over an existing file).

    Args:
        path: Full target path ending in .dwg, under D:\\DCE SITE.
    """
    p = _check_write_path(path)
    if p.suffix.lower() != ".dwg":
        raise ToolError("Le chemin doit se terminer par .dwg")
    if p.exists():
        raise ToolError(f"{p} existe déjà : choisissez un nouveau nom (indice) plutôt que d'écraser.")
    d = _doc()
    if not _confirm(f"enregistrer '{d.Name}' sous {p}"):
        return "Annulé par l'utilisateur."
    p.parent.mkdir(parents=True, exist_ok=True)
    d.SaveAs(str(p))
    _log("save_as", f"{d.Name} -> {p}")
    return f"Enregistré : {p}"


@beta_tool
def dce_write_text_file(path: str, content: str) -> str:
    """Write a text/CSV/Markdown file (notes, lists, bordereau extracts) under D:\\DCE SITE, never overwriting.

    Args:
        path: Full target path under D:\\DCE SITE.
        content: File content.
    """
    p = _check_write_path(path)
    if p.exists():
        raise ToolError(f"{p} existe déjà : choisissez un autre nom.")
    if not _confirm(f"écrire le fichier {p} ({len(content)} caractères)"):
        return "Annulé par l'utilisateur."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    _log("write_file", str(p))
    return f"Écrit : {p}"


ALL_TOOLS = [
    acad_list_documents, acad_open_document, acad_document_info, acad_list_layers, acad_query_entities,
    dce_list_files, dce_read_text_file, revit_differences,
    acad_draw_polyline, acad_add_text, acad_insert_block, acad_move_entity, acad_set_polyline_points,
    acad_delete_entity, acad_save_copy, dce_write_text_file,
]
