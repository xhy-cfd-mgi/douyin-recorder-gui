# 多平台直播自动录屏工具 (Multi-Platform Live Recorder)

[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://www.python.org/downloads/)
[![Python](https://img.shields.io/badge/python-3.9%2B-green)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

基于 Python + tkinter 的 Windows GUI 工具，自动检测直播开播状态并录制视频。支持**抖音、B站、虎牙**等多平台，自动分段存为 MP4。

A Windows GUI tool for automatically detecting and recording live streams from multiple platforms (Douyin, Bilibili, Huya and more). Auto-segmentation to MP4.

## 截图 Screenshot

```
  [添加直播间] [全部开始] [全部停止]

  ---- 直播间列表 ----
  ● 央视网快看    录制中   seg=3   45分30秒
  ○ 主播B        未开播   -       -

  ---- 运行日志 ----
  12:00:01  检测到 央视网快看 开播!
  12:45:31  录制完成 seg003.mp4 (13035.8 MB)

  ---- 状态栏 ----
  共 2 个直播间 | 录制中: 1 | 检查间隔: 300s
```

## 支持的平台 Supported Platforms

| 平台 | 插件 | 已验证 |
|------|------|--------|
| 抖音 Douyin | `douyin` | ✓ |
| B站 Bilibili | `bilibili` | ✓ |
| 虎牙 Huya | `huya` | ✓ |
| Twitch | `twitch` | 支持 |
| YouTube | `youtube` | 支持 |
| 更多 130+ | — | —

## 功能 Features

- **多平台**: 支持抖音、B站、虎牙等 streamlink 内置的 130+ 个平台
- **GUI 管理**: 增删改查直播间，无需手动编辑配置文件
- **自动检测**: 定时轮询，开播自动录制（基于 streamlink Python API）
- **智能分段**: 每 N 分钟自动分片，单个文件不过大
- **多直播间**: 同时监控多个主播，独立录制互不干扰
- **状态指示灯**: ● 绿色（录制中）/ ○ 灰色（离线）/ ✕ 红色（错误）
- **单击刷新**: 单击任意行立即检测该直播间状态
- **内置 ffmpeg**: zip 包内含 ffmpeg.exe，解压即用
- **打包为 EXE**: 运行 `build_exe.bat` 生成独立 .exe，无需 Python 环境

## 快速开始 Quick Start

### 方式一：直接运行（需要 Python）

1. 安装 Python 3.9+，勾选 **"Add Python to PATH"** — https://www.python.org/downloads/
2. 解压后双击 `setup.bat` 安装依赖
3. 双击 `启动.bat` 启动 GUI

### 方式二：打包为 EXE（无需 Python）

1. 在已安装 Python 的电脑上，双击 `build_exe.bat`
2. 等待构建完成，在 `dist/` 目录得到 `DouyinRecorder.exe`
3. 将此 .exe 复制到任意 Windows 电脑，双击即用（无需安装 Python）

## 使用说明 Usage

| 操作 | 方式 |
|------|------|
| 添加 Add | 点击「添加直播间」按钮，保存后自动检测 |
| 编辑 Edit | 双击未在录制中的行 / 右键 → 编辑 |
| 删除 Delete | 右键 → 删除 / 选中后按 Delete |
| 刷新状态 Refresh | **单击行** / 右键 → 立即刷新状态 |
| 全部开始 Start All | 点击「全部开始」 |
| 停止录制 Stop | 右键 → 停止录制 / 「全部停止」 |
| 打开录制目录 Open Dir | 右键 → 打开录制目录 / 双击录制中的行 |

## 配置文件 Config

`douyin_config.json`（也可通过 GUI 管理）:

```json
{
  "check_interval": 300,
  "segment_duration": 7200,
  "output_dir": "recordings",
  "log_file": "douyin_recorder.log",
  "streamers": [
    {"name": "抖音-央视网快看", "url": "https://live.douyin.com/127453393722"},
    {"name": "B站-直播", "url": "https://live.bilibili.com/6"},
    {"name": "虎牙-直播", "url": "https://www.huya.com/lpl"}
  ]
}
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `check_interval` | 300 | 检查间隔（秒） |
| `segment_duration` | 7200 | 单段最长录制时间（秒）= 120 分钟 |
| `output_dir` | `recordings` | 录制文件输出目录 |
| `streamers` | `[]` | 直播间列表 |

## 输出文件 Output

```
recordings/
  └── 主播名/
        ├── 主播名_20260509_203000_seg001.mp4
        ├── 主播名_20260509_222000_seg002.mp4
        └── ...
```

## 技术架构 Architecture

| 组件 | 用途 | 实现方式 |
|------|------|----------|
| streamlink | 直播流检测与下载 | Python API（`streamlink.Streamlink().streams()`） |
| ffmpeg | TS → MP4 转换（remux） | `ffmpeg/bin/ffmpeg.exe`（zip 内置） |
| tkinter | GUI 界面 | Python 标准库 |
| PyInstaller | 打包为独立 EXE | `build_exe.bat` 一键构建 |

录制采用后台线程模型：`_StreamRecorder(threading.Thread)` 直接调用 streamlink Python API 获取直播流并写入文件，通过 `threading.Event` 实现线程安全停止。PyInstaller 打包后无需外部 streamlink 可执行文件。

## 常见问题 FAQ

**Q: 双击 bat 一闪而过？**
A: 确认已安装 Python 并勾选了 "Add Python to PATH"。

**Q: 状态显示未开播，但主播确实在播？**
A: **单击该行**可立即刷新状态。streamlink 检测需要网络，可能超时。

**Q: 打包的 EXE 运行时提示"未找到 ffmpeg"？**
A: 确保 `ffmpeg/bin/ffmpeg.exe` 与 exe 在同一目录下，或使用 zip 包（已内置）。

**Q: 录制文件在哪？**
A: 右键直播间 → 打开录制目录，或在 `recordings/主播名/` 下。

## License

MIT

---

*本项目由 Claude Code + DeepSeek V4 创建 | Built with Claude Code + DeepSeek V4*
