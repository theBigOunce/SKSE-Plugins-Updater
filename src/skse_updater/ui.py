"""Single-page Qt scan window. No installation or network side effects."""
from collections import Counter
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                             QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QHeaderView, QAbstractItemView)

from .models import version_text
from .scanner import scan

COLORS = {"supported": "#70c795", "incompatible": "#fa8585", "review": "#e6bd68",
          "shadowed": "#a4aebc", "helper": "#a4aebc"}
LABELS = {"supported": "Supported*", "incompatible": "Incompatible", "review": "Review",
          "shadowed": "Shadowed", "helper": "Helper"}


class ScanThread(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, snapshot, parent):
        super().__init__(parent)
        self.snapshot = snapshot

    def run(self):
        try:
            self.result.emit(scan(self.snapshot, self.progress.emit, self.isInterruptionRequested))
        except Exception as exc:
            self.failed.emit(str(exc))


class ScannerWindow(QDialog):
    def __init__(self, snapshot_factory, parent=None):
        super().__init__(parent)
        self.factory = snapshot_factory
        self.worker = None
        self.report = None
        self.setWindowTitle("SKSE Plugins Updater — Read-only preview")
        self.resize(1240, 780)
        layout = QVBoxLayout(self)
        self.heading = QLabel("SKSE Plugins Updater")
        self.heading.setStyleSheet("font-size:22px;font-weight:600")
        layout.addWidget(self.heading)
        self.environment = QLabel("Preparing environment scan…")
        self.environment.setTextFormat(Qt.TextFormat.PlainText)
        self.environment.setWordWrap(True)
        layout.addWidget(self.environment)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by mod, DLL, or status")
        self.search.textChanged.connect(self.filter_rows)
        controls.addWidget(self.search)
        self.rescan = QPushButton("Rescan")
        self.rescan.clicked.connect(self.start_scan)
        controls.addWidget(self.rescan)
        self.update = QPushButton("Update selected (planned)")
        self.update.setEnabled(False)
        self.update.setToolTip("Archive verification, backups and reviewed installation are not implemented yet.")
        controls.addWidget(self.update)
        layout.addLayout(controls)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table, 3)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select a DLL to inspect its origin and compatibility evidence.")
        layout.addWidget(self.details, 1)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.summary = QLabel("No files will be installed or modified.")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        QTimer.singleShot(0, self.start_scan)

    def start_scan(self):
        if self.worker is not None:
            return
        self.rescan.setEnabled(False)
        self.summary.setText("Capturing profile…")
        try:
            snapshot = self.factory()
        except Exception as exc:
            self.failed(str(exc))
            self.rescan.setEnabled(True)
            return
        self.progress.setRange(0, 0)
        self.worker = ScanThread(snapshot, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(self.populate)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def on_progress(self, value, total):
        self.progress.setRange(0, total)
        self.progress.setValue(value)

    def worker_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.rescan.setEnabled(True)

    def failed(self, message):
        self.summary.setText("Scan failed: " + message)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def populate(self, report):
        self.report = report
        self.progress.setRange(0, max(1, len(report.rows)))
        self.progress.setValue(max(1, len(report.rows)))
        current = version_text(report.runtime)
        root = "Root-managed SKSE candidates; effective mapping unverified" if report.snapshot.root_candidates else "SKSE components: " + (", ".join(report.skse_components.values()) or "Not found")
        self.environment.setText(f"Profile: {report.snapshot.profile}   |   Skyrim: {current}   |   {root}\n"
                                 f"Address Library: {len(report.snapshot.databases)} database files (encoding not yet verified)   |   {report.snapshot.mode}")
        targets = list(report.rows[0].assessments) if report.rows else []
        headers = ["Mod", "DLL", "Installed release", "Your game"] + [v.removesuffix(".0") for v in targets]
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(report.rows))
        for index, row in enumerate(report.rows):
            texts = [row.provider.mod, Path(row.provider.path).name, row.provider.release or "Unknown"]
            for column, value in enumerate(texts):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.table.setItem(index, column, item)
            for column, target in enumerate([current] + targets, start=3):
                status = row.assessments.get(target)
                item = QTableWidgetItem(LABELS[status.status] if status else "Unknown runtime")
                item.setData(Qt.ItemDataRole.UserRole, index)
                if status:
                    light = self.table.palette().base().color().lightness() > 128
                    colors = {"supported": "#107a45", "incompatible": "#b42318", "review": "#8a5800", "shadowed": "#5c6777", "helper": "#5c6777"} if light else COLORS
                    item.setForeground(QColor(colors[status.status]))
                    item.setToolTip(status.reason)
                self.table.setItem(index, column, item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 240)
        for column in range(2, len(headers)):
            self.table.setColumnWidth(column, 125)
        self.table.setSortingEnabled(True)
        counts = Counter(row.assessments[current].status for row in report.rows if current in row.assessments)
        self.summary.setText(f"{len(report.rows)} DLL providers: " + ", ".join(f"{n} {s}" for s, n in counts.items()) +
                             ".  *Supported means declared runtime support, not verified load or save compatibility.")
        self.details.setPlainText("\n".join(report.snapshot.warnings) or "Select a row for evidence.")
        self.filter_rows()

    def filter_rows(self):
        needle = self.search.text().casefold()
        for index in range(self.table.rowCount()):
            text = " ".join(self.table.item(index, col).text() for col in range(self.table.columnCount()))
            self.table.setRowHidden(index, needle not in text.casefold())

    def show_details(self):
        items = self.table.selectedItems()
        if not items or not self.report:
            return
        row = self.report.rows[items[0].data(Qt.ItemDataRole.UserRole)]
        lines = [f"File: {row.provider.path}", f"SHA-256: {row.binary.sha256}",
                 f"Nexus mod ID: {row.provider.mod_id or 'Unknown'}",
                 "CommonLib variant/version: not established by static metadata"]
        declaration = row.binary.declaration
        if declaration:
            lines.extend([f"Plugin: {declaration.name}; raw version: {declaration.plugin_version:#x}",
                          f"Independence flags: {declaration.flags:#x}; extended flags: {declaration.flags_ex:#x}",
                          f"Minimum SKSE (packed): {declaration.minimum_skse:#x}"])
        lines.extend(f"{target}: {value.reason}" for target, value in row.assessments.items())
        if self.report.snapshot.root_candidates:
            lines.append("SKSE root candidates (file resource versions; mapping unverified):")
            lines.extend(f"{path}: {version}" for path, version in self.report.skse_components.items())
        self.details.setPlainText("\n".join(lines))

    def reject(self):
        if self.worker is not None:
            self.worker.requestInterruption()
            self.summary.setText("Canceling scan; close again when it finishes.")
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.requestInterruption()
            event.ignore()
        else:
            super().closeEvent(event)
