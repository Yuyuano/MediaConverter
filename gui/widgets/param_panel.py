from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
    QSpinBox, QLineEdit, QPushButton, QFileDialog, QGroupBox, QCheckBox,
    QGridLayout, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import pyqtSignal, Qt

from core.options import ConvertOptions
from core.validators import parse_size


def _make_btn_grid(buttons: list[tuple[str, QPushButton]], columns: int = 5) -> QGridLayout:
    """把按钮列表按指定列数放入 QGridLayout"""
    grid = QGridLayout()
    grid.setSpacing(6)
    for i, (label, btn) in enumerate(buttons):
        row, col = divmod(i, columns)
        grid.addWidget(btn, row, col)
    return grid


class ParamPanel(QWidget):
    """参数设置面板"""

    def __init__(self):
        super().__init__()
        self._gpu_available = False
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 用 QScrollArea 包裹，小窗口也能滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # ════════ 分辨率 ════════
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

        # ════════ 帧率 ════════
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
        layout.addLayout(row1)

        # ════════ 质量 ════════
        quality_group = QGroupBox("质量 (CRF: 0=无损 23=默认 51=最差)")
        quality_vl = QVBoxLayout(quality_group)
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

        # ════════ 码率 ════════
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
        row2.addWidget(quality_group, 3)
        row2.addWidget(bitrate_group, 2)
        layout.addLayout(row2)

        # ════════ 编码速度预设 ════════
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
        layout.addLayout(row3)

        # ════════ 视频裁剪 ════════
        self.check_trim = QCheckBox("视频裁剪")
        self.check_trim.stateChanged.connect(self._toggle_trim)
        layout.addWidget(self.check_trim)

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
        layout.addWidget(self.trim_widget)

        # ════════ 智能压缩 ════════
        self.check_compress = QCheckBox("智能压缩 (指定目标大小)")
        self.check_compress.stateChanged.connect(self._toggle_compress)
        layout.addWidget(self.check_compress)

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
        layout.addWidget(self.compress_widget)

        # ════════ 输出目录 ════════
        dir_group = QGroupBox("输出目录")
        dir_layout = QHBoxLayout(dir_group)
        self.combo_output = QComboBox()
        self.combo_output.addItem("与源文件同目录")
        self.combo_output.setEditable(True)
        self.combo_output.setMinimumHeight(30)
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.setMinimumHeight(30)
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_layout.addWidget(self.combo_output, 1)
        dir_layout.addWidget(self.btn_browse)
        layout.addWidget(dir_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── 分辨率 ──
    def _on_res_btn(self, clicked):
        for btn in self._res_btns.values():
            if btn is not clicked:
                btn.setChecked(False)
        if clicked.isChecked():
            self.input_resolution.blockSignals(True)
            self.input_resolution.clear()
            self.input_resolution.blockSignals(False)
        else:
            clicked.setChecked(True)

    def _clear_res_btns(self):
        if self.input_resolution.text().strip():
            for btn in self._res_btns.values():
                btn.setChecked(False)

    def _get_resolution(self) -> str:
        for label, btn in self._res_btns.items():
            if btn.isChecked():
                return label
        return self.input_resolution.text().strip()

    # ── 帧率 ──
    def _on_fps_btn(self, clicked):
        for btn in self._fps_btns.values():
            if btn is not clicked:
                btn.setChecked(False)
        if clicked.isChecked():
            self.input_fps.blockSignals(True)
            self.input_fps.clear()
            self.input_fps.blockSignals(False)
        else:
            clicked.setChecked(True)

    def _clear_fps_btns(self):
        if self.input_fps.text().strip():
            for btn in self._fps_btns.values():
                btn.setChecked(False)

    def _get_fps(self) -> str:
        for label, btn in self._fps_btns.items():
            if btn.isChecked():
                return label
        return self.input_fps.text().strip()

    # ── 质量 ──
    def _on_quality_btn(self, clicked, crf):
        for btn in self._quality_btns.values():
            if btn is not clicked:
                btn.setChecked(False)
        if clicked.isChecked():
            self.slider_quality.blockSignals(True)
            self.spin_quality.blockSignals(True)
            self.slider_quality.setValue(crf)
            self.spin_quality.setValue(crf)
            self.slider_quality.blockSignals(False)
            self.spin_quality.blockSignals(False)
        else:
            clicked.setChecked(True)

    def _on_quality_slider(self, value):
        self.spin_quality.blockSignals(True)
        self.spin_quality.setValue(value)
        self.spin_quality.blockSignals(False)
        self._sync_quality_btns(value)

    def _on_quality_spin(self, value):
        self.slider_quality.blockSignals(True)
        self.slider_quality.setValue(value)
        self.slider_quality.blockSignals(False)
        self._sync_quality_btns(value)

    def _sync_quality_btns(self, value):
        for label, btn in self._quality_btns.items():
            btn.setChecked(self._quality_presets[label] == value)

    # ── 码率 ──
    def _on_bitrate_btn(self, clicked):
        for btn in self._bitrate_btns.values():
            if btn is not clicked:
                btn.setChecked(False)
        if clicked.isChecked():
            self.input_bitrate.blockSignals(True)
            self.input_bitrate.clear()
            self.input_bitrate.blockSignals(False)
        else:
            clicked.setChecked(True)

    def _clear_bitrate_btns(self):
        if self.input_bitrate.text().strip():
            for btn in self._bitrate_btns.values():
                btn.setChecked(False)

    def _get_bitrate(self) -> str:
        for label, btn in self._bitrate_btns.items():
            if btn.isChecked():
                return label
        return self.input_bitrate.text().strip()

    # ── 预设 ──
    def _on_preset_btn(self, clicked):
        for btn in self._preset_btns.values():
            if btn is not clicked:
                btn.setChecked(False)
        if clicked.isChecked():
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentText("默认")
            self.combo_preset.blockSignals(False)
        else:
            clicked.setChecked(True)

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

    # ── 开关 ──
    def _toggle_trim(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.input_start.setEnabled(enabled)
        self.input_duration.setEnabled(enabled)

    def _toggle_compress(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.spin_compress.setEnabled(enabled)

    # ── 公开接口 ──
    def set_gpu_available(self, available: bool, gpu_name: str = ''):
        self._gpu_available = available
        self.check_gpu.setEnabled(available)
        if available:
            self.check_gpu.setText(f"启用 GPU 加速 ({gpu_name})")
        else:
            self.check_gpu.setText("GPU 加速 (不可用)")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.combo_output.setCurrentText(d)

    def is_trim_enabled(self) -> bool:
        return self.check_trim.isChecked()

    def is_compress_enabled(self) -> bool:
        return self.check_compress.isChecked()

    def get_compress_target_mb(self) -> int:
        return self.spin_compress.value()

    def get_options(self) -> ConvertOptions:
        opts = ConvertOptions()

        res_text = self._get_resolution()
        if res_text and res_text != "原图":
            alias = {"4K": "3840x2160", "1080p": "1920x1080",
                     "720p": "1280x720", "480p": "854x480"}
            res_text = alias.get(res_text, res_text)
            w, h = parse_size(res_text)
            opts.width = w
            opts.height = h

        fps_text = self._get_fps()
        if fps_text and fps_text != "原帧":
            if fps_text.isdigit():
                opts.fps = int(fps_text)

        opts.quality = self.spin_quality.value()

        br = self._get_bitrate()
        if br:
            opts.bitrate = br

        pr = self._get_preset()
        if pr:
            opts.preset = pr

        opts.use_gpu = self.check_gpu.isChecked() and self._gpu_available

        if self.check_trim.isChecked():
            start = self.input_start.text().strip()
            if start:
                opts.start_time = start
            dur = self.input_duration.text().strip()
            if dur:
                opts.trim_duration = dur

        out = self.combo_output.currentText().strip()
        if out and out != "与源文件同目录":
            opts.output_dir = out

        return opts
