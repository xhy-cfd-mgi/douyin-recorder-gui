# 从零到发布：一个 Python GUI 工具的完整踩坑记录

> 本项目由 Claude Code + DeepSeek V4 协作完成  
> GitHub: https://github.com/xhy-cfd-mgi/douyin-recorder-gui

---

## 项目概述

做一个 **抖音直播自动录屏工具**。需求很简单：

1. 输入直播间链接
2. 检测开播，自动录制
3. 分段存为 MP4
4. Windows 上能用 GUI 操作
5. 最好能打包成独立 EXE

技术栈：Python + tkinter + streamlink + ffmpeg + PyInstaller

下面按开发时间线，逐阶段记录遇到的问题和解决方案。

---

## 第一阶段：CLI 原型

### 起步 — 命令行版本

先写了一个能在 Linux 后台跑的 CLI 工具。核心逻辑：

```
定时轮询 → streamlink 检测开播 → subprocess 拉流录制 → ffmpeg 转 MP4
```

这个阶段代码跑通后，放到 Linux 服务器上用 `nohup` 后台运行，成功录制了几场直播。

### 问题1：JSON 注释方案

**现象**：用户想用一个配置文件管理直播间列表，希望能"注释掉"暂时不用的条目。

**尝试**：JSON 标准不支持 `//` 注释，于是写了 `strip_json_comments()` 函数，用 `line.split("//")[0]` 去掉注释。

**埋下的坑**：
- URL 里的 `https://` 也会被 `//` 切掉！
- 注释行清空后，上一行的逗号变成 JSON 不允许的尾随逗号

**最终方案**：
```python
# 1. 只处理行首的 //（避免误伤 https://）
if re.match(r'^\s*//', line):
    line = line.split("//")[0]

# 2. 清除尾随逗号
clean = re.sub(r",(\s*[}\]])", r"\1", clean)
```

**教训**：手写解析器要覆盖边界情况。后来干脆去掉了 JSON 注释文件，改为 GUI 直接管理数据。

---

## 第二阶段：GUI 重构

### 问题2：`logging.Formatter` 参数错误

**现象**：GUI 启动后闪退，报错：
```
ValueError: Invalid format '%H:%M:%S' for '%' style
```

**原因**：
```python
# 错误：把时间格式字符串当成日志格式传入了
logging.Formatter("%H:%M:%S")

# 正确：第一个参数是 fmt（日志消息格式），datefmt 才是时间格式
logging.Formatter(fmt="%(asctime)s %(message)s", datefmt="%H:%M:%S")
```

**教训**：`logging.Formatter` 的第一个位置参数是 `fmt`（控制整条日志的格式），时间格式化要用 `datefmt` 关键字参数。Python 3.13 对此做了严格校验。

### 问题3：Windows 批处理文件编码

**现象**：`.bat` 文件在 Windows 上双击一闪而过，中文乱码。

**根因拆解**：

| 问题 | Linux 写入 | Windows 期望 |
|------|-----------|-------------|
| 换行符 | `\n` (LF) | `\r\n` (CRLF) |
| 中文编码 | UTF-8 | GBK (CP936) |
| Python 转义 | `\b` `\f` 被当成转义符 | 需要字面反斜杠 |

**修复**：
```python
# 用 raw bytes 写入，绕过所有编码和转义问题
data = b'@echo off\r\ncd /d "%~dp0"\r\n...'
with open('build_exe.bat', 'wb') as f:
    f.write(data)
```

**教训**：跨平台开发时，文本文件要考虑目标系统的换行符和默认编码。

### 问题4：TKinter GUI 线程模型

**现象**：录制过程中界面卡死、状态不更新。

**主循环改造**：
```python
# 错误：while True + sleep 阻塞 tkinter 事件循环
while True:
    check_streamers()
    time.sleep(300)

# 正确：root.after() 定时器，不阻塞 GUI
def poll_loop():
    check_streamers()
    root.after(300_000, poll_loop)  # 300秒后再次调度

root.after(1000, poll_loop)
root.mainloop()
```

**已录时长实时更新**：
```python
# 录制中的行每秒刷新，非录制行仅在状态变化时刷新
if status == STATUS_RECORDING:
    elapsed_str = f"{elapsed // 60}分{elapsed % 60}秒"
    tree.item(name, values=(name, "● 录制中", segment, elapsed_str, file))
    continue  # 总是更新
if not self._dirty:
    continue  # 非录制行跳过
```

**教训**：GUI 框架有自己的事件循环，不能用传统的 `sleep` 轮询。

---

## 第三阶段：打包问题

### 问题5：subprocess 调用 streamlink 在 EXE 中无限套娃

**现象**：打包的 EXE 每次检测/录制时弹出一个新的 EXE 窗口。

**根因**：
```python
# PyInstaller 打包后，sys.executable 就是 exe 本身
# 这行代码等价于 "再启动一个自己"
subprocess.run([sys.executable, "-m", "streamlink", url])
```

**修复**：放弃 subprocess，改用 streamlink 的 Python API：
```python
# is_live：直接调用 streamlink 库
import streamlink
session = streamlink.Streamlink()
streams = session.streams(url)
return bool(streams)

# start_recording：后台线程，用 stream.open() 读数据
class _StreamRecorder(threading.Thread):
    def run(self):
        fd = stream.open()
        with open(out_path, "wb") as out:
            while not self._stop_event.is_set():
                data = fd.read(1024 * 1024)
                if not data: break
                out.write(data)
```

**教训**：PyInstaller 打包后没有外部 Python 解释器。`sys.executable` 就是你的程序本身。要调用 Python 模块，用 API 而不是 subprocess。

### 问题6：PyInstaller 没有打包 streamlink 模块

**现象**：EXE 运行后日志报 `No module named 'streamlink'`。

**根因**：
- `build_exe.bat` 用系统 `python` 构建，但 streamlink 装在 `.venv` 里
- PyInstaller 找不到 streamlink，自然不会打包

**修复**：
```batch
:: 构建脚本自动检测并使用 venv
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)
!PY! -m pip install streamlink pyinstaller
!PY! -m PyInstaller --hidden-import streamlink --collect-all streamlink ...
```

同时代码顶部加了显式 import：
```python
try:
    import streamlink  # 告诉 PyInstaller 这是依赖
except ImportError:
    pass
```

**教训**：PyInstaller 靠分析 import 语句来决定打包什么。隐式的 subprocess 调用不会被识别。

### 问题7：EXE 数据目录设计

**现象**：打包的 EXE 把配置和录制文件存到了 `%APPDATA%` 深处的某个目录。

**需求**：用户希望 EXE 完全便携——所有文件都在 exe 所在目录。

**修复**：
```python
_RUNNING_AS_EXE = getattr(sys, "frozen", False)
if _RUNNING_AS_EXE:
    DATA_DIR = Path(sys.executable).parent   # exe 所在目录
else:
    DATA_DIR = SCRIPT_DIR                     # 脚本所在目录
```

**教训**：`sys.frozen` 检测是否为 PyInstaller 打包；`sys._MEIPASS` 是临时解压目录（只读）；`sys.executable` 是 exe 的完整路径。

### 问题8：内置 ffmpeg 的查找优先级

**现象**：EXE 找不到 ffmpeg。

**修复**：构建了多级查找链：
```python
def _find_exe(name):
    # 1. venv 目录
    # 2. PATH
    # 3. PyInstaller _MEIPASS（打包进去的文件）
    # 4. SCRIPT_DIR / "ffmpeg" / "bin"（exe 同目录）
    # 5. 常见 Windows 安装路径
    # 6. 未找到：对于 ffmpeg 保留 .ts 文件不丢；对于 streamlink 报错
```

### 问题9：`_StreamRecorder.stop()` 在未启动线程上崩溃

**现象**：
```
RuntimeError: cannot join thread before it is started
```

**修复**：
```python
def stop(self, timeout=10):
    self._stop_event.set()
    if self.is_alive():          # 加这个判断
        self.join(timeout=timeout)
```

**教训**：线程方法不是幂等的——`join()` 只能在已启动的线程上调用。

---

## 问题汇总表

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | JSON 注释解析失败 | `//` 误伤 URL、尾随逗号 | 正则匹配行首 `//` + 清除尾随逗号 |
| 2 | `logging.Formatter` 报错 | 参数位置错误 | `fmt=` vs `datefmt=` |
| 3 | .bat 中文乱码/闪退 | LF 换行 + UTF-8 vs GBK | CRLF + raw bytes |
| 4 | GUI 界面卡死 | `sleep` 阻塞事件循环 | `root.after()` 定时器 |
| 5 | EXE 无限套娃 | `sys.executable -m` | streamlink Python API |
| 6 | EXE 缺 streamlink | 构建时用的 Python 没有 streamlink | venv 检测 + 构建前安装 |
| 7 | 数据目录不对 | EXE 默认存 APPDATA | `sys.executable.parent` |
| 8 | ffmpeg 找不到 | 查找路径不全 | 多级回退查找链 |
| 9 | 线程 join 崩溃 | 未启动时调用 join | `is_alive()` 守卫 |

---

## 关键代码片段

### 完整的跨平台可执行文件查找

```python
def _find_exe(name):
    exe_name = name + ".exe" if sys.platform == "win32" else name
    import shutil

    # 1. venv
    venv_bin = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    if (venv_bin / exe_name).exists():
        return str(venv_bin / exe_name)

    # 2. PATH
    found = shutil.which(exe_name)
    if found: return found

    # 3. PyInstaller _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "ffmpeg" / "bin" / exe_name
        if p.exists(): return str(p)

    # 4. 本地目录 / 常见路径
    for base in [
        SCRIPT_DIR / "ffmpeg" / "bin",
        Path("C:\\ffmpeg\\bin"),
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin",
    ]:
        if (base / exe_name).exists():
            return str(base / exe_name)

    return None
```

### PyInstaller 构建检测

```python
# 判断运行环境
_RUNNING_AS_EXE = getattr(sys, "frozen", False)   # PyInstaller 打包

if _RUNNING_AS_EXE:
    DATA_DIR = Path(sys.executable).parent          # exe 同目录
else:
    DATA_DIR = Path(__file__).resolve().parent      # 脚本同目录
```

### 后台录制线程

```python
class _StreamRecorder(threading.Thread):
    def __init__(self, url, out_path, log_path):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()

    def stop(self, timeout=10):
        self._stop_event.set()
        if self.is_alive():
            self.join(timeout=timeout)

    def run(self):
        session = streamlink.Streamlink()
        streams = session.streams(self.url)
        stream = streams.get("best")
        fd = stream.open()
        with open(self.out_path, "wb") as out:
            while not self._stop_event.is_set():
                data = fd.read(1024 * 1024)
                if not data: break
                out.write(data)
```

### stdout 重定向到 tkinter

```python
class GuiLogHandler(logging.Handler):
    """将 logging 消息转发到 tkinter Text 控件"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        self.callback(self.format(record))
```

---

## 文件结构

```
douyin-recorder-gui/
├── douyin_recorder_gui.py   # GUI 主程序 (~700 行)
├── douyin_config.json       # 配置文件（含直播间列表）
├── ffmpeg/bin/ffmpeg.exe    # Windows ffmpeg 静态构建
├── 启动.bat                 # 一键启动（自动创建 venv）
├── setup.bat                # 环境安装（pip install）
├── build_exe.bat            # PyInstaller 打包脚本
├── README.md                # 双语文档
├── TUTORIAL.md              # 本文件
└── LICENSE                  # MIT
```

### 核心依赖

- **streamlink**: 直播流检测与下载（调用 Python API，不用 CLI）
- **ffmpeg**: TS→MP4 无损 remux（`-c copy`，不重编码）
- **tkinter**: GUI（Python 标准库，Windows 自带）

---

## 面向初学者的通用建议

1. **跨平台开发**：在 Linux/Mac 写代码但目标 Windows 时，注意换行符(CRLF/LF)、编码(GBK/UTF-8)、路径分隔符(`\`/`/`)
2. **PyInstaller**：`--hidden-import` 显式声明隐式依赖；`--collect-all` 包含模块全部文件；`sys.frozen` 判断运行环境；`sys._MEIPASS` 找打包进去的文件
3. **GUI 事件循环**：永不用 `sleep`；用框架提供的定时器；耗时操作放后台线程
4. **subprocess vs API**：能调库就不要调命令行——打包后的 exe 没有外部解释器
5. **配置文件**：读写用同一个编码；JSON 不支持注释，要么用 JSONC 解析器，要么放到 GUI 里管理
6. **线程安全**：`join()` 前检查 `is_alive()`；用 `threading.Event` 发停止信号；`daemon=True` 让线程随主进程退出
7. **先测试再交付**：写一段测试脚本覆盖核心路径（配置读写、API 调用、线程生命周期），能避免一半的来回改 bug
