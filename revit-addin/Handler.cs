using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Text.Json;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Structure;
using Autodesk.Revit.UI;

namespace BaakRevitMcp
{
    internal class Handler : IExternalEventHandler
    {
        private readonly BlockingCollection<Job> _queue;
        public ExternalEvent Event;
        public Handler(BlockingCollection<Job> q) { _queue = q; }
        public string GetName() => "BAAK Revit MCP";

        public void Execute(UIApplication uiapp)
        {
            App.UiApp = uiapp;
            while (_queue.TryTake(out var job))
            {
                try { job.Result = Run(uiapp, job); }
                catch (Exception ex)
                {
                    App.Log("ERR " + job.Method + ": " + ex);
                    job.Result = J(new Dictionary<string, object>
                    { ["ok"] = false, ["error"] = ex.Message, ["method"] = job.Method });
                }
                finally { job.Done.Set(); }
            }
        }

        private static string J(object o) => JsonSerializer.Serialize(o);
        private static double M(double metres) => UnitUtils.ConvertToInternalUnits(metres, UnitTypeId.Meters);
        private static double ToM(double feet) => UnitUtils.ConvertFromInternalUnits(feet, UnitTypeId.Meters);

        private static double D(JsonElement p, string k, double dflt = 0)
            => p.ValueKind == JsonValueKind.Object && p.TryGetProperty(k, out var v)
               && (v.ValueKind == JsonValueKind.Number) ? v.GetDouble() : dflt;
        private static string S(JsonElement p, string k, string dflt = null)
            => p.ValueKind == JsonValueKind.Object && p.TryGetProperty(k, out var v)
               && v.ValueKind == JsonValueKind.String ? v.GetString() : dflt;

        private string Run(UIApplication uiapp, Job job)
        {
            var app = uiapp.Application;
            var p = job.Params;

            switch (job.Method)
            {
                case "info":
                    {
                        var d = uiapp.ActiveUIDocument?.Document;
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = true,
                            ["revit"] = app.VersionNumber + " " + app.VersionBuild,
                            ["document"] = d?.Title,
                            ["path"] = d?.PathName,
                            ["view"] = uiapp.ActiveUIDocument?.ActiveView?.Name,
                            ["templates"] = app.DefaultProjectTemplate,
                        });
                    }

                case "open_document":
                    {
                        string path = S(p, "path") ?? throw new Exception("path is required");
                        var ui = uiapp.OpenAndActivateDocument(path);
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["document"] = ui.Document.Title, ["path"] = ui.Document.PathName });
                    }

                // What the active document actually holds - used to verify a placement run.
                case "count":
                    {
                        var d = Doc(uiapp);
                        var byCat = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Where(e => e.Category != null)
                            .GroupBy(e => e.Category.Name)
                            .OrderByDescending(g => g.Count())
                            .Take(25)
                            .ToDictionary(g => g.Key, g => (object)g.Count());
                        int ds = new FilteredElementCollector(d).OfClass(typeof(DirectShape)).GetElementCount();
                        int fi = new FilteredElementCollector(d).OfClass(typeof(FamilyInstance)).GetElementCount();
                        var marks = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Where(e => !string.IsNullOrEmpty(e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString()))
                            .Count();
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = true, ["document"] = d.Title, ["direct_shapes"] = ds,
                            ["family_instances"] = fi, ["elements_with_a_mark"] = marks, ["by_category"] = byCat
                        });
                    }

                // Every Mark actually present in the model - the only honest way to check a run.
                case "marks":
                    {
                        var d = Doc(uiapp);
                        var list = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Select(e => new { e, m = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString() })
                            .Where(x => !string.IsNullOrEmpty(x.m))
                            .Select(x => new Dictionary<string, object>
                            {
                                ["mark"] = x.m,
                                ["id"] = x.e.Id.Value,
                                ["kind"] = x.e is DirectShape ? "volume" : (x.e is FamilyInstance ? "family" : x.e.GetType().Name),
                                ["category"] = x.e.Category?.Name,
                            })
                            .OrderBy(h => (string)h["mark"]).ToList();
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = list.Count, ["marks"] = list });
                    }

                // Delete every element carrying one of the given Marks - so a piece can be
                // swapped for a better family without rebuilding the whole model.
                case "delete_by_mark":
                    {
                        var d = Doc(uiapp);
                        var wanted = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                        if (p.ValueKind == JsonValueKind.Object && p.TryGetProperty("marks", out var arr)
                            && arr.ValueKind == JsonValueKind.Array)
                            foreach (var e in arr.EnumerateArray())
                                if (e.ValueKind == JsonValueKind.String) wanted.Add(e.GetString());
                        if (wanted.Count == 0) throw new Exception("marks must be a non-empty array");

                        var ids = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Where(e => { var m = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString();
                                          return !string.IsNullOrEmpty(m) && wanted.Contains(m); })
                            .Select(e => e.Id).ToList();

                        var removed = new List<long>();
                        if (ids.Count > 0)
                            using (var t = new Transaction(d, "BAAK MCP - delete by mark"))
                            {
                                t.Start();
                                var del = d.Delete(ids);
                                removed = del.Select(i => i.Value).ToList();
                                t.Commit();
                            }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["matched"] = ids.Count, ["deleted"] = removed.Count });
                    }

                // Copy the model geometry out of a manufacturer's .rvt into the open project,
                // then rotate and move it into place. Many manufacturers publish a project
                // holding a DirectShape rather than a loadable .rfa family.
                case "copy_from_document":
                    {
                        var d = Doc(uiapp);
                        string src = S(p, "src") ?? throw new Exception("src is required");
                        var pt = new XYZ(M(D(p, "x")), M(D(p, "y")), M(D(p, "z")));
                        double rot = D(p, "rot_deg");

                        var sdoc = app.OpenDocumentFile(src);
                        var copied = new List<long>();
                        try
                        {
                            var ids = new FilteredElementCollector(sdoc).WhereElementIsNotElementType()
                                .Where(e => e is DirectShape || e is FamilyInstance)
                                .Select(e => e.Id).ToList();
                            if (ids.Count == 0) throw new Exception("no DirectShape or family instance found in " + src);

                            using (var t = new Transaction(d, "BAAK MCP - copy from document"))
                            {
                                t.Start();
                                var newIds = ElementTransformUtils.CopyElements(
                                    sdoc, ids, d, Transform.Identity, new CopyPasteOptions());
                                var list = newIds.ToList();
                                if (Math.Abs(rot) > 1e-9)
                                    ElementTransformUtils.RotateElements(d, list,
                                        Line.CreateBound(XYZ.Zero, XYZ.BasisZ), rot * Math.PI / 180.0);
                                ElementTransformUtils.MoveElements(d, list, pt);
                                foreach (var id in list) SetMarkAndComment(d, id, S(p, "mark"), S(p, "comment"));
                                copied = list.Select(i => i.Value).ToList();
                                t.Commit();
                            }
                        }
                        finally { try { sdoc.Close(false); } catch { } }

                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["source"] = src, ["copied"] = copied.Count, ["ids"] = copied });
                    }

                // Build a piece of furniture from composed solids: boxes and cylinders placed in
                // the object's own frame, then the whole thing rotated and moved into place.
                // Lets a chair be a seat + back + legs instead of one crude box.
                case "place_parts":
                    {
                        var d = Doc(uiapp);
                        if (p.ValueKind != JsonValueKind.Object || !p.TryGetProperty("parts", out var partsEl)
                            || partsEl.ValueKind != JsonValueKind.Array || partsEl.GetArrayLength() == 0)
                            throw new Exception("parts must be a non-empty array");

                        var solids = new List<GeometryObject>();
                        foreach (var q in partsEl.EnumerateArray())
                        {
                            string shape = (q.TryGetProperty("shape", out var sh) && sh.ValueKind == JsonValueKind.String)
                                           ? sh.GetString() : "box";
                            double dx = M(D(q, "dx")), dy = M(D(q, "dy")), dz = M(D(q, "dz"));
                            double h = M(D(q, "H"));
                            if (h <= 0) throw new Exception("each part needs H > 0 (metres)");
                            double a = D(q, "rot") * Math.PI / 180.0;
                            var curves = new List<Curve>();

                            if (shape.Equals("cyl", StringComparison.OrdinalIgnoreCase))
                            {
                                double r = M(D(q, "D")) / 2.0;
                                if (r <= 0) throw new Exception("a cyl part needs D > 0");
                                var c = new XYZ(dx, dy, dz);
                                curves.Add(Arc.Create(c, r, 0, Math.PI, XYZ.BasisX, XYZ.BasisY));
                                curves.Add(Arc.Create(c, r, Math.PI, 2 * Math.PI, XYZ.BasisX, XYZ.BasisY));
                            }
                            else
                            {
                                double L = M(D(q, "L")), P2 = M(D(q, "P"));
                                if (L <= 0 || P2 <= 0) throw new Exception("a box part needs L and P > 0");
                                var pts = new[]
                                {
                                    new XYZ(-L/2, -P2/2, 0), new XYZ(L/2, -P2/2, 0),
                                    new XYZ(L/2, P2/2, 0),  new XYZ(-L/2, P2/2, 0)
                                }.Select(v => new XYZ(
                                        v.X * Math.Cos(a) - v.Y * Math.Sin(a) + dx,
                                        v.X * Math.Sin(a) + v.Y * Math.Cos(a) + dy,
                                        dz)).ToArray();
                                for (int i = 0; i < 4; i++) curves.Add(Line.CreateBound(pts[i], pts[(i + 1) % 4]));
                            }
                            solids.Add(GeometryCreationUtilities.CreateExtrusionGeometry(
                                new List<CurveLoop> { CurveLoop.Create(curves) }, XYZ.BasisZ, h));
                        }

                        var at = new XYZ(M(D(p, "x")), M(D(p, "y")), M(D(p, "z")));
                        double rotDeg = D(p, "rot_deg");
                        ElementId dsId;
                        using (var t = new Transaction(d, "BAAK MCP - place modelled piece"))
                        {
                            t.Start();
                            var ds = DirectShape.CreateElement(d, new ElementId(BuiltInCategory.OST_Furniture));
                            ds.ApplicationId = "BAAK";
                            ds.ApplicationDataId = S(p, "mark") ?? Guid.NewGuid().ToString();
                            ds.SetShape(solids);
                            string nm = S(p, "name");
                            if (!string.IsNullOrEmpty(nm)) ds.Name = nm;
                            dsId = ds.Id;
                            if (Math.Abs(rotDeg) > 1e-9)
                                ElementTransformUtils.RotateElement(d, dsId,
                                    Line.CreateBound(XYZ.Zero, XYZ.BasisZ), rotDeg * Math.PI / 180.0);
                            ElementTransformUtils.MoveElement(d, dsId, at);
                            SetMarkAndComment(d, dsId, S(p, "mark"), S(p, "comment"));
                            t.Commit();
                        }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["element_id"] = dsId.Value, ["parts"] = solids.Count });
                    }

                case "levels":
                    {
                        var d = Doc(uiapp);
                        var ls = new FilteredElementCollector(d).OfClass(typeof(Level)).Cast<Level>()
                                 .OrderBy(l => l.Elevation)
                                 .Select(l => new Dictionary<string, object>
                                 { ["id"] = l.Id.Value, ["name"] = l.Name, ["elev_m"] = Math.Round(ToM(l.Elevation), 4) })
                                 .ToList();
                        return J(new Dictionary<string, object> { ["ok"] = true, ["levels"] = ls });
                    }

                case "new_project":
                    {
                        string template = S(p, "template");
                        string saveAs = S(p, "save_as");
                        if (string.IsNullOrEmpty(saveAs)) throw new Exception("save_as is required");
                        var nd = string.IsNullOrEmpty(template)
                                 ? app.NewProjectDocument(UnitSystem.Metric)
                                 : app.NewProjectDocument(template);
                        var opts = new SaveAsOptions { OverwriteExistingFile = true };
                        nd.SaveAs(saveAs, opts);
                        nd.Close(false);
                        var ui = uiapp.OpenAndActivateDocument(saveAs);
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["created"] = saveAs, ["document"] = ui.Document.Title });
                    }

                case "link_dwg":
                    {
                        var d = Doc(uiapp);
                        string path = S(p, "path") ?? throw new Exception("path is required");
                        var o = new DWGImportOptions
                        {
                            Placement = ImportPlacement.Origin,
                            ThisViewOnly = false,
                            ColorMode = ImportColorMode.Preserved,
                            Unit = ImportUnit.Meter,
                            OrientToView = false,
                        };
                        ElementId id;
                        using (var t = new Transaction(d, "BAAK MCP - link DWG"))
                        {
                            t.Start();
                            bool okLink = d.Link(path, o, uiapp.ActiveUIDocument.ActiveView, out id);
                            if (!okLink) { t.RollBack(); throw new Exception("Revit refused the DWG link"); }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["linked"] = path, ["element_id"] = id.Value });
                    }

                case "load_family":
                    {
                        var d = Doc(uiapp);
                        string path = S(p, "path") ?? throw new Exception("path is required");
                        Family fam = null;
                        using (var t = new Transaction(d, "BAAK MCP - load family"))
                        {
                            t.Start();
                            bool okLoad = d.LoadFamily(path, new BaakOverwrite(), out fam);
                            t.Commit();
                            if (!okLoad && fam == null) throw new Exception("LoadFamily returned false");
                        }
                        var types = fam.GetFamilySymbolIds()
                                       .Select(i => d.GetElement(i) as FamilySymbol)
                                       .Where(s => s != null)
                                       .Select(s => new Dictionary<string, object>
                                       { ["id"] = s.Id.Value, ["name"] = s.Name })
                                       .ToList();
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["family"] = fam.Name, ["types"] = types });
                    }

                case "place_instance":
                    {
                        var d = Doc(uiapp);
                        string famName = S(p, "family") ?? throw new Exception("family is required");
                        string typeName = S(p, "type");
                        var sym = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol))
                                  .Cast<FamilySymbol>()
                                  .Where(s => s.FamilyName.Equals(famName, StringComparison.OrdinalIgnoreCase))
                                  .OrderBy(s => typeName != null && s.Name == typeName ? 0 : 1)
                                  .FirstOrDefault()
                                  ?? throw new Exception("family not loaded: " + famName);
                        var lvl = LevelByName(d, S(p, "level"));
                        var pt = new XYZ(M(D(p, "x")), M(D(p, "y")), M(D(p, "z")));
                        double rot = D(p, "rot_deg");
                        ElementId newId;
                        using (var t = new Transaction(d, "BAAK MCP - place instance"))
                        {
                            t.Start();
                            if (!sym.IsActive) { sym.Activate(); d.Regenerate(); }
                            var fi = d.Create.NewFamilyInstance(pt, sym, lvl, StructuralType.NonStructural);
                            newId = fi.Id;
                            if (Math.Abs(rot) > 1e-9)
                            {
                                var axis = Line.CreateBound(pt, pt + XYZ.BasisZ);
                                ElementTransformUtils.RotateElement(d, newId, axis, rot * Math.PI / 180.0);
                            }
                            SetMarkAndComment(d, newId, S(p, "mark"), S(p, "comment"));
                            t.Commit();
                        }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["element_id"] = newId.Value, ["family"] = sym.FamilyName, ["type"] = sym.Name });
                    }

                case "place_box":
                    {
                        var d = Doc(uiapp);
                        double L = M(D(p, "L")), P = M(D(p, "P")), H = M(D(p, "H"));
                        if (L <= 0 || P <= 0 || H <= 0) throw new Exception("L, P and H must all be > 0 (metres)");
                        var pt = new XYZ(M(D(p, "x")), M(D(p, "y")), M(D(p, "z")));
                        double rot = D(p, "rot_deg");

                        // rectangle centred on the origin, extruded up by H
                        var a = new XYZ(-L / 2, -P / 2, 0);
                        var b = new XYZ(L / 2, -P / 2, 0);
                        var c = new XYZ(L / 2, P / 2, 0);
                        var e = new XYZ(-L / 2, P / 2, 0);
                        var loop = (S(p, "shape") ?? "") == "cyl"
                            ? CurveLoop.Create(new List<Curve>
                              {
                                  Arc.Create(XYZ.Zero, L / 2, 0, Math.PI, XYZ.BasisX, XYZ.BasisY),
                                  Arc.Create(XYZ.Zero, L / 2, Math.PI, 2 * Math.PI, XYZ.BasisX, XYZ.BasisY)
                              })
                            : CurveLoop.Create(new List<Curve>
                              {
                                  Line.CreateBound(a, b), Line.CreateBound(b, c),
                                  Line.CreateBound(c, e), Line.CreateBound(e, a)
                              });
                        var solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                                        new List<CurveLoop> { loop }, XYZ.BasisZ, H);

                        ElementId dsId;
                        using (var t = new Transaction(d, "BAAK MCP - place volume"))
                        {
                            t.Start();
                            string catKey = (S(p, "category") ?? "").ToLowerInvariant();
                            var bicBox = catKey == "mech" ? BuiltInCategory.OST_MechanicalEquipment
                                       : catKey == "terminal" ? BuiltInCategory.OST_DuctTerminal
                                       : catKey == "plumbing" ? BuiltInCategory.OST_PlumbingFixtures
                                       : catKey == "pipe_acc" ? BuiltInCategory.OST_PipeAccessory
                                       : catKey == "duct_acc" ? BuiltInCategory.OST_DuctAccessory
                                       : BuiltInCategory.OST_Furniture;
                            var cat = new ElementId(bicBox);
                            var ds = DirectShape.CreateElement(d, cat);
                            ds.ApplicationId = "BAAK";
                            ds.ApplicationDataId = S(p, "mark") ?? Guid.NewGuid().ToString();
                            ds.SetShape(new List<GeometryObject> { solid });
                            string nm = S(p, "name");
                            if (!string.IsNullOrEmpty(nm)) ds.Name = nm;
                            dsId = ds.Id;

                            if (Math.Abs(rot) > 1e-9)
                            {
                                var axis = Line.CreateBound(XYZ.Zero, XYZ.BasisZ);
                                ElementTransformUtils.RotateElement(d, dsId, axis, rot * Math.PI / 180.0);
                            }
                            ElementTransformUtils.MoveElement(d, dsId, pt);
                            SetMarkAndComment(d, dsId, S(p, "mark"), S(p, "comment"));
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["element_id"] = dsId.Value });
                    }

                // Many manufacturers publish a .rvt project rather than a .rfa family.
                // Open it in the background, edit each family that is actually placed in it,
                // and save that family out as a proper .rfa we can load.
                case "rvt_to_rfa":
                    {
                        string src = S(p, "src") ?? throw new Exception("src is required");
                        string outDir = S(p, "out_dir") ?? throw new Exception("out_dir is required");
                        Directory.CreateDirectory(outDir);
                        bool onlyPlaced = !(p.ValueKind == JsonValueKind.Object
                                            && p.TryGetProperty("only_placed", out var op)
                                            && op.ValueKind == JsonValueKind.False);

                        var src_doc = app.OpenDocumentFile(src);
                        var saved = new List<Dictionary<string, object>>();
                        var errors = new List<string>();

                        // Some manufacturers ship a family saved under a .rvt name: save it straight out.
                        if (src_doc.IsFamilyDocument)
                        {
                            var nm = Path.GetFileNameWithoutExtension(src);
                            var outP = Path.Combine(outDir, nm + ".rfa");
                            src_doc.SaveAs(outP, new SaveAsOptions { OverwriteExistingFile = true });
                            src_doc.Close(false);
                            return J(new Dictionary<string, object>
                            {
                                ["ok"] = true, ["source"] = src, ["was_family_document"] = true,
                                ["saved"] = new List<Dictionary<string, object>>
                                { new Dictionary<string, object> { ["family"] = nm, ["rfa"] = outP } }
                            });
                        }

                        try
                        {
                            IEnumerable<Family> fams;
                            if (onlyPlaced)
                                fams = new FilteredElementCollector(src_doc).OfClass(typeof(FamilyInstance))
                                       .Cast<FamilyInstance>().Select(fi => fi.Symbol?.Family)
                                       .Where(f => f != null).GroupBy(f => f.Id.Value).Select(g => g.First());
                            else
                                fams = new FilteredElementCollector(src_doc).OfClass(typeof(Family)).Cast<Family>();

                            foreach (var f in fams.Where(f => f.IsEditable).ToList())
                            {
                                try
                                {
                                    var fdoc = src_doc.EditFamily(f);
                                    var safe = string.Join("_", f.Name.Split(Path.GetInvalidFileNameChars()));
                                    var outPath = Path.Combine(outDir, safe + ".rfa");
                                    fdoc.SaveAs(outPath, new SaveAsOptions { OverwriteExistingFile = true });
                                    fdoc.Close(false);
                                    saved.Add(new Dictionary<string, object>
                                    { ["family"] = f.Name, ["rfa"] = outPath, ["category"] = f.FamilyCategory?.Name });
                                }
                                catch (Exception ex) { errors.Add(f.Name + ": " + ex.Message); }
                            }
                        }
                        catch (Exception ex) { errors.Add("scan: " + ex.Message); }

                        // when nothing came out, say what the file actually holds
                        var contents = new Dictionary<string, object>();
                        try
                        {
                            contents["families"] = new FilteredElementCollector(src_doc).OfClass(typeof(Family)).GetElementCount();
                            contents["family_instances"] = new FilteredElementCollector(src_doc).OfClass(typeof(FamilyInstance)).GetElementCount();
                            contents["direct_shapes"] = new FilteredElementCollector(src_doc).OfClass(typeof(DirectShape)).GetElementCount();
                            contents["import_instances"] = new FilteredElementCollector(src_doc).OfClass(typeof(ImportInstance)).GetElementCount();
                            contents["top_categories"] = new FilteredElementCollector(src_doc).WhereElementIsNotElementType()
                                .Where(e => e.Category != null).GroupBy(e => e.Category.Name)
                                .OrderByDescending(g => g.Count()).Take(10)
                                .ToDictionary(g => g.Key, g => g.Count());
                        }
                        catch { }
                        finally { try { src_doc.Close(false); } catch { } }

                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["source"] = src, ["saved"] = saved, ["errors"] = errors, ["contents"] = contents });
                    }

                // Everything a piece carries, so a swap can keep its Mark and Comments and be
                // checked afterwards: bounding box in metres and how much geometry it really holds.
                case "inspect":
                    {
                        var d = Doc(uiapp);
                        var opt = new Options { ComputeReferences = false, DetailLevel = ViewDetailLevel.Fine };
                        var list = new List<Dictionary<string, object>>();
                        foreach (var e in new FilteredElementCollector(d).WhereElementIsNotElementType())
                        {
                            string mk = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString();
                            if (string.IsNullOrEmpty(mk)) continue;
                            int tri = 0, solids = 0, meshes = 0;
                            if (e is DirectShape dshp)
                            {
                                var gel = dshp.get_Geometry(opt);
                                if (gel != null)
                                    foreach (var g in gel)
                                    {
                                        if (g is Solid so && so.Faces.Size > 0) { solids++; tri += so.Faces.Size; }
                                        else if (g is Mesh me) { meshes++; tri += me.NumTriangles; }
                                    }
                            }
                            var bb = e.get_BoundingBox(null);
                            var row = new Dictionary<string, object>
                            {
                                ["mark"] = mk,
                                ["id"] = e.Id.Value,
                                ["kind"] = e is DirectShape ? "volume" : (e is FamilyInstance ? "family" : e.GetType().Name),
                                ["name"] = e.Name,
                                ["comment"] = e.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.AsString(),
                                ["solids"] = solids,
                                ["meshes"] = meshes,
                                ["faces_or_triangles"] = tri,
                            };
                            if (bb != null)
                            {
                                row["bbox_min_m"] = new[] { ToM(bb.Min.X), ToM(bb.Min.Y), ToM(bb.Min.Z) };
                                row["bbox_max_m"] = new[] { ToM(bb.Max.X), ToM(bb.Max.Y), ToM(bb.Max.Z) };
                            }
                            list.Add(row);
                        }
                        list = list.OrderBy(h => (string)h["mark"]).ToList();
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["count"] = list.Count, ["pieces"] = list });
                    }

                // Build DirectShapes from the real triangle meshes exported out of the 3D scene, so a
                // piece looks like the chair it is instead of a box. Each mesh file is BKMSH1:
                //   "BKMSH1" | uint32 nv | uint32 nt | float64[3*nv] xyz in PROJECT METRES | int32[3*nt]
                // The vertices are already in project coordinates, so nothing is rotated or moved here.
                case "place_mesh":
                    {
                        var d = Doc(uiapp);
                        var jobs = new List<JsonElement>();
                        if (p.ValueKind == JsonValueKind.Object && p.TryGetProperty("meshes", out var arr)
                            && arr.ValueKind == JsonValueKind.Array)
                            jobs.AddRange(arr.EnumerateArray());
                        else jobs.Add(p);
                        if (jobs.Count == 0) throw new Exception("nothing to place");

                        var cat = new ElementId(BuiltInCategory.OST_Furniture);
                        var done = new List<Dictionary<string, object>>();
                        using (var t = new Transaction(d, "BAAK MCP - place mesh from 3D"))
                        {
                            t.Start();
                            foreach (var q in jobs)
                            {
                                string file = S(q, "file") ?? throw new Exception("each mesh needs a file");
                                string mark = S(q, "mark");
                                XYZ[] v;
                                int[] f;
                                using (var br = new BinaryReader(File.OpenRead(file)))
                                {
                                    if (new string(br.ReadChars(6)) != "BKMSH1")
                                        throw new Exception("not a BKMSH1 mesh: " + file);
                                    int nv = (int)br.ReadUInt32(), nt = (int)br.ReadUInt32();
                                    v = new XYZ[nv];
                                    f = new int[nt * 3];
                                    for (int i = 0; i < nv; i++)
                                        v[i] = new XYZ(M(br.ReadDouble()), M(br.ReadDouble()), M(br.ReadDouble()));
                                    for (int i = 0; i < nt * 3; i++) f[i] = br.ReadInt32();
                                }

                                // "mesh" is the fast path that always works; "any" asks Revit to try a
                                // real solid first, which is slower and rarely succeeds on scene meshes.
                                bool wantSolid = (S(q, "target") ?? S(p, "target") ?? "mesh") == "any";
                                var tsb = new TessellatedShapeBuilder
                                {
                                    Target = wantSolid ? TessellatedShapeBuilderTarget.AnyGeometry
                                                       : TessellatedShapeBuilderTarget.Mesh,
                                    Fallback = wantSolid ? TessellatedShapeBuilderFallback.Mesh
                                                         : TessellatedShapeBuilderFallback.Salvage,
                                    GraphicsStyleId = ElementId.InvalidElementId,
                                };
                                tsb.OpenConnectedFaceSet(false);
                                int skipped = 0;
                                var tri = new List<XYZ>(3);
                                for (int i = 0; i < f.Length; i += 3)
                                {
                                    tri.Clear();
                                    tri.Add(v[f[i]]);
                                    tri.Add(v[f[i + 1]]);
                                    tri.Add(v[f[i + 2]]);
                                    // Revit refuses a face it finds degenerate: skip it rather than lose the piece
                                    try { tsb.AddFace(new TessellatedFace(tri, ElementId.InvalidElementId)); }
                                    catch { skipped++; }
                                }
                                tsb.CloseConnectedFaceSet();
                                tsb.Build();
                                var geom = tsb.GetBuildResult().GetGeometricalObjects();
                                if (geom == null || geom.Count == 0)
                                    throw new Exception("Revit built no geometry for " + mark);

                                var ds = DirectShape.CreateElement(d, cat);
                                ds.ApplicationId = "BAAK";
                                ds.ApplicationDataId = mark ?? Guid.NewGuid().ToString();
                                ds.SetShape(geom.ToList());
                                string nm = S(q, "name");
                                if (!string.IsNullOrEmpty(nm)) ds.Name = nm;
                                SetMarkAndComment(d, ds.Id, mark, S(q, "comment"));
                                done.Add(new Dictionary<string, object>
                                {
                                    ["mark"] = mark,
                                    ["element_id"] = ds.Id.Value,
                                    ["triangles"] = f.Length / 3,
                                    ["skipped_faces"] = skipped,
                                    ["objects"] = geom.Count,
                                    ["is_solid"] = geom.Any(g => g is Solid),
                                });
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["placed"] = done.Count, ["pieces"] = done });
                    }

                // Build a real loadable family (.rfa) whose geometry is the furniture as modelled in
                // the 3D scene: each mesh file becomes a native FreeFormElement, so the piece is a
                // proper Revit family that schedules, tags and counts - not a DirectShape.
                // Mesh files are BKMSH1, already in FAMILY-LOCAL metres (origin = insertion point,
                // piece un-rotated), so a plain NewFamilyInstance at x/y/z + rot_deg puts it back.
                case "make_family":
                    {
                        string template = S(p, "template") ?? throw new Exception("template is required");
                        string outPath = S(p, "out") ?? throw new Exception("out is required");
                        string typeName = S(p, "type_name") ?? "Standard";
                        var files = new List<string>();
                        if (p.TryGetProperty("meshes", out var mArr) && mArr.ValueKind == JsonValueKind.Array)
                            foreach (var e in mArr.EnumerateArray())
                                if (e.ValueKind == JsonValueKind.String) files.Add(e.GetString());
                        if (files.Count == 0) throw new Exception("meshes must be a non-empty array");

                        string matName = S(p, "material_name");
                        int mr = (int)D(p, "material_r", 160), mg = (int)D(p, "material_g", 160),
                            mb = (int)D(p, "material_b", 160);

                        var fdoc = app.NewFamilyDocument(template);
                        int solids = 0, meshed = 0, failed = 0, tris = 0, curves = 0;
                        bool fineOnly = !(p.ValueKind == JsonValueKind.Object && p.TryGetProperty("fine_only", out var fo) && fo.ValueKind == JsonValueKind.False);
                        var errs = new List<string>();
                        var modes = new Dictionary<string, int>();
                        double[] lo = { 1e9, 1e9, 1e9 }, hi = { -1e9, -1e9, -1e9 };
                        try
                        {
                            using (var t = new Transaction(fdoc, "BAAK MCP - build family geometry"))
                            {
                                t.Start();
                                ElementId matId = ElementId.InvalidElementId;
                                if (!string.IsNullOrEmpty(matName))
                                {
                                    var found = new FilteredElementCollector(fdoc).OfClass(typeof(Material))
                                        .Cast<Material>()
                                        .FirstOrDefault(x => x.Name.Equals(matName, StringComparison.OrdinalIgnoreCase));
                                    if (found == null)
                                    {
                                        matId = Material.Create(fdoc, matName);
                                        var nm = fdoc.GetElement(matId) as Material;
                                        nm.Color = new Color((byte)mr, (byte)mg, (byte)mb);
                                        nm.Shininess = 32;
                                        nm.Smoothness = 40;
                                    }
                                    else matId = found.Id;
                                }

                                foreach (var file in files)
                                {
                                    XYZ[] v;
                                    int[] f;
                                    using (var br = new BinaryReader(File.OpenRead(file)))
                                    {
                                        if (new string(br.ReadChars(6)) != "BKMSH1")
                                            throw new Exception("not a BKMSH1 mesh: " + file);
                                        int nv = (int)br.ReadUInt32(), nt = (int)br.ReadUInt32();
                                        v = new XYZ[nv];
                                        f = new int[nt * 3];
                                        for (int i = 0; i < nv; i++)
                                        {
                                            double x = br.ReadDouble(), y = br.ReadDouble(), z = br.ReadDouble();
                                            lo[0] = Math.Min(lo[0], x); hi[0] = Math.Max(hi[0], x);
                                            lo[1] = Math.Min(lo[1], y); hi[1] = Math.Max(hi[1], y);
                                            lo[2] = Math.Min(lo[2], z); hi[2] = Math.Max(hi[2], z);
                                            v[i] = new XYZ(M(x), M(y), M(z));
                                        }
                                        for (int i = 0; i < nt * 3; i++) f[i] = br.ReadInt32();
                                        tris += nt;
                                    }

                                    // A FreeFormElement needs a Solid, and scene meshes are rarely
                                    // watertight. Ask for solids first - and take ALL of them, a build
                                    // often returns several shells. Whatever still will not close must
                                    // reach the family anyway, as a DirectShape: losing more than half a
                                    // chair is far worse than holding part of it as a mesh.
                                    // isSolid tells Revit the face set is closed. Declaring false - as
                                    // this did - makes it treat even a watertight part as an open shell
                                    // and refuse to build a Solid, which is why whole pieces came back
                                    // as meshes. Try true first, then fall back.
                                    Func<TessellatedShapeBuilderTarget, TessellatedShapeBuilderFallback, bool, IList<GeometryObject>> build =
                                        (tg, fb, isSolid) =>
                                        {
                                            var tsb = new TessellatedShapeBuilder
                                            {
                                                Target = tg,
                                                Fallback = fb,
                                                GraphicsStyleId = ElementId.InvalidElementId,
                                            };
                                            tsb.OpenConnectedFaceSet(isSolid);
                                            var tri = new List<XYZ>(3);
                                            for (int i = 0; i < f.Length; i += 3)
                                            {
                                                tri.Clear();
                                                tri.Add(v[f[i]]);
                                                tri.Add(v[f[i + 1]]);
                                                tri.Add(v[f[i + 2]]);
                                                try { tsb.AddFace(new TessellatedFace(tri, matId)); }
                                                catch { }
                                            }
                                            tsb.CloseConnectedFaceSet();
                                            tsb.Build();
                                            return tsb.GetBuildResult().GetGeometricalObjects();
                                        };

                                    var sols = new List<Solid>();
                                    string won = null;
                                    foreach (var mode in new[]
                                    {
                                        Tuple.Create(TessellatedShapeBuilderTarget.Solid, TessellatedShapeBuilderFallback.Abort, true),
                                        Tuple.Create(TessellatedShapeBuilderTarget.Solid, TessellatedShapeBuilderFallback.Salvage, true),
                                        Tuple.Create(TessellatedShapeBuilderTarget.AnyGeometry, TessellatedShapeBuilderFallback.Mesh, true),
                                        Tuple.Create(TessellatedShapeBuilderTarget.Solid, TessellatedShapeBuilderFallback.Salvage, false),
                                        Tuple.Create(TessellatedShapeBuilderTarget.AnyGeometry, TessellatedShapeBuilderFallback.Mesh, false),
                                    })
                                    {
                                        try
                                        {
                                            var res = build(mode.Item1, mode.Item2, mode.Item3);
                                            if (res != null)
                                                sols = res.OfType<Solid>().Where(s => s.Volume > 1e-12).ToList();
                                        }
                                        catch { sols = new List<Solid>(); }
                                        if (sols.Count > 0)
                                        {
                                            won = mode.Item1 + "/" + mode.Item2 + "/closed=" + mode.Item3;
                                            break;
                                        }
                                    }
                                    if (won != null) modes[won] = modes.TryGetValue(won, out var nw) ? nw + 1 : 1;

                                    if (sols.Count > 0)
                                    {
                                        foreach (var s in sols)
                                        {
                                            var ffe = FreeFormElement.Create(fdoc, s);
                                            if (matId != ElementId.InvalidElementId)
                                                ffe.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)?.Set(matId);
                                            // the 3D belongs in 3D and Fine views; plans read the 2D outline
                                            if (fineOnly)
                                                try
                                                {
                                                    ffe.SetVisibility(new FamilyElementVisibility(FamilyElementVisibilityType.Model)
                                                    { IsShownInCoarse = false, IsShownInMedium = false, IsShownInFine = true });
                                                }
                                                catch { }
                                        }
                                        solids++;
                                    }
                                    else
                                    {
                                        try
                                        {
                                            var res = build(TessellatedShapeBuilderTarget.Mesh,
                                                            TessellatedShapeBuilderFallback.Salvage, false);
                                            if (res == null || res.Count == 0)
                                                throw new Exception("Revit built no geometry at all");
                                            var ds = DirectShape.CreateElement(fdoc, new ElementId(BuiltInCategory.OST_Furniture));
                                            ds.ApplicationId = "BAAK";
                                            ds.ApplicationDataId = Path.GetFileNameWithoutExtension(file);
                                            ds.SetShape(res.ToList());
                                            meshed++;
                                        }
                                        catch (Exception ex)
                                        {
                                            failed++;
                                            if (errs.Count < 12) errs.Add(Path.GetFileName(file) + ": " + ex.Message);
                                        }
                                    }
                                }

                                // The plan representation: a clean 2D outline, the way a manufacturer
                                // family draws. Without it a plan shows every triangle of the 3D.
                                if (p.TryGetProperty("outlines", out var oArr) && oArr.ValueKind == JsonValueKind.Array)
                                {
                                    var sp = SketchPlane.Create(fdoc,
                                        Plane.CreateByNormalAndOrigin(XYZ.BasisZ, XYZ.Zero));
                                    var seen = new FamilyElementVisibility(FamilyElementVisibilityType.ViewSpecific)
                                    { IsShownInCoarse = true, IsShownInMedium = true, IsShownInFine = !fineOnly };
                                    foreach (var loop in oArr.EnumerateArray())
                                    {
                                        var pts = loop.EnumerateArray()
                                            .Select(e => new XYZ(M(e[0].GetDouble()), M(e[1].GetDouble()), 0))
                                            .ToList();
                                        for (int i = 0; i + 1 < pts.Count; i++)
                                        {
                                            if (pts[i].DistanceTo(pts[i + 1]) < 0.004) continue;   // under Revit's shortest curve
                                            try
                                            {
                                                var sc = fdoc.FamilyCreate.NewSymbolicCurve(
                                                    Line.CreateBound(pts[i], pts[i + 1]), sp);
                                                sc.SetVisibility(seen);
                                                curves++;
                                            }
                                            catch { }
                                        }
                                    }
                                }

                                var fm = fdoc.FamilyManager;
                                if (fm.Types.Size == 0) fm.NewType(typeName);
                                else
                                {
                                    foreach (FamilyType ft in fm.Types) { fm.CurrentType = ft; break; }
                                    try { fm.RenameCurrentType(typeName); } catch { }
                                }
                                // the repérage is only useful if it schedules: carry the dossier wording
                                foreach (var kv in new[]
                                {
                                    new { bip = BuiltInParameter.ALL_MODEL_DESCRIPTION, val = S(p, "description") },
                                    new { bip = BuiltInParameter.ALL_MODEL_MANUFACTURER, val = S(p, "manufacturer") },
                                    new { bip = BuiltInParameter.ALL_MODEL_MODEL, val = S(p, "model") },
                                    new { bip = BuiltInParameter.ALL_MODEL_TYPE_COMMENTS, val = S(p, "type_comments") },
                                })
                                {
                                    if (string.IsNullOrEmpty(kv.val)) continue;
                                    try
                                    {
                                        var fp2 = fm.get_Parameter(kv.bip);
                                        if (fp2 != null) fm.Set(fp2, kv.val);
                                    }
                                    catch { }
                                }
                                t.Commit();
                            }

                            Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                            fdoc.SaveAs(outPath, new SaveAsOptions { OverwriteExistingFile = true });
                        }
                        finally { try { fdoc.Close(false); } catch { } }

                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = solids > 0,
                            ["rfa"] = outPath,
                            ["solids"] = solids,
                            ["mesh_only"] = meshed,
                            ["failed"] = failed,
                            ["triangles"] = tris,
                            ["errors"] = errs,
                            ["plan_curves"] = curves,
                            ["solid_modes"] = modes,
                            ["local_bbox_min_m"] = solids + meshed + failed > 0 ? lo : null,
                            ["local_bbox_max_m"] = solids + meshed + failed > 0 ? hi : null,
                        });
                    }

                // Bring the document's levels to the project's real ones. A level that moves takes
                // whatever is hosted on it, so the caller re-checks heights afterwards.
                case "set_levels":
                    {
                        var d = Doc(uiapp);
                        if (p.ValueKind != JsonValueKind.Object || !p.TryGetProperty("levels", out var arr)
                            || arr.ValueKind != JsonValueKind.Array)
                            throw new Exception("levels must be an array");

                        var done = new List<Dictionary<string, object>>();
                        using (var t = new Transaction(d, "BAAK MCP - set levels"))
                        {
                            t.Start();
                            foreach (var q in arr.EnumerateArray())
                            {
                                string name = S(q, "name") ?? throw new Exception("each level needs a name");
                                string from = S(q, "from");
                                double elev = D(q, "elev_m");
                                var all = new FilteredElementCollector(d).OfClass(typeof(Level))
                                          .Cast<Level>().ToList();
                                var lv = !string.IsNullOrEmpty(from)
                                    ? all.FirstOrDefault(l => l.Name.Equals(from, StringComparison.OrdinalIgnoreCase))
                                    : all.FirstOrDefault(l => l.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
                                string what;
                                double was = 0;
                                if (lv == null)
                                {
                                    lv = Level.Create(d, M(elev));
                                    try { lv.Name = name; } catch { }
                                    what = "created";
                                }
                                else
                                {
                                    was = ToM(lv.Elevation);
                                    if (!lv.Name.Equals(name, StringComparison.Ordinal))
                                    { try { lv.Name = name; } catch { } }
                                    if (Math.Abs(was - elev) > 1e-9) lv.Elevation = M(elev);
                                    what = Math.Abs(was - elev) > 1e-9 ? "moved" : "renamed";
                                }
                                done.Add(new Dictionary<string, object>
                                {
                                    ["name"] = lv.Name, ["elev_m"] = elev,
                                    ["was_m"] = was, ["action"] = what,
                                });
                            }
                            t.Commit();
                        }
                        var now = new FilteredElementCollector(d).OfClass(typeof(Level)).Cast<Level>()
                                  .OrderBy(l => l.Elevation)
                                  .Select(l => new Dictionary<string, object>
                                  { ["name"] = l.Name, ["elev_m"] = ToM(l.Elevation) }).ToList();
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["changed"] = done, ["levels"] = now });
                    }

                // Export views to DWG for AutoCAD. Deliverables go under D:\DCE SITE with a new
                // name - never onto G:, and never over an existing file unless asked.
                case "export_dwg":
                    {
                        var d = Doc(uiapp);
                        string folder = S(p, "folder") ?? @"D:\DCE SITE\ARCHITECTURE\DWG";
                        string name = S(p, "name") ?? throw new Exception("name is required");
                        if (folder.TrimStart().StartsWith("G:", StringComparison.OrdinalIgnoreCase))
                            throw new Exception("G: is read-only for this project");
                        Directory.CreateDirectory(folder);

                        var views = new List<ElementId>();
                        var wanted = new List<string>();
                        if (p.TryGetProperty("views", out var vArr) && vArr.ValueKind == JsonValueKind.Array)
                            foreach (var e in vArr.EnumerateArray())
                                if (e.ValueKind == JsonValueKind.String) wanted.Add(e.GetString());
                        string one = S(p, "view");
                        if (!string.IsNullOrEmpty(one)) wanted.Add(one);

                        var all = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>()
                                  .Where(v => !v.IsTemplate && v.CanBePrinted).ToList();
                        if (wanted.Count == 0)
                        {
                            var av = d.ActiveView;
                            if (av == null) throw new Exception("no active view");
                            views.Add(av.Id);
                            wanted.Add(av.Name);
                        }
                        else
                            foreach (var w in wanted)
                            {
                                var v = all.FirstOrDefault(x => x.Name.Equals(w, StringComparison.OrdinalIgnoreCase))
                                        ?? throw new Exception("view not found: " + w);
                                views.Add(v.Id);
                            }

                        var opt = new DWGExportOptions
                        {
                            MergedViews = true,
                            SharedCoords = true,
                            ExportOfSolids = SolidGeometry.ACIS,
                            TargetUnit = ExportUnit.Meter,
                            HideUnreferenceViewTags = true,
                            HideScopeBox = true,
                            HideReferencePlane = true,
                        };
                        string ver = S(p, "version");
                        if (!string.IsNullOrEmpty(ver))
                        {
                            if (ver.Contains("2007")) opt.FileVersion = ACADVersion.R2007;
                            else if (ver.Contains("2010")) opt.FileVersion = ACADVersion.R2010;
                            else if (ver.Contains("2013")) opt.FileVersion = ACADVersion.R2013;
                            else opt.FileVersion = ACADVersion.R2018;
                        }

                        bool okExp = d.Export(folder, name, views, opt);
                        var made = Directory.GetFiles(folder, "*.dwg")
                                   .Where(f => File.GetLastWriteTime(f) > DateTime.Now.AddMinutes(-3))
                                   .Select(f => new Dictionary<string, object>
                                   { ["file"] = f, ["mb"] = Math.Round(new FileInfo(f).Length / 1048576.0, 2) })
                                   .ToList();
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = okExp, ["folder"] = folder, ["views"] = wanted, ["files"] = made,
                        });
                    }

                // Every element of one category (marked or not) with family, type, mark, level, position and box.
                // Where the tall part of each instance is (e.g. a sofa back): centroid of the geometry vertices in the
                // top 25 % of its height vs the centroid of all vertices, in project metres.
                case "top_centroid":
                    {
                        var d = Doc(uiapp);
                        var opt = new Options { ComputeReferences = false, DetailLevel = ViewDetailLevel.Fine };
                        var res = new Dictionary<string, object>();
                        if (p.TryGetProperty("ids", out var tcArr) && tcArr.ValueKind == JsonValueKind.Array)
                            foreach (var je in tcArr.EnumerateArray())
                            {
                                var el = d.GetElement(new ElementId(je.GetInt64()));
                                if (el == null) continue;
                                var pts = new List<XYZ>();
                                void Walk(GeometryElement ge, Transform tr)
                                {
                                    foreach (var g in ge)
                                    {
                                        if (g is Solid so) { foreach (Edge ed in so.Edges) foreach (var q in ed.Tessellate()) pts.Add(tr.OfPoint(q)); }
                                        else if (g is Mesh me) { foreach (var q in me.Vertices) pts.Add(tr.OfPoint(q)); }
                                        else if (g is GeometryInstance gi) Walk(gi.GetSymbolGeometry(), tr.Multiply(gi.Transform));
                                    }
                                }
                                var gel = el.get_Geometry(opt);
                                if (gel != null) Walk(gel, Transform.Identity);
                                if (pts.Count == 0) continue;
                                double zmin = pts.Min(q => q.Z), zmax = pts.Max(q => q.Z), zc = zmin + 0.75 * (zmax - zmin);
                                var top = pts.Where(q => q.Z >= zc).ToList();
                                res[el.Id.Value.ToString()] = new Dictionary<string, object>
                                {
                                    ["all_xy"] = new[] { Math.Round(ToM(pts.Average(q => q.X)), 3), Math.Round(ToM(pts.Average(q => q.Y)), 3) },
                                    ["top_xy"] = new[] { Math.Round(ToM(top.Average(q => q.X)), 3), Math.Round(ToM(top.Average(q => q.Y)), 3) },
                                    ["z"] = new[] { Math.Round(ToM(zmin), 3), Math.Round(ToM(zmax), 3) },
                                    ["n"] = pts.Count,
                                };
                            }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["items"] = res });
                    }

                // Plan footprint (convex hull, project metres) of the geometry of each instance.
                case "footprint":
                    {
                        var d = Doc(uiapp);
                        var opt = new Options { ComputeReferences = false, DetailLevel = ViewDetailLevel.Fine };
                        var res = new Dictionary<string, object>();
                        if (p.TryGetProperty("ids", out var fpArr) && fpArr.ValueKind == JsonValueKind.Array)
                            foreach (var je in fpArr.EnumerateArray())
                            {
                                var el = d.GetElement(new ElementId(je.GetInt64()));
                                if (el == null) continue;
                                var pts = new List<XYZ>();
                                void Walk(GeometryElement ge, Transform tr)
                                {
                                    foreach (var g in ge)
                                    {
                                        if (g is Solid so) { foreach (Edge ed in so.Edges) foreach (var q in ed.Tessellate()) pts.Add(tr.OfPoint(q)); }
                                        else if (g is Mesh me) { foreach (var q in me.Vertices) pts.Add(tr.OfPoint(q)); }
                                        else if (g is GeometryInstance gi) Walk(gi.GetSymbolGeometry(), tr.Multiply(gi.Transform));
                                    }
                                }
                                var gel = el.get_Geometry(opt);
                                if (gel != null) Walk(gel, Transform.Identity);
                                var P = pts.Select(q => (x: ToM(q.X), y: ToM(q.Y))).Distinct().OrderBy(q => q.x).ThenBy(q => q.y).ToList();
                                if (P.Count < 3) continue;
                                double Cross((double x, double y) o, (double x, double y) a, (double x, double y) b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
                                var H = new List<(double x, double y)>();
                                foreach (var q in P) { while (H.Count >= 2 && Cross(H[H.Count - 2], H[H.Count - 1], q) <= 0) H.RemoveAt(H.Count - 1); H.Add(q); }
                                int lower = H.Count + 1;
                                for (int i = P.Count - 2; i >= 0; i--) { var q = P[i]; while (H.Count >= lower && Cross(H[H.Count - 2], H[H.Count - 1], P[i]) <= 0) H.RemoveAt(H.Count - 1); H.Add(q); }
                                H.RemoveAt(H.Count - 1);
                                res[el.Id.Value.ToString()] = H.Select(q => new[] { Math.Round(q.x, 3), Math.Round(q.y, 3) }).ToList();
                            }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["hulls"] = res });
                    }

                // For each point, the nearest ceiling / beam / floor / roof face straight above it (z in metres), within 8 m.
                // Uses a dedicated 3D view "BAAK MCP rayons" (no section box) so nothing is clipped.
                case "soffit":
                    {
                        var d = Doc(uiapp);
                        var v3 = new FilteredElementCollector(d).OfClass(typeof(View3D)).Cast<View3D>()
                                 .FirstOrDefault(v => !v.IsTemplate && v.Name == "BAAK MCP rayons");
                        if (v3 == null)
                            using (var t = new Transaction(d, "BAAK MCP - rays view"))
                            {
                                t.Start();
                                var vft = new FilteredElementCollector(d).OfClass(typeof(ViewFamilyType)).Cast<ViewFamilyType>()
                                          .First(x => x.ViewFamily == ViewFamily.ThreeDimensional);
                                v3 = View3D.CreateIsometric(d, vft.Id);
                                v3.Name = "BAAK MCP rayons";
                                if (v3.ViewTemplateId != ElementId.InvalidElementId) v3.ViewTemplateId = ElementId.InvalidElementId;
                                v3.IsSectionBoxActive = false;
                                t.Commit();
                            }
                        var cats = new Dictionary<BuiltInCategory, string>
                        {
                            [BuiltInCategory.OST_Ceilings] = "ceiling",
                            [BuiltInCategory.OST_StructuralFraming] = "beam",
                            [BuiltInCategory.OST_Floors] = "floor",
                            [BuiltInCategory.OST_Roofs] = "roof",
                        };
                        var ri = new ReferenceIntersector(new ElementMulticategoryFilter(cats.Keys.ToList()), FindReferenceTarget.Face, v3)
                        { FindReferencesInRevitLinks = false };
                        var outPts = new List<Dictionary<string, object>>();
                        foreach (var q in p.GetProperty("points").EnumerateArray())
                        {
                            var a = q.EnumerateArray().Select(x => x.GetDouble()).ToArray();
                            var o = new XYZ(M(a[0]), M(a[1]), M(a[2]));
                            var row = new Dictionary<string, object>();
                            foreach (var h in ri.Find(o, XYZ.BasisZ))
                            {
                                if (h.Proximity > M(8)) continue;
                                var el = d.GetElement(h.GetReference().ElementId);
                                if (el?.Category == null) continue;
                                var bic = (BuiltInCategory)el.Category.Id.Value;
                                if (!cats.TryGetValue(bic, out var key)) continue;
                                double z = Math.Round(a[2] + ToM(h.Proximity), 3);
                                if (!row.ContainsKey(key) || (double)row[key] > z) { row[key] = z; row[key + "_id"] = el.Id.Value; }
                            }
                            outPts.Add(row);
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["points"] = outPts });
                    }

                // MEP types available in the document (pipes, ducts, their systems).
                case "mep_types":
                    {
                        var d = Doc(uiapp);
                        object Rows<T>() where T : Element => new FilteredElementCollector(d).OfClass(typeof(T)).Cast<T>()
                            .Select(t => new Dictionary<string, object> { ["id"] = t.Id.Value, ["name"] = t.Name }).ToList();
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = true,
                            ["pipe_types"] = Rows<Autodesk.Revit.DB.Plumbing.PipeType>(),
                            ["piping_systems"] = Rows<Autodesk.Revit.DB.Plumbing.PipingSystemType>(),
                            ["duct_types"] = Rows<Autodesk.Revit.DB.Mechanical.DuctType>(),
                            ["duct_systems"] = Rows<Autodesk.Revit.DB.Mechanical.MechanicalSystemType>(),
                        });
                    }

                // Create pipes or ducts from straight segments (project metres). params: kind "pipe"|"duct", level,
                // type (name, optional), segments [{x1,y1,z1,x2,y2,z2, d_mm | w_mm,h_mm, system (name), comment}].
                // One transaction; failing segments are reported, not fatal. Neighbouring ends within 5 mm get an elbow.
                case "create_mep":
                    {
                        var d = Doc(uiapp);
                        bool isDuct = (S(p, "kind") ?? "pipe") == "duct";
                        var lvl = LevelByName(d, S(p, "level"));
                        string typeName = S(p, "type");
                        ElementId typeId;
                        if (isDuct)
                            typeId = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.DuctType)).Cast<Element>()
                                     .OrderBy(t => typeName != null && t.Name == typeName ? 0 : 1).First().Id;
                        else
                            typeId = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Plumbing.PipeType)).Cast<Element>()
                                     .OrderBy(t => typeName != null && t.Name == typeName ? 0 : 1).First().Id;
                        var systems = isDuct
                            ? new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.MechanicalSystemType)).Cast<Element>().ToList()
                            : new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Plumbing.PipingSystemType)).Cast<Element>().ToList();
                        var made = new List<long>(); var errs = new List<string>();
                        bool elbows = !(p.TryGetProperty("elbows", out var elEl) && elEl.ValueKind == JsonValueKind.False);
                        using (var t = new Transaction(d, isDuct ? "BAAK MCP - ducts" : "BAAK MCP - pipes"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            var curves = new List<MEPCurve>();
                            int k = 0;
                            if (p.TryGetProperty("segments", out var segs) && segs.ValueKind == JsonValueKind.Array)
                                foreach (var s in segs.EnumerateArray())
                                {
                                    k++;
                                    try
                                    {
                                        var a = new XYZ(M(D(s, "x1")), M(D(s, "y1")), M(D(s, "z1")));
                                        var b = new XYZ(M(D(s, "x2")), M(D(s, "y2")), M(D(s, "z2")));
                                        if (a.DistanceTo(b) < M(0.02)) continue;
                                        string sysName = S(s, "system");
                                        var sys = systems.OrderBy(x => sysName != null && x.Name.IndexOf(sysName, StringComparison.OrdinalIgnoreCase) >= 0 ? 0 : 1).First();
                                        MEPCurve c;
                                        string segType = S(s, "type");
                                        if (isDuct)
                                        {
                                            double dm = D(s, "d_mm");
                                            var dts = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.DuctType))
                                                      .Cast<Autodesk.Revit.DB.Mechanical.DuctType>().ToList();
                                            var wantShape = dm > 0 ? ConnectorProfileType.Round : ConnectorProfileType.Rectangular;
                                            var shapeT = (segType != null ? dts.FirstOrDefault(x => x.Name == segType && x.Shape == wantShape) : null)
                                                         ?? dts.Where(x => x.Shape == wantShape).OrderBy(x => x.Name.StartsWith("BAAK") ? 0 : 1).FirstOrDefault();
                                            var du = Autodesk.Revit.DB.Mechanical.Duct.Create(d, sys.Id, shapeT?.Id ?? typeId, lvl.Id, a, b);
                                            if (dm > 0) du.get_Parameter(BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)?.Set(M(dm / 1000));
                                            else
                                            {
                                                du.get_Parameter(BuiltInParameter.RBS_CURVE_WIDTH_PARAM)?.Set(M(D(s, "w_mm", 400) / 1000));
                                                du.get_Parameter(BuiltInParameter.RBS_CURVE_HEIGHT_PARAM)?.Set(M(D(s, "h_mm", 250) / 1000));
                                            }
                                            c = du;
                                        }
                                        else
                                        {
                                            var ptId = segType == null ? typeId
                                                : (new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Plumbing.PipeType)).Cast<Element>()
                                                   .FirstOrDefault(x => x.Name == segType)?.Id ?? typeId);
                                            var pi = Autodesk.Revit.DB.Plumbing.Pipe.Create(d, sys.Id, ptId, lvl.Id, a, b);
                                            pi.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)?.Set(M(D(s, "d_mm", 50) / 1000));
                                            c = pi;
                                        }
                                        string cm = S(s, "comment");
                                        if (cm != null) c.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.Set(cm);
                                        curves.Add(c); made.Add(c.Id.Value);
                                    }
                                    catch (Exception ex) { errs.Add("segment " + k + ": " + ex.Message); }
                                }
                            int nElb = 0;
                            if (elbows)
                            {
                                double tol = M(0.005);
                                for (int i = 0; i < curves.Count; i++)
                                    for (int j = i + 1; j < curves.Count; j++)
                                    {
                                        foreach (Connector ci in curves[i].ConnectorManager.Connectors)
                                        {
                                            if (ci.IsConnected) continue;
                                            foreach (Connector cj in curves[j].ConnectorManager.Connectors)
                                            {
                                                if (cj.IsConnected || ci.Origin.DistanceTo(cj.Origin) > tol) continue;
                                                try
                                                {
                                                    var di = ((LocationCurve)curves[i].Location).Curve as Line;
                                                    var dj = ((LocationCurve)curves[j].Location).Curve as Line;
                                                    if (di == null || dj == null || di.Length < M(0.30) || dj.Length < M(0.30)) continue;
                                                    if (di != null && dj != null && Math.Abs(di.Direction.DotProduct(dj.Direction)) > 0.999) ci.ConnectTo(cj);
                                                    else d.Create.NewElbowFitting(ci, cj);
                                                    nElb++;
                                                }
                                                catch (Exception ex) { errs.Add("elbow " + curves[i].Id.Value + "/" + curves[j].Id.Value + ": " + ex.Message); }
                                            }
                                        }
                                    }
                            }
                            t.Commit();
                            return J(new Dictionary<string, object> { ["ok"] = true, ["created"] = made.Count, ["ids"] = made, ["joints"] = nElb, ["errors"] = errs.Take(40).ToList(), ["n_errors"] = errs.Count });
                        }
                    }

                // A real native family (Revit forms, no mesh): parts [{kind:"revolve", profile:[[r,z],...]} | {kind:"extrude",
                // loop:[[x,y],...], z0, z1}], metres, family-local (origin = insertion point, Z up). One material per part
                // (material_name/rgb on the part, else the family's). Saved to out (.rfa), not loaded.
                case "make_native_family":
                    {
                        string template = S(p, "template") ?? throw new Exception("template is required");
                        string outPath = S(p, "out") ?? throw new Exception("out is required");
                        var fdoc = app.NewFamilyDocument(template);
                        int made = 0; var errs = new List<string>();
                        try
                        {
                            using (var t = new Transaction(fdoc, "BAAK MCP - native family"))
                            {
                                t.Start();
                                var fhoF = t.GetFailureHandlingOptions(); fhoF.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fhoF);
                                var mats = new Dictionary<string, ElementId>();
                                Func<string, int, int, int, ElementId> matOf = (nm, r, g, b) =>
                                {
                                    if (string.IsNullOrEmpty(nm)) return ElementId.InvalidElementId;
                                    if (mats.TryGetValue(nm, out var id)) return id;
                                    var ex = new FilteredElementCollector(fdoc).OfClass(typeof(Material)).Cast<Material>().FirstOrDefault(m => m.Name == nm);
                                    id = ex?.Id ?? Material.Create(fdoc, nm);
                                    var mt = (Material)fdoc.GetElement(id);
                                    mt.Color = new Color((byte)r, (byte)g, (byte)b);
                                    mats[nm] = id;
                                    return id;
                                };
                                string fMat = S(p, "material_name");
                                int fr = (int)D(p, "material_r", 160), fg = (int)D(p, "material_g", 160), fb = (int)D(p, "material_b", 160);
                                int k = 0;
                                foreach (var part in p.GetProperty("parts").EnumerateArray())
                                {
                                    k++;
                                    try
                                    {
                                        string kind = S(part, "kind") ?? "extrude";
                                        GenericForm form = null;
                                        // closed loop of points -> curves: straight lines, or (smooth) a few Hermite splines through the points
                                        Func<List<XYZ>, bool, CurveArray> loopCurves = (pts, smooth) =>
                                        {
                                            var ca = new CurveArray();
                                            var clean = new List<XYZ>();
                                            foreach (var q in pts) if (clean.Count == 0 || clean[clean.Count - 1].DistanceTo(q) > M(0.002)) clean.Add(q);
                                            if (clean.Count > 2 && clean[0].DistanceTo(clean[clean.Count - 1]) < M(0.002)) clean.RemoveAt(clean.Count - 1);
                                            if (smooth && clean.Count >= 12)
                                            {
                                                int chunks = Math.Max(3, clean.Count / 10), n = clean.Count;
                                                for (int c = 0; c < chunks; c++)
                                                {
                                                    int a0 = c * n / chunks, a1 = (c + 1) * n / chunks;
                                                    var seg = new List<XYZ>();
                                                    for (int i = a0; i <= a1; i++) seg.Add(clean[i % n]);
                                                    if (seg.Count >= 3) ca.Append(HermiteSpline.Create(seg, false));
                                                    else ca.Append(Line.CreateBound(seg[0], seg[seg.Count - 1]));
                                                }
                                            }
                                            else
                                                for (int i = 0; i < clean.Count; i++) ca.Append(Line.CreateBound(clean[i], clean[(i + 1) % clean.Count]));
                                            return ca;
                                        };
                                        if (kind == "blend")
                                        {
                                            double z0 = D(part, "z0"), z1 = D(part, "z1");
                                            var bp = loopCurves(part.GetProperty("base").EnumerateArray().Select(q => new XYZ(M(q[0].GetDouble()), M(q[1].GetDouble()), M(z0))).ToList(), false);
                                            var tp = loopCurves(part.GetProperty("top").EnumerateArray().Select(q => new XYZ(M(q[0].GetDouble()), M(q[1].GetDouble()), M(z1))).ToList(), false);
                                            var sp = SketchPlane.Create(fdoc, Plane.CreateByNormalAndOrigin(XYZ.BasisZ, new XYZ(0, 0, M(z0))));
                                            using (var st = new SubTransaction(fdoc))
                                            {
                                                st.Start();
                                                form = fdoc.FamilyCreate.NewBlend(true, tp, bp, sp);
                                                fdoc.Regenerate();
                                                st.Commit();
                                            }
                                        }
                                        else if (kind == "revolve")
                                        {
                                            double ax = 0, ay = 0;
                                            if (part.TryGetProperty("axis_xy", out var axv)) { ax = axv[0].GetDouble(); ay = axv[1].GetDouble(); }
                                            var o = new XYZ(M(ax), M(ay), 0);
                                            var pts = part.GetProperty("profile").EnumerateArray()
                                                      .Select(q => o + new XYZ(M(q[0].GetDouble()), 0, M(q[1].GetDouble()))).ToList();
                                            var sp = SketchPlane.Create(fdoc, Plane.CreateByNormalAndOrigin(XYZ.BasisY, o));
                                            bool smoothR = part.TryGetProperty("smooth", out var srv) && srv.ValueKind == JsonValueKind.True;
                                            // smooth profile: runs of points off the axis become splines, segments touching the axis stay lines
                                            Func<bool, CurveArrArray> prof = sm =>
                                            {
                                                var ca = new CurveArray();
                                                var clean = new List<XYZ>();
                                                foreach (var q in pts) if (clean.Count == 0 || clean[clean.Count - 1].DistanceTo(q) > M(0.0015)) clean.Add(q);
                                                if (clean.Count > 2 && clean[0].DistanceTo(clean[clean.Count - 1]) < M(0.0015)) clean.RemoveAt(clean.Count - 1);
                                                Func<XYZ, bool> onAxis = q => new XYZ(q.X - o.X, q.Y - o.Y, 0).GetLength() < M(0.0005);
                                                int n = clean.Count, i0 = 0;
                                                if (sm) { while (i0 < n && !onAxis(clean[i0])) i0++; if (i0 == n) { i0 = 0; sm = false; } }
                                                var run = new List<XYZ>();
                                                for (int k = 0; k <= n; k++)
                                                {
                                                    var q = clean[(i0 + k) % n];
                                                    if (!sm) { if (k > 0) ca.Append(Line.CreateBound(clean[(i0 + k - 1) % n], q)); continue; }
                                                    run.Add(q);
                                                    bool end = onAxis(q) && run.Count > 1;
                                                    if (end || k == n)
                                                    {
                                                        if (run.Count <= 3) { for (int m = 1; m < run.Count; m++) ca.Append(Line.CreateBound(run[m - 1], run[m])); }
                                                        else
                                                        {
                                                            ca.Append(Line.CreateBound(run[0], run[1]));
                                                            var mid = run.GetRange(1, run.Count - 2);
                                                            if (mid.Count >= 3) ca.Append(HermiteSpline.Create(mid, false)); else ca.Append(Line.CreateBound(mid[0], mid[mid.Count - 1]));
                                                            ca.Append(Line.CreateBound(run[run.Count - 2], run[run.Count - 1]));
                                                        }
                                                        run = new List<XYZ> { q };
                                                    }
                                                }
                                                var caa = new CurveArrArray(); caa.Append(ca); return caa;
                                            };
                                            try
                                            {
                                                using (var st = new SubTransaction(fdoc))
                                                {
                                                    st.Start();
                                                    form = fdoc.FamilyCreate.NewRevolution(true, prof(smoothR), sp, Line.CreateBound(o, o + XYZ.BasisZ), 0, 2 * Math.PI);
                                                    fdoc.Regenerate();
                                                    st.Commit();
                                                }
                                            }
                                            catch when (smoothR)
                                            {
                                                form = fdoc.FamilyCreate.NewRevolution(true, prof(false), sp, Line.CreateBound(o, o + XYZ.BasisZ), 0, 2 * Math.PI);
                                            }
                                        }
                                        else
                                        {
                                            double z0 = D(part, "z0"), z1 = D(part, "z1");
                                            bool smooth = part.TryGetProperty("smooth", out var smv) && smv.ValueKind == JsonValueKind.True;
                                            var sp = SketchPlane.Create(fdoc, Plane.CreateByNormalAndOrigin(XYZ.BasisZ, new XYZ(0, 0, M(z0))));
                                            Func<bool, CurveArrArray> build = sm =>
                                            {
                                                var caa = new CurveArrArray();
                                                if (part.TryGetProperty("circles", out var cs))
                                                    foreach (var c in cs.EnumerateArray())      // [cx, cy, r]
                                                    {
                                                        var cc = new XYZ(M(c[0].GetDouble()), M(c[1].GetDouble()), M(z0)); double r = M(c[2].GetDouble());
                                                        var ca = new CurveArray();
                                                        ca.Append(Arc.Create(cc, r, 0, Math.PI, XYZ.BasisX, XYZ.BasisY));
                                                        ca.Append(Arc.Create(cc, r, Math.PI, 2 * Math.PI, XYZ.BasisX, XYZ.BasisY));
                                                        caa.Append(ca);
                                                    }
                                                var loops = new List<JsonElement>();
                                                if (part.TryGetProperty("loops", out var ls)) loops.AddRange(ls.EnumerateArray());
                                                if (part.TryGetProperty("loop", out var l1)) loops.Add(l1);
                                                foreach (var lp in loops)
                                                    caa.Append(loopCurves(lp.EnumerateArray().Select(q => new XYZ(M(q[0].GetDouble()), M(q[1].GetDouble()), M(z0))).ToList(), sm));
                                                return caa;
                                            };
                                            try
                                            {
                                                using (var st = new SubTransaction(fdoc))
                                                {
                                                    st.Start();
                                                    form = fdoc.FamilyCreate.NewExtrusion(true, build(smooth), sp, M(z1 - z0));
                                                    fdoc.Regenerate();
                                                    st.Commit();
                                                }
                                            }
                                            catch when (smooth)
                                            {
                                                form = fdoc.FamilyCreate.NewExtrusion(true, build(false), sp, M(z1 - z0));
                                            }
                                        }
                                        string pm = S(part, "material_name") ?? fMat;
                                        var mid = S(part, "material_name") != null
                                            ? matOf(pm, (int)D(part, "material_r", 160), (int)D(part, "material_g", 160), (int)D(part, "material_b", 160))
                                            : matOf(pm, fr, fg, fb);
                                        if (mid != ElementId.InvalidElementId) form.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)?.Set(mid);
                                        made++;
                                    }
                                    catch (Exception ex) { errs.Add("part " + k + ": " + ex.Message); }
                                }
                                string tn = S(p, "type_name");
                                if (!string.IsNullOrEmpty(tn))
                                {
                                    var fm = fdoc.FamilyManager;
                                    if (fm.CurrentType == null) fm.NewType(tn); else fm.RenameCurrentType(tn);
                                }
                                t.Commit();
                            }
                            var so = new SaveAsOptions { OverwriteExistingFile = true };
                            fdoc.SaveAs(outPath, so);
                        }
                        finally { fdoc.Close(false); }
                        return J(new Dictionary<string, object> { ["ok"] = made > 0 && errs.Count == 0, ["out"] = outPath, ["parts"] = made, ["errors"] = errs });
                    }

                // What each family used in the furniture-like categories is made of (opened in the family editor, not saved):
                // native forms (extrusion, revolution, blend, sweep) vs mesh (FreeFormElement, DirectShape, import).
                case "family_audit":
                    {
                        var d = Doc(uiapp);
                        var cats = new HashSet<long> {
                            (long)BuiltInCategory.OST_Furniture, (long)BuiltInCategory.OST_GenericModel, (long)BuiltInCategory.OST_Planting,
                            (long)BuiltInCategory.OST_LightingFixtures, (long)BuiltInCategory.OST_Casework, (long)BuiltInCategory.OST_SpecialityEquipment,
                            (long)BuiltInCategory.OST_FurnitureSystems, (long)BuiltInCategory.OST_PlumbingFixtures };
                        string only = S(p, "family");
                        var groups = new FilteredElementCollector(d).OfClass(typeof(FamilyInstance)).Cast<FamilyInstance>()
                            .Where(fi => fi.Category != null && cats.Contains(fi.Category.Id.Value) && fi.SuperComponent == null)
                            .GroupBy(fi => fi.Symbol.Family.Id.Value).ToList();
                        var rows = new List<object>();
                        foreach (var g in groups)
                        {
                            var fam = d.GetElement(new ElementId(g.Key)) as Family;
                            if (only != null && fam.Name != only) continue;
                            var row = new Dictionary<string, object>
                            {
                                ["family"] = fam.Name, ["family_id"] = fam.Id.Value, ["category"] = g.First().Category.Name, ["instances"] = g.Count(),
                                ["types"] = g.Select(x => x.Symbol.Name).Distinct().ToList(), ["ids"] = g.Select(x => x.Id.Value).ToList()
                            };
                            if (!fam.IsEditable) { row["editable"] = false; rows.Add(row); continue; }
                            Document fd = null;
                            try
                            {
                                fd = d.EditFamily(fam);
                                Func<Type, int> n = ty => new FilteredElementCollector(fd).OfClass(ty).GetElementCount();
                                row["freeform"] = n(typeof(FreeFormElement)); row["directshape"] = n(typeof(DirectShape)); row["import"] = n(typeof(ImportInstance));
                                row["extrusion"] = n(typeof(Extrusion)); row["revolution"] = n(typeof(Revolution)); row["blend"] = n(typeof(Blend));
                                row["sweep"] = n(typeof(Sweep)); row["sweptblend"] = n(typeof(SweptBlend)); row["nested"] = n(typeof(FamilyInstance));
                            }
                            catch (Exception ex) { row["error"] = ex.Message; }
                            finally { fd?.Close(false); }
                            rows.Add(row);
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["families"] = rows });
                    }

                // The geometry of one family instance as a BKMSH1 mesh in the FAMILY-LOCAL frame (instance transform removed), metres.
                case "export_instance_mesh":
                    {
                        var d = Doc(uiapp);
                        var fi = d.GetElement(new ElementId((long)D(p, "id"))) as FamilyInstance ?? throw new Exception("not a family instance");
                        string outPath = S(p, "out") ?? throw new Exception("out is required");
                        var opt = new Options { DetailLevel = ViewDetailLevel.Fine, ComputeReferences = false };
                        var tr = fi.GetTransform(); var inv = tr.Inverse;
                        var V = new List<XYZ>(); var Fs = new List<int>();
                        Action<Mesh> addMesh = m =>
                        {
                            int b = V.Count;
                            foreach (var v in m.Vertices) V.Add(inv.OfPoint(v));
                            for (int i = 0; i < m.NumTriangles; i++)
                            {
                                var t3 = m.get_Triangle(i);
                                Fs.Add(b + (int)t3.get_Index(0)); Fs.Add(b + (int)t3.get_Index(1)); Fs.Add(b + (int)t3.get_Index(2));
                            }
                        };
                        Action<GeometryElement> walk = null;
                        walk = ge =>
                        {
                            foreach (var g in ge)
                            {
                                if (g is GeometryInstance gi) walk(gi.GetInstanceGeometry());
                                else if (g is Solid so && so.Faces.Size > 0) { foreach (Face f in so.Faces) { var m = f.Triangulate(0.6); if (m != null) addMesh(m); } }
                                else if (g is Mesh me) addMesh(me);
                            }
                        };
                        walk(fi.get_Geometry(opt));
                        if (V.Count == 0) throw new Exception("no geometry");
                        using (var fs = new FileStream(outPath, FileMode.Create))
                        using (var bw = new BinaryWriter(fs))
                        {
                            bw.Write("BKMSH1".ToCharArray()); bw.Write((uint)V.Count); bw.Write((uint)(Fs.Count / 3));
                            foreach (var v in V) { bw.Write(ToM(v.X)); bw.Write(ToM(v.Y)); bw.Write(ToM(v.Z)); }
                            foreach (var i in Fs) bw.Write(i);
                        }
                        var lp = (fi.Location as LocationPoint)?.Point ?? tr.Origin;
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = true, ["out"] = outPath, ["vertices"] = V.Count, ["triangles"] = Fs.Count / 3,
                            ["origin_m"] = new[] { ToM(lp.X), ToM(lp.Y), ToM(lp.Z) }, ["rot_deg"] = Math.Atan2(tr.BasisX.Y, tr.BasisX.X) * 180 / Math.PI,
                            ["mirrored"] = fi.Mirrored, ["family"] = fi.Symbol.FamilyName, ["type"] = fi.Symbol.Name
                        });
                    }

                // Replace instances by another family/type at exactly the same transform (location, rotation, level),
                // carrying Mark and Comments over; the old instance is deleted first so marks never clash.
                // items [{old_id, family, type}]
                case "swap_instances":
                    {
                        var d = Doc(uiapp);
                        var syms = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>().ToList();
                        var res = new List<object>(); int ok = 0;
                        using (var t = new Transaction(d, "BAAK MCP - swap instances"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            foreach (var it in p.GetProperty("items").EnumerateArray())
                            {
                                var row = new Dictionary<string, object> { ["old_id"] = (long)D(it, "old_id") };
                                using (var st = new SubTransaction(d))
                                {
                                    st.Start();
                                    try
                                    {
                                        var old = d.GetElement(new ElementId((long)D(it, "old_id"))) as FamilyInstance ?? throw new Exception("old instance not found");
                                        string fn = S(it, "family"), tn = S(it, "type");
                                        var sym = syms.Where(s => s.FamilyName == fn).OrderBy(s => tn != null && s.Name == tn ? 0 : 1).FirstOrDefault()
                                                  ?? throw new Exception("family not loaded: " + fn);
                                        if (!sym.IsActive) { sym.Activate(); d.Regenerate(); }
                                        var tr = old.GetTransform();
                                        var loc = (old.Location as LocationPoint)?.Point ?? tr.Origin;
                                        var lvl = d.GetElement(old.LevelId) as Level ?? LevelByName(d, null);
                                        string mark = old.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString();
                                        string cm = old.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.AsString();
                                        bool mir = old.Mirrored;
                                        d.Delete(old.Id);
                                        var ni = d.Create.NewFamilyInstance(loc, sym, lvl, StructuralType.NonStructural);
                                        d.Regenerate();
                                        var nl = (ni.Location as LocationPoint).Point;
                                        if (nl.DistanceTo(loc) > 1e-7) ElementTransformUtils.MoveElement(d, ni.Id, loc - nl);
                                        double ang = Math.Atan2(tr.BasisX.Y, tr.BasisX.X);
                                        if (Math.Abs(ang) > 1e-9) ElementTransformUtils.RotateElement(d, ni.Id, Line.CreateBound(loc, loc + XYZ.BasisZ), ang);
                                        SetMarkAndComment(d, ni.Id, mark, cm);
                                        string extra = S(it, "comment_suffix");
                                        if (!string.IsNullOrEmpty(extra)) ni.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.Set((cm ?? "") + extra);
                                        st.Commit();
                                        row["new_id"] = ni.Id.Value; row["mark"] = mark; if (mir) row["was_mirrored"] = true; ok++;
                                    }
                                    catch (Exception ex) { st.RollBack(); row["err"] = ex.Message; }
                                }
                                res.Add(row);
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["swapped"] = ok, ["items"] = res });
                    }

                // Fittings / terminals / equipment families loaded, and the routing preferences of every duct and pipe type.
                case "mep_routing":
                    {
                        var d = Doc(uiapp);
                        var fam = new Dictionary<string, object>();
                        foreach (var bic in new[] { BuiltInCategory.OST_DuctFitting, BuiltInCategory.OST_PipeFitting, BuiltInCategory.OST_DuctTerminal, BuiltInCategory.OST_MechanicalEquipment })
                            fam[bic.ToString()] = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol)).OfCategory(bic).Cast<FamilySymbol>()
                                .Select(s => s.FamilyName + " : " + s.Name).ToList();
                        var rows = new List<object>();
                        foreach (var mt in new FilteredElementCollector(d).OfClass(typeof(MEPCurveType)).Cast<MEPCurveType>())
                        {
                            var row = new Dictionary<string, object> { ["id"] = mt.Id.Value, ["class"] = mt.GetType().Name, ["name"] = mt.Name };
                            if (mt is Autodesk.Revit.DB.Mechanical.DuctType dt) row["shape"] = dt.Shape.ToString();
                            RoutingPreferenceManager rpm = null;
                            try { rpm = mt.RoutingPreferenceManager; } catch { }
                            if (rpm != null)
                            {
                                var g = new Dictionary<string, object>();
                                foreach (RoutingPreferenceRuleGroupType gt in Enum.GetValues(typeof(RoutingPreferenceRuleGroupType)))
                                {
                                    try
                                    {
                                        int n = rpm.GetNumberOfRules(gt);
                                        var lst = new List<string>();
                                        for (int i = 0; i < n; i++)
                                        {
                                            var el = d.GetElement(rpm.GetRule(gt, i).MEPPartId);
                                            lst.Add(el is FamilySymbol fs ? fs.FamilyName + " : " + fs.Name : el?.Name);
                                        }
                                        g[gt.ToString()] = lst;
                                    }
                                    catch { }
                                }
                                row["groups"] = g;
                                try { row["junction"] = rpm.PreferredJunctionType.ToString(); } catch { }
                            }
                            rows.Add(row);
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["families"] = fam, ["types"] = rows });
                    }

                // Duplicate an element type (duct type, pipe type...) under a new name; returns the existing one if the name is taken.
                case "dup_type":
                    {
                        var d = Doc(uiapp);
                        var src = d.GetElement(new ElementId((long)D(p, "id"))) as ElementType ?? throw new Exception("type not found");
                        string name = S(p, "name") ?? throw new Exception("name is required");
                        var ex = new FilteredElementCollector(d).OfClass(src.GetType()).Cast<ElementType>().FirstOrDefault(x => x.Name == name);
                        if (ex != null) return J(new Dictionary<string, object> { ["ok"] = true, ["id"] = ex.Id.Value, ["existed"] = true });
                        ElementType nt;
                        using (var t = new Transaction(d, "BAAK MCP - duplicate type")) { t.Start(); nt = src.Duplicate(name); t.Commit(); }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["id"] = nt.Id.Value, ["existed"] = false });
                    }

                // Set routing preference groups of one duct/pipe type: groups {"Elbows": ["Family" | "Family : Type", ...], ...}
                // (each listed group is emptied first), junction "Tee"|"Tap".
                case "set_routing":
                    {
                        var d = Doc(uiapp);
                        var mt = d.GetElement(new ElementId((long)D(p, "type_id"))) as MEPCurveType ?? throw new Exception("type not found");
                        var rpm = mt.RoutingPreferenceManager;
                        var syms = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>().ToList();
                        var done = new Dictionary<string, object>();
                        using (var t = new Transaction(d, "BAAK MCP - routing preferences"))
                        {
                            t.Start();
                            if (p.TryGetProperty("groups", out var grs))
                                foreach (var g in grs.EnumerateObject())
                                {
                                    var gt = (RoutingPreferenceRuleGroupType)Enum.Parse(typeof(RoutingPreferenceRuleGroupType), g.Name);
                                    for (int i = rpm.GetNumberOfRules(gt) - 1; i >= 0; i--) rpm.RemoveRule(gt, i);
                                    var lst = new List<string>();
                                    foreach (var f in g.Value.EnumerateArray())
                                    {
                                        string fn = f.GetString();
                                        var sym = syms.FirstOrDefault(s => (s.FamilyName + " : " + s.Name) == fn) ?? syms.FirstOrDefault(s => s.FamilyName == fn);
                                        if (sym == null) { lst.Add("MISSING " + fn); continue; }
                                        if (!sym.IsActive) sym.Activate();
                                        var rule = new RoutingPreferenceRule(sym.Id, "BAAK");
                                        rule.AddCriterion(PrimarySizeCriterion.All());
                                        rpm.AddRule(gt, rule);
                                        lst.Add(sym.FamilyName + " : " + sym.Name);
                                    }
                                    done[g.Name] = lst;
                                }
                            string jt = S(p, "junction");
                            if (jt != null) rpm.PreferredJunctionType = jt == "Tap" ? PreferredJunctionType.Tap : PreferredJunctionType.Tee;
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["type"] = mt.Name, ["groups"] = done });
                    }

                // Connect ducts/pipes with real fittings: free ends that meet (within tol_m) get an elbow, union, transition,
                // tee or cross; a free end lying on the side of another run gets a takeoff (ducts) or a break + tee (pipes).
                // One small transaction per joint: a joint Revit refuses is rolled back alone and reported.
                case "connect_mep":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        double tol = M(D(p, "tol_m", 0.01));
                        bool doTake = !(p.TryGetProperty("takeoffs", out var tkEl) && tkEl.ValueKind == JsonValueKind.False);
                        var stats = new Dictionary<string, int> { ["elbow"] = 0, ["tee"] = 0, ["cross"] = 0, ["transition"] = 0, ["union"] = 0, ["takeoff"] = 0, ["failed"] = 0 };
                        var fails = new List<object>();
                        Func<Connector, XYZ> dirOf = c => (((c.Owner.Location as LocationCurve)?.Curve) as Line)?.Direction ?? XYZ.BasisX;
                        Func<MEPCurve, XYZ, Connector> connAt = (mc, q) =>
                        {
                            Connector best = null;
                            foreach (Connector k in mc.ConnectorManager.Connectors)
                                if (k.ConnectorType == ConnectorType.End && (best == null || k.Origin.DistanceTo(q) < best.Origin.DistanceTo(q))) best = k;
                            return best;
                        };
                        Func<Connector, Connector, bool> sameSize = (a, b) =>
                        {
                            if (a.Shape != b.Shape) return false;
                            if (a.Shape == ConnectorProfileType.Round) return Math.Abs(a.Radius - b.Radius) < 1e-4;
                            return Math.Abs(a.Width - b.Width) < 1e-4 && Math.Abs(a.Height - b.Height) < 1e-4;
                        };
                        Func<MEPCurve, double> half = mc =>
                        {
                            var k = connAt(mc, XYZ.Zero);
                            return k.Shape == ConnectorProfileType.Round ? k.Radius : Math.Max(k.Width, k.Height) / 2;
                        };
                        Func<string, XYZ, Action, bool> tryJoint = (what, at, act) =>
                        {
                            using (var t = new Transaction(d, "BAAK MCP - " + what))
                            {
                                t.Start();
                                var fho = t.GetFailureHandlingOptions();
                                fho.SetFailuresPreprocessor(new BaakRollbackOnError()); fho.SetClearAfterRollback(true);
                                t.SetFailureHandlingOptions(fho);
                                string err = null;
                                try { act(); } catch (Exception ex) { err = ex.Message; }
                                if (err != null) { t.RollBack(); }
                                else if (t.Commit() != TransactionStatus.Committed) err = "rolled back by Revit (error at commit)";
                                if (err != null)
                                {
                                    stats["failed"]++;
                                    fails.Add(new Dictionary<string, object> { ["what"] = what, ["err"] = err,
                                        ["xyz"] = new[] { Math.Round(ToM(at.X), 2), Math.Round(ToM(at.Y), 2), Math.Round(ToM(at.Z), 2) } });
                                    return false;
                                }
                                stats[what]++;
                                return true;
                            }
                        };
                        Func<List<Connector>> freeEnds = () =>
                        {
                            var l = new List<Connector>();
                            foreach (var id in ids)
                            {
                                if (!(d.GetElement(id) is MEPCurve mc)) continue;
                                foreach (Connector k in mc.ConnectorManager.Connectors)
                                    if (k.ConnectorType == ConnectorType.End && !k.IsConnected) l.Add(k);
                            }
                            return l;
                        };
                        using (var tg = new TransactionGroup(d, "BAAK MCP - connect MEP"))
                        {
                            tg.Start();
                            var ends = freeEnds();
                            var used = new bool[ends.Count];
                            for (int i = 0; i < ends.Count; i++)
                            {
                                if (used[i]) continue;
                                var grp = new List<Connector> { ends[i] }; used[i] = true;
                                for (int j = i + 1; j < ends.Count; j++)
                                    if (!used[j] && ends[j].Owner.Id != ends[i].Owner.Id && ends[i].Origin.DistanceTo(ends[j].Origin) < tol) { grp.Add(ends[j]); used[j] = true; }
                                if (grp.Count < 2) continue;
                                var at = grp[0].Origin;
                                Func<Connector, Connector, bool> par = (a, b) => Math.Abs(dirOf(a).DotProduct(dirOf(b))) > 0.9995;
                                if (grp.Count == 2)
                                {
                                    var a = grp[0]; var b = grp[1];
                                    if (par(a, b))
                                    {
                                        if (sameSize(a, b)) tryJoint("union", at, () => d.Create.NewUnionFitting(a, b));
                                        else tryJoint("transition", at, () => d.Create.NewTransitionFitting(a, b));
                                    }
                                    else tryJoint("elbow", at, () => d.Create.NewElbowFitting(a, b));
                                }
                                else if (grp.Count == 3)
                                {
                                    Connector m1 = null, m2 = null, br = null;
                                    for (int x = 0; x < 3 && m1 == null; x++)
                                        for (int y = x + 1; y < 3; y++)
                                            if (par(grp[x], grp[y])) { m1 = grp[x]; m2 = grp[y]; br = grp[3 - x - y]; break; }
                                    if (m1 != null) tryJoint("tee", at, () => d.Create.NewTeeFitting(m1, m2, br));
                                    else { stats["failed"]++; fails.Add(new Dictionary<string, object> { ["what"] = "tee", ["err"] = "no straight pair at a 3-way node" }); }
                                }
                                else if (grp.Count == 4)
                                {
                                    Connector c1 = null, c2 = null;
                                    for (int x = 1; x < 4; x++) if (par(grp[0], grp[x])) { c1 = grp[0]; c2 = grp[x]; }
                                    var rest = grp.Where(k => k != c1 && k != c2).ToList();
                                    if (c1 != null && rest.Count == 2) tryJoint("cross", at, () => d.Create.NewCrossFitting(c1, c2, rest[0], rest[1]));
                                }
                            }
                            if (doTake)
                            {
                                foreach (var k in freeEnds())
                                {
                                    if (k.IsConnected) continue;
                                    var owner = k.Owner as MEPCurve;
                                    bool kDuct = owner is Autodesk.Revit.DB.Mechanical.Duct;
                                    foreach (var id in ids.ToList())
                                    {
                                        if (id == owner.Id || !(d.GetElement(id) is MEPCurve c2)) continue;
                                        if ((c2 is Autodesk.Revit.DB.Mechanical.Duct) != kDuct) continue;
                                        if (!(((c2.Location as LocationCurve)?.Curve) is Line ln)) continue;
                                        var pr = ln.Project(k.Origin);
                                        if (pr == null || pr.Distance > half(c2) + tol) continue;
                                        var q = pr.XYZPoint;
                                        if (q.DistanceTo(ln.GetEndPoint(0)) < M(0.15) || q.DistanceTo(ln.GetEndPoint(1)) < M(0.15)) continue;
                                        if (Math.Abs(dirOf(k).DotProduct(ln.Direction)) > 0.98) continue;
                                        if (kDuct)
                                        {
                                            if (!tryJoint("takeoff", q, () => d.Create.NewTakeoffFitting(k, c2)))
                                            {
                                                // second try: branch end pulled back to the main's side face
                                                var bl = owner.Location as LocationCurve; var bline = (Line)bl.Curve;
                                                bool atStart = bline.GetEndPoint(0).DistanceTo(k.Origin) < bline.GetEndPoint(1).DistanceTo(k.Origin);
                                                var far = atStart ? bline.GetEndPoint(1) : bline.GetEndPoint(0);
                                                var outw = (k.Origin - far).Normalize();
                                                var surf = q - outw * half(c2);
                                                if (surf.DistanceTo(far) > M(0.2))
                                                {
                                                    stats["failed"]--; fails.RemoveAt(fails.Count - 1);
                                                    tryJoint("takeoff", surf, () =>
                                                    {
                                                        bl.Curve = atStart ? Line.CreateBound(surf, far) : Line.CreateBound(far, surf);
                                                        d.Create.NewTakeoffFitting(connAt(owner, surf), c2);
                                                    });
                                                }
                                            }
                                        }
                                        else
                                        {
                                            tryJoint("tee", q, () =>
                                            {
                                                var newId = Autodesk.Revit.DB.Plumbing.PlumbingUtils.BreakCurve(d, c2.Id, q);
                                                ids.Add(newId);
                                                var c3 = d.GetElement(newId) as MEPCurve;
                                                var bl = owner.Location as LocationCurve; var bline = (Line)bl.Curve;
                                                bool atStart = bline.GetEndPoint(0).DistanceTo(k.Origin) < bline.GetEndPoint(1).DistanceTo(k.Origin);
                                                var far = atStart ? bline.GetEndPoint(1) : bline.GetEndPoint(0);
                                                bl.Curve = atStart ? Line.CreateBound(q, far) : Line.CreateBound(far, q);
                                                d.Regenerate();
                                                d.Create.NewTeeFitting(connAt(c2, q), connAt(c3, q), connAt(owner, q));
                                            });
                                        }
                                        break;
                                    }
                                }
                            }
                            tg.Assimilate();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["stats"] = stats, ["n_fails"] = fails.Count, ["fails"] = fails.Take(80).ToList() });
                    }

                // Place air terminal / equipment families (non hosted) and join each to the nearest free duct end with a
                // flexible duct. items [{family, type, level, x, y, z, rot_deg, comment, mark, ducts:[ids], max_m}]
                case "place_terminals":
                    {
                        var d = Doc(uiapp);
                        var syms = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>().ToList();
                        var flexT = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.FlexDuctType))
                                    .Cast<Autodesk.Revit.DB.Mechanical.FlexDuctType>().OrderBy(x => x.Shape == ConnectorProfileType.Round ? 0 : 1).FirstOrDefault();
                        var res = new List<object>(); int nFlex = 0, nPlaced = 0;
                        foreach (var it in p.GetProperty("items").EnumerateArray())
                        {
                            var row = new Dictionary<string, object>();
                            string fn = S(it, "family"), tn = S(it, "type");
                            var sym = syms.Where(s => s.FamilyName == fn).OrderBy(s => tn != null && s.Name == tn ? 0 : 1).FirstOrDefault();
                            if (sym == null) { row["err"] = "family not loaded: " + fn; res.Add(row); continue; }
                            var lvl = LevelByName(d, S(it, "level"));
                            var pt = new XYZ(M(D(it, "x")), M(D(it, "y")), M(D(it, "z")));
                            using (var t = new Transaction(d, "BAAK MCP - terminal"))
                            {
                                t.Start();
                                var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakRollbackOnError()); fho.SetClearAfterRollback(true); t.SetFailureHandlingOptions(fho);
                                try
                                {
                                    if (!sym.IsActive) { sym.Activate(); d.Regenerate(); }
                                    var fi = d.Create.NewFamilyInstance(pt, sym, lvl, StructuralType.NonStructural);
                                    double rot = D(it, "rot_deg");
                                    if (Math.Abs(rot) > 1e-9) ElementTransformUtils.RotateElement(d, fi.Id, Line.CreateBound(pt, pt + XYZ.BasisZ), rot * Math.PI / 180);
                                    // instance/type size parameters, by name: {"Diamètre": 0.16, ...} in metres
                                    if (it.TryGetProperty("sizes", out var sz))
                                        foreach (var kv in sz.EnumerateObject())
                                        {
                                            var prm = fi.LookupParameter(kv.Name);
                                            if (prm != null && !prm.IsReadOnly) prm.Set(M(kv.Value.GetDouble()));
                                        }
                                    SetMarkAndComment(d, fi.Id, S(it, "mark"), S(it, "comment"));
                                    d.Regenerate();
                                    row["id"] = fi.Id.Value; nPlaced++;
                                    Connector tc = null;
                                    foreach (Connector k in fi.MEPModel?.ConnectorManager?.Connectors ?? new ConnectorSet()) if (!k.IsConnected) { tc = k; break; }
                                    if (tc != null && flexT != null && it.TryGetProperty("ducts", out var dl))
                                    {
                                        Connector best = null; double bd = M(D(it, "max_m", 1.2));
                                        foreach (var de in dl.EnumerateArray())
                                            if (d.GetElement(new ElementId(de.GetInt64())) is MEPCurve mc)
                                                foreach (Connector k in mc.ConnectorManager.Connectors)
                                                    if (k.ConnectorType == ConnectorType.End && !k.IsConnected)
                                                    {
                                                        double dd = new XYZ(k.Origin.X - pt.X, k.Origin.Y - pt.Y, 0).GetLength();
                                                        if (dd < bd) { bd = dd; best = k; }
                                                    }
                                        if (best != null)
                                        {
                                            var fx = d.Create.NewFlexDuct(best, tc, flexT);
                                            SetMarkAndComment(d, fx.Id, null, S(it, "comment"));
                                            row["flex"] = fx.Id.Value; nFlex++;
                                        }
                                    }
                                    if (t.Commit() != TransactionStatus.Committed) { row["err"] = "rolled back"; row.Remove("id"); row.Remove("flex"); nPlaced--; }
                                }
                                catch (Exception ex) { if (t.HasStarted() && !t.HasEnded()) t.RollBack(); row["err"] = ex.Message; }
                            }
                            res.Add(row);
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["placed"] = nPlaced, ["flex"] = nFlex, ["items"] = res });
                    }

                // Make a loaded family work-plane based (and not always vertical) so it can sit on any plane, e.g. a grille on
                // the side of a duct; the edited family is loaded back over itself. Only for families without instances.
                case "family_workplane":
                    {
                        var d = Doc(uiapp);
                        string fn = S(p, "family") ?? throw new Exception("family is required");
                        var fam = new FilteredElementCollector(d).OfClass(typeof(Family)).Cast<Family>().FirstOrDefault(f => f.Name == fn)
                                  ?? throw new Exception("family not loaded: " + fn);
                        var fd = d.EditFamily(fam);
                        string before = fam.FamilyPlacementType.ToString();
                        try
                        {
                            using (var t = new Transaction(fd, "BAAK MCP - work plane based"))
                            {
                                t.Start();
                                fd.OwnerFamily.get_Parameter(BuiltInParameter.FAMILY_WORK_PLANE_BASED)?.Set(1);
                                fd.OwnerFamily.get_Parameter(BuiltInParameter.FAMILY_ALWAYS_VERTICAL)?.Set(0);
                                t.Commit();
                            }
                            fd.LoadFamily(d, new BaakOverwrite());
                        }
                        finally { fd.Close(false); }
                        var fam2 = new FilteredElementCollector(d).OfClass(typeof(Family)).Cast<Family>().First(f => f.Name == fn);
                        return J(new Dictionary<string, object> { ["ok"] = true, ["before"] = before, ["after"] = fam2.FamilyPlacementType.ToString() });
                    }

                // Load chosen types of a family that has a type catalog (.txt beside the .rfa).
                case "load_family_types":
                    {
                        var d = Doc(uiapp);
                        string path = S(p, "path") ?? throw new Exception("path is required");
                        var got = new List<string>(); var bad = new List<string>();
                        using (var t = new Transaction(d, "BAAK MCP - load family types"))
                        {
                            t.Start();
                            foreach (var tn in p.GetProperty("types").EnumerateArray().Select(x => x.GetString()))
                            {
                                try { if (d.LoadFamilySymbol(path, tn, new BaakOverwrite(), out FamilySymbol fs) || fs != null) got.Add(tn); else bad.Add(tn); }
                                catch (Exception ex) { bad.Add(tn + ": " + ex.Message); }
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["loaded"] = got, ["failed"] = bad });
                    }

                // What a loaded family is: category, placement type, types, MEP connectors and parameters (read from the family document).
                case "family_info":
                    {
                        var d = Doc(uiapp);
                        string fn = S(p, "family") ?? throw new Exception("family is required");
                        var fam = new FilteredElementCollector(d).OfClass(typeof(Family)).Cast<Family>().FirstOrDefault(f => f.Name == fn)
                                  ?? throw new Exception("family not loaded: " + fn);
                        var res = new Dictionary<string, object>
                        {
                            ["ok"] = true, ["family"] = fam.Name, ["category"] = fam.FamilyCategory?.Name,
                            ["placement"] = fam.FamilyPlacementType.ToString(),
                            ["types"] = fam.GetFamilySymbolIds().Select(i => d.GetElement(i)?.Name).ToList(),
                        };
                        var fd = d.EditFamily(fam);
                        try
                        {
                            res["connectors"] = new FilteredElementCollector(fd).OfClass(typeof(ConnectorElement)).Cast<ConnectorElement>()
                                .Select(c => new Dictionary<string, object>
                                {
                                    ["domain"] = c.Domain.ToString(), ["shape"] = c.Shape.ToString(), ["system"] = c.SystemClassification.ToString(),
                                    ["origin_m"] = new[] { Math.Round(ToM(c.Origin.X), 3), Math.Round(ToM(c.Origin.Y), 3), Math.Round(ToM(c.Origin.Z), 3) },
                                    ["dir"] = new[] { Math.Round(c.CoordinateSystem.BasisZ.X, 3), Math.Round(c.CoordinateSystem.BasisZ.Y, 3), Math.Round(c.CoordinateSystem.BasisZ.Z, 3) },
                                }).ToList();
                            var fm = fd.FamilyManager;
                            res["params"] = fm.Parameters.Cast<FamilyParameter>().Select(fp => new Dictionary<string, object>
                            {
                                ["name"] = fp.Definition.Name, ["instance"] = fp.IsInstance, ["storage"] = fp.StorageType.ToString(),
                                ["formula"] = fp.Formula,
                                ["value"] = fm.CurrentType == null ? null : (fp.StorageType == StorageType.Double ? (object)Math.Round(ToM(fm.CurrentType.AsDouble(fp) ?? 0), 4)
                                            : fp.StorageType == StorageType.Integer ? (object)fm.CurrentType.AsInteger(fp)
                                            : fp.StorageType == StorageType.String ? fm.CurrentType.AsString(fp) : null),
                            }).ToList();
                        }
                        finally { fd.Close(false); }
                        return J(res);
                    }

                // Place a family whatever its placement type. Face / work-plane based: on a horizontal reference plane at z whose
                // normal points "down" (ceiling underside: product hangs below, neck up) or "up". Level based: on the level with
                // its offset set to z. params {name: number in metres (lengths) or plain number/string}, set on the instance,
                // else on the type when type_params is true. Returns the free connectors.
                case "place_family":
                    {
                        var d = Doc(uiapp);
                        string famName = S(p, "family") ?? throw new Exception("family is required");
                        string typeName = S(p, "type");
                        var sym = new FilteredElementCollector(d).OfClass(typeof(FamilySymbol)).Cast<FamilySymbol>()
                                  .Where(s => s.FamilyName == famName).OrderBy(s => typeName != null && s.Name == typeName ? 0 : 1).FirstOrDefault()
                                  ?? throw new Exception("family not loaded: " + famName);
                        if (typeName != null && sym.Name != typeName) throw new Exception("type not found: " + typeName);
                        var lvl = LevelByName(d, S(p, "level"));
                        var pt = new XYZ(M(D(p, "x")), M(D(p, "y")), M(D(p, "z")));
                        double rot = D(p, "rot_deg") * Math.PI / 180;
                        var refDir = new XYZ(Math.Cos(rot), Math.Sin(rot), 0);
                        bool down = (S(p, "face") ?? "down") == "down";
                        FamilyInstance fi;
                        using (var t = new Transaction(d, "BAAK MCP - place family"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            if (!sym.IsActive) { sym.Activate(); d.Regenerate(); }
                            var pl = sym.Family.FamilyPlacementType;
                            if (pl == FamilyPlacementType.WorkPlaneBased)
                            {
                                View rv = new FilteredElementCollector(d).OfClass(typeof(View3D)).Cast<View3D>().FirstOrDefault(v => !v.IsTemplate && v.Name == "BAAK MCP rayons")
                                          ?? (View)new FilteredElementCollector(d).OfClass(typeof(ViewPlan)).Cast<ViewPlan>().First(v => !v.IsTemplate);
                                ReferencePlane rp;
                                if (p.TryGetProperty("normal", out var nEl))
                                {
                                    // any plane: normal given; the plane's in-plane direction is refDir projected on it
                                    var nv = nEl.EnumerateArray().Select(x => x.GetDouble()).ToArray();
                                    var n = new XYZ(nv[0], nv[1], nv[2]).Normalize();
                                    var a = (refDir - n * refDir.DotProduct(n));
                                    if (a.GetLength() < 1e-6) a = Math.Abs(n.Z) < 0.9 ? XYZ.BasisZ.CrossProduct(n) : XYZ.BasisX;
                                    a = a.Normalize();
                                    var b = n.CrossProduct(a);
                                    rp = d.Create.NewReferencePlane(pt, pt + a, b, rv);
                                    if (rp.Normal.DotProduct(n) < 0) { d.Delete(rp.Id); rp = d.Create.NewReferencePlane(pt, pt + a, -b, rv); }
                                    refDir = a;
                                }
                                else
                                {
                                    var cut = down ? -XYZ.BasisY : XYZ.BasisY;
                                    rp = d.Create.NewReferencePlane(pt, pt + XYZ.BasisX, cut, rv);
                                    if ((rp.Normal.Z < 0) != down) { d.Delete(rp.Id); rp = d.Create.NewReferencePlane(pt, pt + XYZ.BasisX, -cut, rv); }
                                }
                                rp.Name = "BAAK MCP plan " + Guid.NewGuid().ToString("N").Substring(0, 8);
                                fi = d.Create.NewFamilyInstance(rp.GetReference(), pt, refDir, sym);
                            }
                            else
                            {
                                fi = d.Create.NewFamilyInstance(pt, sym, lvl, StructuralType.NonStructural);
                                fi.get_Parameter(BuiltInParameter.INSTANCE_ELEVATION_PARAM)?.Set(pt.Z - lvl.Elevation);
                                if (Math.Abs(rot) > 1e-9) ElementTransformUtils.RotateElement(d, fi.Id, Line.CreateBound(pt, pt + XYZ.BasisZ), rot);
                            }
                            bool typeToo = p.TryGetProperty("type_params", out var tpEl) && tpEl.ValueKind == JsonValueKind.True;
                            var setLog = new List<string>();
                            if (p.TryGetProperty("params", out var prs))
                                foreach (var kv in prs.EnumerateObject())
                                {
                                    var prm = fi.LookupParameter(kv.Name) ?? (typeToo ? fi.Symbol.LookupParameter(kv.Name) : null);
                                    if (prm == null || prm.IsReadOnly) { setLog.Add("skip " + kv.Name); continue; }
                                    if (kv.Value.ValueKind == JsonValueKind.String) prm.Set(kv.Value.GetString());
                                    else if (prm.StorageType == StorageType.Integer) prm.Set(kv.Value.GetInt32());
                                    else if (prm.StorageType == StorageType.Double)
                                    {
                                        var dt = prm.Definition.GetDataType();
                                        double v = kv.Value.GetDouble();
                                        if (dt == SpecTypeId.Length || dt == SpecTypeId.DuctSize || dt == SpecTypeId.PipeSize) prm.Set(M(v));
                                        else if (dt == SpecTypeId.AirFlow) prm.Set(UnitUtils.ConvertToInternalUnits(v, UnitTypeId.CubicMetersPerHour));
                                        else prm.Set(v);
                                    }
                                    setLog.Add("set " + kv.Name);
                                }
                            SetMarkAndComment(d, fi.Id, S(p, "mark"), S(p, "comment"));
                            t.Commit();
                            var cons = new List<object>();
                            foreach (Connector c in fi.MEPModel?.ConnectorManager?.Connectors ?? new ConnectorSet())
                                cons.Add(new Dictionary<string, object>
                                {
                                    ["shape"] = c.Shape.ToString(), ["free"] = !c.IsConnected,
                                    ["origin_m"] = new[] { Math.Round(ToM(c.Origin.X), 3), Math.Round(ToM(c.Origin.Y), 3), Math.Round(ToM(c.Origin.Z), 3) },
                                    ["dir"] = new[] { Math.Round(c.CoordinateSystem.BasisZ.X, 3), Math.Round(c.CoordinateSystem.BasisZ.Y, 3), Math.Round(c.CoordinateSystem.BasisZ.Z, 3) },
                                    ["domain"] = c.Domain.ToString(),
                                    ["size_m"] = c.Shape == ConnectorProfileType.Round ? new[] { Math.Round(ToM(2 * c.Radius), 3) }
                                               : (c.Shape == ConnectorProfileType.Rectangular || c.Shape == ConnectorProfileType.Oval) ? new[] { Math.Round(ToM(c.Width), 3), Math.Round(ToM(c.Height), 3) }
                                               : new double[0],
                                });
                            var bb = fi.get_BoundingBox(null);
                            return J(new Dictionary<string, object>
                            {
                                ["ok"] = true, ["id"] = fi.Id.Value, ["placement"] = sym.Family.FamilyPlacementType.ToString(), ["connectors"] = cons, ["set"] = setLog,
                                ["bbox_min_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Min.X), 3), Math.Round(ToM(bb.Min.Y), 3), Math.Round(ToM(bb.Min.Z), 3) },
                                ["bbox_max_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Max.X), 3), Math.Round(ToM(bb.Max.Y), 3), Math.Round(ToM(bb.Max.Z), 3) },
                            });
                        }
                    }

                // Join an air terminal (or any MEP family) to a duct: mode "on_duct" (terminal on the duct face,
                // MechanicalUtils.ConnectAirTerminalOnDuct) or "end" (nearest free end of the duct: direct when they touch, a
                // transition when collinear, otherwise a flexible duct).
                case "connect_terminal":
                    {
                        var d = Doc(uiapp);
                        var fi = d.GetElement(new ElementId((long)D(p, "terminal_id"))) as FamilyInstance ?? throw new Exception("terminal not found");
                        var du = d.GetElement(new ElementId((long)D(p, "duct_id"))) as MEPCurve ?? throw new Exception("duct not found");
                        string mode = S(p, "mode") ?? "end";
                        string how = null;
                        using (var t = new Transaction(d, "BAAK MCP - connect terminal"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakRollbackOnError()); fho.SetClearAfterRollback(true);
                            t.SetFailureHandlingOptions(fho);
                            try
                            {
                                if (mode == "on_duct")
                                {
                                    if (!(du is Autodesk.Revit.DB.Mechanical.Duct dd)) throw new Exception("on_duct needs a duct");
                                    if (!Autodesk.Revit.DB.Mechanical.MechanicalUtils.ConnectAirTerminalOnDuct(d, fi.Id, dd.Id)) throw new Exception("ConnectAirTerminalOnDuct returned false");
                                    how = "on duct";
                                }
                                else
                                {
                                    // the free HVAC connector of the terminal / unit and the free duct end that are closest to each other
                                    Connector tc = null, best = null;
                                    foreach (Connector c in fi.MEPModel.ConnectorManager.Connectors)
                                    {
                                        if (c.IsConnected || c.Domain != Domain.DomainHvac) continue;
                                        foreach (Connector e2 in du.ConnectorManager.Connectors)
                                            if (e2.ConnectorType == ConnectorType.End && !e2.IsConnected
                                                && (best == null || c.Origin.DistanceTo(e2.Origin) < tc.Origin.DistanceTo(best.Origin))) { tc = c; best = e2; }
                                    }
                                    if (tc == null) throw new Exception("no free air connector on the terminal, or no free end on the duct");
                                    double gap = best.Origin.DistanceTo(tc.Origin);
                                    bool sameSize = best.Shape == tc.Shape && (tc.Shape == ConnectorProfileType.Round ? Math.Abs(best.Radius - tc.Radius) < 1e-4
                                                    : Math.Abs(best.Width - tc.Width) < 1e-4 && Math.Abs(best.Height - tc.Height) < 1e-4);
                                    if (gap < M(0.005) && sameSize) { best.ConnectTo(tc); how = "direct"; }
                                    else if (gap < M(0.005)) { d.Create.NewTransitionFitting(best, tc); how = "transition"; }
                                    else
                                    {
                                        var ft = new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.FlexDuctType)).Cast<Autodesk.Revit.DB.Mechanical.FlexDuctType>()
                                                 .OrderBy(x => x.Shape == tc.Shape ? 0 : 1).First();
                                        var fx = d.Create.NewFlexDuct(best, tc, ft);
                                        SetMarkAndComment(d, fx.Id, null, S(p, "comment"));
                                        how = "flex";
                                    }
                                }
                            }
                            catch (Exception ex) { t.RollBack(); return J(new Dictionary<string, object> { ["ok"] = false, ["error"] = ex.Message }); }
                            if (t.Commit() != TransactionStatus.Committed) return J(new Dictionary<string, object> { ["ok"] = false, ["error"] = "rolled back by Revit" });
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["how"] = how });
                    }

                // A 3D view with a section box and a view direction, shaded with edges, fine detail.
                case "make_view3d":
                    {
                        var d = Doc(uiapp);
                        string name = S(p, "name") ?? throw new Exception("name is required");
                        var mn = p.GetProperty("min").EnumerateArray().Select(x => M(x.GetDouble())).ToArray();
                        var mx = p.GetProperty("max").EnumerateArray().Select(x => M(x.GetDouble())).ToArray();
                        var dir = p.TryGetProperty("dir", out var de) ? de.EnumerateArray().Select(x => x.GetDouble()).ToArray() : new[] { -1.0, 1.0, -0.8 };
                        View3D v;
                        using (var t = new Transaction(d, "BAAK MCP - 3D view"))
                        {
                            t.Start();
                            v = new FilteredElementCollector(d).OfClass(typeof(View3D)).Cast<View3D>().FirstOrDefault(x => !x.IsTemplate && x.Name == name);
                            if (v == null)
                            {
                                var vft = new FilteredElementCollector(d).OfClass(typeof(ViewFamilyType)).Cast<ViewFamilyType>().First(x => x.ViewFamily == ViewFamily.ThreeDimensional);
                                v = View3D.CreateIsometric(d, vft.Id);
                                v.Name = name;
                            }
                            if (v.ViewTemplateId != ElementId.InvalidElementId) v.ViewTemplateId = ElementId.InvalidElementId;
                            var c = new XYZ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2);
                            var fwd = new XYZ(dir[0], dir[1], dir[2]).Normalize();
                            var right = fwd.CrossProduct(XYZ.BasisZ).Normalize();
                            var up = right.CrossProduct(fwd).Normalize();
                            v.SetOrientation(new ViewOrientation3D(c - fwd * M(60), up, fwd));
                            v.IsSectionBoxActive = true;
                            v.SetSectionBox(new BoundingBoxXYZ { Min = new XYZ(mn[0], mn[1], mn[2]), Max = new XYZ(mx[0], mx[1], mx[2]) });
                            v.DetailLevel = ViewDetailLevel.Fine;
                            v.DisplayStyle = DisplayStyle.ShadingWithEdges;
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["view"] = v.Name, ["id"] = v.Id.Value });
                    }

                // Galvanised steel material (library "Galvanized" appearance when available) on every duct system type.
                case "galva_systems":
                    {
                        var d = Doc(uiapp);
                        string mname = S(p, "material") ?? "BAAK - Acier galvanise";
                        string asset = null;
                        using (var t = new Transaction(d, "BAAK MCP - galvanised"))
                        {
                            t.Start();
                            var mat = new FilteredElementCollector(d).OfClass(typeof(Material)).Cast<Material>().FirstOrDefault(m => m.Name == mname)
                                      ?? d.GetElement(Material.Create(d, mname)) as Material;
                            mat.Color = new Color(176, 180, 184);
                            mat.Shininess = 60; mat.Smoothness = 60;
                            try
                            {
                                var assets = uiapp.Application.GetAssets(Autodesk.Revit.DB.Visual.AssetType.Appearance);
                                var a = assets.FirstOrDefault(x => (x.Name ?? "").IndexOf("Galvan", StringComparison.OrdinalIgnoreCase) >= 0
                                                                 || (x.Title ?? "").IndexOf("Galvan", StringComparison.OrdinalIgnoreCase) >= 0);
                                if (a != null)
                                {
                                    var aae = new FilteredElementCollector(d).OfClass(typeof(AppearanceAssetElement)).Cast<AppearanceAssetElement>().FirstOrDefault(x => x.Name == mname)
                                              ?? AppearanceAssetElement.Create(d, mname, a);
                                    mat.AppearanceAssetId = aae.Id;
                                    asset = a.Title ?? a.Name;
                                }
                                else asset = "no Galvanized asset in the library";
                            }
                            catch (Exception ex) { asset = "no library asset: " + ex.Message; }
                            var done = new List<string>();
                            foreach (var st in new FilteredElementCollector(d).OfClass(typeof(Autodesk.Revit.DB.Mechanical.MechanicalSystemType)).Cast<Element>())
                            {
                                var prm = st.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM);
                                if (prm != null && !prm.IsReadOnly) { prm.Set(mat.Id); done.Add(st.Name); }
                            }
                            t.Commit();
                            return J(new Dictionary<string, object> { ["ok"] = true, ["material"] = mat.Name, ["material_id"] = mat.Id.Value, ["appearance"] = asset, ["systems"] = done });
                        }
                    }

                // Vertical obstacle profile: for each point [x,y], the z intervals occupied along the vertical line z0..z1 by the
                // elements of the given categories (default: framing, floors, ceilings, roofs, generic models, walls),
                // one [zlo, zhi, category, id] per element crossed (entry/exit faces of the ray).
                case "zprofile":
                    {
                        var d = Doc(uiapp);
                        var v3 = new FilteredElementCollector(d).OfClass(typeof(View3D)).Cast<View3D>().FirstOrDefault(v => !v.IsTemplate && v.Name == "BAAK MCP rayons")
                                 ?? throw new Exception("view 'BAAK MCP rayons' missing: call soffit once first");
                        var bics = new List<BuiltInCategory>();
                        if (p.TryGetProperty("categories", out var ce))
                            foreach (var x in ce.EnumerateArray()) bics.Add((BuiltInCategory)Enum.Parse(typeof(BuiltInCategory), x.GetString()));
                        if (bics.Count == 0)
                            bics.AddRange(new[] { BuiltInCategory.OST_StructuralFraming, BuiltInCategory.OST_Floors, BuiltInCategory.OST_Ceilings,
                                                  BuiltInCategory.OST_Roofs, BuiltInCategory.OST_GenericModel, BuiltInCategory.OST_Walls });
                        var ri = new ReferenceIntersector(new ElementMulticategoryFilter(bics), FindReferenceTarget.Face, v3) { FindReferencesInRevitLinks = false };
                        double z0 = D(p, "z0"), z1 = D(p, "z1");
                        var outPts = new List<object>();
                        foreach (var q in p.GetProperty("points").EnumerateArray())
                        {
                            var a = q.EnumerateArray().Select(x => x.GetDouble()).ToArray();
                            var o = new XYZ(M(a[0]), M(a[1]), M(z0));
                            var per = new Dictionary<long, List<double>>();
                            var cat = new Dictionary<long, string>();
                            foreach (var h in ri.Find(o, XYZ.BasisZ))
                            {
                                if (h.Proximity > M(z1 - z0)) continue;
                                var id = h.GetReference().ElementId;
                                var el = d.GetElement(id);
                                if (el?.Category == null) continue;
                                if (!per.ContainsKey(id.Value)) { per[id.Value] = new List<double>(); cat[id.Value] = ((BuiltInCategory)el.Category.Id.Value).ToString(); }
                                per[id.Value].Add(z0 + ToM(h.Proximity));
                            }
                            outPts.Add(per.Select(kv => new object[] { Math.Round(kv.Value.Count > 1 ? kv.Value.Min() : z0, 3), Math.Round(kv.Value.Max(), 3), cat[kv.Key], kv.Key }).ToList());
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["points"] = outPts });
                    }

                // Everything connected to the given MEP elements through their connectors (ducts, pipes, fittings, flex,
                // terminals, equipment), breadth first; MEP systems themselves are skipped.
                case "mep_network":
                    {
                        var d = Doc(uiapp);
                        var seen = new HashSet<long>();
                        var queue = new Queue<ElementId>();
                        foreach (var x in p.GetProperty("ids").EnumerateArray()) { var id = new ElementId(x.GetInt64()); if (seen.Add(id.Value)) queue.Enqueue(id); }
                        var rows = new List<object>();
                        while (queue.Count > 0)
                        {
                            var el = d.GetElement(queue.Dequeue());
                            if (el == null) continue;
                            rows.Add(new Dictionary<string, object> { ["id"] = el.Id.Value, ["category"] = el.Category?.Name, ["family"] = (el as FamilyInstance)?.Symbol?.FamilyName });
                            ConnectorManager cm = (el as MEPCurve)?.ConnectorManager ?? (el as FamilyInstance)?.MEPModel?.ConnectorManager;
                            if (cm == null) continue;
                            foreach (Connector c in cm.Connectors)
                                foreach (Connector r in c.AllRefs)
                                {
                                    var ow = r.Owner;
                                    if (ow == null || ow is MEPSystem) continue;
                                    if (seen.Add(ow.Id.Value)) queue.Enqueue(ow.Id);
                                }
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = rows.Count, ["elements"] = rows });
                    }

                // Real solid clash: for each id, the elements of the given categories whose geometry intersects it.
                case "clash":
                    {
                        var d = Doc(uiapp);
                        var bics = p.GetProperty("categories").EnumerateArray().Select(x => (BuiltInCategory)Enum.Parse(typeof(BuiltInCategory), x.GetString())).ToList();
                        var skip = new HashSet<long>();
                        if (p.TryGetProperty("skip", out var sk)) foreach (var x in sk.EnumerateArray()) skip.Add(x.GetInt64());
                        var pool = new FilteredElementCollector(d).WhereElementIsNotElementType().WherePasses(new ElementMulticategoryFilter(bics))
                                   .ToElementIds().Where(i => !skip.Contains(i.Value)).ToList();
                        var res = new Dictionary<string, object>();
                        foreach (var x in p.GetProperty("ids").EnumerateArray())
                        {
                            var el = d.GetElement(new ElementId(x.GetInt64()));
                            if (el == null || pool.Count == 0) continue;
                            try
                            {
                                var hits = new FilteredElementCollector(d, pool).WherePasses(new ElementIntersectsElementFilter(el)).ToElements()
                                           .Where(h => h.Id != el.Id)
                                           .Select(h => new Dictionary<string, object> { ["id"] = h.Id.Value, ["category"] = h.Category?.Name, ["name"] = h.Name,
                                                                                          ["family"] = (h as FamilyInstance)?.Symbol?.FamilyName }).ToList();
                                if (hits.Count > 0) res[el.Id.Value.ToString()] = hits;
                            }
                            catch (Exception ex) { res[el.Id.Value.ToString()] = "error: " + ex.Message; }
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["hits"] = res });
                    }

                // Delete every element of the given built-in categories (optionally only those whose Comments contain a text).
                case "delete_by_category":
                    {
                        var d = Doc(uiapp);
                        string contains = S(p, "comment_contains");
                        var bics = p.GetProperty("bics").EnumerateArray().Select(x => (BuiltInCategory)Enum.Parse(typeof(BuiltInCategory), x.GetString())).ToList();
                        var del = new FilteredElementCollector(d).WhereElementIsNotElementType().WherePasses(new ElementMulticategoryFilter(bics))
                                  .Where(e => contains == null || (e.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.AsString() ?? "").Contains(contains))
                                  .Select(e => e.Id).ToList();
                        int n = 0;
                        if (del.Count > 0)
                            using (var t = new Transaction(d, "BAAK MCP - delete by category"))
                            {
                                t.Start();
                                var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                                n = d.Delete(del).Count;
                                t.Commit();
                            }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["matched"] = del.Count, ["deleted"] = n });
                    }

                case "elements":
                    {
                        var d = Doc(uiapp);
                        string catName = S(p, "category") ?? "Mobilier";
                        var rows = new List<Dictionary<string, object>>();
                        foreach (var e in new FilteredElementCollector(d).WhereElementIsNotElementType())
                        {
                            if (e.Category == null || !e.Category.Name.Equals(catName, StringComparison.OrdinalIgnoreCase)) continue;
                            var fi = e as FamilyInstance;
                            var bb = e.get_BoundingBox(null);
                            var lp = (e.Location as LocationPoint)?.Point;
                            var lvl = d.GetElement(e.LevelId) as Level;
                            var row = new Dictionary<string, object>
                            {
                                ["id"] = e.Id.Value,
                                ["family"] = fi?.Symbol?.FamilyName,
                                ["type"] = e.Name,
                                ["mark"] = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString(),
                                ["level"] = lvl?.Name,
                                ["nested"] = fi?.SuperComponent != null,
                            };
                            if (lp != null) row["xyz_m"] = new[] { Math.Round(ToM(lp.X), 3), Math.Round(ToM(lp.Y), 3), Math.Round(ToM(lp.Z), 3) };
                            if (e.Location is LocationCurve lcv && lcv.Curve != null)
                            {
                                var c0 = lcv.Curve.GetEndPoint(0); var c1 = lcv.Curve.GetEndPoint(1);
                                row["curve_m"] = new[] { Math.Round(ToM(c0.X), 3), Math.Round(ToM(c0.Y), 3), Math.Round(ToM(c0.Z), 3),
                                                         Math.Round(ToM(c1.X), 3), Math.Round(ToM(c1.Y), 3), Math.Round(ToM(c1.Z), 3) };
                                row["curve_kind"] = lcv.Curve.GetType().Name;
                            }
                            if (fi != null)
                            {
                                var fo = fi.FacingOrientation; row["facing"] = new[] { Math.Round(fo.X, 3), Math.Round(fo.Y, 3) };
                                var tr = fi.GetTransform();
                                row["rot_deg"] = Math.Round(Math.Atan2(tr.BasisX.Y, tr.BasisX.X) * 180 / Math.PI, 3);
                                row["mirrored"] = fi.Mirrored;
                                row["symbol_id"] = fi.Symbol?.Id.Value;
                            }
                            if (bb != null)
                            {
                                row["bbox_min_m"] = new[] { Math.Round(ToM(bb.Min.X), 3), Math.Round(ToM(bb.Min.Y), 3), Math.Round(ToM(bb.Min.Z), 3) };
                                row["bbox_max_m"] = new[] { Math.Round(ToM(bb.Max.X), 3), Math.Round(ToM(bb.Max.Y), 3), Math.Round(ToM(bb.Max.Z), 3) };
                            }
                            rows.Add(row);
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["category"] = catName, ["count"] = rows.Count, ["elements"] = rows });
                    }

                // For each given id: the other elements whose solids really intersect it (furniture, casework,
                // generic models, plants, lights, equipment, plumbing) - used to find doubles after a copy.
                case "intersecting":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        var idSet = new HashSet<long>(ids.Select(i => i.Value));
                        var cats = new List<ElementFilter> {
                            new ElementCategoryFilter(BuiltInCategory.OST_Furniture), new ElementCategoryFilter(BuiltInCategory.OST_FurnitureSystems),
                            new ElementCategoryFilter(BuiltInCategory.OST_Casework), new ElementCategoryFilter(BuiltInCategory.OST_GenericModel),
                            new ElementCategoryFilter(BuiltInCategory.OST_Planting), new ElementCategoryFilter(BuiltInCategory.OST_LightingFixtures),
                            new ElementCategoryFilter(BuiltInCategory.OST_SpecialityEquipment), new ElementCategoryFilter(BuiltInCategory.OST_PlumbingFixtures) };
                        var pool = new FilteredElementCollector(d).WhereElementIsNotElementType().WherePasses(new LogicalOrFilter(cats))
                                   .ToElementIds().Where(i => !idSet.Contains(i.Value)).ToList();
                        var res = new Dictionary<string, object>();
                        foreach (var id in ids)
                        {
                            var el = d.GetElement(id);
                            if (el == null || pool.Count == 0) continue;
                            var hits = new FilteredElementCollector(d, pool).WherePasses(new ElementIntersectsElementFilter(el)).ToElements()
                                .Select(h => new Dictionary<string, object>
                                {
                                    ["id"] = h.Id.Value, ["category"] = h.Category?.Name, ["name"] = h.Name,
                                    ["family"] = (h as FamilyInstance)?.Symbol?.FamilyName,
                                    ["mark"] = h.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString(),
                                }).ToList();
                            if (hits.Count > 0) res[id.Value.ToString()] = hits;
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["hits"] = res });
                    }

                // Buildability audit (read-only): ceilings vs structure, lights near walls, walls short of the slab,
                // furniture through walls. Returns one list per check.
                case "audit_real":
                    {
                        var d = Doc(uiapp);
                        Func<Element, Dictionary<string, object>> brief = e =>
                        {
                            var bb = e.get_BoundingBox(null);
                            return new Dictionary<string, object>
                            {
                                ["id"] = e.Id.Value, ["category"] = e.Category?.Name, ["name"] = e.Name,
                                ["family"] = (e as FamilyInstance)?.Symbol?.FamilyName,
                                ["level"] = (d.GetElement(e.LevelId) as Level)?.Name,
                                ["mark"] = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString(),
                                ["bbox_min_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Min.X), 2), Math.Round(ToM(bb.Min.Y), 2), Math.Round(ToM(bb.Min.Z), 2) },
                                ["bbox_max_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Max.X), 2), Math.Round(ToM(bb.Max.Y), 2), Math.Round(ToM(bb.Max.Z), 2) },
                            };
                        };
                        var structIds = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .WherePasses(new LogicalOrFilter(new List<ElementFilter> {
                                new ElementCategoryFilter(BuiltInCategory.OST_StructuralFraming),
                                new ElementCategoryFilter(BuiltInCategory.OST_StructuralColumns) })).ToElementIds();
                        var ceilings = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Where(e => e.Category != null && (e.Category.Id.Value == (long)BuiltInCategory.OST_Ceilings
                                   || (e.Category.Id.Value == (long)BuiltInCategory.OST_GenericModel && e is FamilyInstance gm
                                       && (gm.Symbol.FamilyName.Contains("-PF-") || gm.Symbol.FamilyName.Contains("Lames") || gm.Symbol.FamilyName.Contains("Lattes")))))
                            .ToList();
                        var c1 = new List<object>();
                        foreach (var c in ceilings)
                        {
                            if (structIds.Count == 0) break;
                            var hits = new FilteredElementCollector(d, structIds).WherePasses(new ElementIntersectsElementFilter(c)).ToElements();
                            foreach (var h in hits) c1.Add(new Dictionary<string, object> { ["ceiling"] = brief(c), ["structure"] = brief(h) });
                        }
                        // walls: location line + width + top
                        var walls = new FilteredElementCollector(d).OfClass(typeof(Wall)).Cast<Wall>()
                            .Where(w => w.Location is LocationCurve && w.WallType.Kind == WallKind.Basic).ToList();
                        var lights = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .Where(e => e.Category != null && e is FamilyInstance fi && e.Location is LocationPoint
                                   && (e.Category.Id.Value == (long)BuiltInCategory.OST_LightingFixtures
                                       || fi.Symbol.FamilyName.IndexOf("Spot", StringComparison.OrdinalIgnoreCase) >= 0)).ToList();
                        var c2 = new List<object>();
                        foreach (var lf in lights)
                        {
                            var pt = ((LocationPoint)lf.Location).Point;
                            foreach (var w in walls)
                            {
                                var wb = w.get_BoundingBox(null);
                                if (wb == null || pt.Z < wb.Min.Z - M(0.1) || pt.Z > wb.Max.Z + M(0.1)) continue;
                                var cv = ((LocationCurve)w.Location).Curve;
                                var flat = new XYZ(pt.X, pt.Y, cv.GetEndPoint(0).Z);
                                double dist = ToM(cv.Distance(flat)) - ToM(w.Width) / 2;
                                if (dist < 0.40)
                                {
                                    c2.Add(new Dictionary<string, object> { ["light"] = brief(lf), ["wall"] = brief(w), ["clear_m"] = Math.Round(dist, 3) });
                                    break;
                                }
                            }
                        }
                        // walls stopping well under the next level (void above the wall head)
                        var levels = new FilteredElementCollector(d).OfClass(typeof(Level)).Cast<Level>().OrderBy(l => l.Elevation).ToList();
                        var c3 = new List<object>();
                        foreach (var w in walls)
                        {
                            var wb = w.get_BoundingBox(null);
                            if (wb == null) continue;
                            var above = levels.FirstOrDefault(l => l.Elevation > wb.Min.Z + M(1.0));
                            if (above == null) continue;
                            double gap = ToM(above.Elevation - wb.Max.Z);
                            if (gap > 0.6 && ToM(wb.Max.Z - wb.Min.Z) > 1.9)
                                c3.Add(new Dictionary<string, object> { ["wall"] = brief(w), ["type"] = w.WallType.Name, ["gap_to_next_level_m"] = Math.Round(gap, 2), ["next_level"] = above.Name });
                        }
                        // furniture through walls
                        var wallIds = walls.Select(w => w.Id).ToList();
                        var furn = new FilteredElementCollector(d).OfCategory(BuiltInCategory.OST_Furniture).WhereElementIsNotElementType().ToElements();
                        var c4 = new List<object>();
                        foreach (var f in furn)
                        {
                            if (wallIds.Count == 0) break;
                            var hits = new FilteredElementCollector(d, wallIds).WherePasses(new ElementIntersectsElementFilter(f)).ToElements();
                            foreach (var h in hits) c4.Add(new Dictionary<string, object> { ["furniture"] = brief(f), ["wall"] = brief(h) });
                        }
                        return J(new Dictionary<string, object>
                        {
                            ["ok"] = true,
                            ["ceilings_vs_structure"] = c1, ["lights_near_walls"] = c2,
                            ["walls_short_of_slab"] = c3, ["furniture_through_walls"] = c4,
                            ["counts"] = new Dictionary<string, object> { ["ceilings"] = ceilings.Count, ["structure"] = structIds.Count, ["walls"] = walls.Count, ["lights"] = lights.Count, ["furniture"] = furn.Count },
                        });
                    }

                // Push an element away from a wall, perpendicular to the wall line, so that it keeps "clear" metres
                // from the wall face: mode "point" (location point, e.g. a light) or "box" (whole bounding box, e.g. furniture).
                case "push_off":
                    {
                        var d = Doc(uiapp);
                        var el = d.GetElement(new ElementId((long)D(p, "id"))) ?? throw new Exception("element not found");
                        var w = d.GetElement(new ElementId((long)D(p, "wall_id"))) as Wall ?? throw new Exception("wall not found");
                        double clear = M(D(p, "clear", 0.01));
                        string mode = S(p, "mode") ?? "box";
                        var cv = ((LocationCurve)w.Location).Curve;
                        var a = cv.GetEndPoint(0); var b = cv.GetEndPoint(1);
                        var dir = new XYZ(b.X - a.X, b.Y - a.Y, 0).Normalize();
                        var nrm = new XYZ(-dir.Y, dir.X, 0);
                        var bb = el.get_BoundingBox(null) ?? throw new Exception("no bounding box");
                        var centre = mode == "point" && el.Location is LocationPoint lp ? lp.Point : (bb.Min + bb.Max) / 2;
                        double side = Math.Sign((centre - a).DotProduct(nrm));
                        if (side == 0) side = 1;
                        var n = nrm * side;
                        double half = w.Width / 2;
                        double need;
                        if (mode == "point")
                            need = half + clear - (centre - a).DotProduct(n);
                        else
                        {
                            double minD = double.MaxValue;
                            foreach (var x in new[] { bb.Min.X, bb.Max.X })
                                foreach (var y in new[] { bb.Min.Y, bb.Max.Y })
                                    minD = Math.Min(minD, (new XYZ(x, y, a.Z) - a).DotProduct(n));
                            need = half + clear - minD;
                        }
                        if (need <= 0)
                            return J(new Dictionary<string, object> { ["ok"] = true, ["moved_m"] = 0 });
                        TransactionStatus st;
                        using (var t = new Transaction(d, "BAAK MCP - push off wall"))
                        {
                            t.Start();
                            ElementTransformUtils.MoveElement(d, el.Id, n * need);
                            st = t.Commit();
                        }
                        // a hosted element that cannot leave its host is rolled back by Revit: say so
                        return J(new Dictionary<string, object>
                        { ["ok"] = st == TransactionStatus.Committed, ["status"] = st.ToString(),
                          ["moved_m"] = st == TransactionStatus.Committed ? Math.Round(ToM(need), 3) : 0,
                          ["direction"] = new[] { Math.Round(n.X, 3), Math.Round(n.Y, 3) } });
                    }

                // All parameters of an element (and of its type with "type": true).
                case "params":
                    {
                        var d = Doc(uiapp);
                        var e = d.GetElement(new ElementId((long)D(p, "id"))) ?? throw new Exception("element not found");
                        bool onType = p.TryGetProperty("type", out var tyEl) && tyEl.ValueKind == JsonValueKind.True;
                        var target = onType ? d.GetElement(e.GetTypeId()) : e;
                        var list = new List<Dictionary<string, object>>();
                        foreach (Parameter pa in target.Parameters)
                        {
                            string v = pa.StorageType == StorageType.String ? pa.AsString() : pa.AsValueString();
                            list.Add(new Dictionary<string, object>
                            { ["name"] = pa.Definition.Name, ["value"] = v, ["storage"] = pa.StorageType.ToString(), ["readonly"] = pa.IsReadOnly });
                        }
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["id"] = target.Id.Value, ["name"] = target.Name, ["params"] = list.OrderBy(x => (string)x["name"]).ToList() });
                    }

                // Set parameters by name; lengths are given in metres. {"id", "params": {name: value}, "type": bool}
                case "set_params":
                    {
                        var d = Doc(uiapp);
                        var e = d.GetElement(new ElementId((long)D(p, "id"))) ?? throw new Exception("element not found");
                        bool onType = p.TryGetProperty("type", out var tyEl2) && tyEl2.ValueKind == JsonValueKind.True;
                        var target = onType ? d.GetElement(e.GetTypeId()) : e;
                        var done = new List<string>(); var failed = new List<string>();
                        using (var t = new Transaction(d, "BAAK MCP - set params"))
                        {
                            t.Start();
                            foreach (var kv in p.GetProperty("params").EnumerateObject())
                            {
                                var pa = target.LookupParameter(kv.Name);
                                if (pa == null || pa.IsReadOnly) { failed.Add(kv.Name + (pa == null ? " (absent)" : " (lecture seule)")); continue; }
                                bool ok = false;
                                switch (pa.StorageType)
                                {
                                    case StorageType.String: ok = pa.Set(kv.Value.ToString()); break;
                                    case StorageType.Integer: ok = pa.Set(kv.Value.ValueKind == JsonValueKind.True ? 1 : kv.Value.ValueKind == JsonValueKind.False ? 0 : (int)kv.Value.GetDouble()); break;
                                    case StorageType.ElementId: ok = pa.Set(new ElementId(kv.Value.GetInt64())); break;
                                    case StorageType.Double:
                                        double val = kv.Value.GetDouble();
                                        if (pa.Definition.GetDataType() == SpecTypeId.Length) val = M(val);
                                        else if (pa.Definition.GetDataType() == SpecTypeId.Angle) val = val * Math.PI / 180.0;
                                        ok = pa.Set(val); break;
                                }
                                (ok ? done : failed).Add(kv.Name);
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["set"] = done, ["failed"] = failed });
                    }

                // Element types of a category (by category name) - id, family, name.
                case "types":
                    {
                        var d = Doc(uiapp);
                        string catName = S(p, "category") ?? throw new Exception("category is required");
                        var list = new FilteredElementCollector(d).WhereElementIsElementType().Cast<ElementType>()
                            .Where(t => t.Category != null && t.Category.Name.Equals(catName, StringComparison.OrdinalIgnoreCase))
                            .Select(t => new Dictionary<string, object> { ["id"] = t.Id.Value, ["family"] = t.FamilyName, ["name"] = t.Name })
                            .OrderBy(x => (string)x["family"]).ThenBy(x => (string)x["name"]).ToList();
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = list.Count, ["types"] = list });
                    }

                case "set_type":
                    {
                        var d = Doc(uiapp);
                        var tid = new ElementId((long)D(p, "type_id"));
                        int n = 0;
                        using (var t = new Transaction(d, "BAAK MCP - set type"))
                        {
                            t.Start();
                            foreach (var e in p.GetProperty("ids").EnumerateArray())
                            {
                                var el = d.GetElement(new ElementId(e.GetInt64()));
                                if (el != null && el.IsValidType(tid)) { el.ChangeTypeId(tid); n++; }
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["changed"] = n });
                    }

                case "duplicate_type":
                    {
                        var d = Doc(uiapp);
                        var et = d.GetElement(new ElementId((long)D(p, "type_id"))) as ElementType ?? throw new Exception("type not found");
                        string nn = S(p, "name") ?? throw new Exception("name is required");
                        ElementType dup;
                        using (var t = new Transaction(d, "BAAK MCP - duplicate type"))
                        {
                            t.Start();
                            dup = et.Duplicate(nn);
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["id"] = dup.Id.Value, ["name"] = dup.Name });
                    }

                // Copy elements by an offset (metres); returns the new ids.
                case "copy_ids":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        ICollection<ElementId> nids;
                        using (var t = new Transaction(d, "BAAK MCP - copy ids"))
                        {
                            t.Start();
                            nids = ElementTransformUtils.CopyElements(d, ids, new XYZ(M(D(p, "dx")), M(D(p, "dy")), M(D(p, "dz"))));
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["ids"] = nids.Select(i => i.Value).ToList() });
                    }

                // Rotate elements about a vertical axis through (cx, cy) metres.
                case "rotate_ids":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        var c = new XYZ(M(D(p, "cx")), M(D(p, "cy")), 0);
                        using (var t = new Transaction(d, "BAAK MCP - rotate ids"))
                        {
                            t.Start();
                            ElementTransformUtils.RotateElements(d, ids, Line.CreateBound(c, c + XYZ.BasisZ), D(p, "angle_deg") * Math.PI / 180.0);
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["rotated"] = ids.Count });
                    }

                // Materials whose name contains "filter" - id, name, colour, class.
                case "materials":
                    {
                        var d = Doc(uiapp);
                        string f = S(p, "filter") ?? "";
                        var list = new FilteredElementCollector(d).OfClass(typeof(Material)).Cast<Material>()
                            .Where(m => m.Name.IndexOf(f, StringComparison.OrdinalIgnoreCase) >= 0)
                            .Select(m => new Dictionary<string, object>
                            { ["id"] = m.Id.Value, ["name"] = m.Name, ["class"] = m.MaterialClass, ["rgb"] = new[] { (int)m.Color.Red, (int)m.Color.Green, (int)m.Color.Blue } })
                            .OrderBy(x => (string)x["name"]).ToList();
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = list.Count, ["materials"] = list });
                    }

                // Every element (any category) whose box meets the given box (metres).
                case "in_box":
                    {
                        var d = Doc(uiapp);
                        var mn = p.GetProperty("min").EnumerateArray().Select(x => x.GetDouble()).ToArray();
                        var mxx = p.GetProperty("max").EnumerateArray().Select(x => x.GetDouble()).ToArray();
                        var ol = new Outline(new XYZ(M(mn[0]), M(mn[1]), M(mn[2])), new XYZ(M(mxx[0]), M(mxx[1]), M(mxx[2])));
                        var list = new FilteredElementCollector(d).WhereElementIsNotElementType()
                            .WherePasses(new BoundingBoxIntersectsFilter(ol))
                            .Where(e => e.Category != null && e.Category.CategoryType == CategoryType.Model)
                            .Select(e =>
                            {
                                var bb = e.get_BoundingBox(null);
                                return new Dictionary<string, object>
                                {
                                    ["id"] = e.Id.Value, ["category"] = e.Category.Name, ["name"] = e.Name,
                                    ["family"] = (e as FamilyInstance)?.Symbol?.FamilyName,
                                    ["mark"] = e.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.AsString(),
                                    ["bbox_min_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Min.X), 3), Math.Round(ToM(bb.Min.Y), 3), Math.Round(ToM(bb.Min.Z), 3) },
                                    ["bbox_max_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Max.X), 3), Math.Round(ToM(bb.Max.Y), 3), Math.Round(ToM(bb.Max.Z), 3) },
                                };
                            }).ToList();
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = list.Count, ["elements"] = list });
                    }

                // Move elements by id (metres) - e.g. bring floating pieces back onto their floor.
                case "move_ids":
                    {
                        var d = Doc(uiapp);
                        var ids = new List<ElementId>();
                        if (p.TryGetProperty("ids", out var mvArr) && mvArr.ValueKind == JsonValueKind.Array)
                            foreach (var e in mvArr.EnumerateArray()) ids.Add(new ElementId(e.GetInt64()));
                        var v = new XYZ(M(D(p, "dx")), M(D(p, "dy")), M(D(p, "dz")));
                        bool unpin = p.TryGetProperty("unpin", out var upEl) && upEl.ValueKind == JsonValueKind.True;
                        bool repin = p.TryGetProperty("repin", out var rpEl) && rpEl.ValueKind == JsonValueKind.True;
                        using (var t = new Transaction(d, "BAAK MCP - move ids"))
                        {
                            t.Start();
                            var live = ids.Where(i => d.GetElement(i) != null).ToList();
                            if (unpin) foreach (var i in live) { var el = d.GetElement(i); if (el.Pinned) el.Pinned = false; }
                            ElementTransformUtils.MoveElements(d, live, v);
                            if (repin) foreach (var i in live) d.GetElement(i).Pinned = true;
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["moved"] = ids.Count });
                    }

                // Export a 3D view to FBX (for 3ds Max). Never to G:.
                case "export_fbx":
                    {
                        var d = Doc(uiapp);
                        string folder = S(p, "folder") ?? throw new Exception("folder is required");
                        string name = S(p, "name") ?? throw new Exception("name is required");
                        string viewName = S(p, "view") ?? "{3D}";
                        if (folder.TrimStart().StartsWith("G:", StringComparison.OrdinalIgnoreCase))
                            throw new Exception("G: is read-only for this project");
                        Directory.CreateDirectory(folder);
                        View3D v3;
                        bool fresh = p.TryGetProperty("fresh", out var frEl) && frEl.ValueKind == JsonValueKind.True;
                        if (fresh)
                        {
                            // a new isometric view: no section box, no hidden categories, Fine detail, no template
                            var vft = new FilteredElementCollector(d).OfClass(typeof(ViewFamilyType)).Cast<ViewFamilyType>()
                                      .First(x => x.ViewFamily == ViewFamily.ThreeDimensional);
                            using (var t = new Transaction(d, "BAAK MCP - export 3D view"))
                            {
                                t.Start();
                                v3 = View3D.CreateIsometric(d, vft.Id);
                                v3.ViewTemplateId = ElementId.InvalidElementId;
                                v3.IsSectionBoxActive = false;
                                v3.DetailLevel = ViewDetailLevel.Fine;
                                try { v3.Name = "BAAK EXPORT FBX " + DateTime.Now.ToString("yyyyMMdd HHmm"); } catch { }
                                t.Commit();
                            }
                        }
                        else
                            v3 = new FilteredElementCollector(d).OfClass(typeof(View3D)).Cast<View3D>()
                                 .FirstOrDefault(x => !x.IsTemplate && x.Name.Equals(viewName, StringComparison.OrdinalIgnoreCase))
                                 ?? throw new Exception("3D view not found: " + viewName);
                        var vs = new ViewSet();
                        vs.Insert(v3);
                        var fo = new FBXExportOptions { WithoutBoundaryEdges = true };
                        bool okFbx = d.Export(folder, name, vs, fo);
                        string f = Path.Combine(folder, name.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase) ? name : name + ".fbx");
                        return J(new Dictionary<string, object>
                        { ["ok"] = okFbx, ["file"] = f, ["mb"] = File.Exists(f) ? Math.Round(new FileInfo(f).Length / 1048576.0, 1) : 0 });
                    }

                // Delete elements by id (used to remove doubles after a copy).
                case "delete_ids":
                    {
                        var d = Doc(uiapp);
                        var ids = new List<ElementId>();
                        if (p.TryGetProperty("ids", out var idArr) && idArr.ValueKind == JsonValueKind.Array)
                            foreach (var e in idArr.EnumerateArray()) ids.Add(new ElementId(e.GetInt64()));
                        int n = 0;
                        using (var t = new Transaction(d, "BAAK MCP - delete ids"))
                        {
                            t.Start();
                            foreach (var id in ids) if (d.GetElement(id) != null) { d.Delete(id); n++; }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["deleted"] = n });
                    }

                // Export named views (3D, plans, sections) as PNG images - used to compare the model with the renders.
                case "export_image":
                    {
                        var d = Doc(uiapp);
                        string folder = S(p, "folder") ?? throw new Exception("folder is required");
                        if (folder.TrimStart().StartsWith("G:", StringComparison.OrdinalIgnoreCase))
                            throw new Exception("G: is read-only for this project");
                        Directory.CreateDirectory(folder);
                        var wantedImg = new List<string>();
                        if (p.TryGetProperty("views", out var vArrImg) && vArrImg.ValueKind == JsonValueKind.Array)
                            foreach (var e in vArrImg.EnumerateArray())
                                if (e.ValueKind == JsonValueKind.String) wantedImg.Add(e.GetString());
                        int px = 1800;
                        if (p.TryGetProperty("pixels", out var pxEl) && pxEl.ValueKind == JsonValueKind.Number) px = pxEl.GetInt32();
                        var allImg = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>()
                                     .Where(v => !v.IsTemplate && v.CanBePrinted).ToList();
                        var t0 = DateTime.Now.AddSeconds(-2);
                        var missing = new List<string>();
                        foreach (var w in wantedImg)
                        {
                            var v = allImg.FirstOrDefault(x => x.Name.Equals(w, StringComparison.OrdinalIgnoreCase));
                            if (v == null) { missing.Add(w); continue; }
                            string safe = string.Join("_", w.Split(Path.GetInvalidFileNameChars()));
                            var io = new ImageExportOptions
                            {
                                ExportRange = ExportRange.SetOfViews,
                                FilePath = Path.Combine(folder, safe),
                                FitDirection = FitDirectionType.Horizontal,
                                PixelSize = px,
                                ImageResolution = ImageResolution.DPI_150,
                                HLRandWFViewsFileType = ImageFileType.PNG,
                                ShadowViewsFileType = ImageFileType.PNG,
                                ZoomType = ZoomFitType.FitToPage,
                            };
                            io.SetViewsAndSheets(new List<ElementId> { v.Id });
                            d.ExportImage(io);
                        }
                        var filesImg = Directory.GetFiles(folder, "*.png").Where(f => File.GetLastWriteTime(f) >= t0).ToList();
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["folder"] = folder, ["files"] = filesImg, ["missing"] = missing });
                    }

                // What can be exported: the views this document actually holds.
                case "views":
                    {
                        var d = Doc(uiapp);
                        var list = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>()
                            .Where(v => !v.IsTemplate && v.CanBePrinted)
                            .Select(v => new Dictionary<string, object>
                            {
                                ["name"] = v.Name,
                                ["number"] = (v as ViewSheet)?.SheetNumber,
                                ["type"] = v.ViewType.ToString(),
                                ["detail"] = v.DetailLevel.ToString(),
                                ["active"] = d.ActiveView != null && v.Id == d.ActiveView.Id,
                            })
                            .OrderBy(h => (string)h["type"]).ThenBy(h => (string)h["name"]).ToList();
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["count"] = list.Count, ["views"] = list });
                    }

                case "save":
                    {
                        var d = Doc(uiapp);
                        string path = S(p, "path");
                        if (string.IsNullOrEmpty(path)) d.Save();
                        else d.SaveAs(path, new SaveAsOptions { OverwriteExistingFile = true });
                        return J(new Dictionary<string, object>
                        { ["ok"] = true, ["saved"] = string.IsNullOrEmpty(path) ? d.PathName : path });
                    }

                // ---- Assemblies (21/11, mezzanine locker island swap): list / create / views / sheet viewports / delete with views ----
                case "assemblies":
                    {
                        var d = Doc(uiapp);
                        string filter = S(p, "filter");
                        var allViews = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>().Where(v => !v.IsTemplate).ToList();
                        var vps = new FilteredElementCollector(d).OfClass(typeof(Viewport)).Cast<Viewport>().ToList();
                        var rows = new List<object>();
                        foreach (AssemblyInstance a in new FilteredElementCollector(d).OfClass(typeof(AssemblyInstance)))
                        {
                            string tn = a.AssemblyTypeName ?? "";
                            if (!string.IsNullOrEmpty(filter) && tn.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                            var views = new List<object>();
                            foreach (var v in allViews.Where(v => v.AssociatedAssemblyInstanceId == a.Id))
                            {
                                var vpl = vps.Where(x => x.ViewId == v.Id).Select(x =>
                                {
                                    var sh = d.GetElement(x.SheetId) as ViewSheet; var c = x.GetBoxCenter();
                                    return new Dictionary<string, object>
                                    {
                                        ["viewport_id"] = x.Id.Value, ["sheet_id"] = x.SheetId.Value, ["sheet_number"] = sh?.SheetNumber, ["sheet_name"] = sh?.Name,
                                        ["center_m"] = new[] { Math.Round(ToM(c.X), 4), Math.Round(ToM(c.Y), 4) }, ["viewport_type_id"] = x.GetTypeId().Value,
                                    };
                                }).ToList();
                                int nAnn = -1;
                                try { nAnn = new FilteredElementCollector(d, v.Id).WhereElementIsNotElementType().Where(e => e.Category != null && e.Category.CategoryType == CategoryType.Annotation).Count(); } catch { }
                                views.Add(new Dictionary<string, object>
                                {
                                    ["id"] = v.Id.Value, ["name"] = v.Name, ["view_type"] = v.ViewType.ToString(), ["scale"] = v.Scale,
                                    ["detail_level"] = v.DetailLevel.ToString(), ["template_id"] = v.ViewTemplateId.Value, ["annotations"] = nAnn, ["viewports"] = vpl,
                                });
                            }
                            var bb = a.get_BoundingBox(null);
                            rows.Add(new Dictionary<string, object>
                            {
                                ["id"] = a.Id.Value, ["type_id"] = a.GetTypeId().Value, ["type_name"] = tn,
                                ["naming_category"] = Category.GetCategory(d, a.NamingCategoryId)?.Name,
                                ["members"] = a.GetMemberIds().Select(x => x.Value).ToList(),
                                ["bbox_min_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Min.X), 3), Math.Round(ToM(bb.Min.Y), 3), Math.Round(ToM(bb.Min.Z), 3) },
                                ["bbox_max_m"] = bb == null ? null : new[] { Math.Round(ToM(bb.Max.X), 3), Math.Round(ToM(bb.Max.Y), 3), Math.Round(ToM(bb.Max.Z), 3) },
                                ["views"] = views,
                            });
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["count"] = rows.Count, ["assemblies"] = rows });
                    }

                // Create an assembly from element ids, then name its type (the name can only be set in a second transaction).
                case "assembly_create":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        string name = S(p, "name");
                        ElementId cat = d.GetElement(ids[0]).Category.Id;
                        if (!AssemblyInstance.IsValidNamingCategory(d, cat, ids))
                            cat = ids.Select(i => d.GetElement(i).Category.Id).FirstOrDefault(c => AssemblyInstance.IsValidNamingCategory(d, c, ids)) ?? throw new Exception("no valid naming category");
                        AssemblyInstance a;
                        using (var t = new Transaction(d, "BAAK MCP - assembly create"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            a = AssemblyInstance.Create(d, ids, cat);
                            t.Commit();
                        }
                        string note = null;
                        if (!string.IsNullOrEmpty(name))
                            using (var t = new Transaction(d, "BAAK MCP - assembly name"))
                            {
                                t.Start();
                                try { a.AssemblyTypeName = name; } catch (Exception ex) { note = "rename failed: " + ex.Message; }
                                t.Commit();
                            }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["id"] = a.Id.Value, ["type_name"] = a.AssemblyTypeName, ["note"] = note });
                    }

                // Create assembly views: views:[{kind: "3D" | AssemblyDetailViewOrientation (ElevationTop, ElevationFront, DetailSectionA...),
                // name, template_id, scale, detail_level}] - same set as the old assembly sheets (3D, PLAN DESSUS, ELEVATION FACE, COUPE A).
                case "assembly_views":
                    {
                        var d = Doc(uiapp);
                        var aid = new ElementId((long)D(p, "assembly_id"));
                        var res = new List<object>();
                        using (var t = new Transaction(d, "BAAK MCP - assembly views"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            foreach (var it in p.GetProperty("views").EnumerateArray())
                            {
                                string kind = S(it, "kind"); string vname = S(it, "name");
                                var tpl = new ElementId((long)D(it, "template_id", -1));
                                bool useTpl = tpl.Value > 0 && d.GetElement(tpl) is View;
                                View v;
                                if (kind == "3D") v = useTpl ? AssemblyViewUtils.Create3DOrthographic(d, aid, tpl, true) : AssemblyViewUtils.Create3DOrthographic(d, aid);
                                else
                                {
                                    var o = (AssemblyDetailViewOrientation)Enum.Parse(typeof(AssemblyDetailViewOrientation), kind);
                                    v = useTpl ? AssemblyViewUtils.CreateDetailSection(d, aid, o, tpl, true) : AssemblyViewUtils.CreateDetailSection(d, aid, o);
                                }
                                var row = new Dictionary<string, object> { ["kind"] = kind, ["id"] = v.Id.Value };
                                int sc = (int)D(it, "scale", 0);
                                if (sc > 0) try { v.Scale = sc; } catch (Exception ex) { row["scale_note"] = ex.Message; }
                                string dl = S(it, "detail_level");
                                if (dl != null) try { v.DetailLevel = (ViewDetailLevel)Enum.Parse(typeof(ViewDetailLevel), dl); } catch (Exception ex) { row["detail_note"] = ex.Message; }
                                if (vname != null) try { v.Name = vname; } catch (Exception ex) { row["name_note"] = ex.Message; }
                                row["name"] = v.Name;
                                res.Add(row);
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["views"] = res });
                    }

                // Put a new view on the sheet in place of an old one: same sheet, same centre, same viewport type.
                case "viewport_replace":
                    {
                        var d = Doc(uiapp);
                        var oldView = new ElementId((long)D(p, "old_view_id"));
                        var newView = new ElementId((long)D(p, "new_view_id"));
                        var vp = new FilteredElementCollector(d).OfClass(typeof(Viewport)).Cast<Viewport>().FirstOrDefault(x => x.ViewId == oldView)
                                 ?? throw new Exception("the old view is on no sheet");
                        var sheetId = vp.SheetId; var c = vp.GetBoxCenter(); var typeId = vp.GetTypeId();
                        Viewport nv;
                        using (var t = new Transaction(d, "BAAK MCP - viewport replace"))
                        {
                            t.Start();
                            d.Delete(vp.Id);
                            if (!Viewport.CanAddViewToSheet(d, sheetId, newView)) throw new Exception("the new view cannot go on that sheet (already placed?)");
                            nv = Viewport.Create(d, sheetId, newView, c);
                            if (typeId != ElementId.InvalidElementId) try { nv.ChangeTypeId(typeId); } catch { }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["sheet_id"] = sheetId.Value, ["viewport_id"] = nv.Id.Value });
                    }

                // Delete assemblies cleanly: their own views first, disassemble, then optionally the members.
                case "assembly_delete":
                    {
                        var d = Doc(uiapp);
                        var ids = p.GetProperty("ids").EnumerateArray().Select(x => new ElementId(x.GetInt64())).ToList();
                        bool members = p.TryGetProperty("delete_members", out var dmEl) && dmEl.ValueKind == JsonValueKind.True;
                        bool keepViews = p.TryGetProperty("keep_views", out var kvEl) && kvEl.ValueKind == JsonValueKind.True;
                        var log = new List<object>();
                        using (var t = new Transaction(d, "BAAK MCP - assembly delete"))
                        {
                            t.Start();
                            var fho = t.GetFailureHandlingOptions(); fho.SetFailuresPreprocessor(new BaakSwallowWarnings()); t.SetFailureHandlingOptions(fho);
                            foreach (var id in ids)
                            {
                                if (!(d.GetElement(id) is AssemblyInstance a)) { log.Add(new Dictionary<string, object> { ["id"] = id.Value, ["err"] = "not an assembly" }); continue; }
                                var mem = a.GetMemberIds().ToList();
                                var views = new FilteredElementCollector(d).OfClass(typeof(View)).Cast<View>().Where(v => v.AssociatedAssemblyInstanceId == a.Id).Select(v => v.Id).ToList();
                                if (!keepViews && views.Count > 0) d.Delete(views);
                                a.Disassemble();
                                if (members) d.Delete(mem);
                                log.Add(new Dictionary<string, object> { ["id"] = id.Value, ["views_deleted"] = keepViews ? 0 : views.Count, ["members"] = mem.Select(x => x.Value).ToList(), ["members_deleted"] = members });
                            }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["log"] = log });
                    }

                // New sheet with the same title block as an existing one: {like_sheet_id, number, name}.
                case "sheet_create":
                    {
                        var d = Doc(uiapp);
                        var like = d.GetElement(new ElementId((long)D(p, "like_sheet_id"))) as ViewSheet ?? throw new Exception("like_sheet_id is not a sheet");
                        var tb = new FilteredElementCollector(d, like.Id).OfCategory(BuiltInCategory.OST_TitleBlocks).WhereElementIsNotElementType().FirstElement();
                        ViewSheet sh;
                        using (var t = new Transaction(d, "BAAK MCP - sheet create"))
                        {
                            t.Start();
                            sh = ViewSheet.Create(d, tb?.GetTypeId() ?? ElementId.InvalidElementId);
                            string num = S(p, "number"), name = S(p, "name");
                            if (num != null) sh.SheetNumber = num;
                            if (name != null) sh.Name = name;
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["id"] = sh.Id.Value, ["number"] = sh.SheetNumber, ["name"] = sh.Name });
                    }

                // Place a view on a sheet at a centre (metres, sheet coordinates), optional viewport type: {sheet_id, view_id, center_m:[x,y], type_id}.
                case "viewport_place":
                    {
                        var d = Doc(uiapp);
                        var sheetId = new ElementId((long)D(p, "sheet_id")); var viewId = new ElementId((long)D(p, "view_id"));
                        var cArr = p.GetProperty("center_m").EnumerateArray().Select(x => x.GetDouble()).ToArray();
                        Viewport vp;
                        using (var t = new Transaction(d, "BAAK MCP - viewport place"))
                        {
                            t.Start();
                            if (!Viewport.CanAddViewToSheet(d, sheetId, viewId)) throw new Exception("this view cannot go on that sheet (already placed?)");
                            vp = Viewport.Create(d, sheetId, viewId, new XYZ(M(cArr[0]), M(cArr[1]), 0));
                            long tid = (long)D(p, "type_id", -1);
                            if (tid > 0) try { vp.ChangeTypeId(new ElementId(tid)); } catch { }
                            t.Commit();
                        }
                        return J(new Dictionary<string, object> { ["ok"] = true, ["viewport_id"] = vp.Id.Value });
                    }

                default:
                    throw new Exception("unknown method: " + job.Method);
            }
        }

        // Reloading a family that is already in the project needs this, or LoadFamily just returns false.
        private class BaakOverwrite : IFamilyLoadOptions
        {
            public bool OnFamilyFound(bool familyInUse, out bool overwriteParameterValues)
            { overwriteParameterValues = true; return true; }
            public bool OnSharedFamilyFound(Family sharedFamily, bool familyInUse, out FamilySource source, out bool overwriteParameterValues)
            { source = FamilySource.Family; overwriteParameterValues = true; return true; }
        }

        // Drop warnings (e.g. "elements overlap") so a batch commit is not blocked by a dialog; errors still roll back.
        private class BaakSwallowWarnings : IFailuresPreprocessor
        {
            public FailureProcessingResult PreprocessFailures(FailuresAccessor fa)
            {
                bool fixedSome = false;
                foreach (var f in fa.GetFailureMessages())
                {
                    if (f.GetSeverity() == FailureSeverity.Warning) { fa.DeleteWarning(f); continue; }
                    // errors (e.g. "line too short" after an elbow): drop the failing elements instead of a blocking dialog
                    if (f.HasResolutionOfType(FailureResolutionType.DeleteElements))
                    { f.SetCurrentResolutionType(FailureResolutionType.DeleteElements); fa.ResolveFailure(f); fixedSome = true; }
                    else if (f.GetFailingElementIds().Count > 0)
                    { fa.DeleteElements(f.GetFailingElementIds().ToList()); fixedSome = true; }
                }
                return fixedSome ? FailureProcessingResult.ProceedWithCommit : FailureProcessingResult.Continue;
            }
        }

        // One joint per transaction: warnings dropped, any error rolls the joint back (no dialog, nothing else deleted).
        private class BaakRollbackOnError : IFailuresPreprocessor
        {
            public FailureProcessingResult PreprocessFailures(FailuresAccessor fa)
            {
                bool err = false;
                foreach (var f in fa.GetFailureMessages())
                {
                    if (f.GetSeverity() == FailureSeverity.Warning) fa.DeleteWarning(f);
                    else err = true;
                }
                return err ? FailureProcessingResult.ProceedWithRollBack : FailureProcessingResult.Continue;
            }
        }

        private static Document Doc(UIApplication uiapp)
            => uiapp.ActiveUIDocument?.Document ?? throw new Exception("no document is open in Revit");

        private static Level LevelByName(Document d, string name)
        {
            var levels = new FilteredElementCollector(d).OfClass(typeof(Level)).Cast<Level>().ToList();
            if (levels.Count == 0) throw new Exception("the document has no level");
            if (string.IsNullOrEmpty(name)) return levels.OrderBy(l => l.Elevation).First();
            return levels.FirstOrDefault(l => l.Name.Equals(name, StringComparison.OrdinalIgnoreCase))
                   ?? levels.OrderBy(l => Math.Abs(l.Elevation)).First();
        }

        private static void SetMarkAndComment(Document d, ElementId id, string mark, string comment)
        {
            var el = d.GetElement(id);
            if (el == null) return;
            if (!string.IsNullOrEmpty(mark))
                el.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)?.Set(mark);
            if (!string.IsNullOrEmpty(comment))
                el.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)?.Set(comment);
        }
    }
}
