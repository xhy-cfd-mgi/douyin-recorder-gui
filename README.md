# 抖音直播自动录屏工具 (Douyin Live Recorder)

[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://www.python.org/downloads/)
[![Python](https://img.shields.io/badge/python-3.9%2B-green)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

一个基于 Python + tkinter 的 Windows GUI 工具，自动检测抖音直播间开播状态并录制视频。支持多直播间监控、自动分段、后台运行。

A Windows GUI tool for automatically detecting and recording Douyin (TikTok China) live streams. Supports multiple streamers, auto-segmentation, and background operation.

## 功能 Features

- **GUI 管理**: 增删改查直播间，无需手动编辑配置文件
- **自动检测**: 定时轮询，开播自动录制
- **智能分段**: 每 N 分钟自动分片，单个文件不过大
- **多直播间**: 同时监控多个主播，独立录制互不干扰
- **状态指示灯**: 绿色（录制中）/ 灰色（离线）/ 红色（错误）
- **内置 ffmpeg**: 无需手动安装，开箱即用

## 快速开始 Quick Start

### 1. 安装 Python

下载安装 Python 3.9+，安装时勾选 **"Add Python to PATH"**。

Download and install Python 3.9+, check **"Add Python to PATH"** during installation.

https://www.python.org/downloads/

### 2. 运行 Run

解压后双击 `启动.bat`，首次运行会自动安装依赖。

Double-click `启动.bat` after extracting. Dependencies are auto-installed on first run.

### 3. 添加直播间 Add Streamers

点击「添加直播间」，输入主播名称和直播间链接（如 `https://live.douyin.com/xxxxx`），保存后自动检测开播状态。

Click "Add Streamer", enter the name and Douyin live URL (e.g. `https://live.douyin.com/xxxxx`). Status is automatically checked after saving.

## 使用说明 Usage

| 操作 | 方式 |
|------|------|
| 添加 Add | 点击「添加直播间」按钮 |
| 编辑 Edit | 双击行 / 右键 → 编辑 |
| 删除 Delete | 右键 → 删除 / 选中后按 Delete |
| 刷新状态 Refresh | 单击行 / 右键 → 立即刷新状态 |
| 手动触发 Manually Start | 点击「全部开始」 |
| 停止录制 Stop | 右键 → 停止录制 / 「全部停止」 |
| 打开录制目录 Open Dir | 右键 → 打开录制目录 / 双击录制中的行 |

## 配置文件 Config

`douyin_config.json`:

```json
{
  "check_interval": 300,
  "segment_duration": 7200,
  "output_dir": "recordings",
  "log_file": "douyin_recorder.log",
  "streamers": []
}
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `check_interval` | 300 | 检查间隔（秒） |
| `segment_duration` | 7200 | 单段最长录制时间（秒），超时自动分段 |
| `output_dir` | `recordings` | 录制文件输出目录 |
| `streamers` | `[]` | 直播间列表（也可通过 GUI 管理） |

## 输出文件 Output

```
recordings/
└── 主播名/
    ├── 主播名_20260509_203000_seg001.mp4
    ├── 主播名_20260509_222000_seg002.mp4
    └── ...
```

## 依赖 Dependencies

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| Python 3.9+ | 运行环境 | python.org |
| streamlink | 直播流抓取 | 启动脚本自动安装 |
| ffmpeg | TS → MP4 转换 | 已在 zip 包内置 |

## 常见问题 FAQ

**Q: 双击 bat 一闪而过？**
A: 确认已安装 Python 并勾选了 "Add Python to PATH"。右键编辑 `启动.bat`，在最后一行前加 `pause` 查看报错。

**Q: 状态显示未开播，但主播确实在播？**
A: 单击该行可立即刷新状态。也可能需要更新 streamlink：运行 `setup.bat`。

**Q: 录制文件在哪？**
A: 右键直播间 → 打开录制目录，或在 `recordings/主播名/` 下。

**Q: 如何同时录制多个主播？**
A: 添加多个直播间即可，每个主播独立录制到各自的子目录。

## License

MIT
