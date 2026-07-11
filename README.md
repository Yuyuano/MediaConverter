# MediaConverter - 媒体格式转换工具

Windows 环境的一体化媒体转换工具，基于 FFmpeg，支持视频/图片/音频格式互转。

**v4.0 更新：流复制/音频控制/自动裁剪/进度ETA/完成通知/视频拼接/媒体信息导出/批量模板。**

## 功能特性

### 视频转换
- 一键转码：MP4、AVI、MKV、MOV、WEBM、WMV、FLV
- 自主选择编码器：H.264 / H.265 / VP9 / Xvid / WMV2 / GPU 加速
- 视频转 GIF 动图（自动优化调色板）
- 提取音频为 MP3 / WAV / FLAC 等
- 智能压缩（指定目标文件大小，自动计算码率）
- 视频裁剪（指定起始时间和持续时长）
- GPU 硬件加速（NVIDIA NVENC / AMD AMF / Intel QSV，启动自动检测）
- **流复制** — 快速转换容器格式，不重新编码（只改封装）
- **音频控制** — 移除原音频、替换为外部音频文件
- **自动裁剪检测** — 一键检测视频黑边区域并应用裁剪
- **视频拼接** — 多视频文件合并，支持流复制无损拼接

### 音频转换
- 音频格式互转：MP3 / WAV / AAC / FLAC / OGG / WMA / M4A

### 图片转换
- 格式互转：JPG、PNG、WEBP、BMP、GIF、TIFF
- 视频提取帧为图片
- 图片合成视频（幻灯片效果）

### 信息与工具
- **媒体信息查看** — 展示编码、分辨率、帧率、时长、码率、文件大小 + 缩略图预览
- **信息导出** — 文件信息导出为 TXT / JSON
- **批量模板** — 支持 `{原名}/{格式}/{序号}/{日期}/{原路径}` 自定义输出路径

### GUI 功能
- 侧边栏三页导航（视频/图片/音频独立页面 + 历史记录）
- 拖拽选择文件 + 文件信息展示
- 分辨率/帧率/质量/码率/编码器/编码预设 — 预设按钮 + 自定义输入
- 编码器下拉选择（自动 / CPU / GPU 编码器随检随显）
- 裁剪/压缩/流复制/音频控制 — 勾选启用，不干扰其他参数
- **自动裁剪检测** — 检测视频黑边并自动填入裁剪参数
- 转换进度实时百分比 + **剩余时间 (ETA) 显示**
- **转换完成弹出通知**
- **媒体信息对话框** — 缩略图 + 详细文件信息 + TXT/JSON 导出
- 批量转换 — 拖入多个文件或整个文件夹，设定并发数 + **模板自定义输出路径**
- **视频拼接对话框** — 拖拽排序文件列表，支持流复制
- 历史记录一键重转
- 卡片化 UI + 渐变按钮 + 芯片格式 + 暗色主题（Catppuccin 风格）

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

# 运行测试
.venv\Scripts\python -m unittest discover tests -v
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
| 帧率 | 原帧 / 24 / 30 / 60 / 120 | 如 29.97（支持浮点） |
| 质量 (CRF) | 无损(0) / 高质量(15) / 默认(23) / 低质量(35) / 极小(51) | 0-51 滑块（可切换按钮） |
| 码率 | 1M / 2M / 5M / 10M / 20M | 如 5000k |
| 编码器 | 自动 / H.264 / H.265 / VP9 / Xvid / WMV2 / GPU | 下拉选择 |
| 编码预设 | 最快 / 较快 / 中等 / 较慢 / 最慢 | 下拉完整列表（按钮可取消） |
| GPU 加速 | 自动检测 NVIDIA/AMD/Intel | 勾选启用 |
| 视频裁剪 | — | 起始时间 + 时长（勾选启用） |
| 智能压缩 | — | 目标 MB 数（勾选启用） |
| **流复制** | 勾选启用（无损改封装） | 视频+音频透传，不变码 |
| **音频控制** | — | 移除音频 / 替换为外部文件 |
| **自动裁剪** | 检测黑边并填入裁剪参数 | 一键检测按钮 |

## 项目结构

```
MediaConverter/
├── main.py                  # GUI 入口
├── core/                    # 业务逻辑层（无 Qt 依赖）
│   ├── constants.py         # 共享文件扩展名常量 + 版本号
│   ├── converter.py         # 核心转换引擎
│   ├── options.py           # ConvertOptions 参数数据类
│   ├── ffmpeg.py            # FFmpeg 路径查找 + GPU 检测
│   ├── history.py           # 历史记录管理
│   ├── queue.py             # 批量转换队列
│   └── validators.py        # FFmpeg 参数白名单 + 路径校验
├── gui/                     # PyQt6 GUI 层
│   ├── main_window.py       # 主窗口（侧边栏 + QStackedWidget）
│   ├── pages/               # 独立功能页面
│   │   └── convert_page.py  # 自包含转换页面（实例化 3 次）
│   ├── widgets/             # 可复用控件
│   │   ├── sidebar.py       # 侧边栏导航（4 项）
│   │   ├── param_panel.py   # 参数面板（分辨率/帧率/质量/码率/编码器/预设/GPU/流复制/音频/裁剪）
│   │   ├── file_drop.py     # 文件拖拽 + 信息按钮
│   │   ├── format_selector.py # 输出格式选择（芯片式按钮）
│   │   ├── progress_panel.py # 进度条 + ETA + 日志
│   │   └── history_table.py # 历史记录表格
│   ├── workers/             # QThread 后台线程
│   │   ├── convert_worker.py # 转换 + 批量 Worker（含 ETA 信号）
│   │   └── detect_worker.py  # GPU 检测
│   ├── dialogs/             # 对话框
│   │   ├── batch_dialog.py  # 批量转换（格式选择 + 路径模板）
│   │   ├── concat_dialog.py # 视频拼接（拖拽排序 + 流复制）
│   │   └── info_dialog.py   # 媒体信息（缩略图 + 详情 + 导出）
│   └── styles/dark.qss      # 暗色主题（卡片/渐变/芯片样式）
├── tests/                   # 核心模块单元测试（105 项，7 文件）
├── ico/                     # 应用图标
├── ffmpeg/                  # FFmpeg 二进制（gitignore）
├── build.py                 # PyInstaller 打包脚本
├── requirements.txt
└── README.md
```

## 技术细节

- GUI：PyQt6 + QSS 暗色主题
- 核心引擎：FFmpeg 7.x
- 视频编码：H.264 (libx264/GPU)、H.265 (libx265)、VP9 (libvpx-vp9)、Xvid (libxvid)、WMV2
- 硬件加速：`-hwaccel cuda/d3d11va/qsv` 解码 + GPU 编码器
- 音频编码：AAC / libopus / wmav2 / libmp3lame / FLAC / PCM / libvorbis（按格式自动选择）
- 图片处理：Lanczos 缩放、高质量压缩、GIF 调色板优化
- 并发：ThreadPoolExecutor + `threading.Event` 取消 + 多进程追踪
- 进度：实时解析 `ffmpeg stderr:time=` 输出为百分比 + `speed=` 计算 ETA
- 批量模板：`{原名}` `{格式}` `{序号}` `{日期}` `{原路径}` 自定义文件名
- 拼接：`-f concat` demuxer + 临时文件列表，支持 `-c copy` 无损
- 打包：PyInstaller（目录模式，~120MB 含 FFmpeg）

## 测试

```bash
# 核心测试（105 tests，7 文件）
.venv\Scripts\python.exe -m unittest discover tests -v

# 旧版 CLI 模块测试（19 tests，在 backup/ 目录）
.venv\Scripts\python.exe -m unittest backup.test_converter -v
```

## 注意事项

- 首次构建需确保 FFmpeg 文件正确放置
- 打包前关闭运行中的 MediaConverter.exe
- 自动创建不存在的输出目录

## 许可证

- 本项目代码：[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
- FFmpeg：GPL/LGPL 许可（详见 [FFmpeg 官网](https://ffmpeg.org/legal.html)）

## 致谢

- [FFmpeg](https://ffmpeg.org/) - 多媒体处理框架
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) - Qt Python 绑定
- [PyInstaller](https://pyinstaller.org/) - Python 打包工具
- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) - Windows FFmpeg 构建版本
