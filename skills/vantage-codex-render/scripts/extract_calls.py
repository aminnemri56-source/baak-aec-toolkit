"""Lists every 3ds Max MCP call of this session after a UTC time, in order, with its success flag; saves inline scripts to files.
usage: extract_calls.py transcript.jsonl 2026-11-07T10:22:00 outdir"""
import json
import os
import sys

path, since, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(outdir, exist_ok=True)
calls = []
results = {}
for line in open(path, encoding="utf-8", errors="replace"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    ts = d.get("timestamp", "")
    msg = d.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, list):
        continue
    for c in content:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use" and str(c.get("name", "")).startswith("mcp__max-ultra-mcp__"):
            calls.append((ts, c.get("id"), c.get("name").replace("mcp__max-ultra-mcp__", ""), c.get("input", {})))
        elif c.get("type") == "tool_result":
            txt = c.get("content")
            if isinstance(txt, list):
                txt = " ".join(x.get("text", "") for x in txt if isinstance(x, dict))
            results[c.get("tool_use_id")] = str(txt)[:400]
seen = set()
rows = []
for ts, tid, name, inp in calls:
    if ts < since or tid in seen:
        continue
    seen.add(tid)
    res = results.get(tid, "")
    ok = '"ok":true' in res.replace(" ", "")
    n = len(rows) + 1
    what = inp.get("activity", "")
    if name == "max_execute":
        f = os.path.join(outdir, "call_%03d.ms" % n)
        open(f, "w", encoding="utf-8").write(inp.get("script", ""))
        target = f
    elif name == "max_run_script_file":
        target = inp.get("filePath", "")
    else:
        target = json.dumps(inp)[:160]
    rows.append("%03d | %s | %-20s | %s | %s | %s | %s" % (n, ts[11:19], name, "OK" if ok else "FAIL", what[:60], target, res[:160].replace("\n", " ")))
open(os.path.join(outdir, "calls.txt"), "w", encoding="utf-8").write("\n".join(rows))
print(len(rows), "calls")
