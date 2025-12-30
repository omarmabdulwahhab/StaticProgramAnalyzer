from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .ast import Statement


@dataclass
class CFGNode:
    """CFG node wrapping a statement."""

    statement: Statement
    successors: list[int] = field(default_factory=list)
    predecessors: list[int] = field(default_factory=list)


@dataclass
class CFG:
    """Control-flow graph container."""

    nodes: dict[int, CFGNode]
    entry: int | None
    exit: int | None

    def __iter__(self) -> Iterable[CFGNode]:
        return iter(self.nodes.values())

    def add_edge(self, source: int, target: int) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("CFG edge endpoints must exist in nodes.")
        src_node = self.nodes[source]
        tgt_node = self.nodes[target]
        if target not in src_node.successors:
            src_node.successors.append(target)
        if source not in tgt_node.predecessors:
            tgt_node.predecessors.append(source)

    def remove_edge(self, source: int, target: int) -> None:
        if source not in self.nodes or target not in self.nodes:
            return
        src_node = self.nodes[source]
        tgt_node = self.nodes[target]
        if target in src_node.successors:
            src_node.successors.remove(target)
        if source in tgt_node.predecessors:
            tgt_node.predecessors.remove(source)


@dataclass
class ControlInfo:
    kind: str
    body_start: int | None
    body_end: int | None
    after_body: int | None


def _build_block_pairs(statements: list[Statement]) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for idx, stmt in enumerate(statements):
        if stmt.kind == "block_start":
            stack.append(idx)
        elif stmt.kind == "block_end" and stack:
            start_idx = stack.pop()
            pairs[start_idx] = idx
    return pairs


def _previous_non_synthetic(index: int, statements: list[Statement]) -> int | None:
    for idx in range(index - 1, -1, -1):
        if not statements[idx].synthetic:
            return idx
    return None


def _body_range(
    index: int, statements: list[Statement], block_pairs: dict[int, int]
) -> ControlInfo:
    if index + 1 >= len(statements):
        return ControlInfo(statements[index].kind, None, None, None)
    start = index + 1
    if statements[start].kind == "block_start":
        end = block_pairs.get(start, start)
    else:
        end = start
    after = end + 1 if end + 1 < len(statements) else None
    return ControlInfo(statements[index].kind, start, end, after)


def build_cfg(statements: list[Statement]) -> CFG:
    """Build a control-flow graph using lightweight structured heuristics."""
    nodes: dict[int, CFGNode] = {stmt.sid: CFGNode(statement=stmt) for stmt in statements}
    if not nodes:
        return CFG(nodes={}, entry=None, exit=None)

    ordered = list(statements)
    entry = ordered[0].sid
    exit_node = ordered[-1].sid

    cfg = CFG(nodes=nodes, entry=entry, exit=exit_node)

    # Default sequential edges.
    for current, nxt in zip(ordered, ordered[1:]):
        if current.kind in {"return", "break", "continue", "goto"}:
            continue
        cfg.add_edge(current.sid, nxt.sid)

    block_pairs = _build_block_pairs(ordered)
    block_owner: dict[int, int] = {}
    for start_idx in block_pairs:
        owner = _previous_non_synthetic(start_idx, ordered)
        if owner is not None:
            block_owner[start_idx] = owner

    control_info: dict[int, ControlInfo] = {}
    for idx, stmt in enumerate(ordered):
        if stmt.kind in {"if", "else_if", "else", "while", "for", "switch", "do"}:
            control_info[idx] = _body_range(idx, ordered, block_pairs)

    do_tail_map: dict[int, int] = {}
    do_tail_set: set[int] = set()
    for start_idx, end_idx in block_pairs.items():
        owner_idx = block_owner.get(start_idx)
        if owner_idx is None:
            continue
        owner_stmt = ordered[owner_idx]
        if owner_stmt.kind != "do":
            continue
        tail_idx = end_idx + 1
        if tail_idx < len(ordered) and ordered[tail_idx].kind == "while":
            do_tail_map[owner_idx] = tail_idx
            do_tail_set.add(tail_idx)
    for idx, stmt in enumerate(ordered):
        if stmt.kind != "do":
            continue
        info = control_info.get(idx)
        if info is None or info.after_body is None:
            continue
        if ordered[info.after_body].kind == "while":
            do_tail_map[idx] = info.after_body
            do_tail_set.add(info.after_body)

    # Branch edges for if/else-if.
    for idx, stmt in enumerate(ordered):
        if stmt.kind not in {"if", "else_if"}:
            continue
        info = control_info.get(idx)
        if info is None or info.after_body is None:
            continue
        after_stmt = ordered[info.after_body]
        if after_stmt.kind in {"else", "else_if"}:
            cfg.add_edge(stmt.sid, after_stmt.sid)
        else:
            cfg.add_edge(stmt.sid, after_stmt.sid)

    def _find_else_chain_join(start_idx: int) -> int | None:
        current = start_idx
        join: int | None = None
        while current is not None and ordered[current].kind in {"else", "else_if"}:
            current_info = control_info.get(current)
            if current_info is None:
                break
            join = current_info.after_body
            if join is None:
                break
            if join < len(ordered) and ordered[join].kind in {"else", "else_if"}:
                current = join
                continue
            return join
        return join

    # Ensure if/else bodies do not fall through into subsequent else blocks.
    for idx, stmt in enumerate(ordered):
        if stmt.kind not in {"if", "else_if"}:
            continue
        info = control_info.get(idx)
        if info is None or info.body_end is None or info.after_body is None:
            continue
        if ordered[info.after_body].kind not in {"else", "else_if"}:
            continue
        join_idx = _find_else_chain_join(info.after_body)
        if join_idx is None:
            continue
        cfg.remove_edge(ordered[info.body_end].sid, ordered[info.after_body].sid)
        cfg.add_edge(ordered[info.body_end].sid, ordered[join_idx].sid)

    for idx, stmt in enumerate(ordered):
        if stmt.kind not in {"else_if", "else"}:
            continue
        info = control_info.get(idx)
        if info is None or info.body_end is None or info.after_body is None:
            continue
        if ordered[info.after_body].kind not in {"else", "else_if"}:
            continue
        join_idx = _find_else_chain_join(info.after_body)
        if join_idx is None:
            continue
        cfg.remove_edge(ordered[info.body_end].sid, ordered[info.after_body].sid)
        cfg.add_edge(ordered[info.body_end].sid, ordered[join_idx].sid)

    # Loop edges for while/for.
    for idx, stmt in enumerate(ordered):
        if stmt.kind not in {"while", "for"} or idx in do_tail_set:
            continue
        info = control_info.get(idx)
        if info is None or info.body_start is None or info.body_end is None:
            continue
        if info.after_body is not None:
            cfg.add_edge(stmt.sid, ordered[info.after_body].sid)
        cfg.add_edge(ordered[info.body_end].sid, stmt.sid)
        if info.after_body is not None:
            cfg.remove_edge(ordered[info.body_end].sid, ordered[info.after_body].sid)

    # Switch edges to cases.
    for idx, stmt in enumerate(ordered):
        if stmt.kind != "switch":
            continue
        info = control_info.get(idx)
        if info is None or info.body_start is None or info.body_end is None:
            continue
        if info.after_body is not None:
            cfg.add_edge(stmt.sid, ordered[info.after_body].sid)
        for case_idx in range(info.body_start, info.body_end + 1):
            if ordered[case_idx].kind in {"case", "default"}:
                cfg.add_edge(stmt.sid, ordered[case_idx].sid)

    # Do-while edges from tail condition back to body start.
    for do_idx, tail_idx in do_tail_map.items():
        info = control_info.get(do_idx)
        if info is None or info.body_start is None:
            continue
        cfg.add_edge(ordered[tail_idx].sid, ordered[info.body_start].sid)

    # Break/continue/goto handling with a context stack.
    label_map = {
        stmt.label: stmt.sid for stmt in ordered if stmt.kind == "label" and stmt.label
    }

    loop_kinds = {"while", "for", "do"}
    break_kinds = loop_kinds | {"switch"}
    context_stack: list[int] = []
    for idx, stmt in enumerate(ordered):
        if stmt.kind in break_kinds and idx in control_info:
            context_stack.append(idx)

        if stmt.kind == "break":
            target_idx = None
            for ctx_idx in reversed(context_stack):
                if ordered[ctx_idx].kind in break_kinds:
                    if ordered[ctx_idx].kind == "do":
                        tail_idx = do_tail_map.get(ctx_idx)
                        if tail_idx is not None:
                            target_idx = (
                                tail_idx + 1 if tail_idx + 1 < len(ordered) else None
                            )
                        else:
                            target_idx = control_info[ctx_idx].after_body
                    else:
                        target_idx = control_info[ctx_idx].after_body
                    break
            if target_idx is not None:
                cfg.add_edge(stmt.sid, ordered[target_idx].sid)

        if stmt.kind == "continue":
            target_idx = None
            for ctx_idx in reversed(context_stack):
                if ordered[ctx_idx].kind in loop_kinds:
                    target_idx = do_tail_map.get(ctx_idx, ctx_idx)
                    break
            if target_idx is not None:
                cfg.add_edge(stmt.sid, ordered[target_idx].sid)

        if stmt.kind == "goto" and stmt.target:
            target_sid = label_map.get(stmt.target)
            if target_sid is not None:
                cfg.add_edge(stmt.sid, target_sid)

        if stmt.kind == "if_goto" and stmt.target:
            target_sid = label_map.get(stmt.target)
            if target_sid is not None:
                cfg.add_edge(stmt.sid, target_sid)

        if stmt.kind == "switch_goto" and stmt.targets:
            for target in stmt.targets:
                target_sid = label_map.get(target)
                if target_sid is not None:
                    cfg.add_edge(stmt.sid, target_sid)

        while (
            context_stack
            and control_info[context_stack[-1]].body_end is not None
            and control_info[context_stack[-1]].body_end == idx
        ):
            context_stack.pop()

    return cfg


def build_linear_cfg(statements: list[Statement]) -> CFG:
    """Build a CFG with structured edges using parser metadata."""
    return build_cfg(statements)
