"""Correlated, in-memory Nexus metadata refresh through MO2's existing login."""
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .updates import nexus_game, utc_now


class NexusQuery(QObject):
    completed = pyqtSignal(object)

    def __init__(self, bridge_factory, parent=None):
        super().__init__(parent)
        self.factory = bridge_factory
        self.bridge = None
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.finish(error="Nexus metadata request timed out"))

    def request(self, provider):
        if self.pending:
            return False
        game = nexus_game(provider.game_domain)
        if not provider.mod_id or not game:
            return False
        if self.bridge is None:
            self.bridge = self.factory()
            self.bridge.descriptionAvailable.connect(self.on_description)
            self.bridge.requestFailed.connect(self.on_error)
        token = uuid.uuid4().hex
        self.pending = (game, provider.mod_id, token)
        self.timer.start(30000)
        try:
            self.bridge.requestDescription(game, provider.mod_id, token)
        except Exception:
            self.finish(error="Could not request Nexus metadata through MO2")
        return True

    def matches(self, game, mod_id, token):
        return self.pending == (game, mod_id, token)

    def on_description(self, game, mod_id, token, payload):
        if not self.matches(game, mod_id, token):
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
            self.finish(error="Nexus returned no usable mod version")
            return
        self.finish(version=payload["version"][:128])

    def on_error(self, game, mod_id, file_id, token, code, message):
        if self.matches(game, mod_id, token):
            # Don't copy arbitrary network messages/URLs into reports; they may contain tokens.
            self.finish(error=f"Nexus request failed ({code}); check the MO2 connection")

    def finish(self, version=None, error=""):
        if self.pending is None:
            return
        game, mod_id, token = self.pending
        self.pending = None
        self.timer.stop()
        self.completed.emit({"game": game, "mod_id": mod_id, "version": version,
                             "error": error, "checked_at": utc_now()})

    def cancel(self):
        # Requests can still complete in MO2; the correlation token rejects stale callbacks.
        self.pending = None
        self.timer.stop()
