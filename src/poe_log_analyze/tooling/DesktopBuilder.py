import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from importlib import metadata

from pathlib import Path

from poe_log_analyze.runtime.CodeProvenance import CodeProvenance
from poe_log_analyze.runtime.JsonFiles import JsonFiles

from poe_log_analyze.stages.rendering.ReportTemplates import ReportTemplates

from poe_log_analyze.runtime.Workspace import Workspace
from poe_log_analyze.runtime.NativePlatform import NativePlatform
from poe_log_analyze.runtime.ProcessEnvironment import ProcessEnvironment

from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue

from poe_log_analyze.tooling.LicenseBundleWriter import LicenseBundleWriter
from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.DesktopDistribution import DesktopDistribution
from poe_log_analyze.tooling.BuildVersion import BuildVersion
from poe_log_analyze.tooling.NativeLicenseCollector import NativeLicenseCollector
from poe_log_analyze.tooling.PythonLicense import PythonLicense

class DesktopBuilder:
    """Build a native Linux/Windows x86_64 application directory with Nuitka."""

    ROOT = Path(__file__).resolve().parents[3]
    EXCLUDED_PACKAGES = ("poe_log_analyze.tooling", "markdown.test_tools", "unittest",
                         "PySide6", "shiboken6", "PIL.ImageQt")

    @staticmethod
    def main():
        """Record code and resource metadata without including user data."""

        parser = argparse.ArgumentParser(description = 'Native build for Linux/Windows x86_64')
        parser.add_argument("--output", type = Path, default = DesktopBuilder.ROOT / "build" / "standalone")
        parser.add_argument("--jobs", type = int, default = 2)
        parser.add_argument("--release-tag", help = "Require a clean checkout of this exact application version tag")
        catalogues = parser.add_mutually_exclusive_group()
        catalogues.add_argument("--native-catalogue", type = Path, help = "Use a verified native notice catalogue (.json and .txt)")
        catalogues.add_argument("--collect-native-licenses", action = "store_true",
                                help = "Collect a separate Linux catalogue from actual installed Debian packages and wheels")
        args = parser.parse_args()
        native = NativePlatform.current()
        version = BuildVersion.read(DesktopBuilder.ROOT, args.release_tag)

        if native.windows and (args.native_catalogue is not None or args.collect_native_licenses):
            parser.error('Native catalogue options are supported only for Linux builds')

        for language in ("ru", "en"):
            TranslationCatalogue(language, DesktopBuilder.ROOT)

        output = Workspace.local_output(args.output)
        output.mkdir(parents = True, exist_ok = False)
        resources = output / "staging" / "resources"
        resources.mkdir(parents = True)

        for name in ReportTemplates.files():
            destination = resources / name
            destination.parent.mkdir(parents = True, exist_ok = True)
            shutil.copyfile(DesktopBuilder.ROOT / name, destination)

        import tzdata
        shutil.copytree(Path(tzdata.__file__).parent / "zoneinfo", resources / "zoneinfo",
                        ignore = shutil.ignore_patterns("*.py", "__pycache__"))
        dependencies = ("tzdata", "Nuitka",
                        "Jinja2", "MarkupSafe", "Markdown", "reportlab", "pillow", "charset-normalizer")

        if not native.windows:
            dependencies += ("patchelf",)

        python_license = PythonLicense.find()

        if native.windows:
            LicenseBundleWriter.add_windows_toolkit(LicenseTextArchive(), python_license.parent, DesktopBuilder.ROOT)

        build = {
            "build_schema_version": "2", "python": platform.python_version(), "distribution_layout": "app",
            "version": version.version, "release_tag": version.release_tag,
            "target": native.system, "architecture": "x86_64", "report_languages": ["ru", "en"],
            "gui": {"name": "tkinter", "bindings": "stdlib"},
            "platform": platform.platform(), "libc": platform.libc_ver(),
            "source_image": os.environ.get("POE_BUILD_IMAGE"),
            "dependencies": {name: metadata.version(name) for name in dependencies},
            "timezone_database": tzdata.IANA_VERSION,
            "renderer": {"name": "Jinja2", "versions": {name: metadata.version(name)
                         for name in ("Jinja2", "MarkupSafe", "Markdown", "reportlab", "pillow", "charset-normalizer")}},
            "code": {"git": {"sha": version.commit, "dirty": version.dirty}, "files_sha256": CodeProvenance.source_hashes(DesktopBuilder.ROOT / "src" / "poe_log_analyze")},
            "templates_sha256": {name: hashlib.sha256((DesktopBuilder.ROOT / name).read_bytes()).hexdigest() for name in ReportTemplates.files()},
            "excluded_packages": list(DesktopBuilder.EXCLUDED_PACKAGES),
        }
        JsonFiles.write_json(resources / "build-info.json", build)
        env = ProcessEnvironment.within(output)
        env["PYTHONPATH"] = str(DesktopBuilder.ROOT / "src")
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        env["NUITKA_CACHE_DIR"] = str(output / "cache")
        # GCC LTO produces an invalid makefile when the local TMPDIR contains spaces.
        command = [sys.executable, "-m", "nuitka", "--mode=standalone", "--enable-plugin=tk-inter",
                   "--include-package=poe_log_analyze",
                   *(f"--include-module=markdown.extensions.{name}" for name in ("tables", "fenced_code", "toc")),
                   *(f"--include-distribution-metadata={name}" for name in ("Jinja2", "MarkupSafe", "Markdown", "reportlab", "pillow", "charset-normalizer")),
                   *(f"--nofollow-import-to={name}" for name in DesktopBuilder.EXCLUDED_PACKAGES),
                   "--update-check=never",
                   "--disable-cache=ccache", "--lto=no", f"--jobs={args.jobs}", f"--output-filename={native.application_name}",
                   f"--include-data-dir={resources}=poe_log_analyze/resources",
                   f"--output-dir={output}", f"--report={output / 'compilation-report.xml'}",
                   *DesktopBuilder.platform_options(native), str(DesktopBuilder.ROOT / "scripts" / "poe_desktop.py")]
        JsonFiles.write_json(output / "build-command.json", {"command": command})
        subprocess.run(command, cwd = DesktopBuilder.ROOT, env = env, check = True)
        build["runtime_modules"] = DesktopBuilder.validate_runtime_modules(output / "compilation-report.xml")
        JsonFiles.write_json(output / "package-check.json", {
            "runtime_modules": build["runtime_modules"], "excluded_packages": build["excluded_packages"]})
        dist = output / "poe_desktop.dist"
        LicenseBundleWriter.finish_distribution(DesktopBuilder.ROOT, dist)
        final_resources = dist / "poe_log_analyze" / "resources"
        catalogue = args.native_catalogue

        if args.collect_native_licenses:
            catalogue = NativeLicenseCollector.collect(output / "compilation-report.xml", output / "native-licenses/Native.json")

        license_bundle = LicenseBundleWriter.stage(DesktopBuilder.ROOT, final_resources / "licenses", dependencies,
                                                  python_license,
                                                  system = native.system,
                                                  native_report = output / "compilation-report.xml",
                                                  native_catalogue = catalogue)
        build["license_bundle"] = license_bundle
        JsonFiles.write_json(final_resources / "build-info.json", build)
        JsonFiles.write_json(output / "license-check.json", {
            "gui": "tkinter", "license_files": len(license_bundle["files_sha256"]),
            "pending_release_checks": ["native_dependencies_review"]})
        DesktopDistribution.arrange(dist, native)
        JsonFiles.write_json(output / "distribution-sha256.json", {
            p.relative_to(dist).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(dist.rglob("*")) if p.is_file()
        })

        for name in ("tmp", "cache", "staging", "poe_desktop.build"):
            shutil.rmtree(output / name, ignore_errors = True)

        version.verify(DesktopBuilder.ROOT)
        print(f"Application directory: {dist}")
        print('Check the application on a clean supported system before distribution.')

    @staticmethod
    def platform_options(native: NativePlatform) -> list[str]:
        """Windows uses installed MSVC; Linux uses dynamic libpython."""

        return ["--msvc=latest", "--windows-console-mode=attach", "--assume-yes-for-downloads"] if native.windows else ["--static-libpython=no"]

    @staticmethod
    def validate_runtime_modules(report: Path) -> list[str]:
        """Validate the actual compiler report rather than command options alone."""

        modules = sorted(node.attrib["name"] for node in ET.parse(report).getroot().findall("module")
                         if node.attrib.get("name"))

        if "poe_log_analyze.cli.DesktopLauncher" not in modules:
            raise ValueError('The compiler report is missing the application entry point')

        required = {"tkinter", "tkinter.ttk", "_tkinter"}

        if not required.issubset(modules):
            raise ValueError('The compiler report is missing Tkinter')

        unexpected = [name for name in modules if any(name == package or name.startswith(package + ".")
                                                     for package in DesktopBuilder.EXCLUDED_PACKAGES)]

        if unexpected:
            raise ValueError('Excluded modules were included in the application: ' + ", ".join(unexpected))

        return [name for name in modules if name.startswith("poe_log_analyze")]
