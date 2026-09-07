"""Read-only live-adapter contract checks with a synthetic organizer."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from skse_updater.mo2_adapter import live_snapshot


class AdapterTests(unittest.TestCase):
    def test_live_resolver_overrides_disk_priority_and_adds_mapped_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Data").mkdir()
            (root / "overwrite").mkdir()
            for name in ("low", "high"):
                folder = root / name / "SKSE/Plugins"
                folder.mkdir(parents=True)
                (folder / "Demo.dll").touch()
            winner = root / "low/SKSE/Plugins/Demo.dll"
            mapped = root / "Mapped.dll"
            mapped.touch()
            mods = SimpleNamespace(
                allMods=lambda: ["low", "high"], priority=lambda n: ["low", "high"].index(n),
                state=lambda n: 1,
                getMod=lambda n: SimpleNamespace(absolutePath=lambda: str(root / n)))
            def find_files(path, predicate):
                return [f for f in (SimpleNamespace(filePath="Demo.dll"),
                                    SimpleNamespace(filePath="Mapped.dll")) if predicate(f)]
            organizer = SimpleNamespace(
                managedGame=lambda: SimpleNamespace(gameDirectory=lambda: SimpleNamespace(absolutePath=lambda: str(root))),
                modList=lambda: mods, overwritePath=lambda: str(root / "overwrite"),
                profileName=lambda: "Example", findFileInfos=find_files,
                resolvePath=lambda p: str(winner if p.endswith("Demo.dll") else mapped),
                createNexusBridge=lambda: None,
                downloadManager=lambda: SimpleNamespace(startDownloadNexusFile=lambda *args: None))
            with patch.dict(sys.modules, {"mobase": SimpleNamespace(ModState=SimpleNamespace(ACTIVE=1))}):
                result = live_snapshot(organizer)
            self.assertEqual([p.effective for p in result.providers], [True, False, True])
            self.assertEqual(result.providers[-1].mod, "MO2 virtual provider")
            self.assertTrue(result.capabilities["nexus_metadata_bridge"])
            self.assertTrue(result.capabilities["nexus_download_service"])
