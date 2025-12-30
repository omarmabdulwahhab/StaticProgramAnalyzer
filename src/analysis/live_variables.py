from __future__ import annotations

from ..intermediate_representation.cfg import CFG
from .solver import DataFlowResult


def compute_live_variables(cfg: CFG) -> DataFlowResult:
    """Stub for live variable analysis (backward data-flow).

    How to implement:
    - Define GEN/KILL per node from statements and variable uses/defs.
    - Use a backward worklist solver to compute in/out sets.
    - Return DataFlowResult keyed by CFG node id.
    """
    raise NotImplementedError("Live variable analysis not implemented yet.")
