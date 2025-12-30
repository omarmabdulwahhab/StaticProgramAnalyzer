from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Statement:
    """
    A lightweight IR statement node.

    This IR is intentionally minimal: it preserves statement order, basic semantic
    tags (kind), and def/use sets for dataflow analyses, plus optional control-flow
    metadata for CFG construction (labels and jump targets).
    """

    sid: int
    text: str
    kind: str = "stmt"

    # Dataflow metadata
    defs: tuple[str, ...] = field(default_factory=tuple)
    uses: tuple[str, ...] = field(default_factory=tuple)

    # Control metadata (optional; used by CFG builder)
    condition: str | None = None
    label: str | None = None
    target: str | None = None
    targets: tuple[str, ...] = field(default_factory=tuple)

    # Utility flag for parser-inserted braces / synthetic nodes
    synthetic: bool = False


@dataclass(frozen=True)
class Program:
    """Program container for IR statements."""

    statements: list[Statement]
    language: str = "unknown"
    source: str | None = None

    def variables(self) -> set[str]:
        """Collect variable names mentioned across statements."""
        variables: set[str] = set()
        for stmt in self.statements:
            variables.update(stmt.defs)
            variables.update(stmt.uses)
        return variables

    def __iter__(self) -> Iterable[Statement]:
        return iter(self.statements)

    def by_id(self) -> dict[int, Statement]:
        """Quick lookup map from statement id to statement."""
        return {stmt.sid: stmt for stmt in self.statements}
