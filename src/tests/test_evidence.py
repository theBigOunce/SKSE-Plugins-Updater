"""Evidence-focused compatibility and update regression tests."""
import struct
import tempfile
import unittest
from pathlib import Path

from skse_updater.address_library import inspect_database
from skse_updater.compatibility import assess, environment_assessment
from skse_updater.models import Database, Provider
from skse_updater.pe_scan import inspect_bytes
from skse_updater.updates import apply_update, nexus_game, update_status
from test_core import fixture

TARGET = (1, 6, 1170, 0)


class LoaderRulesTests(unittest.TestCase):
    def binary(self, flags=1, flags_ex=1):
        data = fixture(flags=flags, runtimes=(0x01000000,) * 16)
        struct.pack_into("<I", data, 0x704, flags_ex)
        return inspect_bytes(data)

    def test_ng_independence_with_no_structure_use(self):
        result = assess(self.binary(), TARGET)
        self.assertEqual(result.status, "supported")
        self.assertTrue(result.evidence)

    def test_post629_layout(self):
        self.assertEqual(assess(self.binary(5, 0), TARGET).status, "supported")

    def test_old_layout_is_rejected(self):
        self.assertEqual(assess(self.binary(1, 0), TARGET).status, "incompatible")

    def test_signature_scanning_with_no_structure_use(self):
        self.assertEqual(assess(self.binary(2, 1), TARGET).status, "supported")

    def test_legacy_requires_query(self):
        self.assertEqual(assess(self.binary(), (1, 5, 97, 0)).status, "incompatible")

    def test_query_presence_is_not_proof(self):
        binary = self.binary()
        binary.exports.append("SKSEPlugin_Query")
        self.assertEqual(assess(binary, (1, 5, 97, 0)).status, "review")

    def test_new_encoding_not_assumed(self):
        self.assertEqual(assess(self.binary(1, 3), (1, 7, 99, 0)).status, "review")

    def test_all_local_prerequisites(self):
        binary = self.binary()
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("valid", "Header checked"), (2, 2, 6, 0),
                                        storefront="steam")
        self.assertEqual(result.status, "supported")

    def test_bad_database_not_overridden_by_good_declaration(self):
        binary = self.binary()
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("invalid", "Wrong encoding"), (2, 2, 6, 0),
                                        storefront="steam")
        self.assertEqual(result.status, "incompatible")

    def test_signature_scanning_needs_no_database(self):
        binary = self.binary(2, 1)
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("missing", "Absent"), (2, 2, 6, 0),
                                        storefront="steam")
        self.assertEqual(result.status, "supported")

    def test_minimum_skse(self):
        binary = self.binary()
        binary.declaration.minimum_skse = 0x02030000
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("valid", "Header checked"), (2, 2, 6, 0),
                                        storefront="steam")
        self.assertEqual(result.status, "incompatible")

    def test_unknown_skse(self):
        binary = self.binary()
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("valid", "Header checked"), None,
                                        storefront="steam")
        self.assertEqual(result.status, "review")

    def test_storefront_is_separate(self):
        binary = self.binary()
        result = environment_assessment(binary, assess(binary, TARGET),
                                        Database("valid", "Header checked"), (2, 2, 6, 0))
        self.assertEqual(result.status, "review")


class DatabaseTests(unittest.TestCase):
    def check(self, *, format_id=2, runtime=TARGET, name=b"SkyrimSE.exe", pointer=8, count=4, payload=b"\0"*4):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "library.bin"
            path.write_bytes(struct.pack("<6i", format_id, *runtime, len(name)) + name
                             + struct.pack("<2i", pointer, count) + payload)
            return inspect_database(path, TARGET)

    def test_valid_header(self):
        self.assertEqual(self.check().status, "valid")

    def test_wrong_runtime(self):
        self.assertEqual(self.check(runtime=(1, 6, 640, 0)).status, "invalid")

    def test_wrong_format(self):
        self.assertEqual(self.check(format_id=1).status, "invalid")

    def test_new_format_unknown(self):
        self.assertEqual(self.check(format_id=5).status, "unknown")

    def test_wrong_executable(self):
        self.assertEqual(self.check(name=b"Fallout4.exe").status, "invalid")

    def test_wrong_pointer_size(self):
        self.assertEqual(self.check(pointer=4).status, "invalid")

    def test_truncated_payload(self):
        self.assertEqual(self.check(count=100).status, "invalid")

    def test_missing(self):
        self.assertEqual(inspect_database(None, TARGET).status, "missing")


class UpdateTests(unittest.TestCase):
    def test_newer(self):
        self.assertEqual(update_status("1.9", "1.10")[0], "available")

    def test_padding_equal(self):
        self.assertEqual(update_status("v2.2.6", "2.2.6.0")[0], "current")

    def test_beta_ambiguous(self):
        self.assertEqual(update_status("1.0-beta", "1.0")[0], "unknown")

    def test_installed_ahead(self):
        self.assertEqual(update_status("3.0", "2.0")[0], "ahead")

    def test_no_cached_check(self):
        self.assertEqual(update_status("1.0", "")[0], "unknown")

    def test_missing_identity(self):
        provider = Provider("Example", "example.dll", "example.dll", release="1.0")
        apply_update(provider, "2.0")
        self.assertEqual(provider.update_status, "unknown")

    def test_does_not_change_installed_version(self):
        provider = Provider("Example", "example.dll", "example.dll", release="1.0", mod_id=1)
        apply_update(provider, "2.0", "now", "Live Nexus check")
        self.assertEqual(provider.release, "1.0")
        self.assertEqual(provider.update_status, "available")
        self.assertEqual(provider.update_source, "Live Nexus check")

    def test_domain_whitelist(self):
        self.assertEqual(nexus_game("SkyrimSE"), "skyrimspecialedition")
        self.assertIsNone(nexus_game("Fallout4"))
