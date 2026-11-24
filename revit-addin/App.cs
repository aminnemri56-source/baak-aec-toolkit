using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace BaakRevitMcp
{
    // One queued call from the socket thread, executed on Revit's UI thread.
    internal class Job
    {
        public string Method;
        public JsonElement Params;
        public string Result;                       // JSON written by the handler
        public readonly ManualResetEventSlim Done = new ManualResetEventSlim(false);
    }

    /// <summary>
    /// Revit add-in: opens a line-oriented JSON socket on 127.0.0.1:8099 at Revit startup
    /// (no ribbon button, nothing to click) and runs each request on the UI thread.
    /// </summary>
    public class App : IExternalApplication
    {
        internal const int PORT = 8099;
        internal static UIControlledApplication UiCtrl;
        internal static UIApplication UiApp;
        private static ExternalEvent _event;
        private static Handler _handler;
        private static readonly BlockingCollection<Job> Queue = new BlockingCollection<Job>();
        private static TcpListener _listener;
        private static Thread _thread;
        private static volatile bool _stop;
        internal static string LogPath;

        public Result OnStartup(UIControlledApplication a)
        {
            UiCtrl = a;
            LogPath = Path.Combine(Path.GetTempPath(), "baak_revit_mcp.log");
            Log("OnStartup");
            _handler = new Handler(Queue);
            _event = ExternalEvent.Create(_handler);
            _handler.Event = _event;

            // UIApplication is only reachable once the first idle tick happens.
            a.Idling += OnFirstIdle;

            _thread = new Thread(Serve) { IsBackground = true, Name = "BaakRevitMcp" };
            _thread.Start();
            return Result.Succeeded;
        }

        private void OnFirstIdle(object sender, Autodesk.Revit.UI.Events.IdlingEventArgs e)
        {
            if (UiApp == null && sender is UIApplication ua) { UiApp = ua; Log("UIApplication captured"); }
        }

        public Result OnShutdown(UIControlledApplication a)
        {
            _stop = true;
            try { _listener?.Stop(); } catch { }
            return Result.Succeeded;
        }

        internal static void Log(string m)
        {
            try { File.AppendAllText(LogPath, DateTime.Now.ToString("HH:mm:ss.fff") + "  " + m + Environment.NewLine); } catch { }
        }

        private static void Serve()
        {
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, PORT);
                _listener.Start();
                Log("listening on 127.0.0.1:" + PORT);
            }
            catch (Exception ex) { Log("listen failed: " + ex.Message); return; }

            while (!_stop)
            {
                TcpClient client = null;
                try { client = _listener.AcceptTcpClient(); }
                catch { if (_stop) break; continue; }
                var c = client;
                new Thread(() => Session(c)) { IsBackground = true }.Start();
            }
        }

        private static void Session(TcpClient client)
        {
            try
            {
                using var _c = client;
                var stream = client.GetStream();
                var reader = new StreamReader(stream, new UTF8Encoding(false));
                var writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true };
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (line.Trim().Length == 0) continue;
                    string reply;
                    try { reply = Dispatch(line); }
                    catch (Exception ex) { reply = Err(ex.Message); }
                    writer.WriteLine(reply);
                }
            }
            catch (Exception ex) { Log("session: " + ex.Message); }
        }

        private static string Err(string m) =>
            JsonSerializer.Serialize(new Dictionary<string, object> { ["ok"] = false, ["error"] = m });

        private static string Dispatch(string line)
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            string method = root.TryGetProperty("method", out var mEl) ? mEl.GetString() : null;
            if (string.IsNullOrEmpty(method)) return Err("no method");

            // answered on this thread, no Revit API needed
            if (method == "ping")
                return JsonSerializer.Serialize(new Dictionary<string, object>
                { ["ok"] = true, ["pong"] = true, ["port"] = PORT, ["log"] = LogPath });

            var job = new Job { Method = method };
            if (root.TryGetProperty("params", out var p))
            {
                // the JsonDocument dies with this scope, so keep an independent copy
                job.Params = JsonDocument.Parse(p.GetRawText()).RootElement.Clone();
            }
            Queue.Add(job);
            _event.Raise();
            if (!job.Done.Wait(TimeSpan.FromMinutes(10))) return Err("timed out waiting for Revit");
            return job.Result ?? Err("no result");
        }
    }
}
