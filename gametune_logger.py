#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GameTuneLogger - lightweight system-tray game performance logger for Windows.

- FPS / frametimes  : Intel PresentMon (bundled PresentMon.exe, passive ETW - no game injection)
- CPU temp/clock/W  : LibreHardwareMonitorLib.dll via pythonnet (requires Administrator)
- GPU temp/clock/W  : NVIDIA NVML (pynvml)
- Output per session: summary.txt, timeline.csv (1 row/sec), sensors.csv,
  presentmon_raw.csv.gz -> all zipped into logs/session_YYYYMMDD_HHMMSS.zip
"""

import os
import sys
import csv
import json
import time
import gzip
import ctypes
import shutil
import signal
import logging
import zipfile
import threading
import subprocess
from datetime import datetime

APP_NAME = "GameTuneLogger"
POLL_SEC = 1.0
FT_COLS = ("msbetweenpresents", "frametime")  # PresentMon v1 / v2 column names
MAX_STORED_FRAMES = 3_000_000

BLACKLIST = {
    "dwm.exe", "explorer.exe", "searchhost.exe", "searchapp.exe",
    "shellexperiencehost.exe", "startmenuexperiencehost.exe",
    "textinputhost.exe", "applicationframehost.exe", "lockapp.exe",
    "steamwebhelper.exe", "steam.exe", "discord.exe", "chrome.exe",
    "msedge.exe", "msedgewebview2.exe", "firefox.exe", "opera.exe",
    "obs64.exe", "obs32.exe", "nvcontainer.exe", "nvidia overlay.exe",
    "nvidia share.exe", "widgets.exe", "widgetboard.exe",
    "gamebar.exe", "xboxgamebar.exe", "gamebarftserver.exe",
    "wallpaper64.exe", "wallpaper32.exe", "taskmgr.exe",
    "hwinfo64.exe", "hwinfo32.exe", "presentmon.exe",
    "gametunelogger.exe", "python.exe", "pythonw.exe",
}


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE = base_dir()
LOG_DIR = os.path.join(BASE, "logs")

logging.basicConfig(
    filename=os.path.join(BASE, "gametune_debug.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(APP_NAME)


def msgbox(text, title=APP_NAME, flags=0x40):
    try:
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), flags)
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin():
    try:
        if getattr(sys, "frozen", False):
            exe, params = sys.executable, ""
        else:
            exe = sys.executable
            params = '"%s"' % os.path.abspath(__file__)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    except Exception:
        log.exception("relaunch_as_admin failed")


# ----------------------------------------------------------------- GPU (NVML)

THROTTLE_BITS = [
    (0x1, "IDLE"),
    (0x2, "APP_CLK"),
    (0x4, "SW_PWR"),
    (0x8, "HW_SLOW"),
    (0x10, "SYNC"),
    (0x20, "SW_THERM"),
    (0x40, "HW_THERM"),
    (0x80, "PWR_BRAKE"),
    (0x100, "DISP_CLK"),
]


class GpuReader(object):
    def __init__(self):
        import pynvml
        self.nv = pynvml
        pynvml.nvmlInit()
        self.h = pynvml.nvmlDeviceGetHandleByIndex(0)
        try:
            name = pynvml.nvmlDeviceGetName(self.h)
            self.name = name.decode() if isinstance(name, bytes) else str(name)
        except Exception:
            self.name = "NVIDIA GPU"

    def read(self):
        nv, h = self.nv, self.h
        d = {}
        try:
            d["gpu_temp_c"] = nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)
        except Exception:
            d["gpu_temp_c"] = None
        try:
            d["gpu_clock_mhz"] = nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_GRAPHICS)
        except Exception:
            d["gpu_clock_mhz"] = None
        try:
            d["gpu_load_pct"] = nv.nvmlDeviceGetUtilizationRates(h).gpu
        except Exception:
            d["gpu_load_pct"] = None
        try:
            d["gpu_power_w"] = round(nv.nvmlDeviceGetPowerUsage(h) / 1000.0, 1)
        except Exception:
            d["gpu_power_w"] = None
        try:
            m = nv.nvmlDeviceGetMemoryInfo(h)
            d["gpu_vram_mb"] = int(m.used / (1024 * 1024))
        except Exception:
            d["gpu_vram_mb"] = None
        try:
            d["gpu_pstate"] = "P%d" % nv.nvmlDeviceGetPerformanceState(h)
        except Exception:
            d["gpu_pstate"] = None
        try:
            r = nv.nvmlDeviceGetCurrentClocksThrottleReasons(h)
            labels = [name for bit, name in THROTTLE_BITS if r & bit]
            d["gpu_throttle"] = "+".join(labels) if labels else "NONE"
        except Exception:
            d["gpu_throttle"] = None
        return d

    def close(self):
        try:
            self.nv.nvmlShutdown()
        except Exception:
            pass


# ------------------------------------------------- CPU (LibreHardwareMonitor)

class CpuReader(object):
    def __init__(self, dll_dir):
        import pythonnet
        if getattr(sys, "frozen", False):
            import glob
            pydll = glob.glob(os.path.join(sys._MEIPASS, "python3*.dll"))
            if pydll:
                os.environ["PYTHONNET_PYDLL"] = pydll[0]
        try:
            pythonnet.load("netfx")
        except Exception:
            try:
                pythonnet.load()
            except Exception:
                pass
        import clr
        sys.path.append(dll_dir)
        clr.AddReference("LibreHardwareMonitorLib")
        from LibreHardwareMonitor import Hardware
        comp = Hardware.Computer()
        comp.IsCpuEnabled = True
        comp.Open()
        self.comp = comp

    def read(self):
        d = {"cpu_temp_c": None, "cpu_clock_mhz": None,
             "cpu_load_pct": None, "cpu_power_w": None}
        try:
            for hw in self.comp.Hardware:
                if "cpu" not in str(hw.HardwareType).lower():
                    continue
                hw.Update()
                clocks = []
                core_max = None
                for s in hw.Sensors:
                    try:
                        if s.Value is None:
                            continue
                        st = str(s.SensorType).lower()
                        name = str(s.Name)
                        val = float(s.Value)
                    except Exception:
                        continue
                    if st == "temperature":
                        if name == "CPU Package":
                            d["cpu_temp_c"] = round(val, 1)
                        elif name == "Core Max":
                            core_max = round(val, 1)
                    elif st == "load" and name == "CPU Total":
                        d["cpu_load_pct"] = round(val, 1)
                    elif st == "power" and name in ("CPU Package", "Package"):
                        d["cpu_power_w"] = round(val, 1)
                    elif st == "clock" and "core" in name.lower() and "bus" not in name.lower():
                        clocks.append(val)
                if d["cpu_temp_c"] is None and core_max is not None:
                    d["cpu_temp_c"] = core_max
                if clocks:
                    d["cpu_clock_mhz"] = int(max(clocks))
        except Exception:
            log.exception("CpuReader.read failed")
        return d

    def close(self):
        try:
            self.comp.Close()
        except Exception:
            pass


# ------------------------------------------------------------- PresentMon run

class PresentMonRunner(object):
    def __init__(self, exe_path, out_csv):
        self.exe = exe_path
        self.out_csv = out_csv
        self.proc = None

    def start(self):
        flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        args = [self.exe, "--output_file", self.out_csv, "--stop_existing_session"]
        self.proc = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=flags)
        log.info("PresentMon started pid=%s", self.proc.pid)

    def stop(self):
        p = self.proc
        if p is None:
            return
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT)
            p.wait(timeout=5)
        except Exception:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        log.info("PresentMon stopped")


# --------------------------------------------------------- frametime parsing

class FrameParser(threading.Thread):
    """Tails the PresentMon CSV and aggregates frametimes per process."""

    def __init__(self, csv_path):
        super(FrameParser, self).__init__(daemon=True)
        self.csv_path = csv_path
        self.stop_event = threading.Event()
        self.apps = {}  # (app, pid) -> {"fts": [], "cum": float, "buckets": {sec: [n, sum, max]}}
        self.first_row_wall = None
        self.header_ok = False
        self.error = None
        self.truncated = False

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.error = str(e)
            log.exception("FrameParser crashed")

    def _run(self):
        t0 = time.time()
        while not os.path.exists(self.csv_path):
            if self.stop_event.is_set() or time.time() - t0 > 25:
                self.error = "PresentMon CSV never appeared (is PresentMon.exe present / admin rights?)"
                return
            time.sleep(0.3)
        f = open(self.csv_path, "r", encoding="utf-8-sig", errors="ignore", newline="")
        try:
            header = self._read_line_blocking(f, timeout=20)
            if not header:
                self.error = "PresentMon CSV header timeout"
                return
            cols = [c.strip().lower() for c in header.strip().split(",")]
            try:
                app_i = cols.index("application")
                pid_i = cols.index("processid")
            except ValueError:
                self.error = "unexpected CSV header: %s" % header.strip()
                return
            ft_i = None
            for cand in FT_COLS:
                if cand in cols:
                    ft_i = cols.index(cand)
                    break
            if ft_i is None:
                self.error = "no frametime column in header: %s" % header.strip()
                return
            self.header_ok = True
            need = max(app_i, pid_i, ft_i) + 1
            pending = ""
            while True:
                chunk = f.readline()
                if chunk:
                    pending += chunk
                    if not pending.endswith("\n"):
                        continue
                    line, pending = pending, ""
                    self._row(line, app_i, pid_i, ft_i, need)
                    continue
                if self.stop_event.is_set():
                    break
                time.sleep(0.25)
        finally:
            f.close()

    def _read_line_blocking(self, f, timeout):
        t0 = time.time()
        buf = ""
        while time.time() - t0 < timeout:
            chunk = f.readline()
            if chunk:
                buf += chunk
                if buf.endswith("\n"):
                    return buf
            else:
                if self.stop_event.is_set():
                    return buf if buf else None
                time.sleep(0.2)
        return buf if buf.endswith("\n") else None

    def _row(self, line, app_i, pid_i, ft_i, need):
        parts = line.rstrip("\r\n").split(",")
        if len(parts) < need:
            return
        try:
            ft = float(parts[ft_i])
        except ValueError:
            return
        if not (0.0 < ft < 10000.0):
            return
        app = parts[app_i].strip().lower()
        key = (app, parts[pid_i].strip())
        rec = self.apps.get(key)
        if rec is None:
            rec = {"fts": [], "cum": 0.0, "buckets": {}}
            self.apps[key] = rec
        rec["cum"] += ft / 1000.0
        if len(rec["fts"]) < MAX_STORED_FRAMES:
            rec["fts"].append(ft)
        else:
            self.truncated = True
        sec = int(rec["cum"])
        b = rec["buckets"].get(sec)
        if b is None:
            rec["buckets"][sec] = [1, ft, ft]
        else:
            b[0] += 1
            b[1] += ft
            if ft > b[2]:
                b[2] = ft
        if self.first_row_wall is None:
            self.first_row_wall = time.time()


# ------------------------------------------------------------- sensor logger

class SensorLogger(threading.Thread):
    FIELDS = ["ts", "elapsed_s", "cpu_temp_c", "cpu_clock_mhz", "cpu_load_pct",
              "cpu_power_w", "gpu_temp_c", "gpu_clock_mhz", "gpu_load_pct",
              "gpu_power_w", "gpu_vram_mb", "gpu_pstate", "gpu_throttle",
              "ram_used_gb"]

    def __init__(self, out_csv, cpu_reader, gpu_reader, wall_start):
        super(SensorLogger, self).__init__(daemon=True)
        self.out_csv = out_csv
        self.cpu = cpu_reader
        self.gpu = gpu_reader
        self.wall_start = wall_start
        self.stop_event = threading.Event()
        self.samples = {}

    def run(self):
        try:
            import psutil
        except Exception:
            psutil = None
        if psutil:
            try:
                psutil.cpu_percent(None)
            except Exception:
                pass
        try:
            f = open(self.out_csv, "w", newline="", encoding="utf-8")
        except Exception:
            log.exception("sensors.csv open failed")
            return
        w = csv.DictWriter(f, fieldnames=self.FIELDS)
        w.writeheader()
        n = 0
        while not self.stop_event.is_set():
            target = self.wall_start + n * POLL_SEC
            delay = target - time.time()
            if delay > 0 and self.stop_event.wait(delay):
                break
            n += 1
            row = dict((k, None) for k in self.FIELDS)
            row["ts"] = datetime.now().strftime("%H:%M:%S")
            elapsed = int(round(time.time() - self.wall_start))
            row["elapsed_s"] = elapsed
            try:
                if self.cpu:
                    row.update(self.cpu.read())
            except Exception:
                pass
            try:
                if self.gpu:
                    row.update(self.gpu.read())
            except Exception:
                pass
            if psutil:
                try:
                    row["ram_used_gb"] = round(psutil.virtual_memory().used / 1e9, 2)
                    if row["cpu_load_pct"] is None:
                        row["cpu_load_pct"] = psutil.cpu_percent(None)
                    if row["cpu_clock_mhz"] is None:
                        fr = psutil.cpu_freq()
                        if fr:
                            row["cpu_clock_mhz"] = int(fr.current)
                except Exception:
                    pass
            self.samples[elapsed] = row
            try:
                w.writerow(row)
                f.flush()
            except Exception:
                pass
        try:
            f.close()
        except Exception:
            pass


# ------------------------------------------------------------------ analysis

def pct_ft(sorted_ft, p):
    if not sorted_ft:
        return None
    i = min(len(sorted_ft) - 1, int(len(sorted_ft) * p))
    return round(sorted_ft[i], 2)


def low_fps(sorted_ft, frac):
    if not sorted_ft:
        return None
    n = max(1, int(len(sorted_ft) * frac))
    worst = sorted_ft[-n:]
    return round(1000.0 / (sum(worst) / len(worst)), 1)


def whea_count(seconds):
    try:
        ms = int(max(1, seconds) * 1000)
        q = ("*[System[Provider[@Name='Microsoft-Windows-WHEA-Logger'] "
             "and TimeCreated[timediff(@SystemTime) <= %d]]]" % ms)
        out = subprocess.run(
            ["wevtutil", "qe", "System", "/q:" + q, "/f:xml", "/c:500"],
            capture_output=True, text=True, timeout=25,
            creationflags=0x08000000)
        return out.stdout.count("</Event>")
    except Exception:
        log.exception("whea_count failed")
        return None


# ----------------------------------------------------------------------- app

class App(object):
    def __init__(self):
        self.recording = False
        self.busy = False
        self.lock = threading.Lock()
        self.session = None
        self.icon = None
        self.init_notes = []
        self.gpu = None
        self.cpu = None
        try:
            self.gpu = GpuReader()
        except Exception as e:
            self.init_notes.append("GPU (NVML) unavailable: %s" % e)
            log.exception("GpuReader init failed")
        dll = os.path.join(BASE, "LibreHardwareMonitorLib.dll")
        if os.path.exists(dll):
            try:
                self.cpu = CpuReader(BASE)
            except Exception as e:
                self.init_notes.append("CPU sensors failed (LibreHardwareMonitor): %s" % e)
                log.exception("CpuReader init failed")
        else:
            self.init_notes.append("LibreHardwareMonitorLib.dll not found - no CPU temp")
        self.pm_exe = os.path.join(BASE, "PresentMon.exe")
        if not os.path.exists(self.pm_exe):
            self.init_notes.append("PresentMon.exe not found - FPS capture disabled")

    # ---- tray helpers

    def make_image(self, rec):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        color = (220, 40, 40, 255) if rec else (40, 180, 70, 255)
        d.ellipse([6, 6, 58, 58], fill=color)
        d.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))
        return img

    def refresh(self):
        if not self.icon:
            return
        try:
            self.icon.icon = self.make_image(self.recording)
            self.icon.title = APP_NAME + (" - RECORDING" if self.recording else " - idle")
            self.icon.update_menu()
        except Exception:
            pass

    def notify(self, msg):
        log.info("notify: %s", msg)
        try:
            self.icon.notify(msg, APP_NAME)
        except Exception:
            pass

    # ---- session control

    def on_toggle(self, icon=None, item=None):
        threading.Thread(target=self._toggle, daemon=True).start()

    def _toggle(self):
        with self.lock:
            if self.busy:
                return
            self.busy = True
        try:
            if self.recording:
                self._stop()
            else:
                self._start()
        finally:
            self.busy = False
            self.refresh()

    def _start(self):
        if not os.path.exists(self.pm_exe):
            self.notify("PresentMon.exe not found next to the app - cannot capture FPS")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sdir = os.path.join(LOG_DIR, "session_" + stamp)
        os.makedirs(sdir, exist_ok=True)
        raw = os.path.join(sdir, "presentmon_raw.csv")
        pm = PresentMonRunner(self.pm_exe, raw)
        try:
            pm.start()
        except Exception as e:
            self.notify("PresentMon failed to start: %s" % e)
            return
        wall = time.time()
        parser = FrameParser(raw)
        parser.start()
        sensors = SensorLogger(os.path.join(sdir, "sensors.csv"),
                               self.cpu, self.gpu, wall)
        sensors.start()
        self.session = {"dir": sdir, "stamp": stamp, "wall_start": wall,
                        "pm": pm, "parser": parser, "sensors": sensors}
        self.recording = True
        self.refresh()
        self.notify("Recording started - play now, press Stop after the match")

    def _stop(self):
        s = self.session
        if not s:
            self.recording = False
            return
        self.notify("Saving session, please wait...")
        s["sensors"].stop_event.set()
        s["pm"].stop()
        time.sleep(0.5)
        s["parser"].stop_event.set()
        s["parser"].join(timeout=30)
        s["sensors"].join(timeout=10)
        try:
            zip_path = self._finish(s)
            self.notify("Saved: %s" % os.path.basename(zip_path))
            try:
                os.startfile(LOG_DIR)
            except Exception:
                pass
        except Exception as e:
            log.exception("finish failed")
            self.notify("Error while saving: %s" % e)
        self.recording = False
        self.session = None

    # ---- summary / files

    def _finish(self, s):
        parser = s["parser"]
        sensors = s["sensors"]
        wall_dur = time.time() - s["wall_start"]
        notes = list(self.init_notes)
        if parser.error:
            notes.append("PresentMon parser: %s" % parser.error)
        if parser.truncated:
            notes.append("frametime list truncated at %d frames (stats from first part)"
                         % MAX_STORED_FRAMES)

        def frames_of(rec):
            return sum(b[0] for b in rec["buckets"].values())

        game_key, game_n = None, 0
        for key, rec in parser.apps.items():
            if key[0] in BLACKLIST:
                continue
            n = frames_of(rec)
            if n > game_n:
                game_key, game_n = key, n
        if game_key is None or game_n < 300:
            for key, rec in parser.apps.items():
                n = frames_of(rec)
                if n > game_n:
                    game_key, game_n = key, n
            if game_key is not None:
                notes.append("WARNING: no obvious game process; using largest presenter")

        summary = {"session": s["stamp"], "wall_duration_s": round(wall_dur, 1),
                   "notes": notes}
        top = sorted(((frames_of(r), k[0], k[1]) for k, r in parser.apps.items()),
                     reverse=True)[:5]
        summary["top_presenters"] = [
            {"app": a, "pid": p, "frames": n} for n, a, p in top]

        secs = 0
        rec = None
        if game_key is not None:
            rec = parser.apps[game_key]
            fts = sorted(rec["fts"])
            dur = rec["cum"]
            secs = int(dur)
            summary.update({
                "game": game_key[0],
                "pid": game_key[1],
                "duration_s": round(dur, 1),
                "frames": game_n,
                "avg_fps": round(game_n / dur, 1) if dur > 0 else None,
                "median_fps": (round(1000.0 / pct_ft(fts, 0.5), 1)
                               if fts else None),
                "fps_1pct_low": low_fps(fts, 0.01),
                "fps_01pct_low": low_fps(fts, 0.001),
                "ft_p99_ms": pct_ft(fts, 0.99),
                "ft_p999_ms": pct_ft(fts, 0.999),
                "ft_max_ms": round(fts[-1], 2) if fts else None,
                "spikes_gt50ms": sum(1 for x in fts if x > 50.0),
                "spikes_gt100ms": sum(1 for x in fts if x > 100.0),
            })
            if dur > 0:
                summary["spikes_gt50ms_per_min"] = round(
                    summary["spikes_gt50ms"] / (dur / 60.0), 2)
            full = [x for x in rec["buckets"] if x < secs]
            summary["worst_1s_fps"] = (min(rec["buckets"][x][0] for x in full)
                                       if full else None)
            per_sec = [rec["buckets"].get(i, [0, 0, 0])[0] for i in range(secs)]
            if secs >= 10:
                acc = sum(per_sec[:10])
                best = acc
                for i in range(10, secs):
                    acc += per_sec[i] - per_sec[i - 10]
                    if acc < best:
                        best = acc
                summary["worst_10s_avg_fps"] = round(best / 10.0, 1)
        else:
            summary["game"] = None
            notes.append("no frames captured at all")

        # sensor aggregates
        def vals(key):
            return [r[key] for r in sensors.samples.values()
                    if isinstance(r.get(key), (int, float))]

        def agg(key, fn):
            v = vals(key)
            return round(fn(v), 1) if v else None

        summary.update({
            "cpu_temp_avg_c": agg("cpu_temp_c", lambda v: sum(v) / len(v)),
            "cpu_temp_max_c": agg("cpu_temp_c", max),
            "cpu_clock_max_mhz": agg("cpu_clock_mhz", max),
            "cpu_load_avg_pct": agg("cpu_load_pct", lambda v: sum(v) / len(v)),
            "cpu_power_avg_w": agg("cpu_power_w", lambda v: sum(v) / len(v)),
            "cpu_power_max_w": agg("cpu_power_w", max),
            "gpu_temp_avg_c": agg("gpu_temp_c", lambda v: sum(v) / len(v)),
            "gpu_temp_max_c": agg("gpu_temp_c", max),
            "gpu_load_avg_pct": agg("gpu_load_pct", lambda v: sum(v) / len(v)),
            "gpu_power_avg_w": agg("gpu_power_w", lambda v: sum(v) / len(v)),
            "gpu_power_max_w": agg("gpu_power_w", max),
            "ram_used_max_gb": agg("ram_used_gb", max),
        })
        loaded_clk = [r["gpu_clock_mhz"] for r in sensors.samples.values()
                      if isinstance(r.get("gpu_clock_mhz"), (int, float))
                      and isinstance(r.get("gpu_load_pct"), (int, float))
                      and r["gpu_load_pct"] >= 90]
        summary["gpu_clock_min_under_load_mhz"] = (int(min(loaded_clk))
                                                   if loaded_clk else None)
        limited = 0
        for r in sensors.samples.values():
            t = r.get("gpu_throttle")
            if t and any(k in t for k in ("THERM", "SW_PWR", "HW", "PWR_BRAKE")):
                limited += 1
        summary["gpu_limited_secs"] = limited
        summary["whea_events"] = whea_count(wall_dur)

        # timeline.csv (per-second, game + sensors joined)
        offset = 0
        if parser.first_row_wall:
            offset = int(round(parser.first_row_wall - s["wall_start"]))
        tl_path = os.path.join(s["dir"], "timeline.csv")
        with open(tl_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["sec", "fps", "ft_avg_ms", "ft_max_ms"] +
                       SensorLogger.FIELDS[2:])
            for i in range(secs):
                b = rec["buckets"].get(i) if rec else None
                fps = b[0] if b else 0
                ft_avg = round(b[1] / b[0], 2) if b else None
                ft_max = round(b[2], 2) if b else None
                srow = (sensors.samples.get(i + offset) or
                        sensors.samples.get(i + offset + 1) or
                        sensors.samples.get(i + offset - 1) or {})
                w.writerow([i, fps, ft_avg, ft_max] +
                           [srow.get(k) for k in SensorLogger.FIELDS[2:]])

        # summary.txt
        sum_path = os.path.join(s["dir"], "summary.txt")
        with open(sum_path, "w", encoding="utf-8") as f:
            f.write("%s session summary\n" % APP_NAME)
            f.write("=" * 34 + "\n")
            order = ["session", "game", "pid", "duration_s", "frames",
                     "avg_fps", "median_fps", "fps_1pct_low", "fps_01pct_low",
                     "ft_p99_ms", "ft_p999_ms", "ft_max_ms", "worst_1s_fps",
                     "worst_10s_avg_fps", "spikes_gt50ms",
                     "spikes_gt50ms_per_min", "spikes_gt100ms",
                     "cpu_temp_avg_c", "cpu_temp_max_c", "cpu_clock_max_mhz",
                     "cpu_load_avg_pct", "cpu_power_avg_w", "cpu_power_max_w",
                     "gpu_temp_avg_c", "gpu_temp_max_c", "gpu_load_avg_pct",
                     "gpu_power_avg_w", "gpu_power_max_w",
                     "gpu_clock_min_under_load_mhz", "gpu_limited_secs",
                     "ram_used_max_gb", "whea_events"]
            for k in order:
                f.write("%-30s: %s\n" % (k, summary.get(k)))
            f.write("notes: %s\n" % "; ".join(notes) if notes else "notes: -\n")
            f.write("\n=== JSON ===\n")
            f.write(json.dumps(summary, indent=2))

        # gzip raw presentmon csv
        raw = os.path.join(s["dir"], "presentmon_raw.csv")
        try:
            if os.path.exists(raw):
                with open(raw, "rb") as fin, gzip.open(raw + ".gz", "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                os.remove(raw)
        except Exception:
            log.exception("gzip raw failed")

        # zip everything
        zip_path = os.path.join(LOG_DIR, "session_%s.zip" % s["stamp"])
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for fn in os.listdir(s["dir"]):
                z.write(os.path.join(s["dir"], fn), arcname=fn)
        
        try:
            shutil.rmtree(s["dir"])
        except Exception as e:
            log.warning("Could not remove session dir: %s", e)
            
        return zip_path

    # ---- exit / run

    def on_exit(self, icon=None, item=None):
        def worker():
            try:
                with self.lock:
                    grabbed = not self.busy
                    if grabbed:
                        self.busy = True
                if grabbed and self.recording:
                    try:
                        self._stop()
                    except Exception:
                        log.exception("stop-on-exit failed")
            finally:
                try:
                    if self.gpu:
                        self.gpu.close()
                    if self.cpu:
                        self.cpu.close()
                except Exception:
                    pass
                try:
                    self.icon.stop()
                except Exception:
                    pass
                os._exit(0)
        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        import pystray
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: ("Stop & save log" if self.recording
                              else "Start logging"),
                self.on_toggle, default=True),
            pystray.MenuItem("Open logs folder",
                             lambda icon, item: os.startfile(LOG_DIR)),
            pystray.MenuItem("Exit", self.on_exit),
        )
        self.icon = pystray.Icon(APP_NAME, self.make_image(False),
                                 APP_NAME + " - idle", menu)
        if self.init_notes:
            msg = "; ".join(self.init_notes)

            def delayed():
                time.sleep(2)
                self.notify(msg)
            threading.Thread(target=delayed, daemon=True).start()
        self.icon.run()


def main():
    if sys.platform != "win32":
        print("GameTuneLogger runs on Windows only.")
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    main.mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\GameTuneLoggerMutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return
    if not is_admin():
        relaunch_as_admin()
        return
    App().run()


if __name__ == "__main__":
    main()
