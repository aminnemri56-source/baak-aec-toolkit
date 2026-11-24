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
