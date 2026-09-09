"""User-reviewed Nexus downloads followed by synchronous MO2 installer handoffs."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import re
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from .inventory import ini
from .updates import nexus_game

DOMAIN = "skyrimspecialedition"


def file_id_from_link(value, mod_id):
    value = value.strip()
    if re.fullmatch(r"[1-9][0-9]{0,9}", value):
        return int(value)
    url = urlsplit(value)
    if (url.scheme != "https" or url.hostname not in ("www.nexusmods.com", "nexusmods.com")
            or url.username or url.password or url.port not in (None, 443)
            or url.path.rstrip("/") != f"/{DOMAIN}/mods/{mod_id}"):
        raise ValueError("Use a public Skyrim SE Nexus file URL for the selected mod, or its file ID.")
    ids = parse_qs(url.query).get("file_id", [])
    if len(ids) != 1 or not re.fullmatch(r"[1-9][0-9]{0,9}", ids[0]):
        raise ValueError("The URL needs an exact file_id; a mod page alone does not select a download.")
    return int(ids[0])


@dataclass
class QueueEntry:
    mod: str
    mod_id: int
    file_id: int
    name: str
    version: str
    filename: str
    state: str = "Queued"
    path: str = ""


class FileLookup(QObject):
    completed = pyqtSignal(object, str)

    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory, self.bridge, self.pending = factory, None, None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.finish(None, "File lookup timed out; check MO2's Nexus connection."))

    def request(self, provider, file_id):
        if self.pending:
            return
        self.pending = (provider.mod, provider.mod_id, file_id, uuid.uuid4().hex)
        self.timer.start(30000)
        try:
            if self.bridge is None:
                self.bridge = self.factory()
                self.bridge.fileInfoAvailable.connect(self.received)
                self.bridge.requestFailed.connect(self.failed)
            self.bridge.requestFileInfo(DOMAIN, provider.mod_id, file_id, self.pending[3])
        except Exception:
            self.finish(None, "MO2 file lookup is unavailable.")

    def received(self, game, mod_id, file_id, token, payload):
        if not self.pending or (nexus_game(game), mod_id, file_id, token) != (DOMAIN, *self.pending[1:]):
            return
        try:
            if not isinstance(payload, dict) or payload.get("file_id") != file_id:
                raise ValueError()
            filename = payload["file_name"]
            if not isinstance(filename, str) or len(filename) > 512 or Path(filename).suffix.lower() not in (".zip", ".7z", ".rar"):
                raise ValueError()
            entry = QueueEntry(self.pending[0], mod_id, file_id, str(payload.get("name", ""))[:512],
                               str(payload.get("version", ""))[:128], filename)
            self.finish(entry, "")
        except (KeyError, TypeError, ValueError):
            self.finish(None, "Nexus did not return a matching supported archive file.")

    def failed(self, game, mod_id, file_id, token, code, message):
        if self.pending and (nexus_game(game), mod_id, file_id, token) == (DOMAIN, *self.pending[1:]):
            self.finish(None, f"Nexus file lookup failed ({code}); check MO2.")

    def finish(self, entry, error):
        self.pending = None
        self.timer.stop()
        self.completed.emit(entry, error)

    def cancel(self):
        self.pending = None
        self.timer.stop()


def matching_archive(path, entry):
    """Never trust a mutable download-row index as archive identity."""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in (".zip", ".7z", ".rar") or path.stat().st_size == 0:
        return False
    return matching_identity(path, entry)


def matching_identity(path, entry):
    metadata = ini(Path(str(path) + ".meta"))
    section = metadata["General"] if metadata.has_section("General") else {}
    return (nexus_game(section.get("gameName", "")) == DOMAIN
            and section.get("modID") == str(entry.mod_id)
            and section.get("fileID") == str(entry.file_id))


class InstallQueue(QObject):
    changed = pyqtSignal()
    notice = pyqtSignal(str)

    def __init__(self, organizer, parent=None):
        super().__init__(parent)
        self.organizer = organizer
        self.manager = organizer.downloadManager()
        self.entries = []
        self.context_valid = lambda: True
        self.active = False
        self.installing = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self.pause("Download timed out. Finish it in MO2, then attach the completed archive."))
        if self.manager.onDownloadComplete(self.download_complete) is False:
            raise RuntimeError("MO2 download completion callback unavailable")
        for name in ("onDownloadFailed", "onDownloadPaused", "onDownloadRemoved"):
            method = getattr(self.manager, name, None)
            if callable(method):
                method(self.download_problem)

    def start(self):
        if self.active or self.installing or not self.entries:
            return
        self.active = True
        self.notice.emit("Downloading reviewed files; installers open after all downloads finish.")
        self.changed.emit()
        self.timer.start(0)

    def pause(self, message="Queue paused. Existing MO2 downloads may continue; no further installer will open."):
        self.active = False
        self.timer.stop()
        self.timeout.stop()
        self.notice.emit(message)
        self.changed.emit()

    def advance(self):
        if not self.active or self.installing:
            return
        try:
            valid = self.context_valid()
        except Exception:
            valid = False
        if not valid:
            self.pause("The profile, game or runtime changed. Return to the reviewed environment, or clear the queue and rescan.")
            return
        if any(e.state == "Downloading" for e in self.entries):
            self.timeout.start(1800000)
            return
        entry = next((e for e in self.entries if e.state == "Queued"), None)
        if entry:
            entry.state = "Downloading"
            self.changed.emit()
            self.timeout.start(1800000)
            try:
                if self.manager.startDownloadNexusFile(entry.mod_id, entry.file_id) < 0:
                    raise ValueError()
            except Exception:
                entry.state = "Queued"
                self.pause("MO2 could not start this download. Use the Nexus website, then attach the completed archive.")
            return
        entry = next((e for e in self.entries if e.state == "Ready"), None)
        if entry is None:
            self.pause("Queue complete. Rescan the active profile to check the installed DLLs.")
            return
        try:
            if not matching_archive(entry.path, entry):
                raise ValueError()
        except Exception:
            entry.state = "Queued"
            entry.path = ""
            self.pause("Archive identity changed or is unavailable. Download or attach it again.")
            return
        self.installing = True
        entry.state = "Installing"
        self.changed.emit()
        try:
            installed = self.organizer.installMod(entry.path, entry.mod)
            entry.state = "Installed" if installed is not None else "Ready"
        except Exception:
            installed = None
            entry.state = "Ready"
        finally:
            self.installing = False
        if installed is None:
            self.pause("MO2 canceled or failed the installation. Resume to retry, or remove this item.")
        else:
            self.changed.emit()
            if self.active:
                self.timer.start(1000)

    def download_problem(self, download_id):
        if not self.active:
            return
        try:
            path = self.manager.downloadPath(download_id)
            if any(e.state == "Downloading" and matching_identity(path, e) for e in self.entries):
                self.pause("Download paused, removed or failed in MO2. Resolve it there, or attach the completed archive.")
        except Exception:
            return

    def download_complete(self, download_id):
        try:
            path = self.manager.downloadPath(download_id)
            for entry in self.entries:
                if entry.state in ("Queued", "Downloading") and matching_archive(path, entry):
                    entry.path = str(Path(path).resolve())
                    was_downloading = entry.state == "Downloading"
                    entry.state = "Ready"
                    if was_downloading:
                        self.timeout.stop()
                    self.changed.emit()
            if self.active:
                self.timer.start(0)
        except Exception:
            # Callbacks from unrelated downloads must never affect the queue.
            return

    def attach(self, entry, path):
        if self.active or self.installing:
            raise ValueError("Pause the queue before attaching a file.")
        if not matching_archive(path, entry):
            raise ValueError("Archive needs a matching MO2 .meta sidecar with this Nexus game, mod ID and file ID.")
        entry.path = str(Path(path).resolve())
        entry.state = "Ready"
        self.changed.emit()
