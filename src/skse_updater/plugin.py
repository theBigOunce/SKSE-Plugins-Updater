"""MO2 2.5.x tool registration."""
import mobase
from PyQt6.QtGui import QIcon


class ScannerPlugin(mobase.IPluginTool):
    def __init__(self):
        super().__init__()
        self.organizer = None
        self.window = None

    def init(self, organizer):
        self.organizer = organizer
        return True

    def name(self):
        return "SKSE Plugins Updater"

    def localizedName(self):
        return self.name()

    def displayName(self):
        return self.name()

    def author(self):
        return "theBigOunce"

    def description(self):
        return "SKSE compatibility evidence and reviewed Nexus downloads with interactive MO2 installation."

    def tooltip(self):
        return self.description()

    def version(self):
        return mobase.VersionInfo(0, 4, 0)

    def settings(self):
        return []

    def icon(self):
        return QIcon()

    def display(self):
        from .mo2_adapter import live_snapshot
        from .ui import ScannerWindow
        if self.window is None:
            self.window = ScannerWindow(lambda: live_snapshot(self.organizer), self._parentWidget(),
                                        nexus_bridge_factory=self.organizer.createNexusBridge, organizer=self.organizer)
        elif not self.window.isVisible():
            self.window.start_scan()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
