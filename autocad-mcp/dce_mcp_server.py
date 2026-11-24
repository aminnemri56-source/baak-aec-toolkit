"""MCP server (stdio) exposing the BAAK DCE / AutoCAD tools to Claude Code - no API key needed.

Claude Code starts it from ~/.claude.json and asks the user before each tool call, so the tools'
own console confirmation is switched off here; the safety rules in acad_tools still apply
(nothing written to G:, saves only under D:\\DCE SITE, existing layers and blocks only, no overwrite).
"""

import json
import sys

import pythoncom

import acad_tools

acad_tools.AUTO_APPROVE = True

INSTRUCTIONS = """BAAK DCE tools for the PROJECT gym in Site (Avenue Moulay Al Hassan / Rue Imam Chaffai): they read and
correct the DCE drawings in the AutoCAD that is open on this PC.
- Never write, save or change anything on G:. Drawings on G: open read-only; copies and deliverables go under
  D:\\DCE SITE with a new name or index (acad_save_copy refuses anything else and never overwrites).
- Draw with LWPOLYLINE (acad_draw_polyline), not LINE. Use the drawing's existing layers, blocks (LEGENDE, cartouche BAAK)
  and dimension styles - the BAAK charter; never invent a layer: if the right one is missing, ask the user.
- Details and bordereau items are filed by CAH code (CAH-01 to CAH-09, bordereau indice B).
- Before a multi-step job, state the phases, then run them. Inspect (acad_list_layers, acad_query_entities) before
  you change anything, and give handles and coordinates when pointing at entities.
- revit_differences lists Revit APS V2 elements missing or partial in the 3D, with their extent in DWG metres.
  Revit APS V2 (12/10/2026) is older than the DCE (25/10/2026): treat a difference as a point to check, not an automatic fix.
- Coordinates: 3D (cm) -> DWG mezzanine sheet (m): x = (x3D - 18549) / 100, y = (y3D + 9239) / 100; RDC/site sheet: y - 100 m."""

READ_ONLY = {"acad_list_documents", "acad_document_info", "acad_list_layers", "acad_query_entities",
             "dce_list_files", "dce_read_text_file", "revit_differences"}
TOOLS = {t.to_dict()["name"]: t for t in acad_tools.ALL_TOOLS}


def _tool_list():
    out = []
    for name, t in TOOLS.items():
        d = t.to_dict()
        ro = name in READ_ONLY
        out.append({"name": name, "description": d.get("description", ""), "inputSchema": d["input_schema"],
                    "annotations": {"readOnlyHint": ro, "destructiveHint": not ro}})
    return out


def _handle(msg):
    method = msg.get("method")
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        return {"protocolVersion": version, "capabilities": {"tools": {}},
                "serverInfo": {"name": "dce-autocad", "version": "1.0.0"}, "instructions": INSTRUCTIONS}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": _tool_list()}
    if method == "tools/call":
        params = msg.get("params") or {}
        tool = TOOLS.get(params.get("name"))
        if tool is None:
            return {"content": [{"type": "text", "text": f"Outil inconnu : {params.get('name')}"}], "isError": True}
        try:
            result = tool.call(params.get("arguments") or {})
            text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except Exception as e:  # tool errors go back to Claude as text, never crash the server
            return {"content": [{"type": "text", "text": f"Erreur : {e}"}], "isError": True}
    raise LookupError(method)


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    pythoncom.CoInitialize()
    for line in sys.stdin:
        line = line.strip().lstrip("﻿")
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stderr.write(f"dce-autocad: unreadable message skipped: {line[:120]}\n")
            continue
        if "id" not in msg:  # notifications (e.g. notifications/initialized) need no answer
            continue
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": _handle(msg)}
        except LookupError:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"Method not found: {msg.get('method')}"}}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
