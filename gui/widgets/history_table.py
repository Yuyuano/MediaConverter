from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal
from pathlib import Path

from core.history import HistoryManager


class HistoryTable(QWidget):
    """历史记录表格"""
    replay_requested = pyqtSignal(dict)  # record

    def __init__(self, history_mgr: HistoryManager):
        super().__init__()
        self._history = history_mgr
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header_row.addWidget(QPushButton("刷新", clicked=self.refresh))
        self.btn_clear = QPushButton("清空历史")
        self.btn_clear.clicked.connect(self._clear_all)
        header_row.addWidget(self.btn_clear)
        header_row.addStretch()
        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "文件", "格式", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 56)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 180)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(34)
        layout.addWidget(self.table)

    def refresh(self):
        records = self._history.get_recent(20)
        self.table.setRowCount(len(records))
        for i, rec in enumerate(records):
            self.table.setItem(i, 0, QTableWidgetItem(rec.get('time', '')))
            name = Path(rec.get('file', '')).name
            self.table.setItem(i, 1, QTableWidgetItem(name))
            self.table.setItem(i, 2, QTableWidgetItem(rec.get('format', '')))

            btn_replay = QPushButton("重新转换")
            btn_replay.setFixedSize(72, 26)
            btn_replay.setStyleSheet(
                "QPushButton { padding: 0px 4px; font-size: 12px; }"
            )
            btn_replay.clicked.connect(lambda checked, r=rec: self.replay_requested.emit(r))
            btn_delete = QPushButton("删除")
            btn_delete.setFixedSize(42, 26)
            btn_delete.setStyleSheet(
                "QPushButton { padding: 0px 4px; font-size: 12px; }"
            )
            btn_delete.clicked.connect(lambda checked, row=i: self._delete_row(row))

            action_widget = QWidget()
            action_widget.setFixedHeight(30)
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.addStretch()
            action_layout.addWidget(btn_replay)
            action_layout.addWidget(btn_delete)
            action_layout.addStretch()
            self.table.setCellWidget(i, 3, action_widget)

    def _delete_row(self, row: int):
        self._history.delete_record(row)
        self.refresh()

    def _clear_all(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._history.clear_history()
            self.refresh()
