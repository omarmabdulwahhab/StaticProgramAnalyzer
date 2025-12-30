from __future__ import annotations

from ..intermediate_representation.cfg import CFG
from .solver import DataFlowResult


def compute_reaching_definitions(cfg: CFG) -> DataFlowResult:
    """Stub for reaching definitions analysis (forward data-flow).

    How to implement:
    - Define GEN/KILL per node based on variable definitions.
    - Use a forward worklist solver to compute in/out sets.
    - Represent definitions with stable ids (e.g., var@node).
    """
    raise NotImplementedError("Reaching definitions analysis not implemented yet.")
