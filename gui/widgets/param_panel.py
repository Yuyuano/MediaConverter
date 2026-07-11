from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
    QSpinBox, QLineEdit, QPushButton, QFileDialog, QGroupBox, QCheckBox,
    QGridLayout, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import pyqtSignal, Qt
from pathlib import Path
 
from core.options import ConvertOptions
from core.validators import parse_size


def _make_btn_grid(buttons: list[tuple[str, QPushButton]], columns: int = 5) -> QGridLayout:
    grid = QGridLayout()
    grid.setSpacing(6)
    for i, (label, btn) in enumerate(buttons):
        row, col = divmod(i, columns)
        grid.addWidget(btn, row, col)
    return grid


class ParamPanel(QWidget):

    crop_detect_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._gpu_available = False
        self._gpu_type = ''
        self._quality_user_set = False
        self._media_type = None
        self._selected_res_btn = None
        self._selected_fps_btn = None
        self._selected_bitrate_btn = None
        self._replace_audio_path = ''
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # ═══════════════════ 视频参数 ═══════════════════
        self._video_panel = QWidget()
        video_layout = QVBoxLayout(self._video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(10)

        # 分辨率
        res_group = QGroupBox("分辨率")
        res_vl = QVBoxLayout(res_group)
        res_btns = []
        res_labels = [
            ("原图", "原图"), ("4K", "4K"), ("1080p", "1080p"),
            ("720p", "720p"), ("480p", "480p")
        ]
        for key, display in res_labels:
            btn = QPushButton(display)
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(60)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setObjectName("presetBtn")
            btn.setToolTip({"原图": "保持原始分辨率", "4K": "3840×2160",
                           "1080p": "1920×1080", "720p": "1280×720",
                           "480p": "854×480"}.get(key, ""))
            res_btns.append(btn)
        self._res_btns = dict(zip([k for k, _ in res_labels], res_btns))
        for btn in self._res_btns.values():
            btn.clicked.connect(lambda checked, b=btn: self._on_res_btn(b))
        res_grid = _make_btn_grid(list(zip(self._res_btns.keys(), res_btns)), columns=3)
        res_custom = QHBoxLayout()
        res_custom.addWidget(QLabel("自定义:"))
        self.input_resolution = QLineEdit()
        self.input_resolution.setPlaceholderText("如 1600x900")
        self.input_resolution.setMinimumHeight(30)
        self.input_resolution.textChanged.connect(lambda _: self._clear_res_btns())
        res_custom.addWidget(self.input_resolution, 1)
        res_vl.addLayout(res_grid)
        res_vl.addLayout(res_custom)

        # 帧率
        fps_group = QGroupBox("帧率")
        fps_vl = QVBoxLayout(fps_group)
        fps_btns = []
        fps_labels = [
            ("原帧", "原帧"), ("24", "24"), ("30", "30"), ("60", "60"), ("120", "120")
        ]
        for key, display in fps_labels:
            btn = QPushButton(display)
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(50)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setObjectName("presetBtn")
            fps_btns.append(btn)
        self._fps_btns = dict(zip([k for k, _ in fps_labels], fps_btns))
        for btn in self._fps_btns.values():
            btn.clicked.connect(lambda checked, b=btn: self._on_fps_btn(b))
        fps_grid = _make_btn_grid(list(zip(self._fps_btns.keys(), fps_btns)), columns=3)
        fps_custom = QHBoxLayout()
        fps_custom.addWidget(QLabel("自定义:"))
        self.input_fps = QLineEdit()
        self.input_fps.setPlaceholderText("如 48")
        self.input_fps.setMinimumHeight(30)
        self.input_fps.textChanged.connect(lambda _: self._clear_fps_btns())
        fps_custom.addWidget(self.input_fps, 1)
        fps_vl.addLayout(fps_grid)
        fps_vl.addLayout(fps_custom)

        row1 = QHBoxLayout()
        row1.addWidget(res_group, 3)
        row1.addWidget(fps_group, 2)
        video_layout.addLayout(row1)

        # 质量
        self._quality_group = QGroupBox("质量 (CRF: 0=无损 23=默认 51=最差)")
        quality_vl = QVBoxLayout(self._quality_group)
        self._quality_presets = {"无损": 0, "高质量": 15, "默认": 23, "低质量": 35, "极小": 51}
        self._quality_btns = {}
        q_btn_list = []
        for label, crf in self._quality_presets.items():
            btn = QPushButton(f"{label} ({crf})")
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(70)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setObjectName("presetBtn")
            btn.clicked.connect(lambda checked, b=btn, c=crf: self._on_quality_btn(b, c))
            self._quality_btns[label] = btn
            q_btn_list.append((label, btn))
        quality_grid = _make_btn_grid(q_btn_list, columns=3)
        quality_slider_row = QHBoxLayout()
        quality_slider_row.addWidget(QLabel("精确:"))
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(0, 51)
        self.slider_quality.setValue(23)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(0, 51)
        self.spin_quality.setValue(23)
        self.spin_quality.setMinimumWidth(55)
        self.slider_quality.valueChanged.connect(self._on_quality_slider)
        self.spin_quality.valueChanged.connect(self._on_quality_spin)
        quality_slider_row.addWidget(self.slider_quality, 1)
        quality_slider_row.addWidget(self.spin_quality)
        quality_vl.addLayout(quality_grid)
        quality_vl.addLayout(quality_slider_row)

        # 码率
        bitrate_group = QGroupBox("码率 (留空=自动)")
        bitrate_vl = QVBoxLayout(bitrate_group)
        self._bitrate_btns = {}
        br_btn_list = []
        for label in ["1M", "2M", "5M", "10M", "20M"]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setMinimumWidth(50)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setObjectName("presetBtn")
            btn.clicked.connect(lambda checked, b=btn: self._on_bitrate_btn(b))
            self._bitrate_btns[label] = btn
            br_btn_list.append((label, btn))
        bitrate_grid = _make_btn_grid(br_btn_list, columns=3)
        br_custom = QHBoxLayout()
        br_custom.addWidget(QLabel("自定义:"))
        self.input_bitrate = QLineEdit()
        self.input_bitrate.setPlaceholderText("如 5000k, 2M")
        self.input_bitrate.setMinimumHeight(30)
        self.input_bitrate.textChanged.connect(lambda _: self._clear_bitrate_btns())
        br_custom.addWidget(self.input_bitrate, 1)
        bitrate_vl.addLayout(bitrate_grid)
        bitrate_vl.addLayout(br_custom)

        row2 = QHBoxLayout()
        row2.addWidget(self._quality_group, 3)
        row2.addWidget(bitrate_group, 2)
        video_layout.addLayout(row2)

        # 视频编码器
        codec_group = QGroupBox("视频编码器")
        codec_layout = QHBoxLayout(codec_group)
        codec_layout.addWidget(QLabel("编码器:"))
        self.combo_codec = QComboBox()
        self.combo_codec.setMinimumHeight(30)
        self.combo_codec.addItem("自动 (推荐)", "")
        self.combo_codec.addItem("H.264 (libx264)", "libx264")
        self.combo_codec.addItem("H.265 (libx265)", "libx265")
        self.combo_codec.addItem("VP9 (libvpx-vp9)", "libvpx-vp9")
        self.combo_codec.addItem("Xvid (libxvid)", "libxvid")
        self.combo_codec.addItem("WMV2 (wmv2)", "wmv2")
        codec_layout.addWidget(self.combo_codec, 1)
        video_layout.addWidget(codec_group)

        # 编码速度预设
        preset_group = QGroupBox("编码速度预设")
        preset_vl = QVBoxLayout(preset_group)
        preset_map = [
            ("最快", "ultrafast"), ("较快", "faster"), ("中等", "medium"),
            ("较慢", "slower"), ("最慢", "veryslow")
        ]
        self._preset_btns = {}
        pr_btn_list = []
        for display, value in preset_map:
            btn = QPushButton(display)
            btn.setCheckable(True)
            btn.setMinimumHeight(30)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setObjectName("presetBtn")
            btn.setProperty("preset_value", value)
            btn.clicked.connect(lambda checked, b=btn: self._on_preset_btn(b))
            self._preset_btns[value] = btn
            pr_btn_list.append((value, btn))
        preset_grid = _make_btn_grid(pr_btn_list, columns=3)
        pr_custom = QHBoxLayout()
        pr_custom.addWidget(QLabel("精确选择:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems([
            "默认", "ultrafast", "superfast", "veryfast", "faster",
            "fast", "medium", "slow", "slower", "veryslow"
        ])
        self.combo_preset.setMinimumHeight(30)
        self.combo_preset.currentTextChanged.connect(self._on_preset_combo)
        pr_custom.addWidget(self.combo_preset, 1)
        preset_vl.addLayout(preset_grid)
        preset_vl.addLayout(pr_custom)

        # GPU
        self.check_gpu = QCheckBox("启用 GPU 硬件加速")
        self.check_gpu.setEnabled(False)
        self.check_gpu.setMinimumHeight(30)

        row3 = QHBoxLayout()
        row3.addWidget(preset_group, 3)
        row3.addWidget(self.check_gpu, 2)
        video_layout.addLayout(row3)

        # 视频裁剪
        self.check_trim = QCheckBox("视频裁剪")
        self.check_trim.stateChanged.connect(self._toggle_trim)
        video_layout.addWidget(self.check_trim)

        self.trim_widget = QWidget()
        trim_layout = QHBoxLayout(self.trim_widget)
        trim_layout.setContentsMargins(24, 0, 0, 0)
        trim_layout.addWidget(QLabel("起始:"))
        self.input_start = QLineEdit()
        self.input_start.setPlaceholderText("00:01:30 或 90 秒")
        self.input_start.setEnabled(False)
        self.input_start.setMinimumHeight(30)
        trim_layout.addWidget(self.input_start, 1)
        trim_layout.addWidget(QLabel("时长:"))
        self.input_duration = QLineEdit()
        self.input_duration.setPlaceholderText("00:00:30 或 30 秒")
        self.input_duration.setEnabled(False)
        self.input_duration.setMinimumHeight(30)
        trim_layout.addWidget(self.input_duration, 1)
        video_layout.addWidget(self.trim_widget)

        # 智能压缩
        self.check_compress = QCheckBox("智能压缩 (指定目标大小)")
        self.check_compress.stateChanged.connect(self._toggle_compress)
        video_layout.addWidget(self.check_compress)

        self.compress_widget = QWidget()
        compress_layout = QHBoxLayout(self.compress_widget)
        compress_layout.setContentsMargins(24, 0, 0, 0)
        compress_layout.addWidget(QLabel("目标大小:"))
        self.spin_compress = QSpinBox()
        self.spin_compress.setRange(1, 10000)
        self.spin_compress.setValue(50)
        self.spin_compress.setSuffix(" MB")
        self.spin_compress.setEnabled(False)
        self.spin_compress.setMinimumHeight(30)
        self.spin_compress.setMinimumWidth(80)
        compress_layout.addWidget(self.spin_compress)
        self.label_estimate = QLabel("")
        compress_layout.addWidget(self.label_estimate)
        compress_layout.addStretch()
        video_layout.addWidget(self.compress_widget)

        # 视频容器内音频编码
        audio_in_video_group = QGroupBox("视频内音频编码")
        audio_in_video_layout = QHBoxLayout(audio_in_video_group)
        audio_in_video_layout.addWidget(QLabel("音频编码器:"))
        self.combo_audio_codec = QComboBox()
        self.combo_audio_codec.setMinimumHeight(30)
        self.combo_audio_codec.addItem("自动 (根据容器选择)", "")
        self.combo_audio_codec.addItem("AAC", "aac")
        self.combo_audio_codec.addItem("MP3 (libmp3lame)", "libmp3lame")
        self.combo_audio_codec.addItem("FLAC", "flac")
        self.combo_audio_codec.addItem("Opus (libopus)", "libopus")
        self.combo_audio_codec.addItem("PCM (pcm_s16le)", "pcm_s16le")
        audio_in_video_layout.addWidget(self.combo_audio_codec, 1)
        audio_in_video_layout.addWidget(QLabel("码率:"))
        self.combo_audio_bitrate = QComboBox()
        self.combo_audio_bitrate.setMinimumHeight(30)
        self.combo_audio_bitrate.addItems(["自动", "128k", "192k", "256k", "320k", "64k", "96k"])
        self.combo_audio_bitrate.setCurrentText("192k")
        audio_in_video_layout.addWidget(self.combo_audio_bitrate)
        video_layout.addWidget(audio_in_video_group)

        # 流复制模式
        self.check_stream_copy = QCheckBox("流复制（不重编码，仅改变容器格式）")
        self.check_stream_copy.setMinimumHeight(30)
        self.check_stream_copy.toggled.connect(self._toggle_stream_copy)
        video_layout.addWidget(self.check_stream_copy)

        # 音频处理（移除/替换）
        audio_action_group = QGroupBox("音频处理")
        audio_action_layout = QHBoxLayout(audio_action_group)
        self.check_remove_audio = QCheckBox("移除音频")
        self.check_remove_audio.setMinimumHeight(30)
        self.btn_replace_audio = QPushButton("替换音频文件...")
        self.btn_replace_audio.setMinimumHeight(30)
        self.btn_replace_audio.clicked.connect(self._select_replace_audio)
        self.label_replace_audio = QLabel("")
        self.label_replace_audio.setStyleSheet("color: #888; font-size: 11px;")
        audio_action_layout.addWidget(self.check_remove_audio)
        audio_action_layout.addWidget(self.btn_replace_audio)
        audio_action_layout.addWidget(self.label_replace_audio, 1)
        video_layout.addWidget(audio_action_group)

        # 画面裁剪
        crop_group = QGroupBox("画面裁剪")
        crop_layout = QHBoxLayout(crop_group)
        crop_layout.addWidget(QLabel("宽:"))
        self.spin_crop_w = QSpinBox()
        self.spin_crop_w.setRange(0, 10000)
        self.spin_crop_w.setValue(0)
        self.spin_crop_w.setSuffix(" px (0=不裁剪)")
        self.spin_crop_w.setMinimumWidth(100)
        crop_layout.addWidget(self.spin_crop_w)
        crop_layout.addWidget(QLabel("高:"))
        self.spin_crop_h = QSpinBox()
        self.spin_crop_h.setRange(0, 10000)
        self.spin_crop_h.setValue(0)
        self.spin_crop_h.setSuffix(" px")
        self.spin_crop_h.setMinimumWidth(100)
        crop_layout.addWidget(self.spin_crop_h)
        crop_layout.addWidget(QLabel("起点X:"))
        self.spin_crop_x = QSpinBox()
        self.spin_crop_x.setRange(0, 10000)
        self.spin_crop_x.setValue(0)
        self.spin_crop_x.setMinimumWidth(70)
        crop_layout.addWidget(self.spin_crop_x)
        crop_layout.addWidget(QLabel("Y:"))
        self.spin_crop_y = QSpinBox()
        self.spin_crop_y.setRange(0, 10000)
        self.spin_crop_y.setValue(0)
        self.spin_crop_y.setMinimumWidth(70)
        crop_layout.addWidget(self.spin_crop_y)
        self.btn_auto_crop = QPushButton("自动检测黑边")
        self.btn_auto_crop.setMinimumHeight(30)
        self.btn_auto_crop.clicked.connect(self._on_auto_crop)
        crop_layout.addWidget(self.btn_auto_crop)
        video_layout.addWidget(crop_group)

        video_layout.addStretch()

        # ═══════════════════ 图片参数 ═══════════════════
        self._image_panel = QWidget()
        image_layout = QVBoxLayout(self._image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(10)

        img_quality_group = QGroupBox("图片质量")
        img_quality_layout = QVBoxLayout(img_quality_group)
        img_quality_label_row = QHBoxLayout()
        img_quality_label_row.addWidget(QLabel("质量 (数值越大质量越高):"))
        self.spin_img_quality = QSpinBox()
        self.spin_img_quality.setRange(1, 100)
        self.spin_img_quality.setValue(85)
        self.spin_img_quality.setMinimumWidth(60)
        img_quality_label_row.addWidget(self.spin_img_quality)
        img_quality_label_row.addStretch()
        img_quality_layout.addLayout(img_quality_label_row)

        img_info_label = QLabel("JPG/WebP: 1-100  |  PNG: 压缩级别自动映射")
        img_info_label.setStyleSheet("color: #888; font-size: 11px;")
        img_quality_layout.addWidget(img_info_label)
        image_layout.addWidget(img_quality_group)

        img_resize_group = QGroupBox("缩放")
        img_resize_layout = QHBoxLayout(img_resize_group)
        img_resize_layout.addWidget(QLabel("宽度:"))
        self.spin_img_width = QSpinBox()
        self.spin_img_width.setRange(0, 10000)
        self.spin_img_width.setValue(0)
        self.spin_img_width.setSuffix(" px (0=原宽)")
        self.spin_img_width.setMinimumWidth(120)
        img_resize_layout.addWidget(self.spin_img_width)
        img_resize_layout.addWidget(QLabel("高度:"))
        self.spin_img_height = QSpinBox()
        self.spin_img_height.setRange(0, 10000)
        self.spin_img_height.setValue(0)
        self.spin_img_height.setSuffix(" px (0=原高)")
        self.spin_img_height.setMinimumWidth(120)
        img_resize_layout.addWidget(self.spin_img_height)
        img_resize_layout.addStretch()
        image_layout.addWidget(img_resize_group)
        image_layout.addStretch()

        # ═══════════════════ 音频参数 ═══════════════════
        self._audio_panel = QWidget()
        audio_layout = QVBoxLayout(self._audio_panel)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setSpacing(10)

        audio_codec_group = QGroupBox("音频编码器")
        audio_codec_layout = QHBoxLayout(audio_codec_group)
        audio_codec_layout.addWidget(QLabel("编码器:"))
        self.combo_audio_only_codec = QComboBox()
        self.combo_audio_only_codec.setMinimumHeight(30)
        self.combo_audio_only_codec.addItem("自动 (推荐)", "")
        self.combo_audio_only_codec.addItem("AAC", "aac")
        self.combo_audio_only_codec.addItem("MP3 (libmp3lame)", "libmp3lame")
        self.combo_audio_only_codec.addItem("FLAC", "flac")
        self.combo_audio_only_codec.addItem("WAV (pcm_s16le)", "pcm_s16le")
        self.combo_audio_only_codec.addItem("Opus (libopus)", "libopus")
        self.combo_audio_only_codec.addItem("Vorbis (libvorbis)", "libvorbis")
        self.combo_audio_only_codec.addItem("WMA (wmav2)", "wmav2")
        audio_codec_layout.addWidget(self.combo_audio_only_codec, 1)
        audio_layout.addWidget(audio_codec_group)

        audio_bitrate_group = QGroupBox("音频码率")
        audio_bitrate_layout = QHBoxLayout(audio_bitrate_group)
        audio_bitrate_layout.addWidget(QLabel("码率:"))
        self.combo_audio_only_bitrate = QComboBox()
        self.combo_audio_only_bitrate.setMinimumHeight(30)
        self.combo_audio_only_bitrate.addItems(["自动", "64k", "96k", "128k", "192k", "256k", "320k"])
        self.combo_audio_only_bitrate.setCurrentText("192k")
        audio_bitrate_layout.addWidget(self.combo_audio_only_bitrate)
        audio_bitrate_layout.addStretch()
        audio_layout.addWidget(audio_bitrate_group)
        audio_layout.addStretch()

        # 组装
        layout.addWidget(self._video_panel)
        layout.addWidget(self._image_panel)
        layout.addWidget(self._audio_panel)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._video_panel.hide()
        self._image_panel.hide()
        self._audio_panel.hide()

    # ═══════════════════ 模式切换 ═══════════════════
    def set_media_type(self, media_type: str):
        self._media_type = media_type
        self._video_panel.setVisible(media_type == 'video')
        self._image_panel.setVisible(media_type == 'image')
        self._audio_panel.setVisible(media_type == 'audio')

    # ═══════════════════ 分辨率 ═══════════════════
    def _on_res_btn(self, clicked):
        if self._selected_res_btn is clicked:
            self._selected_res_btn = None
            clicked.setChecked(False)
            return
        for btn in self._res_btns.values():
            btn.setChecked(btn is clicked)
        self._selected_res_btn = clicked
        self.input_resolution.blockSignals(True)
        self.input_resolution.clear()
        self.input_resolution.blockSignals(False)

    def _clear_res_btns(self):
        if self.input_resolution.text().strip():
            self._selected_res_btn = None
            for btn in self._res_btns.values():
                btn.setChecked(False)

    def _get_resolution(self) -> str:
        for label, btn in self._res_btns.items():
            if btn.isChecked():
                return label
        return self.input_resolution.text().strip()

    # ═══════════════════ 帧率 ═══════════════════
    def _on_fps_btn(self, clicked):
        if self._selected_fps_btn is clicked:
            self._selected_fps_btn = None
            clicked.setChecked(False)
            return
        for btn in self._fps_btns.values():
            btn.setChecked(btn is clicked)
        self._selected_fps_btn = clicked
        self.input_fps.blockSignals(True)
        self.input_fps.clear()
        self.input_fps.blockSignals(False)

    def _clear_fps_btns(self):
        if self.input_fps.text().strip():
            self._selected_fps_btn = None
            for btn in self._fps_btns.values():
                btn.setChecked(False)

    def _get_fps(self) -> str:
        for label, btn in self._fps_btns.items():
            if btn.isChecked():
                return label
        return self.input_fps.text().strip()

    # ═══════════════════ 质量 (视频 CRF) ═══════════════════
    def _on_quality_btn(self, clicked, crf):
        self._quality_user_set = True
        if clicked.isChecked():
            for btn in self._quality_btns.values():
                btn.setChecked(btn is clicked)
            self.slider_quality.blockSignals(True)
            self.spin_quality.blockSignals(True)
            self.slider_quality.setValue(crf)
            self.spin_quality.setValue(crf)
            self.slider_quality.blockSignals(False)
            self.spin_quality.blockSignals(False)
        else:
            for btn in self._quality_btns.values():
                btn.setChecked(btn is clicked)
            self._quality_user_set = False

    def _on_quality_slider(self, value):
        self._quality_user_set = True
        self.spin_quality.blockSignals(True)
        self.spin_quality.setValue(value)
        self.spin_quality.blockSignals(False)
        self._sync_quality_btns(value)

    def _on_quality_spin(self, value):
        self._quality_user_set = True
        self.slider_quality.blockSignals(True)
        self.slider_quality.setValue(value)
        self.slider_quality.blockSignals(False)
        self._sync_quality_btns(value)

    def _sync_quality_btns(self, value):
        for label, btn in self._quality_btns.items():
            btn.setChecked(self._quality_presets[label] == value)

    # ═══════════════════ 码率 ═══════════════════
    def _on_bitrate_btn(self, clicked):
        if self._selected_bitrate_btn is clicked:
            self._selected_bitrate_btn = None
            clicked.setChecked(False)
            return
        for btn in self._bitrate_btns.values():
            btn.setChecked(btn is clicked)
        self._selected_bitrate_btn = clicked
        self.input_bitrate.blockSignals(True)
        self.input_bitrate.clear()
        self.input_bitrate.blockSignals(False)

    def _clear_bitrate_btns(self):
        if self.input_bitrate.text().strip():
            self._selected_bitrate_btn = None
            for btn in self._bitrate_btns.values():
                btn.setChecked(False)

    def _get_bitrate(self) -> str:
        for label, btn in self._bitrate_btns.items():
            if btn.isChecked():
                return label
        return self.input_bitrate.text().strip()

    # ═══════════════════ 预设 ═══════════════════
    def _on_preset_btn(self, clicked):
        preset_value = clicked.property("preset_value")
        if preset_value is None:
            return
        if clicked.isChecked():
            for btn in self._preset_btns.values():
                btn.setChecked(btn is clicked)
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentText(preset_value)
            self.combo_preset.blockSignals(False)
        else:
            for btn in self._preset_btns.values():
                btn.setChecked(False)
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentText("默认")
            self.combo_preset.blockSignals(False)

    def _on_preset_combo(self, text):
        if text != "默认":
            for btn in self._preset_btns.values():
                btn.setChecked(False)

    def _get_preset(self) -> str:
        for btn in self._preset_btns.values():
            if btn.isChecked():
                return btn.property("preset_value")
        pr = self.combo_preset.currentText()
        return "" if pr == "默认" else pr

    # ═══════════════════ 开关 ═══════════════════
    def _toggle_trim(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.input_start.setEnabled(enabled)
        self.input_duration.setEnabled(enabled)
        if not enabled:
            self.input_start.clear()
            self.input_duration.clear()

    def _toggle_compress(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.spin_compress.setEnabled(enabled)

    # ═══════════════════ 流复制 ═══════════════════
    def _toggle_stream_copy(self, checked):
        enabled = not checked
        for btn in self._res_btns.values():
            btn.setEnabled(enabled)
        self.input_resolution.setEnabled(enabled)
        for btn in self._fps_btns.values():
            btn.setEnabled(enabled)
        self.input_fps.setEnabled(enabled)
        self._quality_group.setEnabled(enabled)
        for btn in self._bitrate_btns.values():
            btn.setEnabled(enabled)
        self.input_bitrate.setEnabled(enabled)
        self.combo_codec.setEnabled(enabled)
        for btn in self._preset_btns.values():
            btn.setEnabled(enabled)
        self.combo_preset.setEnabled(enabled)
        self.check_gpu.setEnabled(enabled and self._gpu_available)
        self.check_compress.setEnabled(enabled)
        if checked:
            self.check_remove_audio.setEnabled(True)
            self.btn_replace_audio.setEnabled(True)
        else:
            self.check_remove_audio.setEnabled(True)
            self.btn_replace_audio.setEnabled(True)

    # ═══════════════════ 音频替换/移除 ═══════════════════
    def _select_replace_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择替换音频文件", filter="音频文件 (*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma);;所有文件 (*.*)")
        if path:
            self._replace_audio_path = path
            self.label_replace_audio.setText(Path(path).name)
        else:
            self._replace_audio_path = ''
            self.label_replace_audio.setText('')

    # ═══════════════════ 自动裁剪检测 ═══════════════════
    def _on_auto_crop(self):
        if self._media_type == 'video':
            self.btn_auto_crop.setEnabled(False)
            self.btn_auto_crop.setText("检测中...")
            self.crop_detect_requested.emit('video')

    def set_crop_result(self, w: int, h: int, x: int, y: int):
        self.spin_crop_w.setValue(w)
        self.spin_crop_h.setValue(h)
        self.spin_crop_x.setValue(x)
        self.spin_crop_y.setValue(y)
        self.btn_auto_crop.setEnabled(True)
        self.btn_auto_crop.setText("自动检测黑边")

    def set_crop_error(self):
        self.btn_auto_crop.setEnabled(True)
        self.btn_auto_crop.setText("自动检测黑边")

    # ═══════════════════ 公开接口 ═══════════════════
    def set_gpu_available(self, available: bool, gpu_name: str = '', gpu_type: str = ''):
        self._gpu_available = available
        self._gpu_type = gpu_type
        self.check_gpu.setEnabled(available)
        if available:
            self.check_gpu.setText(f"启用 GPU 加速 ({gpu_name})")
        else:
            self.check_gpu.setText("GPU 加速 (不可用)")

        gpu_items = {'nvidia': ('h264_nvenc', 'H.264 NVENC (GPU)'),
                     'amd': ('h264_amf', 'H.264 AMF (GPU)'),
                     'intel': ('h264_qsv', 'H.264 QSV (GPU)')}
        for i in range(self.combo_codec.count() - 1, -1, -1):
            data = self.combo_codec.itemData(i)
            if data in ('h264_nvenc', 'h264_amf', 'h264_qsv'):
                self.combo_codec.removeItem(i)
        if available and gpu_type in gpu_items:
            codec_id, label = gpu_items[gpu_type]
            self.combo_codec.addItem(label, codec_id)

    def is_trim_enabled(self) -> bool:
        return self.check_trim.isChecked()

    def is_compress_enabled(self) -> bool:
        return self.check_compress.isChecked()

    def get_compress_target_mb(self) -> int:
        return self.spin_compress.value()

    def get_options(self) -> ConvertOptions:
        opts = ConvertOptions()

        if self._media_type == 'video':
            res_text = self._get_resolution()
            if res_text and res_text != "原图":
                alias = {"4K": "3840x2160", "1080p": "1920x1080",
                         "720p": "1280x720", "480p": "854x480"}
                res_text = alias.get(res_text, res_text)
                w, h = parse_size(res_text)
                if w is not None:
                    opts.width = w
                if h is not None:
                    opts.height = h

            fps_text = self._get_fps()
            if fps_text and fps_text != "原帧":
                try:
                    fps_val = float(fps_text)
                    if fps_val > 0:
                        opts.fps = int(fps_val) if fps_val == int(fps_val) else fps_val
                except ValueError:
                    pass

            if self._quality_user_set:
                opts.quality = self.spin_quality.value()

            br = self._get_bitrate()
            if br:
                opts.bitrate = br

            pr = self._get_preset()
            if pr:
                opts.preset = pr

            opts.use_gpu = self.check_gpu.isChecked() and self._gpu_available

            codec = self.combo_codec.currentData()
            if codec:
                opts.codec = codec

            if self.check_trim.isChecked():
                start = self.input_start.text().strip()
                if start:
                    opts.start_time = start
                dur = self.input_duration.text().strip()
                if dur:
                    opts.trim_duration = dur

            ac = self.combo_audio_codec.currentData()
            if ac:
                opts.audio_codec = ac
            ab = self.combo_audio_bitrate.currentText()
            if ab and ab != '自动':
                opts.audio_bitrate = ab

            opts.stream_copy = self.check_stream_copy.isChecked()
            opts.remove_audio = self.check_remove_audio.isChecked()
            if self._replace_audio_path:
                opts.replace_audio_file = self._replace_audio_path
            cw = self.spin_crop_w.value()
            ch = self.spin_crop_h.value()
            if cw > 0 and ch > 0:
                opts.crop_w = cw
                opts.crop_h = ch
                opts.crop_x = self.spin_crop_x.value()
                opts.crop_y = self.spin_crop_y.value()

        elif self._media_type == 'image':
            q = self.spin_img_quality.value()
            opts.quality = q
            w = self.spin_img_width.value()
            h = self.spin_img_height.value()
            if w > 0:
                opts.width = w
            if h > 0:
                opts.height = h

        elif self._media_type == 'audio':
            ac = self.combo_audio_only_codec.currentData()
            if ac:
                opts.codec = ac
            ab = self.combo_audio_only_bitrate.currentText()
            if ab and ab != '自动':
                opts.audio_bitrate = ab

        return opts
