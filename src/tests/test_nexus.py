"""Nexus bridge signal and request-lifecycle tests; no actual network requests."""
import unittest
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication
    from skse_updater.nexus import NexusQuery
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
from skse_updater.models import Provider

if QT_AVAILABLE:
    class Bridge(QObject):
        descriptionAvailable = pyqtSignal(str, int, object, object)
        requestFailed = pyqtSignal(str, int, int, object, int, str)

        def requestDescription(self, game, mod_id, token):
            self.request = (game, mod_id, token)


@unittest.skipUnless(QT_AVAILABLE, "PyQt6 not available")
class NexusTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.bridge = Bridge()
        self.query = NexusQuery(lambda: self.bridge)
        self.results = []
        self.query.completed.connect(self.results.append)
        self.provider = Provider("Example", "Example.dll", "Example.dll",
                                 release="1.0", mod_id=12, game_domain="SkyrimSE")

    def tearDown(self):
        self.query.cancel()

    def test_matching_result(self):
        self.assertTrue(self.query.request(self.provider))
        self.bridge.descriptionAvailable.emit(*self.bridge.request, {"version": "2.0", "irrelevant": "ignored"})
        self.assertEqual(self.results[0]["version"], "2.0")
        self.assertNotIn("irrelevant", self.results[0])
        self.assertIsNone(self.query.pending)

    def test_stale_result_ignored(self):
        self.query.request(self.provider)
        old = self.bridge.request
        self.query.cancel()
        self.query.request(self.provider)
        self.bridge.descriptionAvailable.emit(*old, {"version": "2.0"})
        self.assertEqual(self.results, [])

    def test_second_concurrent_request_refused(self):
        self.query.request(self.provider)
        self.assertFalse(self.query.request(self.provider))

    def test_failure_omits_raw_message(self):
        self.query.request(self.provider)
        game, mod, token = self.bridge.request
        self.bridge.requestFailed.emit(game, mod, 0, token, 403, "sensitive-url")
        self.assertNotIn("sensitive-url", self.results[0]["error"])

    def test_bad_payload(self):
        self.query.request(self.provider)
        self.bridge.descriptionAvailable.emit(*self.bridge.request, {})
        self.assertTrue(self.results[0]["error"])

    def test_timeout(self):
        self.query.request(self.provider)
        self.query.timer.timeout.emit()
        self.assertIn("timed out", self.results[0]["error"])
        self.assertIsNone(self.query.pending)
