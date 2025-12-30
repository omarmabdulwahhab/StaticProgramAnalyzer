from __future__ import annotations

from ..analysis.pointer_analysis import PointerAnalysisResult
from ..analysis.solver import DataFlowResult
from ..intermediate_representation.cfg import CFG


def render_text_report(
    cfg: CFG,
    live_vars: DataFlowResult,
    reaching_defs: DataFlowResult,
    pointer_result: PointerAnalysisResult,
) -> str:
    """Stub for textual reporting.

    How to implement:
    - Build a readable report per CFG block (statements, successors).
    - Show live variable and reaching definitions in/out sets.
    - Add a pointer analysis summary at the end.
    """
    raise NotImplementedError("Text reporting not implemented yet.")
