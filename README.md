# MediaConverter - 媒体格式转换工具

Windows 环境的一体化媒体转换工具，基于 FFmpeg，支持视频/图片/音频格式互转。

**v3.0 新增图形界面**，拖拽操作、参数预设按钮、批量队列、暗色主题，无需记忆命令行。

## 功能特性

### 视频转换
- 一键转码：MP4、AVI、MKV、MOV、WEBM、WMV、FLV
- 视频转 GIF 动图（自动优化调色板）
- 提取音频为 MP3
- 智能压缩（指定目标文件大小，自动计算码率）
- 视频裁剪（指定起始时间和持续时长）
- GPU 硬件加速（NVIDIA NVENC / AMD AMF / Intel QSV，启动自动检测）

### 图片转换
- 格式互转：JPG、PNG、WEBP、BMP、GIF、TIFF
- 视频提取帧为图片
- 图片合成视频（幻灯片效果）

### GUI 功能
- 拖拽选择文件
- 分辨率/帧率/质量/码率/编码预设 — 预设按钮 + 自定义输入
- 裁剪/压缩 — 勾选启用，不干扰其他参数
- 批量转换 — 拖入多个文件或整个文件夹，设定并发数
- 转换进度实时显示
- 历史记录一键重转
- 暗色主题（Catppuccin 风格）

## 下载使用

### 直接使用
1. 下载 `MediaConverter/` 文件夹
2. 双击 `MediaConverter.exe` 运行
3. 无需安装 FFmpeg，无需配置环境变量

### 从源码运行

```bash
# 克隆项目
git clone https://github.com/Yuyuano/MediaConverter.git
cd MediaConverter

# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 运行 GUI 版
.venv\Scripts\python main.py
```

### 打包成 exe

```bash
# 方式 A：指定本地 FFmpeg 路径（推荐）
set FFMPEG_PATH=C:\ffmpeg\bin
.venv\Scripts\python build.py

# 方式 B：手动放置
# 将 ffmpeg.exe、ffprobe.exe 及 DLL 放入 ffmpeg/ 目录
.venv\Scripts\python build.py
```

生成的 `MediaConverter/` 文件夹位于项目根目录。

## 可自定义参数

| 参数 | 预设选项 | 自定义 |
|------|----------|--------|
| 分辨率 | 原图 / 4K / 1080p / 720p / 480p | 如 1600x900 |
| 帧率 | 原帧 / 24 / 30 / 60 / 120 | 如 48 |
| 质量 (CRF) | 无损(0) / 高质量(15) / 默认(23) / 低质量(35) / 极小(51) | 0-51 滑块 |
| 码率 | 1M / 2M / 5M / 10M / 20M | 如 5000k |
| 编码预设 | 最快 / 较快 / 中等 / 较慢 / 最慢 | 下拉完整列表 |
| GPU 加速 | 自动检测 NVIDIA/AMD/Intel | 勾选启用 |
| 视频裁剪 | — | 起始时间 + 时长（勾选启用） |
| 智能压缩 | — | 目标 MB 数（勾选启用） |

## 项目结构
```
MediaConverter/
├── main.py                  # GUI 入口
├── core/                    # 业务逻辑层
│   ├── converter.py         # 核心转换引擎
│   ├── options.py           # 参数数据类
│   ├── ffmpeg.py            # FFmpeg 查找 + GPU 检测
│   ├── history.py           # 历史记录管理
│   ├── queue.py             # 批量队列
│   └── validators.py        # 路径/参数校验
├── gui/                     # PyQt6 GUI 层
│   ├── main_window.py       # 主窗口
│   ├── widgets/             # 控件（拖拽、格式选择、参数面板、进度、历史）
│   ├── workers/             # 后台线程（转换、GPU检测）
│   ├── dialogs/             # 对话框（批量转换）
│   └── styles/dark.qss      # 暗色主题
├── ico/                     # 应用图标
├── ffmpeg/                  # FFmpeg 二进制文件
├── build.py                 # 打包脚本
├── converter.py             # CLI 版（旧版兼容）
├── requirements.txt
└── README.md
```

## 技术细节
- GUI：PyQt6 + QSS 暗色主题
- 核心引擎：FFmpeg 7.x
- 视频编码：H.264 (libx264)、NVENC、AMF、QSV、VP9、Xvid
- 硬件加速：-hwaccel cuda/d3d11va/qsv 解码 + GPU 编码器
- 音频编码：AAC
- 图片处理：Lanczos 缩放、高质量压缩、调色板优化
- 并发：QThreadPool + 信号槽机制
- 打包：PyInstaller（目录模式，~120MB）

## 注意事项
- 首次构建需确保 FFmpeg 文件正确放置
- 打包前关闭运行中的 MediaConverter.exe
- 自动创建不存在的输出目录
- CLI 版仍保留在 `converter.py`，可独立运行

## 许可证
- 本项目代码：[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
- FFmpeg：GPL/LGPL 许可（详见 [FFmpeg 官网](https://ffmpeg.org/legal.html)）

## 致谢
- [FFmpeg](https://ffmpeg.org/) - 多媒体处理框架
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) - Qt Python 绑定
- [PyInstaller](https://pyinstaller.org/) - Python 打包工具
- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) - Windows FFmpeg 构建版本
