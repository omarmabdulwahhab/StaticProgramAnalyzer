from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Hashable, Iterable


@dataclass
class DataFlowResult:
    """Placeholder data structure for analysis results."""

    in_sets: dict[Hashable, set[str]]
    out_sets: dict[Hashable, set[str]]


TransferFn = Callable[[Hashable, set[str]], set[str]]


def solve_worklist(
    nodes: Iterable[Hashable],
    predecessors: Callable[[Hashable], Iterable[Hashable]],
    successors: Callable[[Hashable], Iterable[Hashable]],
    direction: str,
    transfer: TransferFn,
) -> DataFlowResult:
    """Stub for worklist/fixpoint solver; to be implemented by the analysis team.

    How to implement:
    - Initialize in/out maps to empty sets per node.
    - Push all nodes to a worklist; pop until fixpoint.
    - Recompute in/out from preds/succs based on direction and transfer.
    - Re-enqueue neighbors when a node's out set changes.
    """
    raise NotImplementedError("Worklist solver not implemented yet.")
