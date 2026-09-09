"""MO2 contract tests use synthetic archives; no real download or installation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QObject, pyqtSignal
    from skse_updater.install_queue import InstallQueue, QueueEntry, FileLookup, file_id_from_link
    QT = True
except ImportError:
    QT = False


if QT:
    class Bridge(QObject):
        fileInfoAvailable = pyqtSignal(str, int, int, object, object)
        requestFailed = pyqtSignal(str, int, int, object, int, str)

        def requestFileInfo(self, *args):
            self.request = args


class Downloads:
    def __init__(self):
        self.paths = {}
        self.started = []

    def onDownloadComplete(self, callback):
        self.complete = callback
        return True

    def startDownloadNexusFile(self, mod_id, file_id):
        self.started.append((mod_id, file_id))
        return 0

    def downloadPath(self, index):
        return self.paths[index]


@unittest.skipUnless(QT, "Qt unavailable")
class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = Downloads()
        self.organizer = Mock()
        self.organizer.downloadManager.return_value = self.manager
        self.organizer.installMod.return_value = object()
        self.queue = InstallQueue(self.organizer)
        self.queue.entries = [QueueEntry("Existing mod", 123, 456, "New file", "2", "a.7z"),
                              QueueEntry("Second mod", 789, 999, "Other file", "3", "b.zip")]

    def tearDown(self):
        self.queue.pause()
        self.queue.deleteLater()
        self.temp.cleanup()

    def archive(self, entry, index=1, file_id=None):
        path = Path(self.temp.name) / f"archive{index}.7z"
        path.write_bytes(b"synthetic archive: never extracted")
        Path(str(path) + ".meta").write_text(
            f"[General]\ngameName=SkyrimSE\nmodID={entry.mod_id}\nfileID={file_id or entry.file_id}\n", encoding="utf-8")
        self.manager.paths[index] = str(path)
        return str(path)

    def advance(self):
        self.queue.timer.stop()
        self.queue.advance()

    def test_download_all_before_first_installer_and_wait_for_return(self):
        self.queue.start()
        self.advance()
        self.assertEqual(self.manager.started, [(123, 456)])
        self.archive(self.queue.entries[0], 10)
        self.manager.complete(10)  # Different from the guessed start row 0.
        self.advance()
        self.organizer.installMod.assert_not_called()
        self.assertEqual(self.manager.started[-1], (789, 999))
        self.archive(self.queue.entries[1], 20)
        self.manager.complete(20)
        def install(path, name):
            self.assertTrue(self.queue.installing)
            self.advance()  # Simulate reentrant Qt event processing inside a FOMOD.
            self.assertEqual(self.organizer.installMod.call_count, 1)
            return object()
        self.organizer.installMod.side_effect = install
        self.advance()
        self.assertEqual(self.organizer.installMod.call_args.args[1], "Existing mod")
        self.assertEqual(self.queue.entries[0].state, "Installed")
        self.organizer.installMod.side_effect = None
        self.advance()
        self.assertEqual(self.organizer.installMod.call_count, 2)

    def test_unrelated_download_never_installed(self):
        self.queue.start()
        self.advance()
        self.archive(self.queue.entries[0], 0, file_id=111)
        self.manager.complete(0)
        self.advance()
        self.assertEqual(self.queue.entries[0].state, "Downloading")
        self.organizer.installMod.assert_not_called()

    def test_cancel_in_mo2_pauses_remaining(self):
        for i, entry in enumerate(self.queue.entries):
            self.queue.attach(entry, self.archive(entry, i))
        self.organizer.installMod.return_value = None
        self.queue.start()
        self.advance()
        self.assertFalse(self.queue.active)
        self.assertEqual(self.queue.entries[0].state, "Ready")
        self.advance()
        self.assertEqual(self.organizer.installMod.call_count, 1)

    def test_profile_change_blocks_both_download_and_install(self):
        self.queue.context_valid = lambda: False
        self.queue.start()
        self.advance()
        self.assertFalse(self.queue.active)
        self.assertEqual(self.manager.started, [])

    def test_close_pause_ignores_late_install_scheduling(self):
        self.queue.start()
        self.advance()
        self.queue.pause()
        self.archive(self.queue.entries[0])
        self.manager.complete(1)
        self.advance()
        self.assertEqual(self.queue.entries[0].state, "Ready")
        self.organizer.installMod.assert_not_called()

    def test_attach_requires_matching_metadata(self):
        entry = self.queue.entries[0]
        with self.assertRaises(ValueError):
            self.queue.attach(entry, self.archive(entry, file_id=12))

    def test_recheck_archive_before_install(self):
        entry = self.queue.entries[0]
        self.queue.entries = [entry]
        path = self.archive(entry)
        self.queue.attach(entry, path)
        Path(str(path) + ".meta").write_text("[General]\nmodID=12\n", encoding="utf-8")
        self.queue.start()
        self.advance()
        self.assertFalse(self.queue.active)
        self.organizer.installMod.assert_not_called()

    def test_exact_link_validation(self):
        self.assertEqual(file_id_from_link("456", 123), 456)
        self.assertEqual(file_id_from_link("https://www.nexusmods.com/skyrimspecialedition/mods/123?tab=files&file_id=456",123),456)
        for link in ("https://www.nexusmods.com/skyrimspecialedition/mods/999?file_id=456",
                     "https://evil.test/skyrimspecialedition/mods/123?file_id=456",
                     "https://www.nexusmods.com/skyrimspecialedition/mods/123", "-1"):
            with self.subTest(link=link), self.assertRaises(ValueError):
                file_id_from_link(link, 123)

    def test_file_lookup_stale_and_mismatched_results(self):
        from skse_updater.models import Provider
        bridge = Bridge()
        lookup = FileLookup(lambda: bridge)
        result = []
        lookup.completed.connect(lambda entry, error: result.append((entry, error)))
        p = Provider("Existing", "", "", mod_id=123, game_domain="SkyrimSE")
        lookup.request(p, 456)
        old = bridge.request
        lookup.cancel()
        lookup.request(p, 789)
        bridge.fileInfoAvailable.emit(*old, {"file_id":456,"file_name":"a.7z"})
        self.assertFalse(result)
        bridge.fileInfoAvailable.emit(*bridge.request, {"file_id":789,"file_name":"a.7z","version":"2"})
        self.assertEqual(result[0][0].file_id,789)
        lookup.deleteLater()

    def test_matching_download_failure_pauses_queue(self):
        self.queue.start()
        self.advance()
        self.archive(self.queue.entries[0], 33)
        self.queue.download_problem(33)
        self.assertFalse(self.queue.active)
        self.organizer.installMod.assert_not_called()

    def test_queue_review_ui(self):
        from skse_updater.queue_ui import QueueWindow
        from skse_updater.models import Provider, Row, Binary, Report, Snapshot
        from PyQt6.QtGui import QFontDatabase, QFont
        import os
        bridge = Bridge()
        self.organizer.createNexusBridge.return_value = bridge
        provider = Provider("Existing mod", "", "", mod_id=123, game_domain="SkyrimSE")
        report = Report(2, "0.4.0", Snapshot("Test profile", ".", "live MO2"), (1,6,1170,0), {}, [Row(provider,Binary(),{})])
        window = QueueWindow(self.organizer, report)
        try:
            window.link.setText("456")
            window.find_file()
            self.assertFalse(window.add.isEnabled())
            bridge.fileInfoAvailable.emit(*bridge.request, {"file_id":456,"file_name":"a.7z","name":"Target runtime file","version":"2"})
            self.assertFalse(window.add.isEnabled())
            window.reviewed.setChecked(True)
            self.assertTrue(window.add.isEnabled())
            window.add_file()
            self.assertEqual(window.table.rowCount(),1)
            self.assertTrue(window.start.isEnabled())
            self.assertFalse(window.add.isEnabled())
            window.show()
            self.app.processEvents()
            if os.environ.get("SKSE_QUEUE_SCREENSHOT"):
                window.grab().save(os.environ["SKSE_QUEUE_SCREENSHOT"])
        finally:
            window.close()
            window.deleteLater()
