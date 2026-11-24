# BAAK AEC Toolkit

AI-native production tools for architects, built and used daily at an architecture studio.
They connect AI assistants (Claude Code, MCP) to the software buildings are designed in:
Revit, AutoCAD, 3ds Max, Blender and Chaos Vantage.

| Folder | What it does |
|---|---|
| `revit-addin/` | Revit 2025 add-in: opens a local JSON socket at startup and exposes 45 operations (place/edit families, inspect, clash checks, native families from meshes, export views/DWG/FBX), all run on Revit's UI thread. |
| `autocad-mcp/` | MCP server for AutoCAD: read, correct and check tender drawings in the open document. |
| `skills/` | Claude Code skills: DWG work through the AutoCAD headless console, 3D-to-drawings (V-Ray scene to hidden-line elevations via Blender Line Art), drawing/model QA, archviz cameras, render-to-photo pipelines, visual identity. |

Project names, contacts and local paths have been replaced with placeholders.

## Requirements

- **Revit add-in:** Revit 2025, .NET 8 SDK. Build with `dotnet build -c Release`, then copy the `.addin` manifest and the DLL to `%APPDATA%\Autodesk\Revit\Addins\2025\`. The socket opens on `127.0.0.1:8099` when Revit starts. Lengths are in metres.
- **AutoCAD MCP server:** Python 3, AutoCAD 2027 running on the same machine. Register `dce_mcp_server.py` as a stdio MCP server in Claude Code.
- **Skills:** copy a folder from `skills/` into `~/.claude/skills/`. The headless AutoCAD tools use `accoreconsole.exe`; the 3D-to-drawings skill needs Blender.
