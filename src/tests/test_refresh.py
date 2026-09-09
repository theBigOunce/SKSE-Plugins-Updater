"""Regression coverage for URLs, archive variants and automatic Nexus refresh."""
import io
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from skse_updater.archives import inspect_archive
from skse_updater.models import Provider
from skse_updater.updates import mod_url
from test_core import fixture
import test_ui


class CandidateTests(unittest.TestCase):
    def test_links(self):
        provider = Provider("a", "", "", mod_id=123, game_domain="SkyrimSE")
        self.assertEqual(mod_url(provider), "https://www.nexusmods.com/skyrimspecialedition/mods/123")
        provider.nexus_url = "https://www.nexusmods.com/skyrimspecialedition/mods/456?tab=files"
        self.assertTrue(mod_url(provider).endswith("/456"))
        provider.nexus_url = "https://www.nexusmods.com.evil.test/skyrimspecialedition/mods/456"
        self.assertTrue(mod_url(provider).endswith("/123"))

    def archive(self, entries):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            for name, data in entries:
                archive.writestr(name, data)
        buffer.seek(0)
        return buffer

    def test_variants_and_fomod_no_extraction(self):
        archive = self.archive([("fomod/ModuleConfig.xml", "<config/>"),
                                ("AE/SKSE/Plugins/test.dll", fixture()),
                                ("other/helper.dll", b"invalid")])
        fomod, rows = inspect_archive(archive, (1, 6, 1170, 0))
        self.assertTrue(fomod)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][2].status, "supported")
        self.assertEqual(rows[1][2].status, "review")
        self.assertEqual(len(rows[0][1]), 64)

    def test_unsafe_paths(self):
        for name in ("../a.dll", "x/../../a.dll", "C:/a.dll", r"x\\..\\a.dll"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_archive(self.archive([(name, b"x")]), (1, 6, 1170, 0))


@unittest.skipUnless(test_ui.QT_AVAILABLE, "PyQt6 unavailable")
class RefreshTests(unittest.TestCase):
    setUpClass = test_ui.WindowTests.__dict__["setUpClass"]
    setUp = test_ui.WindowTests.setUp
    tearDown = test_ui.WindowTests.tearDown
    demo = test_ui.WindowTests.demo

    def prepare(self):
        from test_nexus import Bridge
        from skse_updater.nexus import NexusQuery
        bridge = Bridge()
        self.window.nexus = NexusQuery(lambda: bridge, self.window)
        self.window.nexus.completed.connect(self.window.nexus_completed)
        report = self.demo()
        for row in report.rows:
            row.provider.mod_id = 123
            row.provider.game_domain = "SkyrimSE"
        self.window.populate(report)
        return bridge, report

    def test_batch_deduplicates_and_preserves_selection(self):
        bridge, report = self.prepare()
        self.window.table.selectRow(1)
        self.window.refresh_all()
        self.assertEqual(self.window.refresh_total, 1)
        bridge.descriptionAvailable.emit(*bridge.request, {"version": "3.0"})
        self.assertEqual(self.window.table.currentRow(), 1)
        self.assertTrue(all(r.provider.newest_release == "3.0" for r in report.rows))
        self.assertFalse(self.window.refresh_queue)

    def test_rescan_starts_network_and_discards_old_callback(self):
        import time
        bridge, report = self.prepare()
        self.window.refresh_all()
        old = bridge.request
        with patch("skse_updater.ui.scan", return_value=report):
            self.window.start_scan()
            deadline = time.monotonic() + 5
            while self.window.worker is not None:
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.005)
        self.assertNotEqual(old, bridge.request)
        bridge.descriptionAvailable.emit(*old, {"version": "99.0"})
        self.assertNotEqual(report.rows[0].provider.newest_release, "99.0")
        bridge.descriptionAvailable.emit(*bridge.request, {"version": "4.0"})
        self.assertEqual(report.rows[0].provider.newest_release, "4.0")

    def test_double_click_name_only(self):
        bridge, report = self.prepare()
        with patch("skse_updater.ui.QDesktopServices.openUrl") as opened:
            self.window.open_mod(0, 1)
            opened.assert_not_called()
            self.window.open_mod(0, 0)
            self.assertTrue(opened.call_args.args[0].toString().endswith("/123"))

    def test_failure_is_visible_and_preserves_cache(self):
        bridge, report = self.prepare()
        old = report.rows[0].provider.newest_release
        self.window.refresh_all()
        self.window.nexus.finish(error="Connection unavailable")
        self.assertEqual(report.rows[0].provider.newest_release, old)
        self.assertEqual(self.window.table.item(0, 3).text(), "Check failed (cached)")

    def test_initial_launch_starts_refresh(self):
        import time
        from skse_updater.ui import ScannerWindow
        bridge, report = self.prepare()
        self.window.close()
        self.window.deleteLater()
        with patch("skse_updater.ui.scan", return_value=report):
            self.window = ScannerWindow(lambda: report.snapshot, nexus_bridge_factory=lambda: bridge)
            self.window.show()
            deadline = time.monotonic() + 5
            while self.window.report is None or self.window.worker is not None:
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.005)
        self.assertIsNotNone(self.window.nexus.pending)
        bridge.descriptionAvailable.emit(*bridge.request, {"version": "5.0"})
        self.assertEqual(report.rows[0].provider.newest_release, "5.0")

    def test_archive_worker_and_network_do_not_erase_preview(self):
        import time
        import tempfile
        from pathlib import Path
        bridge, report = self.prepare()
        self.window.refresh_all()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("SKSE/Plugins/test.dll", fixture())
            with patch("skse_updater.ui.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                self.window.inspect_zip()
            deadline = time.monotonic() + 5
            while self.window.worker is not None:
                self.app.processEvents()
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.005)
            before = self.window.details.toPlainText()
            self.assertIn("SHA-256:", before)
            bridge.descriptionAvailable.emit(*bridge.request, {"version": "3.0"})
            self.assertEqual(self.window.details.toPlainText(), before)
