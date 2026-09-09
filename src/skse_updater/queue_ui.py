"""Review exact Nexus files before handing user-approved work to MO2."""
from pathlib import Path
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                            QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                            QCheckBox, QFileDialog, QAbstractItemView)
from .install_queue import FileLookup, InstallQueue, file_id_from_link
from .updates import nexus_game
from .models import version_text
from .runtime import file_version


class QueueWindow(QDialog):
    def __init__(self, organizer, report, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Nexus files and MO2 install queue")
        self.resize(1080, 580)
        self.organizer = organizer
        self.report = report
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.controller = InstallQueue(organizer, self)
        self.context = (report.snapshot.profile, str(Path(report.snapshot.game_path).resolve()).casefold(), report.runtime)
        self.controller.context_valid = self.context_valid
        self.lookup = FileLookup(organizer.createNexusBridge, self)
        self.lookup.completed.connect(self.lookup_completed)
        self.candidate = None
        layout = QVBoxLayout(self)
        self.environment = QLabel(f"Profile: {report.snapshot.profile} | Skyrim: {version_text(report.runtime)}\n"
                       "Choose the exact file supporting this runtime. MO2 handles downloads and every installer prompt.")
        self.environment.setTextFormat(Qt.TextFormat.PlainText)
        self.environment.setWordWrap(True)
        layout.addWidget(self.environment)
        controls = QHBoxLayout()
        self.mods = QComboBox()
        seen = set()
        for row in report.rows:
            p = row.provider
            key = (p.mod, p.mod_id)
            if p.managed and p.mod_id and nexus_game(p.game_domain) and key not in seen:
                seen.add(key)
                self.mods.addItem(p.mod, p)
        controls.addWidget(self.mods, 1)
        self.website = QPushButton("Open Nexus files")
        self.website.clicked.connect(self.open_files)
        controls.addWidget(self.website)
        self.link = QLineEdit()
        self.link.setPlaceholderText("Exact file ID or Nexus URL containing file_id")
        controls.addWidget(self.link, 2)
        self.find = QPushButton("Look up file")
        self.find.clicked.connect(self.find_file)
        controls.addWidget(self.find)
        layout.addLayout(controls)
        self.info = QLabel("File compatibility is not established by the Nexus page version or file name.")
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        row = QHBoxLayout()
        self.reviewed = QCheckBox("I reviewed this file for the target runtime (including any FOMOD choices)")
        row.addWidget(self.reviewed)
        self.add = QPushButton("Add reviewed file")
        self.add.clicked.connect(self.add_file)
        row.addWidget(self.add)
        layout.addLayout(row)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Existing mod name", "Nexus file ID", "File / version", "State", "Archive"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.remove = QPushButton("Remove selected")
        self.remove.clicked.connect(self.remove_entry)
        self.attach = QPushButton("Attach completed MO2 download")
        self.attach.clicked.connect(self.attach_entry)
        self.start = QPushButton("Download, then open MO2 installers / Resume")
        self.start.clicked.connect(self.controller.start)
        self.stop = QPushButton("Pause queue")
        self.stop.clicked.connect(lambda: self.controller.pause())
        for button in (self.remove, self.attach, self.start, self.stop):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel("Each MO2 installer runs to completion before the next opens. Cancel/failure pauses the queue.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.controller.notice.connect(self.status.setText)
        self.controller.changed.connect(self.render)
        self.reviewed.toggled.connect(self.update_controls)
        self.mods.currentIndexChanged.connect(self.invalidate_candidate)
        self.link.textChanged.connect(self.invalidate_candidate)
        self.render()

    def reset_report(self, report):
        if self.controller.entries or self.controller.active or self.controller.installing:
            return
        self.lookup.cancel()
        self.report = report
        self.context = (report.snapshot.profile, str(Path(report.snapshot.game_path).resolve()).casefold(), report.runtime)
        self.environment.setText(f"Profile: {report.snapshot.profile} | Skyrim: {version_text(report.runtime)}")
        self.mods.clear()
        seen = set()
        for row in report.rows:
            p = row.provider
            key = (p.mod, p.mod_id)
            if p.managed and p.mod_id and nexus_game(p.game_domain) and key not in seen:
                seen.add(key)
                self.mods.addItem(p.mod, p)
        self.invalidate_candidate()

    def context_valid(self):
        game = self.organizer.managedGame()
        path = Path(game.gameDirectory().absolutePath())
        return (self.context[2] is not None and nexus_game(game.gameShortName()) is not None and
                (self.organizer.profileName(), str(path.resolve()).casefold(), file_version(path / "SkyrimSE.exe")) == self.context)

    def invalidate_candidate(self, *args):
        self.lookup.cancel()
        self.candidate = None
        self.reviewed.setChecked(False)
        self.info.setText("Look up the selected file; compatibility requires your review.")
        self.update_controls()

    def open_files(self):
        p = self.mods.currentData()
        if p:
            QDesktopServices.openUrl(QUrl(f"https://www.nexusmods.com/skyrimspecialedition/mods/{p.mod_id}?tab=files"))

    def find_file(self):
        p = self.mods.currentData()
        if not p:
            return
        try:
            file_id = file_id_from_link(self.link.text(), p.mod_id)
            self.candidate = None
            self.reviewed.setChecked(False)
            self.lookup.request(p, file_id)
            self.update_controls()
        except ValueError as exc:
            self.info.setText(str(exc))

    def lookup_completed(self, entry, error):
        self.candidate = entry
        self.reviewed.setChecked(False)
        self.info.setText(error if error else f"File {entry.file_id}: {entry.name} | Version: {entry.version}\n"
                          f"{entry.filename}\nCompatibility unverified: check the author requirements and FOMOD branches.")
        self.update_controls()

    def add_file(self):
        if not self.candidate or not self.reviewed.isChecked() or self.controller.active:
            return
        if any(e.mod == self.candidate.mod for e in self.controller.entries):
            self.status.setText("This installed mod already has a queued file. Remove it before choosing another.")
            return
        self.controller.entries.append(self.candidate)
        self.invalidate_candidate()
        self.render()

    def selected_entry(self):
        index = self.table.currentRow()
        return self.controller.entries[index] if 0 <= index < len(self.controller.entries) else None

    def remove_entry(self):
        entry = self.selected_entry()
        if entry and not self.controller.active and not self.controller.installing:
            self.controller.entries.remove(entry)
            self.render()

    def attach_entry(self):
        entry = self.selected_entry()
        if not entry:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select completed MO2 download with .meta sidecar", "",
                                             "Mod archives (*.zip *.7z *.rar)")
        if path:
            try:
                self.controller.attach(entry, path)
            except Exception as exc:
                self.status.setText(str(exc))

    def update_controls(self, *args):
        busy = self.controller.active or self.controller.installing
        self.add.setEnabled(bool(self.candidate and self.reviewed.isChecked() and not busy))
        self.find.setEnabled(not busy and self.lookup.pending is None)
        self.mods.setEnabled(not busy)
        self.link.setEnabled(not busy)
        self.reviewed.setEnabled(not busy)
        self.start.setEnabled(bool(self.controller.entries) and not busy and self.lookup.pending is None)
        self.remove.setEnabled(not busy)
        self.attach.setEnabled(not busy)
        self.stop.setEnabled(busy)

    def render(self):
        selected = self.table.currentRow()
        self.table.setRowCount(len(self.controller.entries))
        for index, entry in enumerate(self.controller.entries):
            for column, text in enumerate((entry.mod, str(entry.file_id), entry.name + " / " + entry.version, entry.state, entry.path)):
                self.table.setItem(index, column, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        if selected >= 0:
            self.table.selectRow(selected)
        self.update_controls()

    def reject(self):
        self.lookup.cancel()
        self.controller.pause()
        if not self.controller.installing:
            super().reject()

    def closeEvent(self, event):
        self.lookup.cancel()
        self.controller.pause()
        if self.controller.installing:
            event.ignore()
        else:
            super().closeEvent(event)
