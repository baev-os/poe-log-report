"""Protect dependency directions and complete code fingerprints."""

import ast
import hashlib
import importlib.util
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.runtime.CodeProvenance import CodeProvenance

from ArchitecturePolicy import ArchitecturePolicy

PACKAGE = Path(__file__).resolve().parents[1] / "src/poe_log_analyze"


class ArchitectureTests(unittest.TestCase):
    """Protect interface and application-stage boundaries."""

    def test_layer_dependencies(self):
        for path in PACKAGE.rglob("*.py"):
            relative = path.relative_to(PACKAGE)

            if len(relative.parts) < 2:
                continue

            layer = relative.parts[0]
            module = "poe_log_analyze." + relative.with_suffix("").as_posix().replace("/", ".")
            package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]

            for node in ast.walk(ast.parse(path.read_text())):
                targets = []

                if isinstance(node, ast.ImportFrom):
                    target = node.module or ""

                    if node.level:
                        target = importlib.util.resolve_name("." * node.level + target, package)

                    targets = [target]
                elif isinstance(node, ast.Import):
                    targets = [n.name for n in node.names]

                for target in targets:
                    with self.subTest(path = relative, dependency = target):
                        self.assertIsNone(ArchitecturePolicy.violation(module, target))

    def test_rejects_crossing_boundaries(self):
        cases = (
            ("stages.parsing.LogParser", "poe_log_analyze.desktop.MainWindow"),
            ("stages.merging.MergeHistory", "poe_log_analyze.stages.rendering.RenderReport"),
            ("stages.parsing.ParseLogs", "poe_log_analyze.core.ReportWorkspace"),
            ("stages.verification.VerifyReport", "poe_log_analyze.core.process.GenerationProcess"),
            ("stages.composition.ComposeReport", "poe_log_analyze.core.ReportGenerator"),
            ("core.plan.ReportPlan", "poe_log_analyze.stages.parsing.ParseLogs"),
            ("desktop.MainWindow", "poe_log_analyze.Bootstrap"),
            ("cli.AnalysisCli", "poe_log_analyze.stages.parsing.LogParser"),
            ("stages.parsing.LogParser", "PySide6.QtCore"),
            ("desktop.InputPanel", "PySide6.QtWidgets"),
            ("stages.parsing.LogParser", "tkinter.ttk"),
            ("core.request.ReportRequest", "poe_log_analyze.core.ReportGenerator"),
            ("core.result.ReportResult", "poe_log_analyze.core.process.GenerationProcess"),
            ("core.plan.ReportPlan", "poe_log_analyze.core.process.GenerationStatus"),
            ("core.process.GenerationProcess", "poe_log_analyze.core.execution.ExecutionContext"),
            ("core.execution.ExecutionContext", "poe_log_analyze.core.ReportWorkspace"),
        )

        for source, target in cases:
            with self.subTest(source = source, target = target):
                self.assertIsNotNone(ArchitecturePolicy.violation("poe_log_analyze." + source, target))

    def test_accepts_stage_results_and_desktop_adapters(self):
        cases = (
            ("core.ReportGenerator", "poe_log_analyze.stages.parsing.ParseLogs"),
            ("stages.merging.MergeHistory", "poe_log_analyze.stages.reconstruction.SourceHistory"),
            ("stages.parsing.ParseLogs", "poe_log_analyze.core.execution.ExecutionContext"),
            ("desktop.InputPanel", "tkinter.ttk"),
            ("core.request.ReportRequest", "poe_log_analyze.core.request.ReportMode"),
            ("core.result.ReportResult", "poe_log_analyze.core.result.AnalysisSummary"),
            ("core.plan.ReportPlan", "poe_log_analyze.core.request.ReportMode"),
            ("core.process.GenerationProcess", "poe_log_analyze.core.plan.ReportPlan"),
            ("core.execution.ExecutionContext", "poe_log_analyze.core.process.GenerationSnapshot"),
        )

        for source, target in cases:
            with self.subTest(source = source, target = target):
                self.assertIsNone(ArchitecturePolicy.violation("poe_log_analyze." + source, target))

    def test_nested_modules_are_hashed_with_distinct_relative_paths(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            for folder, contents in (("a", "first"), ("b", "second")):
                (root / folder).mkdir()
                (root / folder / "models.py").write_text(contents)

            self.assertEqual(CodeProvenance.source_hashes(root), {
                "a/models.py": hashlib.sha256(b"first").hexdigest(),
                "b/models.py": hashlib.sha256(b"second").hexdigest(),
            })

            (root / "b/models.py").write_text("changed")

            self.assertEqual(CodeProvenance.source_hashes(root)["b/models.py"], hashlib.sha256(b"changed").hexdigest())

    def test_one_named_class_per_source_file(self):
        """The filename must directly name its single implemented class."""

        for root in (PACKAGE, PACKAGE.parents[1] / 'tests'):
            for path in root.rglob('*.py'):
                if path.name in {'__init__.py', '__main__.py', 'report.py'}:
                    continue

                tree = ast.parse(path.read_text())
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

                with self.subTest(path = path):
                    self.assertEqual(classes, [path.stem])

    def test_every_function_is_a_direct_class_method(self):
        """Callbacks and fixtures must not become hidden module-level procedures."""

        root = PACKAGE.parents[1]

        for folder in ('src', 'scripts', 'tests'):
            for path in (root / folder).rglob('*.py'):
                tree = ast.parse(path.read_text())

                for parent in ast.walk(tree):
                    for node in ast.iter_child_nodes(parent):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            with self.subTest(path = path, method = node.name):
                                self.assertIsInstance(parent, ast.ClassDef)

    def test_package_initializers_do_not_hide_implementations(self):
        """Import a class from its file rather than an implicit package facade."""

        for path in PACKAGE.rglob('__init__.py'):
            with self.subTest(path = path):
                tree = ast.parse(path.read_text())

                self.assertFalse(any(isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
                                     for node in tree.body))
