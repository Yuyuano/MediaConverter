# MediaConverter - 媒体格式转换工具

Windows 环境的一体化媒体转换工具，基于 FFmpeg，支持视频/图片/音频格式互转，无需配置环境，开箱即用。

## 功能特性

### 视频转换
- 一键转码：MP4、AVI、MKV、MOV、WEBM、WMV、FLV
- 视频转 GIF 动图（自动优化调色板）
- 提取音频为 MP3
- 智能压缩（指定目标文件大小，自动计算码率）
- **视频裁剪**（指定起始时间和持续时长）

### 图片转换
- 格式互转：JPG、PNG、WEBP、BMP、GIF、TIFF
- 视频提取帧为图片
- 图片合成视频（幻灯片效果）

### 高级功能
- 自定义输出尺寸（1920x1080、1080p、720p 等）
- 调整质量/码率/帧率
- 选择编码速度预设（ultrafast ~ veryslow）
- **视频裁剪**（所有视频模式均支持）
- **转换参数预览确认**（避免误操作）
- **自定义输出目录**（默认与输入文件同目录）
- **彩色终端输出**（成功/失败/信息一目了然）
- **历史记录复用**（一键重新转换最近文件）
- **批量队列模式**（并发处理多个文件）

## 下载使用

### 直接使用
1. 下载 `MediaConverter.exe`（或 `MediaConverter/` 文件夹）
2. 双击运行，按菜单提示操作
3. 无需安装 FFmpeg，无需配置环境变量

### 从源码构建

#### 环境要求
- Python 3.7+
- Windows 系统

#### 构建步骤

**1. 克隆项目**
```bash
git clone https://github.com/Yuyuano/MediaConverter.git
cd MediaConverter
```

**2. 安装依赖**
```bash
pip install pyinstaller colorama
```

**3. 准备 FFmpeg**

方式 A - 指定本地路径（推荐）：
修改 `build.py` 中的 `FFMPEG_SOURCE = r"C:\ffmpeg\bin"`

方式 B - 手动放置：
创建 `ffmpeg/` 目录，放入 `ffmpeg.exe`、`ffprobe.exe` 及相关 DLL

方式 C - 自动下载：
设置 `build.py` 中 `AUTO_DOWNLOAD = True`

**4. 执行打包**
```bash
python build.py
```
生成的 `MediaConverter/` 文件夹位于项目根目录。

## 使用指南

### 快速模式
```
 1. 视频 → MP4       8. 图片 → JPG
 2. 视频 → AVI       9. 图片 → PNG
 3. 视频 → MKV      10. 图片 → WEBP
 4. 视频 → MOV      11. 图片 → BMP
 5. 视频 → WEBM
 6. 视频 → GIF
 7. 视频 → MP3
操作流程：选择功能 → 拖入文件 → 选择输出目录 → 设置裁剪(可选) → 确认预览 → 自动转换
```

### 高级模式
```
12. 视频转换 + 自定义参数
13. 图片转换 + 自定义参数
14. 视频 ↔ 图片 互转
15. 智能压缩
16. 重新转换最近文件
17. 批量转换队列模式
```

#### 可自定义参数
| 参数 | 说明 |
|------|------|
| 输出尺寸 | `1920x1080`、`1080p`、`720p`、`480p` 或自定义宽度 |
| 视频质量 | CRF 0-51（0=无损，23=默认，51=最低） |
| 图片质量 | 2-31（2=最高，31=最低） |
| 帧率 | 30、60 等 |
| 码率 | `2M`、`5000k` 等 |
| 编码预设 | ultrafast ~ veryslow |
| 视频裁剪 | 起始时间 + 持续时长（回车跳过） |

#### 输出文件命名规则
| 模式 | 命名格式 |
|------|----------|
| 快速转换 | `原文件名_converted.扩展名` |
| 高级转换 | `原文件名_custom.扩展名` |
| 压缩视频 | `原文件名_compressed.mp4` |
| 提取帧 | `原文件名_frame.扩展名` |
| 提取音频 | `原文件名_audio.mp3` |
| 历史重转 | `原文件名_history.扩展名` |
| 批量队列 | `原文件名_batch.扩展名` |

## 项目结构
```
MediaConverter/
├── converter.py           # 主程序源码
├── build.py               # 打包脚本
├── ffmpeg/                # FFmpeg 二进制文件
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   └── *.dll
├── requirements.txt       # Python 依赖
├── .gitignore
└── README.md
```

## 技术细节
- 核心引擎：FFmpeg 4.x/5.x/6.x/7.x
- 视频编码：H.264 (libx264)、H.265、VP9、Xvid 等
- 音频编码：AAC、MP3、PCM、Opus 等
- 图片处理：Lanczos 缩放、高质量压缩、调色板优化
- 配色方案：colorama 彩色终端输出

## 注意事项
- 首次构建时确保 FFmpeg 文件正确放置
- 打包前请关闭运行中的 MediaConverter.exe
- 自定义输出目录不存在时会自动创建
- 某些系统目录可能需要管理员权限

## 许可证
- 本项目代码：[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
- FFmpeg：GPL/LGPL 许可（详见 [FFmpeg 官网](https://ffmpeg.org/legal.html)）

本程序分发了 FFmpeg 库。根据 GPL 许可证的要求，本项目的全部源代码均在 GPL v3.0 许可证下提供。

## 致谢
- [FFmpeg](https://ffmpeg.org/) - 强大的多媒体处理框架
- [PyInstaller](https://pyinstaller.org/) - Python 打包工具
- [colorama](https://github.com/tartley/colorama) - 终端彩色输出
- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) - Windows FFmpeg 构建版本
