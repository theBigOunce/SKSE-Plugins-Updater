"""Synthetic fixtures only; never contains user mod binaries or metadata."""
import configparser
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skse_updater.compatibility import assess
from skse_updater.inventory import collect, offline_snapshot, qt_text
from skse_updater.models import Binary, Declaration, Provider, Snapshot
from skse_updater.pe_scan import inspect_bytes
from skse_updater.scanner import scan


def fixture(*, schema=1, flags=0, runtimes=(0x01064920,), machine=0x8664):
    data = bytearray(0x1000)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, machine, 1)
    struct.pack_into("<H", data, 0x94, 240)
    struct.pack_into("<H", data, 0x98, 0x20b)
    struct.pack_into("<I", data, 0x98 + 60, 0x200)
    struct.pack_into("<I", data, 0x98 + 108, 16)
    struct.pack_into("<II", data, 0x98 + 112, 0x1000, 0x100)
    struct.pack_into("<IIII", data, 0x188 + 8, 0xe00, 0x1000, 0xe00, 0x200)
    struct.pack_into("<IIIII", data, 0x200 + 20, 2, 2, 0x1040, 0x1050, 0x1060)
    struct.pack_into("<II", data, 0x240, 0x1200, 0x1500)
    struct.pack_into("<II", data, 0x250, 0x1080, 0x10b0)
    struct.pack_into("<HH", data, 0x260, 0, 1)
    for at, name in ((0x280, b"SKSEPlugin_Version\0"), (0x2b0, b"SKSEPlugin_Load\0")):
        data[at:at + len(name)] = name
    struct.pack_into("<II", data, 0x400, schema, 42)
    data[0x408:0x40d] = b"Demo\0"
    struct.pack_into("<II", data, 0x704, 0, flags)
    struct.pack_into("<16I", data, 0x70c, *(list(runtimes) + [0] * (16 - len(runtimes))))
    return data


class ParserTests(unittest.TestCase):
    def test_valid_declaration(self):
        binary = inspect_bytes(fixture())
        self.assertFalse(binary.error)
        self.assertEqual(binary.declaration.name, "Demo")
        self.assertEqual(binary.declaration.runtimes, [(1, 6, 1170, 0)])

    def test_full_runtime_array_is_bounded(self):
        binary = inspect_bytes(fixture(flags=1, runtimes=(0x01000000,) * 16))
        self.assertFalse(binary.error)
        self.assertEqual(len(binary.declaration.runtimes), 16)

    def test_truncation_never_escapes(self):
        data = fixture()
        for length in (0, 2, 63, 130, 400, 700, 1000, 1500):
            with self.subTest(length=length):
                self.assertTrue(inspect_bytes(data[:length]).error)

    def test_bad_ordinal(self):
        data = fixture()
        struct.pack_into("<H", data, 0x260, 99)
        self.assertIn("ordinal", inspect_bytes(data).error)

    def test_forwarded_metadata(self):
        data = fixture()
        struct.pack_into("<I", data, 0x240, 0x1080)
        self.assertIn("Forwarded", inspect_bytes(data).error)

    def test_virtual_only_metadata(self):
        data = fixture()
        struct.pack_into("<I", data, 0x240, 0x5000)
        self.assertIn("RVA", inspect_bytes(data).error)

    def test_future_schema(self):
        self.assertIn("schema", inspect_bytes(fixture(schema=8)).error)

    def test_huge_count(self):
        data = fixture()
        struct.pack_into("<I", data, 0x218, 1000000)
        self.assertIn("count", inspect_bytes(data).error)


class PolicyTests(unittest.TestCase):
    def test_explicit_runtime(self):
        self.assertEqual(assess(inspect_bytes(fixture()), (1, 6, 1170, 0)).status, "supported")

    def test_wrong_runtime(self):
        self.assertEqual(assess(inspect_bytes(fixture()), (1, 5, 97, 0)).status, "incompatible")

    def test_legacy_unknown(self):
        binary = Binary(machine=0x8664, exports=["SKSEPlugin_Query", "SKSEPlugin_Load"])
        self.assertEqual(assess(binary, (1, 5, 97, 0)).status, "review")

    def test_ng_is_not_universal(self):
        binary = inspect_bytes(fixture(flags=1))
        self.assertEqual(assess(binary, (1, 7, 99, 0), database_present=True).status, "review")

    def test_database_missing(self):
        self.assertEqual(assess(inspect_bytes(fixture(flags=1)), (1, 6, 1170, 0)).status, "incompatible")

    def test_unknown_flags(self):
        self.assertEqual(assess(inspect_bytes(fixture(flags=128)), (1, 6, 1170, 0)).status, "review")

    def test_wrong_architecture(self):
        self.assertEqual(assess(inspect_bytes(fixture(machine=0x14c)), (1, 6, 1170, 0)).status, "incompatible")

    def test_unknown_origin(self):
        self.assertEqual(assess(inspect_bytes(fixture()), (1, 6, 1170, 0), effective=None).status, "review")

    def test_shadowed(self):
        self.assertEqual(assess(inspect_bytes(fixture()), (1, 6, 1170, 0), effective=False).status, "shadowed")

    def test_future_runtime(self):
        self.assertEqual(assess(inspect_bytes(fixture()), (1, 8, 0, 0)).status, "review")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def mod(self, name):
        folder = self.root / name
        plugin = folder / "SKSE" / "Plugins"
        plugin.mkdir(parents=True)
        (plugin / "Demo.dll").write_bytes(fixture())
        return folder

    def test_priority_hidden_files_and_metadata(self):
        low, high = self.mod("low"), self.mod("high")
        (high / "meta.ini").write_text("[General]\nversion=2.0\nmodid=123\nsecret=not-exported\n")
        (high / "SKSE/Plugins/Other.dll.mohidden").write_bytes(b"ignored")
        result = collect("Example", self.root, [("low", low, True), ("high", high, True)], "offline")
        self.assertEqual([p.effective for p in result.providers], [False, True])
        self.assertEqual(result.providers[1].mod_id, 123)
        self.assertEqual(result.providers[1].release, "2.0")
        self.assertFalse(hasattr(result.providers[1], "secret"))

    def test_offline_never_claims_verified_winner(self):
        root = self.mod("mod")
        snapshot = collect("Example", self.root, [("mod", root, True)], "offline")
        with patch("skse_updater.scanner.file_version", return_value=(1, 6, 1170, 0)):
            report = scan(snapshot)
        self.assertEqual(report.rows[0].assessments["1.6.1170.0"].status, "review")

    def test_offline_profile_order(self):
        instance = self.root / "instance"
        game = self.root / "game"
        game.mkdir()
        (game / "SkyrimSE.exe").touch()
        (game / "Data").mkdir()
        (instance / "profiles/Example").mkdir(parents=True)
        (instance / "profiles/Example/modlist.txt").write_text("+high\n-disabled\n+low\n")
        for name in ("high", "low", "disabled"):
            plugin = instance / "mods" / name / "SKSE/Plugins"
            plugin.mkdir(parents=True)
            (plugin / "Demo.dll").write_bytes(fixture())
        (instance / "ModOrganizer.ini").write_text(f"[General]\nselected_profile=Example\ngamePath={game}\n")
        result = offline_snapshot(instance)
        self.assertEqual([p.mod for p in result.providers], ["low", "high"])
        self.assertEqual([p.effective for p in result.providers], [False, True])

    def test_qt_bytearray(self):
        self.assertEqual(qt_text("@ByteArray(Example)"), "Example")

    def test_cancel(self):
        root = self.mod("mod")
        snapshot = collect("Example", self.root, [("mod", root, True)], "offline")
        with self.assertRaises(InterruptedError):
            scan(snapshot, canceled=lambda: True)


if __name__ == "__main__":
    unittest.main()
