#!/usr/bin/env python3
"""
抖音直播自动录屏工具 — Windows GUI 版本
==========================================
- tkinter 界面，管理多个直播间（增删改查）
- 自动检测开播并录制
- 每 N 分钟截断分片，remux 为 MP4

用法:
  python3 douyin_recorder_gui.py
"""

import json
import os
import sys
import time
import logging
import threading
import subprocess
from datetime import datetime
from pathlib import Path

# 确保 PyInstaller 打包时包含 streamlink
try:
    import streamlink  # noqa: F401
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent

# PyInstaller 打包后数据文件存到 exe 所在目录（便携式）
_RUNNING_AS_EXE = getattr(sys, "frozen", False)
if _RUNNING_AS_EXE:
    DATA_DIR = Path(sys.executable).parent
else:
    DATA_DIR = SCRIPT_DIR

CONFIG_PATH = DATA_DIR / "douyin_config.json"
STATE_PATH = DATA_DIR / "douyin_state.json"
PID_FILE = DATA_DIR / "douyin_recorder.pid"

DEFAULT_CONFIG = {
    "check_interval": 300,
    "segment_duration": 7200,
    "output_dir": "recordings",
    "log_file": "douyin_recorder.log",
    "streamers": [],
}

STATUS_IDLE = "idle"
STATUS_RECORDING = "recording"
STATUS_ERROR = "error"

logger = logging.getLogger("douyin_recorder_gui")
LOG_TRIM_LINES = 1000


class GuiLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        self.callback(self.format(record))


def setup_logging(log_path, gui_callback):
    logging.addLevelName(25, "IMPORTANT")
    log_path = Path(log_path)
    if not log_path.is_absolute():
        log_path = DATA_DIR / log_path
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    gh = GuiLogHandler(gui_callback)
    logger.addHandler(fh)
    logger.addHandler(gh)
    logger.setLevel(logging.DEBUG)


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                               encoding="utf-8-sig")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    cfg["output_dir"] = Path(cfg["output_dir"])
    if not cfg["output_dir"].is_absolute():
        cfg["output_dir"] = DATA_DIR / cfg["output_dir"]
    cfg["output_dir"].mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(cfg):
    """保存配置（含直播间列表）到 douyin_config.json"""
    out = {
        "check_interval": cfg["check_interval"],
        "segment_duration": cfg["segment_duration"],
        "output_dir": str(cfg["output_dir"]),
        "log_file": cfg["log_file"],
        "streamers": [{"name": s["name"], "url": s["url"]} for s in cfg["streamers"]],
    }
    CONFIG_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            logger.warning("状态文件损坏，重置")
    return {}


def save_state(state):
    clean = {}
    for name, s in state.items():
        clean[name] = {k: v for k, v in s.items() if not k.startswith("_")}
    STATE_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                          encoding="utf-8-sig")


def write_pid():
    PID_FILE.write_text(str(os.getpid()))


def remove_pid():
    try:
        PID_FILE.unlink(missing_ok=True)
    except TypeError:
        if PID_FILE.exists():
            PID_FILE.unlink()


WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class _StreamRecorder(threading.Thread):
    """后台线程：使用 streamlink Python API 录制直播流到文件"""

    def __init__(self, url, out_path, log_path):
        super().__init__(daemon=True)
        self.url = url
        self.out_path = out_path
        self.log_path = log_path
        self._stop_event = threading.Event()
        self._error = None

    def stop(self, timeout=10):
        self._stop_event.set()
        if self.is_alive():
            self.join(timeout=timeout)

    def run(self):
        import streamlink
        try:
            session = streamlink.Streamlink()
            session.set_option("http-no-ssl-verify", True)
            session.set_option("stream-segment-attempts", 5)
            session.set_option("stream-segment-timeout", 30.0)
            session.set_option("stream-timeout", 60.0)
            streams = session.streams(self.url)
            if not streams:
                self._error = "no streams available"
                return
            stream = streams.get("best")
            if not stream:
                self._error = "no best stream"
                return
            fd = stream.open()
            with open(self.out_path, "wb") as out_fd:
                while not self._stop_event.is_set():
                    data = fd.read(1024 * 1024)  # 1MB chunks
                    if not data:
                        break
                    out_fd.write(data)
            fd.close()
        except Exception as e:
            self._error = str(e)


def _find_exe(name):
    """查找可执行文件：优先 venv，其次 PATH，再查常见安装路径"""
    exe_name = name + ".exe" if sys.platform == "win32" else name
    import shutil

    candidates = []

    # 1. venv 目录
    venv_bin = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    candidates.append(venv_bin / exe_name)

    # 2. PATH
    found = shutil.which(exe_name)
    if found:
        return found

    # 3. PyInstaller 打包后的 _MEIPASS 目录
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "ffmpeg" / "bin" / exe_name
        if candidate.exists():
            return str(candidate)

    # 4. Windows 常见 ffmpeg 安装路径
    if sys.platform == "win32" and name == "ffmpeg":
        for base in [
            SCRIPT_DIR / "ffmpeg" / "bin",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "ffmpeg" / "bin",
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "ffmpeg" / "bin",
            Path(os.environ.get("LOCALAPPDATA", "")) / "ffmpeg" / "bin",
            Path("C:\\ffmpeg\\bin"),
        ]:
            try:
                if (base / exe_name).exists():
                    return str(base / exe_name)
            except Exception:
                pass

    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass

    return None  # 未找到


def _stop_recorder(recorder, timeout=10):
    if recorder is None:
        return
    if isinstance(recorder, subprocess.Popen):
        if recorder.poll() is not None:
            return
        recorder.terminate()
        try:
            recorder.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            recorder.kill()
            recorder.wait()
    elif isinstance(recorder, _StreamRecorder):
        recorder.stop(timeout=timeout)


def is_live(name, url):
    try:
        import streamlink
        session = streamlink.Streamlink()
        session.set_option("http-no-ssl-verify", True)
        streams = session.streams(url)
        return bool(streams)
    except Exception as e:
        logger.warning(f"[{name}] 检查直播状态失败: {e}")
        return False


def start_recording(cfg, name, url, segment):
    out_path = get_output_path(cfg, name, segment)
    log_path = cfg["output_dir"] / f"{name}_streamlink.log"
    recorder = _StreamRecorder(url, out_path, log_path)
    recorder.start()
    logger.log(25, f"[{name}] 开始录制 segment {segment} → {out_path.name}")
    return recorder, out_path


def get_output_path(cfg, name, segment):
    name_dir = cfg["output_dir"] / name
    name_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return name_dir / f"{name}_{ts}_seg{segment:03d}.ts"


def post_process(out_path):
    if not out_path.exists():
        return
    ffmpeg = _find_exe("ffmpeg")
    if not ffmpeg:
        logger.warning(f"[跳过转码] 未找到 ffmpeg，保留原始文件: {out_path.name}")
        logger.warning("安装 ffmpeg: winget install ffmpeg  或  https://ffmpeg.org/download.html")
        return
    mp4_path = out_path.with_suffix(".mp4")
    if mp4_path.exists():
        mp4_path = out_path.parent / f"{out_path.stem}_dup.mp4"
    try:
        subprocess.run(
            [ffmpeg, "-i", str(out_path), "-c", "copy", "-y", str(mp4_path)],
            capture_output=True, check=True, timeout=300,
            creationflags=WINDOW_FLAGS,
        )
        size = mp4_path.stat().st_size
        logger.log(25, f"[录制完成] {mp4_path.name} ({size / 1024 / 1024:.1f} MB)")
        try:
            out_path.unlink(missing_ok=True)
        except TypeError:
            if out_path.exists():
                out_path.unlink()
    except subprocess.CalledProcessError as e:
        logger.error(f"[后处理失败] {out_path.name}: {e.stderr.decode(errors='replace')[:200]}")
        logger.warning(f"原始文件已保留: {out_path.name}")


try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False


def resolve_streamer_name(url):
    """通过平台 API 解析主播名，失败返回 None"""
    import urllib.request, re, ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    def fetch(api_url, referer=None):
        h = dict(headers)
        if referer:
            h["Referer"] = referer
        req = urllib.request.Request(api_url, headers=h)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return json.loads(resp.read())

    try:
        # 抖音 Douyin — 页面内嵌 JSON (同 streamlink 插件方式，无 geo-restriction)
        m = re.search(r"live\.douyin\.com/(\d+)", url)
        if m:
            req = urllib.request.Request(url, headers={**headers, "Referer": "https://live.douyin.com/"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # 匹配 self.__pace_f.push([0,"json:..."]) 模式
            matches = re.findall(
                r'self\.__pace_f\.push\(\[\d+,("\w+:(?:.(?!self\.__pace_f))*?")]\)',
                html, re.DOTALL)
            for m_raw in matches:
                try:
                    # 去掉前缀如 "json:" 或 "state:"
                    decoded = json.loads(m_raw)
                    inner = re.sub(r'^\w+:', '', decoded)
                    state = json.loads(inner)
                    # 遍历数组找包含 state 的字典
                    for item in state:
                        if isinstance(item, dict) and "state" in item:
                            rs = item["state"].get("roomStore", {})
                            room = rs.get("roomInfo", {}).get("room")
                            anchor = rs.get("roomInfo", {}).get("anchor")
                            if anchor:
                                if isinstance(anchor, dict):
                                    return anchor.get("nickname", "")
                                return anchor
                            if room and len(room) > 2:
                                return room[2]  # title fallback
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue

        # B站 Bilibili — 两步：room info → uid → user info → uname
        m = re.search(r"(?:live|www)\.bilibili\.com/(\d+)", url)
        if m:
            data = fetch(f"https://api.live.bilibili.com/room/v1/Room/get_info?id={m.group(1)}",
                         referer="https://live.bilibili.com/")
            uid = data.get("data", {}).get("uid", 0)
            if uid:
                udata = fetch(f"https://api.live.bilibili.com/live_user/v1/Master/info?uid={uid}",
                              referer="https://live.bilibili.com/")
                uname = udata.get("data", {}).get("info", {}).get("uname", "")
                if uname:
                    return uname
            # fallback: 用直播间标题
            title = data.get("data", {}).get("title", "")
            if title:
                return title

        # 虎牙 Huya — 页面标题提取
        m = re.search(r"huya\.com/(\w+)", url)
        if m:
            req = urllib.request.Request(url, headers={**headers, "Referer": "https://www.huya.com/"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            tag = re.search(r'<title>([^<]+)</title>', html)
            if tag:
                title = tag.group(1).strip()
                for sep in [" - ", "_"]:
                    if sep in title:
                        return title.split(sep)[0]
                return title

    except Exception:
        pass
    return None


class StreamerDialog(tk.Toplevel):
    """添加 / 编辑直播间的弹窗"""

    def __init__(self, parent, title, initial_name="", initial_url=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x190")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.result = None

        ttk.Label(self, text="主播名:").grid(row=0, column=0, padx=10, pady=(10, 5), sticky=tk.W)
        self.name_entry = ttk.Entry(self, width=38)
        self.name_entry.insert(0, initial_name)
        self.name_entry.grid(row=0, column=1, padx=10, pady=(10, 5))

        ttk.Label(self, text="直播间 URL:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        url_frame = ttk.Frame(self)
        url_frame.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        self.url_entry = ttk.Entry(url_frame, width=28)
        self.url_entry.insert(0, initial_url)
        self.url_entry.pack(side=tk.LEFT)
        ttk.Button(url_frame, text="解析", width=6, command=self._on_resolve).pack(side=tk.LEFT, padx=(4, 0))
        self._resolve_btn = url_frame.winfo_children()[-1]

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="保存", command=self._on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.name_entry.focus_set()
        self.name_entry.selection_range(0, tk.END)

    def _on_resolve(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        self._resolve_btn.config(text="...", state=tk.DISABLED)
        self.update()

        def _do():
            try:
                name = resolve_streamer_name(url)
            except Exception as e:
                name = None
            self.after(0, lambda n=name: self._on_resolve_done(n))

        threading.Thread(target=_do, daemon=True).start()

    def _on_resolve_done(self, name):
        self._resolve_btn.config(text="解析", state=tk.NORMAL)
        if name:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)
        else:
            messagebox.showwarning("解析失败", "无法获取主播名，请手动输入", parent=self)

    def _on_save(self):
        name = self.name_entry.get().strip()
        url = self.url_entry.get().strip()
        if not name or not url:
            messagebox.showwarning("输入不完整", "主播名和 URL 不能为空", parent=self)
            return
        self.result = (name, url)
        self.destroy()


class RecorderApp:
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        self.state = {}
        self.poll_job = None
        self.ui_job = None
        self._shutting_down = False
        self._dirty = True

        self._load_initial_state()
        self._build_ui()
        self._start_polling()
        self._start_ui_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_initial_state(self):
        self.state = load_state()
        for info in self.state.values():
            info["_proc"] = None
            info["_out_path"] = None

    def _build_ui(self):
        self.root.title("抖音直播自动录屏")
        self.root.geometry("900x620")
        self.root.minsize(700, 450)

        topbar = ttk.Frame(self.root, padding="5")
        topbar.pack(fill=tk.X)
        ttk.Button(topbar, text="添加直播间", command=self._add_streamer).pack(side=tk.LEFT, padx=2)
        ttk.Button(topbar, text="全部开始", command=self._start_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(topbar, text="全部停止", command=self._stop_all).pack(side=tk.LEFT, padx=2)
        ttk.Separator(topbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(topbar, text="检查间隔(s):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.cfg["check_interval"]))
        ttk.Entry(topbar, textvariable=self.interval_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(topbar, text="分段时长(s):").pack(side=tk.LEFT, padx=(8, 0))
        self.segment_var = tk.StringVar(value=str(self.cfg["segment_duration"]))
        ttk.Entry(topbar, textvariable=self.segment_var, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(topbar, text="应用", command=self._apply_settings).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.LabelFrame(self.root, text="直播间列表", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        columns = ("name", "status", "segment", "elapsed", "file")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="browse", height=10)
        self.tree.heading("name", text="主播", anchor=tk.W)
        self.tree.heading("status", text="状态", anchor=tk.W)
        self.tree.heading("segment", text="分段", anchor=tk.CENTER)
        self.tree.heading("elapsed", text="已录时长", anchor=tk.W)
        self.tree.heading("file", text="当前文件", anchor=tk.W)
        self.tree.column("name", width=130)
        self.tree.column("status", width=100)
        self.tree.column("segment", width=50, anchor=tk.CENTER)
        self.tree.column("elapsed", width=110)
        self.tree.column("file", width=250)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_single_click)
        self.tree.bind("<Delete>", lambda e: self._delete_streamer())

        # 行颜色标签: green=录制中, yellow=等待/检测中, red=错误/离线
        self.tree.tag_configure("recording", foreground="#006600")
        self.tree.tag_configure("offline", foreground="#999999")
        self.tree.tag_configure("error", foreground="#cc0000")

        self.tree_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_menu.add_command(label="立即刷新状态", command=self._refresh_selected)
        self.tree_menu.add_command(label="编辑...", command=self._edit_streamer)
        self.tree_menu.add_command(label="停止录制", command=self._stop_selected)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="删除直播间", command=self._delete_streamer)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="打开录制目录", command=self._open_recording_dir)
        self.tree.bind("<Button-2>", self._on_right_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED,
                                font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                      command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        statusbar = ttk.Frame(self.root, padding="2")
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(statusbar, text="就绪")
        self.status_label.pack(side=tk.LEFT)

        self._rebuild_tree()

    def _log_to_gui(self, msg):
        def _append():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > LOG_TRIM_LINES:
                self.log_text.delete("1.0", f"{line_count - LOG_TRIM_LINES + 200}.0")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        if self.root:
            self.root.after(0, _append)

    def _rebuild_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.cfg["streamers"]:
            self.tree.insert("", tk.END, iid=s["name"], tags=("offline",),
                             values=(s["name"], "等待检测", "-", "-", "-"))

    def _start_ui_refresh(self):
        self._ui_refresh()
        self.ui_job = self.root.after(1000, self._start_ui_refresh)

    def _ui_refresh(self):
        now = time.time()
        recording_count = 0

        for s in self.cfg["streamers"]:
            name = s["name"]
            info = self.state.get(name)
            if not info:
                continue
            status = info.get("status", STATUS_IDLE)

            if status == STATUS_RECORDING:
                start_time = info.get("start_time", 0)
                if start_time:
                    elapsed_sec = int(now - start_time)
                    elapsed_str = f"{elapsed_sec // 60}分{elapsed_sec % 60}秒"
                else:
                    elapsed_str = "启动中..."
                recording_count += 1
                out_path = info.get("_out_path")
                file_name = out_path.name if out_path else "-"
                segment = info.get("segment", 0)
                self.tree.item(name, tags=("recording",),
                               values=(name, "● 录制中", segment, elapsed_str, file_name))
                continue

            # 非录制状态仅在脏时更新
            if not self._dirty:
                continue

            elapsed_str = "-"
            status_display = {
                STATUS_IDLE: "○ 未开播",
                STATUS_ERROR: "✕ 错误",
            }.get(status, status)
            out_path = info.get("_out_path")
            file_name = out_path.name if out_path else "-"
            segment = info.get("segment", 0)
            tag = "error" if status == STATUS_ERROR else "offline"
            self.tree.item(name, tags=(tag,),
                           values=(name, status_display, segment, elapsed_str, file_name))

        self._dirty = False

        total = len(self.cfg["streamers"])
        self.status_label.config(
            text=f"共 {total} 个直播间 | 录制中: {recording_count} | "
                 f"检查间隔: {self.cfg['check_interval']}s"
        )

    def _start_polling(self):
        self.poll_job = self.root.after(1000, self._poll_loop)

    def _poll_loop(self):
        if self._shutting_down:
            return
        for s in self.cfg["streamers"]:
            try:
                self._handle_streamer(s["name"], s["url"])
            except Exception as e:
                logger.error(f"[{s['name']}] 检查出错: {e}")
        save_state(self.state)
        self.poll_job = self.root.after(self.cfg["check_interval"] * 1000, self._poll_loop)

    def _handle_streamer(self, name, url):
        now = time.time()
        info = self.state.setdefault(name, {
            "status": STATUS_IDLE, "pid": None, "start_time": 0,
            "segment": 0, "next_check": 0, "error_count": 0,
            "_proc": None, "_out_path": None,
        })
        prev_status = info["status"]
        prev_segment = info.get("segment", 0)

        if info["status"] == STATUS_RECORDING:
            rec = info["_proc"]
            if rec and rec.is_alive():
                elapsed = now - info["start_time"]
                if elapsed >= self.cfg["segment_duration"]:
                    logger.log(25, f"[{name}] segment {info['segment']} 已达 "
                                     f"{int(elapsed // 60)} 分钟，截断")
                    _stop_recorder(rec)
                    post_process(info["_out_path"])
                    info["segment"] += 1
                    info["start_time"] = now
                    rec2, path2 = start_recording(self.cfg, name, url, info["segment"])
                    if rec2 is None:
                        info["status"] = STATUS_IDLE
                        info["next_check"] = now + self.cfg["check_interval"]
                    else:
                        info["_proc"] = rec2
                        info["_out_path"] = path2
                    self._dirty = True
            else:
                err = getattr(rec, "_error", None) if rec else None
                if info["_out_path"]:
                    logger.info(f"[{name}] 录制线程结束"
                                + (f" (错误: {err})" if err else ""))
                    post_process(info["_out_path"])
                info["status"] = STATUS_IDLE
                info["start_time"] = 0
                info["_proc"] = None
                info["_out_path"] = None
                info["next_check"] = now + self.cfg["check_interval"]
                info["error_count"] = 0
                self._dirty = True
            return

        if now < info["next_check"]:
            return

        live = is_live(name, url)
        if not live:
            info["status"] = STATUS_IDLE
            info["next_check"] = now + self.cfg["check_interval"]
            info["error_count"] = 0
            if prev_status != info["status"] or prev_segment != info["segment"]:
                self._dirty = True
            return

        logger.log(25, f"[{name}] 检测到开播!")
        info["segment"] += 1
        info["start_time"] = time.time()
        info["status"] = STATUS_RECORDING
        info["error_count"] = 0
        proc, out_path = start_recording(self.cfg, name, url, info["segment"])
        if proc is None:
            info["status"] = STATUS_IDLE
            info["next_check"] = now + self.cfg["check_interval"]
            self._dirty = True
            return
        info["_proc"] = proc
        info["_out_path"] = out_path
        self._dirty = True

    # ── 直播间增删改 ─────────────────────────────────────────────────────

    def _add_streamer(self):
        dlg = StreamerDialog(self.root, "添加直播间")
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        name, url = dlg.result
        if any(s["name"] == name for s in self.cfg["streamers"]):
            messagebox.showwarning("重复", f"主播 '{name}' 已存在")
            return
        self.cfg["streamers"].append({"name": name, "url": url})
        save_config(self.cfg)
        self.tree.insert("", tk.END, iid=name, tags=("offline",),
                         values=(name, "检测中...", "-", "-", "-"))
        self._dirty = True
        logger.info(f"已添加直播间: {name}")
        # 立即检测
        self.root.after(200, lambda: self._check_one_streamer(name))

    def _edit_streamer(self):
        sel = self.tree.selection()
        if not sel:
            return
        old_name = sel[0]
        entry = next((s for s in self.cfg["streamers"] if s["name"] == old_name), None)
        if not entry:
            return
        info = self.state.get(old_name, {})
        if info.get("status") == STATUS_RECORDING:
            messagebox.showwarning("录制中", "录制中无法编辑，请先停止")
            return

        dlg = StreamerDialog(self.root, "编辑直播间", entry["name"], entry["url"])
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        new_name, new_url = dlg.result

        if new_name != old_name and any(s["name"] == new_name for s in self.cfg["streamers"]):
            messagebox.showwarning("重复", f"主播 '{new_name}' 已存在")
            return

        entry["name"] = new_name
        entry["url"] = new_url
        save_config(self.cfg)

        # 更新 UI：改 iid 的话需要重建
        if new_name != old_name:
            self.tree.delete(old_name)
            self.tree.insert("", tk.END, iid=new_name, tags=("offline",),
                             values=(new_name, "等待检测", "-", "-", "-"))
            info = self.state.pop(old_name, None)
            if info:
                self.state[new_name] = info
                save_state(self.state)
        self._dirty = True
        logger.info(f"已更新直播间: {new_name}")
        # 编辑后立即刷新
        self.root.after(200, lambda: self._check_one_streamer(new_name))

    def _delete_streamer(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        info = self.state.get(name, {})
        if info.get("status") == STATUS_RECORDING:
            messagebox.showwarning("录制中", f"'{name}' 正在录制，请先停止")
            return
        if messagebox.askyesno("确认删除", f"确定要删除直播间 '{name}' 吗？"):
            self.cfg["streamers"] = [s for s in self.cfg["streamers"] if s["name"] != name]
            save_config(self.cfg)
            self.tree.delete(name)
            self.state.pop(name, None)
            save_state(self.state)
            self._dirty = True
            logger.info(f"已删除直播间: {name}")

    # ── 控制操作 ─────────────────────────────────────────────────────────

    def _start_all(self):
        for s in self.cfg["streamers"]:
            info = self.state.get(s["name"])
            if info and info.get("status") != STATUS_RECORDING:
                info["next_check"] = 0
                self.state[s["name"]] = info
        if self.poll_job:
            self.root.after_cancel(self.poll_job)
        self._dirty = True
        self.poll_job = self.root.after(500, self._poll_loop)
        logger.info("手动触发全部检查")

    def _stop_all(self):
        for s in self.cfg["streamers"]:
            self._stop_streamer(s["name"])
        logger.info("已停止所有录制")

    def _stop_selected(self):
        sel = self.tree.selection()
        if sel:
            self._stop_streamer(sel[0])

    def _stop_streamer(self, name):
        info = self.state.get(name)
        if not info:
            return
        proc = info.get("_proc")
        out_path = info.get("_out_path")
        _stop_recorder(proc)
        if out_path:
            logger.info(f"[{name}] 手动停止录制")
            post_process(out_path)
        info.update({"status": STATUS_IDLE, "pid": None, "start_time": 0,
                     "_proc": None, "_out_path": None,
                     "next_check": time.time() + self.cfg["check_interval"]})
        self.state[name] = info
        self._dirty = True
        save_state(self.state)

    def _apply_settings(self):
        try:
            interval = int(self.interval_var.get())
            segment = int(self.segment_var.get())
            if interval < 30 or segment < 60:
                raise ValueError
        except ValueError:
            messagebox.showwarning("无效设置", "检查间隔 >= 30s, 分段时长 >= 60s")
            return
        self.cfg["check_interval"] = interval
        self.cfg["segment_duration"] = segment
        save_config(self.cfg)
        logger.info(f"设置已更新: 检查间隔={interval}s, 分段={segment // 60}min")

    def _install_ffmpeg(self):
        """自动下载安装 ffmpeg 到当前目录"""
        ffmpeg = _find_exe("ffmpeg")
        if ffmpeg:
            messagebox.showinfo("ffmpeg", f"ffmpeg 已安装:\n{ffmpeg}")
            return
        if sys.platform != "win32":
            messagebox.showinfo("提示", "请用系统包管理器安装 ffmpeg:\n  sudo apt install ffmpeg")
            return

        if not messagebox.askyesno("安装 ffmpeg",
                                   "将自动下载 ffmpeg (~80MB) 到当前目录。\n"
                                   "下载过程约需 1-3 分钟，继续？"):
            return

        import urllib.request, zipfile, tempfile
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        dest = SCRIPT_DIR / "ffmpeg"
        logger.info("正在下载 ffmpeg ...")
        self.status_label.config(text="正在下载 ffmpeg (~80MB)...")

        def _download():
            try:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                urllib.request.urlretrieve(url, str(tmp_path),
                                           reporthook=lambda c, b, t:
                                           self.root.after(0, self.status_label.config,
                                                           {"text": f"下载 ffmpeg: {c * b / t:.0%}"})
                                           if t > 0 else None)
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    # ffmpeg essentials zip 内文件在 ffmpeg-x.x.x-essentials/bin/ 下
                    bin_members = [m for m in zf.namelist()
                                   if m.endswith((".exe", ".dll")) and "/bin/" in m]
                    for m in bin_members:
                        zf.extract(m, dest)
                        # 扁平化到 ffmpeg/bin/
                        extracted = dest / m
                        target = dest / "bin" / Path(m).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if extracted != target:
                            import shutil
                            shutil.move(str(extracted), str(target))
                # 清理空目录和临时文件
                tmp_path.unlink(missing_ok=True)
                for d in sorted(dest.rglob("*"), reverse=True):
                    if d.is_dir() and not any(d.iterdir()):
                        d.rmdir()

                ffmpeg_exe = dest / "bin" / "ffmpeg.exe"
                if ffmpeg_exe.exists():
                    logger.log(25, f"ffmpeg 安装完成: {ffmpeg_exe}")
                    self.root.after(0, lambda: messagebox.showinfo("完成",
                                       f"ffmpeg 已安装到:\n{ffmpeg_exe}\n\n请重启程序生效"))
                else:
                    raise FileNotFoundError("解压后未找到 ffmpeg.exe")
            except Exception as e:
                logger.error(f"ffmpeg 下载失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("失败",
                                       f"ffmpeg 自动下载失败:\n{e}\n\n"
                                       "请手动安装: winget install ffmpeg\n"
                                       "或访问 https://ffmpeg.org/download.html"))
            finally:
                self.root.after(0, self.status_label.config, {"text": "就绪"})

        threading.Thread(target=_download, daemon=True).start()

    def _open_recording_dir(self):
        sel = self.tree.selection()
        if not sel:
            return
        d = self.cfg["output_dir"] / sel[0]
        if sys.platform == "win32" and d.exists():
            os.startfile(str(d))

    # ── 事件 ─────────────────────────────────────────────────────────────

    def _on_single_click(self, event):
        """单击：立即刷新该直播间状态"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # 避免点表头触发
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        self._check_one_streamer(item)

    def _on_double_click(self, event):
        """双击：录制中打开目录，否则编辑直播间"""
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        info = self.state.get(name, {})
        if info.get("status") == STATUS_RECORDING:
            d = self.cfg["output_dir"] / name
            if sys.platform == "win32" and d.exists():
                os.startfile(str(d))
        else:
            self._edit_streamer()

    def _refresh_selected(self):
        sel = self.tree.selection()
        if sel:
            self._check_one_streamer(sel[0])

    def _check_one_streamer(self, name):
        """立即检测单个直播间状态（双击/单击/右键刷新触发）"""
        entry = next((s for s in self.cfg["streamers"] if s["name"] == name), None)
        if not entry:
            return
        self.tree.item(name, tags=("offline",),
                       values=(name, "检测中...", "-", "-", "-"))
        live = is_live(name, entry["url"])
        now = time.time()
        info = self.state.setdefault(name, {
            "status": STATUS_IDLE, "pid": None, "start_time": 0,
            "segment": 0, "next_check": 0, "error_count": 0,
            "_proc": None, "_out_path": None,
        })
        if live:
            logger.info(f"[{name}] 手动检测: 开播中")
            if info.get("status") != STATUS_RECORDING:
                info["next_check"] = 0
                self.state[name] = info
                # 立即启动录制（不等下一轮轮询）
                self._handle_streamer(name, entry["url"])
                return
        else:
            logger.info(f"[{name}] 手动检测: 未开播")
            info["status"] = STATUS_IDLE
            info["next_check"] = now + self.cfg["check_interval"]
        self.state[name] = info
        save_state(self.state)
        self._dirty = True

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

    def _on_close(self):
        if any(info.get("status") == STATUS_RECORDING for info in self.state.values()):
            if not messagebox.askyesno("确认退出", "有直播间正在录制中，确定退出并停止所有录制吗？"):
                return
        self._shutting_down = True
        if self.poll_job:
            self.root.after_cancel(self.poll_job)
        if self.ui_job:
            self.root.after_cancel(self.ui_job)
        for name, info in self.state.items():
            _stop_recorder(info.get("_proc"))
            out_path = info.get("_out_path")
            if out_path:
                logger.info(f"[{name}] 退出时停止录制")
                post_process(out_path)
        save_state(self.state)
        remove_pid()
        self.root.destroy()


def main():
    cfg = load_config()
    if not HAS_TK:
        print("错误: 未找到 tkinter。Windows 版 Python 自带 tkinter，请使用官方安装包。")
        sys.exit(1)

    root = tk.Tk()
    app = RecorderApp(root, cfg)
    setup_logging(cfg["log_file"], app._log_to_gui)

    write_pid()
    logger.info("=" * 60)
    logger.info("抖音直播录屏工具 (GUI) 启动")
    logger.info(f"检查间隔: {cfg['check_interval']}s  分段时长: {cfg['segment_duration'] // 60}min")
    logger.info(f"监控主播数: {len(cfg['streamers'])}")
    for s in cfg["streamers"]:
        logger.info(f"  └ {s['name']}: {s['url']}")
    logger.info("=" * 60)

    root.mainloop()


if __name__ == "__main__":
    main()
