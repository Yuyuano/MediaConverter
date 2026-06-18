from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView
from PyQt6.QtCore import pyqtSignal

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
        header_row.addStretch()
        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["时间", "文件", "格式", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self):
        records = self._history.get_recent(10)
        self.table.setRowCount(len(records))
        for i, rec in enumerate(records):
            self.table.setItem(i, 0, QTableWidgetItem(rec.get('time', '')))
            from pathlib import Path
            name = Path(rec.get('file', '')).name
            self.table.setItem(i, 1, QTableWidgetItem(name))
            self.table.setItem(i, 2, QTableWidgetItem(rec.get('format', '')))
            btn = QPushButton("重新转换")
            btn.clicked.connect(lambda checked, r=rec: self.replay_requested.emit(r))
            self.table.setCellWidget(i, 3, btn)
