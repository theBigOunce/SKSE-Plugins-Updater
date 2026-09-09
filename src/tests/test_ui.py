"""Optional Qt integration checks; skipped when PyQt6 is unavailable."""
import os
import time
import unittest
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication
    from skse_updater.ui import ScannerWindow
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from skse_updater.models import Assessment, Binary, Provider, Report, Row, Snapshot


@unittest.skipUnless(QT_AVAILABLE, "PyQt6 not available")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = ScannerWindow(lambda: Snapshot("Example", ".", "offline"))
        self.window.show()
        deadline = time.monotonic() + 5
        # Process the scheduled scan and wait for its bounded worker.
        while self.window.report is None or self.window.worker is not None:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Scan worker did not finish")
            time.sleep(0.005)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def demo(self):
        rows = []
        for name, status in (("Example Plugin", "supported"), ("Other Plugin", "incompatible")):
            values = {v: Assessment(status if v == "1.6.1170.0" else "review", "Synthetic evidence for testing") for v in
                      ("1.5.97.0", "1.6.1170.0", "1.7.99.0")}
            rows.append(Row(Provider(name, name + ".dll", "SKSE/Plugins/" + name + ".dll"),
                            Binary(sha256="demo"), values))
        from skse_updater.updates import apply_update
        rows[0].provider.mod_id = 123
        rows[0].provider.release = "1.0"
        apply_update(rows[0].provider, "2.0")
        return Report(2, "0.2.0", Snapshot("Example profile", ".", "offline"),
                      (1, 6, 1170, 0), {}, rows)

    def test_render_filter_and_details(self):
        self.window.populate(self.demo())
        self.assertEqual(self.window.table.rowCount(), 2)
        self.assertFalse(self.window.update.isEnabled())
        badges = [self.window.table.item(i, 3) for i in range(2)]
        self.assertTrue(any(item.text() == "Update (cached)" and not item.icon().isNull() for item in badges))
        self.window.search.setText("Other")
        visible = [i for i in range(2) if not self.window.table.isRowHidden(i)]
        self.assertEqual(len(visible), 1)
        self.window.table.selectRow(visible[0])
        self.assertIn("Synthetic evidence", self.window.details.toPlainText())
        self.window.search.clear()
        if os.environ.get("SKSE_TEST_SCREENSHOT"):
            self.app.processEvents()
            self.assertTrue(self.window.grab().save(os.environ["SKSE_TEST_SCREENSHOT"]))

    def test_rescan_and_empty_profile(self):
        self.assertEqual(self.window.table.rowCount(), 0)
        self.window.start_scan()
        deadline = time.monotonic() + 5
        while self.window.worker is not None:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Rescan did not finish")
            time.sleep(0.005)
        self.assertTrue(self.window.rescan.isEnabled())


    def test_live_refresh_updates_badge_without_changing_installed_release(self):
        from test_nexus import Bridge
        from skse_updater.nexus import NexusQuery
        bridge = Bridge()
        self.window.nexus = NexusQuery(lambda: bridge, self.window)
        self.window.nexus.completed.connect(self.window.nexus_completed)
        report = self.demo()
        report.rows[0].provider.game_domain = "SkyrimSE"
        self.window.populate(report)
        self.window.table.selectRow(0)
        self.assertTrue(self.window.nexus_button.isEnabled())
        self.window.check_nexus()
        self.assertFalse(self.window.nexus_button.isEnabled())
        bridge.descriptionAvailable.emit(*bridge.request, {"version": "3.0"})
        provider = self.window.report.rows[0].provider
        self.assertEqual(provider.release, "1.0")
        self.assertEqual(provider.newest_release, "3.0")
        self.assertEqual(provider.update_source, "Live Nexus check")
        self.assertEqual(self.window.table.item(0, 3).text(), "Update available")
