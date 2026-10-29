"""Archive integrity and relocated native-launcher checks with synthetic files."""

import io
import json
import os
import tarfile
import unittest
import zipfile

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from poe_log_analyze.runtime.NativePlatform import NativePlatform

from poe_log_analyze.tooling.BuildVersion import BuildVersion
from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.ReleasePackager import ReleasePackager
from poe_log_analyze.tooling.ReleaseVerifier import ReleaseVerifier
from poe_log_analyze.tooling.WindowsNativeCatalogue import WindowsNativeCatalogue


class ReleasePackagingTests(unittest.TestCase):
    """Verify portable contents, identity, safe extraction, and real shell execution."""

    COMMIT = "a" * 40
    PROVENANCE = {"verified": True, "scope": "included_dll", "libraries": 9,
                  "python": "3.14.4", "catalogue_sha256": "b" * 64}

    def setUp(self):
        temporary = Path(__file__).resolve().parents[1] / "build/tmp"
        temporary.mkdir(parents = True, exist_ok = True)
        self.temporary = TemporaryDirectory(dir = temporary)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.distribution = self.root / "distribution"
        self.output = self.root / "release"
        source = patch.object(BuildVersion, "read", return_value = BuildVersion("0.1.0", "v0.1.0", self.COMMIT, False))
        source.start()
        self.addCleanup(source.stop)

    def fixture(self, target = "Linux"):
        build = {"version": "0.1.0", "release_tag": "v0.1.0", "target": target,
                 "architecture": "x86_64", "distribution_layout": "app",
                 "code": {"git": {"sha": self.COMMIT, "dirty": False}}}
        metadata = self.distribution / ReleasePackager.METADATA
        metadata.parent.mkdir(parents = True)
        metadata.write_text(json.dumps(build), encoding = "utf-8")

        for name in ("README.md", "app/LICENSE", "app/THIRD_PARTY_NOTICES.md",
                     "app/poe_log_analyze/resources/licenses/manifest.json",
                     "app/poe_log_analyze/resources/licenses/THIRD_PARTY_LICENSES.txt",
                     "app/poe_log_analyze/resources/templates/пример.html", "app/library.so"):
            path = self.distribution / name
            path.parent.mkdir(parents = True, exist_ok = True)
            path.write_text("Synthetic distribution content\n", encoding = "utf-8")

        launcher = self.distribution / ("poe-log-analyze.cmd" if target == "Windows" else "poe-log-analyze")

        if target == "Windows":
            launcher.write_text('@echo off\r\n"%~dp0app\\poe-log-analyze.exe" %*\r\n', encoding = "utf-8", newline = "")
            (self.distribution / "app/poe-log-analyze.exe").write_bytes(b"synthetic executable")
        else:
            launcher.write_text('#!/bin/sh\nset -eu\nmkdir -p "$2"\n'
                                'printf \'{"passed":true,"report_language":"%s",'
                                '"cancellation_preserved_report":true,"replacement_removed_pdf":true,'
                                '"temporary_files_removed":true}\\n\' "$4" > "$2/self-test.json"\n',
                                encoding = "utf-8", newline = "\n")
            launcher.chmod(0o755)
            binary = self.distribution / "app/poe-log-analyze"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding = "utf-8", newline = "\n")
            binary.chmod(0o755)

        return build

    def package(self):
        return ReleasePackager.package(self.distribution, self.output, "v0.1.0", self.COMMIT)

    def windows_provenance_fixture(self):
        build = self.fixture("Windows")
        build["license_bundle"] = {"windows_native_provenance": dict(self.PROVENANCE)}
        (self.distribution / ReleasePackager.METADATA).write_text(json.dumps(build), encoding = "utf-8")
        licenses = self.distribution / "app/poe_log_analyze/resources/licenses"
        archive = LicenseTextArchive()
        archive.add("native/windows/synthetic/LICENSE", b"Original synthetic DLL notice\r\n")
        archive.write(licenses / "THIRD_PARTY_LICENSES.txt", licenses / "sources.json")

        return build

    @unittest.skipUnless(os.name == "posix", "Linux modes and symlinks require POSIX")
    def test_tar_roundtrip_preserves_internal_symlink_modes_resources_and_notices(self):
        self.fixture()
        (self.distribution / "app/alias.so").symlink_to("library.so")
        artifact = self.package()
        metadata = json.loads(artifact.manifest.read_text())
        extraction = self.root / "extracted"
        extraction.mkdir()
        ReleaseVerifier.extract(artifact.archive, extraction, metadata["root"])
        copied = extraction / metadata["root"]

        self.assertEqual(artifact.archive.name, "poe-log-report-0.1.0-linux-x86_64.tar.gz")
        self.assertEqual((copied / "app/alias.so").readlink(), Path("library.so"))
        self.assertEqual((copied / "app/alias.so").read_bytes(), (self.distribution / "app/library.so").read_bytes())
        self.assertTrue(os.access(copied / "poe-log-analyze", os.X_OK))
        self.assertTrue((copied / "app/poe_log_analyze/resources/templates/пример.html").is_file())
        self.assertEqual((copied / "app/LICENSE").read_bytes(), (self.distribution / "app/LICENSE").read_bytes())
        self.assertEqual((self.output / "SHA256SUMS").read_text(), artifact.checksum.read_text())
        self.assertIn(ReleasePackager.sha256(artifact.archive), artifact.checksum.read_text())

    def test_windows_zip_contains_full_app_and_matching_release_identity(self):
        self.fixture("Windows")
        artifact = self.package()

        self.assertEqual(artifact.archive.suffix, ".zip")

        with zipfile.ZipFile(artifact.archive) as archive:
            names = archive.namelist()

        self.assertIn("poe-log-report-0.1.0-windows-x64/poe-log-analyze.cmd", names)
        self.assertIn("poe-log-report-0.1.0-windows-x64/app/poe-log-analyze.exe", names)
        self.assertTrue(any(name.endswith("resources/licenses/THIRD_PARTY_LICENSES.txt") for name in names))

        manifest = json.loads(artifact.manifest.read_text())

        self.assertEqual(manifest["commit"], self.COMMIT)
        self.assertEqual(manifest["tag"], "v0.1.0")
        self.assertEqual(manifest["archive_sha256"], ReleasePackager.sha256(artifact.archive))
        self.assertNotIn("windows_native_provenance", manifest)

    def test_windows_provenance_is_rechecked_and_retained_in_manifest_and_verification(self):
        self.windows_provenance_fixture()

        with patch.object(WindowsNativeCatalogue, "verify_distribution", return_value = dict(self.PROVENANCE)) as verify:
            artifact = self.package()
            self.assertEqual(verify.call_args.args[0], self.distribution / "app")
            archive = verify.call_args.args[1]
            self.assertEqual(next(iter(archive.texts.values())), b"Original synthetic DLL notice\r\n")

            with patch.object(NativePlatform, "current", return_value = NativePlatform("Windows", "AMD64", 64)), \
                    patch.dict(os.environ, {"SYSTEMROOT": str(self.root / "Windows")}), \
                    patch("subprocess.run", side_effect = self.windows_self_test):
                report = ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / "verification")

        manifest = json.loads(artifact.manifest.read_text())
        receipt = json.loads(report.read_text())

        self.assertEqual(verify.call_count, 2)
        self.assertEqual(manifest["windows_native_provenance"], self.PROVENANCE)
        self.assertEqual(receipt["windows_native_provenance"], self.PROVENANCE)
        self.assertNotEqual(verify.call_args_list[1].args[0], self.distribution / "app")

    def test_windows_provenance_claim_cannot_bypass_failed_dll_or_notice_verification(self):
        self.windows_provenance_fixture()

        with patch.object(WindowsNativeCatalogue, "verify_distribution", side_effect = ValueError("Changed DLL bytes")) as verify:
            with self.assertRaisesRegex(ValueError, "Changed DLL bytes"):
                self.package()

        verify.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_windows_build_summary_must_match_rechecked_dlls_and_notices(self):
        self.windows_provenance_fixture()
        changed = dict(self.PROVENANCE, catalogue_sha256 = "c" * 64)

        with patch.object(WindowsNativeCatalogue, "verify_distribution", return_value = changed):
            with self.assertRaisesRegex(ValueError, "does not match the actual DLLs"):
                self.package()

        self.assertFalse(self.output.exists())

    def test_corrupted_original_notice_archive_prevents_native_claim_from_packaging(self):
        self.windows_provenance_fixture()
        licenses = self.distribution / "app/poe_log_analyze/resources/licenses"
        (licenses / "THIRD_PARTY_LICENSES.txt").write_bytes(b"Changed original notice")

        with patch.object(WindowsNativeCatalogue, "verify_distribution") as verify:
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self.package()

        verify.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_windows_provenance_is_rejected_on_linux_and_when_explicitly_null(self):
        build = self.fixture()
        metadata = self.distribution / ReleasePackager.METADATA

        for summary in (dict(self.PROVENANCE), None):
            with self.subTest(summary = summary):
                build["license_bundle"] = {"windows_native_provenance": summary}
                metadata.write_text(json.dumps(build))

                with self.assertRaisesRegex(ValueError, "Windows distribution"):
                    self.package()

        self.assertFalse(self.output.exists())

    def test_windows_verifier_rejects_missing_changed_or_malformed_manifest_provenance(self):
        self.windows_provenance_fixture()

        with patch.object(WindowsNativeCatalogue, "verify_distribution", return_value = dict(self.PROVENANCE)):
            artifact = self.package()

        original = json.loads(artifact.manifest.read_text())

        for index, summary in enumerate((None, dict(self.PROVENANCE, catalogue_sha256 = "c" * 64),
                                         dict(self.PROVENANCE, libraries = 9.0))):
            metadata = dict(original)

            if summary is None:
                del metadata["windows_native_provenance"]
            else:
                metadata["windows_native_provenance"] = summary

            artifact.manifest.write_text(json.dumps(metadata))

            with self.subTest(summary = summary), \
                    patch.object(NativePlatform, "current", return_value = NativePlatform("Windows", "AMD64", 64)), \
                    patch.object(WindowsNativeCatalogue, "verify_distribution", return_value = dict(self.PROVENANCE)), \
                    patch("subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "provenance"):
                    ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / ("verification-" + str(index)))

                run.assert_not_called()

    def test_windows_verifier_rechecks_dlls_before_executing_an_archived_application(self):
        self.windows_provenance_fixture()

        with patch.object(WindowsNativeCatalogue, "verify_distribution", return_value = dict(self.PROVENANCE)):
            artifact = self.package()

        with patch.object(NativePlatform, "current", return_value = NativePlatform("Windows", "AMD64", 64)), \
                patch.object(WindowsNativeCatalogue, "verify_distribution", side_effect = ValueError("Changed DLL bytes")) as verify, \
                patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "Changed DLL bytes"):
                ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / "verification")

        verify.assert_called_once()
        run.assert_not_called()

    def test_dirty_or_mismatched_release_build_is_rejected_before_creating_assets(self):
        build = self.fixture()
        metadata = self.distribution / ReleasePackager.METADATA

        for key, value in (("dirty", True), ("sha", "b" * 40), ("sha", None)):
            with self.subTest(key = key, value = value):
                changed = json.loads(json.dumps(build))
                changed["code"]["git"][key] = value
                metadata.write_text(json.dumps(changed))

                with self.assertRaisesRegex(ValueError, "must match"):
                    self.package()

        for key in ("version", "release_tag"):
            changed = json.loads(json.dumps(build))
            changed[key] = "other"
            metadata.write_text(json.dumps(changed))

            with self.assertRaisesRegex(ValueError, "must match"):
                self.package()

        self.assertFalse(self.output.exists())

    def test_root_outputs_and_nested_build_data_are_rejected(self):
        self.fixture()
        report = self.distribution / "report"
        report.mkdir()

        with self.assertRaisesRegex(ValueError, "root must contain only"):
            self.package()

        report.rmdir()
        (self.distribution / "app/build").mkdir()

        with self.assertRaisesRegex(ValueError, "Development or user output"):
            self.package()

    def test_changed_source_checkout_is_rejected_even_when_build_metadata_is_clean(self):
        self.fixture()

        with patch.object(BuildVersion, "read", side_effect = ValueError("Source checkout changed")):
            with self.assertRaisesRegex(ValueError, "Source checkout changed"):
                self.package()

        self.assertFalse(self.output.exists())

    @unittest.skipUnless(os.name == "posix", "Symlink checks require POSIX")
    def test_external_and_directory_symlinks_are_rejected(self):
        self.fixture()
        outside = self.root / "outside.txt"
        outside.write_text("Synthetic private material")
        link = self.distribution / "app/alias.so"
        link.symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.package()

        link.unlink()
        link.symlink_to("poe_log_analyze", target_is_directory = True)

        with self.assertRaisesRegex(ValueError, "internal files"):
            self.package()

    def test_existing_release_assets_are_never_overwritten(self):
        self.fixture()
        artifact = self.package()
        before = artifact.archive.read_bytes()

        with self.assertRaises(FileExistsError):
            self.package()

        self.assertEqual(artifact.archive.read_bytes(), before)

    @unittest.skipUnless(os.name == "posix", "The synthetic executable is a POSIX shell script")
    def test_archive_runs_both_languages_from_relocated_unicode_path(self):
        self.fixture()
        artifact = self.package()
        before = ReleasePackager.sha256(artifact.archive)
        report = ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / "verification")
        result = json.loads(report.read_text())

        self.assertTrue(result["passed"])
        self.assertTrue(result["relocated"])
        self.assertEqual(result["languages"], {"en": {"passed": True}, "ru": {"passed": True}})
        self.assertEqual(ReleasePackager.sha256(artifact.archive), before)
        self.assertFalse((self.distribution / "build").exists())

    def test_changed_archive_fails_before_extraction_or_execution(self):
        self.fixture()
        artifact = self.package()

        with artifact.archive.open("ab") as stream:
            stream.write(b"corruption")

        with self.assertRaisesRegex(ValueError, "SHA256"):
            ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / "verification")

        self.assertFalse((self.output / "verification").exists())

    def windows_self_test(self, command, **options):
        windows_root = self.root / "Windows"

        self.assertEqual(command[:5], [str(windows_root / "System32/cmd.exe"), "/d", "/s", "/c", "call"])
        self.assertEqual(options["env"]["PATH"], str(windows_root / "System32") + os.pathsep + str(windows_root))
        self.assertNotIn("PYTHONPATH", options["env"])
        self.assertNotIn("VIRTUAL_ENV", options["env"])
        result = Path(command[7])
        result.mkdir(parents = True)
        (result / "self-test.json").write_text(json.dumps({
            "passed": True, "report_language": command[9], "cancellation_preserved_report": True,
            "replacement_removed_pdf": True, "temporary_files_removed": True,
        }), encoding = "utf-8")

    def test_windows_verification_uses_explicit_system_shell_and_excludes_developer_path(self):
        self.fixture("Windows")
        artifact = self.package()

        with patch.object(NativePlatform, "current", return_value = NativePlatform("Windows", "AMD64", 64)), \
                patch.dict(os.environ, {"SYSTEMROOT": str(self.root / "Windows"), "PYTHONPATH": "synthetic-dev-path"}), \
                patch("subprocess.run", side_effect = self.windows_self_test) as run:
            report = ReleaseVerifier.verify(artifact.archive, artifact.manifest, self.output / "verification")

        self.assertTrue(json.loads(report.read_text())["passed"])
        self.assertEqual(run.call_count, 2)

    def test_zip_and_tar_traversal_are_rejected_without_writing_outside_extraction(self):
        for suffix in ("zip", "tar.gz"):
            with self.subTest(suffix = suffix):
                archive = self.root / ("unsafe." + suffix)
                destination = self.root / suffix
                destination.mkdir()

                if suffix == "zip":
                    with zipfile.ZipFile(archive, "w") as bundle:
                        bundle.writestr("root/../../escaped.txt", "unsafe")
                else:
                    with tarfile.open(archive, "w:gz") as bundle:
                        member = tarfile.TarInfo("root/../../escaped.txt")
                        member.size = 6
                        bundle.addfile(member, io.BytesIO(b"unsafe"))

                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    ReleaseVerifier.extract(archive, destination, "root")

                self.assertFalse((self.root / "escaped.txt").exists())
