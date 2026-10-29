from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs


@dataclass(frozen = True, slots = True)
class RenderedReport:
    """Rendered site awaiting verification and publication."""

    directory: Path
    content: ReportContent
    language: str
    renderer_versions: dict[str, str]
    pdf: bool = False
    search: dict[str, Any] = field(default_factory = dict)
    basic_block: bool = False
    outputs: ReportOutputs | None = None
    children: tuple['RenderedReport', ...] = ()
    pdf_dark: bool = False
