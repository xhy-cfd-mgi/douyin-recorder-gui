# 多平台直播自动录屏工具 (Multi-Platform Live Recorder)

[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://www.python.org/downloads/)
[![Python](https://img.shields.io/badge/python-3.9%2B-green)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/badge/release-v2.1-brightgreen)](https://github.com/xhy-cfd-mgi/douyin-recorder-gui/releases/tag/v2.1)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

基于 Python + tkinter 的 Windows GUI 工具，自动检测直播开播状态并录制视频。支持**抖音、B站、虎牙**等多平台，自动分段存为 MP4。

A Windows GUI tool for automatically detecting and recording live streams from multiple platforms (Douyin, Bilibili, Huya and more). Auto-segmentation to MP4.

## 截图 Screenshot

```
  [添加直播间] [全部开始] [全部停止]

  ---- 直播间列表 ----
  ● 央视网快看    录制中   seg=3   45分30秒
  ○ 甲乙丙丁dota2  未开播   -       -

  ---- 运行日志 ----
  12:00:01  检测到 央视网快看 开播!
  12:45:31  录制完成 seg003.mp4 (13035.8 MB)

  ---- 状态栏 ----
  共 2 个直播间 | 录制中: 1 | 检查间隔: 300s
```

## 支持的平台 Supported Platforms

| 平台 | 域名 | 插件 | 直播检测 | 录制 | URL 解析 |
|------|------|------|---------|------|---------|
| 抖音 | `live.douyin.com` | `douyin` | ✓ | ✓ | ✓ |
| B站 | `live.bilibili.com` | `bilibili` | ✓ | ✓ | ✓ |
| 虎牙 | `huya.com` | `huya` | ✓ | ✓ | ✓ |
| Twitch / YouTube / 更多 | — | 130+ | 支持 | 支持 | — |

## 功能 Features

- **多平台**: 抖音、B站、虎牙已验证，streamlink 内置 130+ 平台
- **URL 解析**: 粘贴直播链接，点「解析」自动获取主播名（无需手打）
- **GUI 管理**: 增删改查直播间，配置自动保存
- **自动检测**: 定时轮询，开播自动录制
- **智能分段**: 每 N 分钟自动分片（remux 存为 MP4）
- **多直播间**: 同时监控多个主播，独立录制互不干扰
- **状态指示灯**: ● 绿色（录制中）/ ○ 灰色（离线）/ ✕ 红色（错误）
- **单击刷新**: 单击行立即检测，添加后自动检测
- **内置 ffmpeg**: zip 包内含 Windows 版 ffmpeg.exe
- **便携 EXE**: `build_exe.bat` 一键打包独立 .exe，无需 Python

## 快速开始 Quick Start

### 方式一：源码运行（需要 Python 3.9+）

1. 安装 Python，勾选 **"Add Python to PATH"** — https://www.python.org/downloads/
2. 解压后双击 `setup.bat`
3. 双击 `启动.bat`

### 方式二：独立 EXE（无需 Python）

1. 双击 `build_exe.bat`
2. 在 `dist/` 目录得到 `DouyinRecorder.exe`
3. 复制到任意 Windows 电脑，双击即用。所有文件产生在 exe 同目录。

## 使用说明 Usage

| 操作 | 方式 |
|------|------|
| 添加直播间 | 点击「添加直播间」→ 粘贴链接 → 点「**解析**」获取主播名 → 保存 |
| 编辑 | 双击行 / 右键 → 编辑 |
| 删除 | 右键 → 删除 / 选中后 Delete |
| 刷新状态 | **单击行** / 右键 → 立即刷新 |
| 全部开始 | 点击「全部开始」 |
| 停止录制 | 右键 → 停止录制 |
| 打开录制目录 | 右键 → 打开录制目录 |

## URL 解析功能 URL Resolver

| 平台 | 解析方式 | 示例 |
|------|---------|------|
| 抖音 | 页面内嵌 JSON 提取 | `live.douyin.com/563079089093` → `甲乙丙丁dota2` |
| B站 | Room API → uid → User API | `live.bilibili.com/41515` → `youc-` |
| 虎牙 | 页面标题提取 | `huya.com/lpl` → `2026LPL第二赛段` |

## 配置文件 Config

`douyin_config.json`（GUI 自动管理，也可手动编辑）:

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
| `output_dir` | `recordings` | 录制输出目录 |
| `streamers` | `[]` | 直播间列表 |

## 文件结构 Project Structure

```
douyin-recorder-gui/
├── douyin_recorder_gui.py   # 主程序 (~750 行)
├── douyin_config.json       # 配置文件
├── ffmpeg/bin/ffmpeg.exe    # 内置 Windows ffmpeg
├── 启动.bat                 # 一键启动
├── setup.bat                # 环境安装
├── build_exe.bat            # 打包独立 EXE
├── README.md                # 本文件
├── TUTORIAL.md              # 开发踩坑全记录
└── LICENSE                  # MIT
```

## 技术架构 Architecture

- **streamlink Python API**: `streamlink.Streamlink().streams()` 检测 + `stream.open()` 拉流
- **后台录制线程**: `_StreamRecorder(threading.Thread)` 线程安全停止
- **ffmpeg remux**: `-c copy` 无损转 MP4（不重编码）
- **PyInstaller**: `--onefile` 单文件打包，检测 `sys.frozen` 适配路径
- **utf-8-sig**: 配置文件兼容 Windows 记事本的 BOM

## 常见问题 FAQ

**Q: 双击 bat 一闪而过？**
A: 确认已安装 Python 并勾选 "Add Python to PATH"。

**Q: 解析主播名失败？**
A: 抖音需境内网络（页面 JSON 方式）；B站/虎牙无此限制。失败时手动输入即可。

**Q: EXE 运行没有反应？**
A: 检查 `ffmpeg/bin/ffmpeg.exe` 是否在同目录。或使用 zip 包（已内置）。

**Q: 录制文件在哪？**
A: 右键直播间 → 打开录制目录；或 `recordings/主播名/` 下。

## License

MIT

---

*本项目由 Claude Code + DeepSeek V4 创建 | Built with Claude Code + DeepSeek V4*
