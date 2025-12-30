from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..intermediate_representation.ast import Program, Statement
from .parser import parse_cpp


@dataclass
class _CollectedStatement:
    key: tuple[int, int, int]
    kind: str
    text: str
    defs: tuple[str, ...]
    uses: tuple[str, ...]
    label: str | None = None
    target: str | None = None
    synthetic: bool = False


def _run_clang(source: str) -> dict:
    clang_cmd = os.environ.get("CLANG_CMD", "clang++")
    with tempfile.TemporaryDirectory(prefix="clang-src-") as tmpdir:
        src_path = Path(tmpdir) / "input.cpp"
        src_path.write_text(source, encoding="utf-8")

        cmd = [
            clang_cmd,
            "-Xclang",
            "-ast-dump=json",
            "-fsyntax-only",
            "-std=c++17",
            str(src_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Clang failed: {stderr}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse Clang AST JSON output.") from exc


def _offset_to_line_col(source_lines: list[str], offset: int) -> tuple[int, int] | None:
    if offset < 0:
        return None
    total = 0
    for idx, line in enumerate(source_lines, start=1):
        line_len = len(line)
        if offset <= total + line_len:
            return idx, max(1, offset - total + 1)
        total += line_len + 1
    return None


def _range_key(
    node: dict,
    tie: int,
    source_lines: list[str],
    use_end: bool = False,
) -> tuple[int, int, int] | None:
    node_range = node.get("range")
    if not node_range:
        return None
    point = node_range.get("end") if use_end else node_range.get("begin")
    point = point or {}
    line = point.get("line")
    col = point.get("col")
    if line is None or col is None:
        offset = point.get("offset")
        if offset is None:
            return None
        mapped = _offset_to_line_col(source_lines, int(offset))
        if not mapped:
            return None
        line, col = mapped
    return int(line), int(col), tie


def _slice_source(source_lines: list[str], node: dict) -> str:
    node_range = node.get("range") or {}
    begin = node_range.get("begin") or {}
    end = node_range.get("end") or {}
    b_line = begin.get("line")
    b_col = begin.get("col")
    e_line = end.get("line")
    e_col = end.get("col")
    if not all(isinstance(x, int) for x in (b_line, b_col, e_line, e_col)):
        return node.get("kind", "stmt")
    if b_line < 1 or e_line < 1:
        return node.get("kind", "stmt")
    if b_line == e_line:
        line = source_lines[b_line - 1]
        return line[b_col - 1 : e_col].strip()
    snippet = [source_lines[b_line - 1][b_col - 1 :]]
    for line_no in range(b_line, e_line - 1):
        snippet.append(source_lines[line_no])
    snippet.append(source_lines[e_line - 1][: e_col])
    return " ".join(part.strip() for part in snippet if part.strip()) or node.get(
        "kind", "stmt"
    )


def _collect_declref_names(node: dict) -> list[str]:
    names: list[str] = []
    if isinstance(node, dict):
        if node.get("kind") in {"DeclRefExpr", "MemberExpr"}:
            name = node.get("name")
            if isinstance(name, str):
                names.append(name)
        for child in node.get("inner", []) or []:
            names.extend(_collect_declref_names(child))
    elif isinstance(node, list):
        for child in node:
            names.extend(_collect_declref_names(child))
    return names


def _collect_vardecl_names(node: dict) -> list[str]:
    names: list[str] = []
    if isinstance(node, dict):
        if node.get("kind") == "VarDecl":
            name = node.get("name")
            if isinstance(name, str):
                names.append(name)
        for child in node.get("inner", []) or []:
            names.extend(_collect_vardecl_names(child))
    elif isinstance(node, list):
        for child in node:
            names.extend(_collect_vardecl_names(child))
    return names


def _first_expr_child(children: list[dict]) -> dict | None:
    for child in children:
        if not isinstance(child, dict):
            continue
        kind = child.get("kind", "")
        if kind.endswith("Expr") or kind in {"ImplicitCastExpr", "ParenExpr", "UnaryOperator"}:
            return child
    return None


def _find_call_expr(node: dict | None) -> dict | None:
    if not isinstance(node, dict):
        return None
    if node.get("kind") in {"CallExpr", "CXXMemberCallExpr", "CXXOperatorCallExpr"}:
        return node
    for child in node.get("inner", []) or []:
        if isinstance(child, dict):
            found = _find_call_expr(child)
            if found:
                return found
    return None


def _condition_expr(node: dict) -> dict | None:
    children = node.get("inner", []) or []
    expr = _first_expr_child(children)
    if expr:
        return expr
    for child in children:
        if isinstance(child, dict) and child.get("kind") in {"BinaryOperator", "UnaryOperator"}:
            return child
    return None


def _extract_case_value(node: dict) -> str | None:
    for child in node.get("inner", []) or []:
        if isinstance(child, dict) and child.get("kind") == "IntegerLiteral":
            value = child.get("value")
            if value is not None:
                return str(value)
    return None


def _collect_statements(node: dict, source_lines: list[str]) -> list[_CollectedStatement]:
    statements: list[_CollectedStatement] = []
    kind = node.get("kind")

    if kind == "CompoundStmt":
        start_key = _range_key(node, 0, source_lines)
        end_key = _range_key(node, 2, source_lines, use_end=True)
        if start_key:
            statements.append(
                _CollectedStatement(
                    key=start_key,
                    kind="block_start",
                    text="{",
                    defs=tuple(),
                    uses=tuple(),
                    synthetic=True,
                )
            )
        if end_key:
            statements.append(
                _CollectedStatement(
                    key=end_key,
                    kind="block_end",
                    text="}",
                    defs=tuple(),
                    uses=tuple(),
                    synthetic=True,
                )
            )

    control_map = {
        "IfStmt": "if",
        "ForStmt": "for",
        "WhileStmt": "while",
        "DoStmt": "do",
        "SwitchStmt": "switch",
        "CaseStmt": "case",
        "DefaultStmt": "default",
        "BreakStmt": "break",
        "ContinueStmt": "continue",
        "ReturnStmt": "return",
        "GotoStmt": "goto",
        "LabelStmt": "label",
    }
    if kind in control_map:
        key = _range_key(node, 1, source_lines)
        if key:
            text = _slice_source(source_lines, node)
            label = None
            target = None
            uses = tuple()
            if kind == "LabelStmt":
                label = node.get("name") or node.get("label")
                if isinstance(label, str):
                    text = f"{label}:"
            if kind == "GotoStmt":
                target = node.get("label") or node.get("name")
            if kind == "CaseStmt":
                target = _extract_case_value(node)
            if kind in {"IfStmt", "WhileStmt", "DoStmt", "SwitchStmt", "ForStmt"}:
                cond = _condition_expr(node)
                if cond:
                    uses = tuple(_collect_declref_names(cond))
            if kind == "ReturnStmt":
                expr = _condition_expr(node)
                if expr:
                    uses = tuple(_collect_declref_names(expr))
            statements.append(
                _CollectedStatement(
                    key=key,
                    kind=control_map[kind],
                    text=text,
                    defs=tuple(),
                    uses=uses,
                    label=label if isinstance(label, str) else None,
                    target=target if isinstance(target, str) else None,
                )
            )

    if kind in {"CallExpr", "CXXMemberCallExpr", "CXXOperatorCallExpr"}:
        key = _range_key(node, 1, source_lines)
        if key:
            text = _slice_source(source_lines, node)
            uses = tuple(_collect_declref_names(node))
            statements.append(
                _CollectedStatement(
                    key=key,
                    kind="expr",
                    text=text,
                    defs=tuple(),
                    uses=uses,
                )
            )

    if kind == "UnaryOperator":
        opcode = node.get("opcode")
        if opcode in {"++", "--"}:
            key = _range_key(node, 1, source_lines)
            if not key:
                child = _first_expr_child(node.get("inner", []) or [])
                key = _range_key(child, 1, source_lines) if child else None
            if key:
                text = _slice_source(source_lines, node)
                if opcode not in text:
                    operand = None
                    for child in node.get("inner", []) or []:
                        if isinstance(child, dict):
                            operand = child
                            break
                    operand_text = _slice_source(source_lines, operand) if operand else ""
                    if node.get("isPostfix") is True:
                        text = f"{operand_text}{opcode}" if operand_text else f"{text}{opcode}"
                    else:
                        text = f"{opcode}{operand_text}" if operand_text else f"{opcode}{text}"
                defs = tuple(_collect_declref_names(node))
                statements.append(
                    _CollectedStatement(
                        key=key,
                        kind="assign",
                        text=text,
                        defs=defs[:1],
                        uses=defs,
                    )
                )

    if kind == "CXXThrowExpr":
        key = _range_key(node, 1, source_lines)
        if key:
            text = _slice_source(source_lines, node)
            uses = tuple(_collect_declref_names(node))
            statements.append(
                _CollectedStatement(
                    key=key,
                    kind="throw",
                    text=text,
                    defs=tuple(),
                    uses=uses,
                )
            )

    if kind == "DeclStmt":
        key = _range_key(node, 1, source_lines)
        if key:
            defs = tuple(_collect_vardecl_names(node))
            uses = tuple(_collect_declref_names(node))
            text = _slice_source(source_lines, node)
            statements.append(
                _CollectedStatement(
                    key=key,
                    kind="decl",
                    text=text,
                    defs=defs,
                    uses=uses,
                )
            )

    if kind in {"BinaryOperator", "CompoundAssignOperator"}:
        opcode = node.get("opcode")
        if opcode:
            key = _range_key(node, 1, source_lines)
            if key:
                text = _slice_source(source_lines, node)
                inner = node.get("inner") or []
                lhs = inner[0] if inner else {}
                rhs = inner[1] if len(inner) > 1 else {}
                defs = tuple(_collect_declref_names(lhs))
                uses = tuple(_collect_declref_names(rhs))
                if opcode == "=":
                    statements.append(
                        _CollectedStatement(
                            key=key,
                            kind="assign",
                            text=text,
                            defs=defs[:1],
                            uses=uses,
                        )
                    )
                    call_expr = _find_call_expr(rhs if isinstance(rhs, dict) else None)
                    if call_expr:
                        call_key = _range_key(call_expr, 1, source_lines) or _range_key(
                            node, 2, source_lines
                        )
                        if call_key:
                            call_text = _slice_source(source_lines, call_expr)
                            call_uses = tuple(_collect_declref_names(call_expr))
                            statements.append(
                                _CollectedStatement(
                                    key=call_key,
                                    kind="expr",
                                    text=call_text,
                                    defs=tuple(),
                                    uses=call_uses,
                                )
                            )
                elif kind == "CompoundAssignOperator":
                    statements.append(
                        _CollectedStatement(
                            key=key,
                            kind="assign",
                            text=text,
                            defs=defs[:1],
                            uses=tuple(defs[:1]) + uses,
                        )
                    )

    if kind == "ExprStmt":
        child = _first_expr_child(node.get("inner", []) or [])
        key = _range_key(node, 1, source_lines)
        if not key and child:
            key = _range_key(child, 1, source_lines)
        if key:
            text = _slice_source(source_lines, child or node)
            uses = tuple(_collect_declref_names(child or node))
            defs: tuple[str, ...] = tuple()
            expr_kind = "expr"
            if child and child.get("kind") == "UnaryOperator":
                opcode = child.get("opcode")
                if opcode in {"++", "--"}:
                    defs = tuple(_collect_declref_names(child))
                    uses = defs
                    expr_kind = "assign"
            elif "++" in text or "--" in text:
                defs = tuple(_collect_declref_names(child or node))
                uses = defs
                expr_kind = "assign"
            statements.append(
                _CollectedStatement(
                    key=key,
                    kind=expr_kind,
                    text=text,
                    defs=defs[:1],
                    uses=uses,
                )
            )


    for child in node.get("inner", []) or []:
        if isinstance(child, dict):
            statements.extend(_collect_statements(child, source_lines))
    return statements


def _parse_clang_ast(source: str, ast: dict) -> list[Statement]:
    source_lines = source.splitlines()
    collected = _collect_statements(ast, source_lines)
    collected.sort(key=lambda item: item.key)
    statements: list[Statement] = []
    sid = 1
    seen: set[tuple[tuple[int, int, int], str, str]] = set()
    for item in collected:
        key = (item.key, item.kind, item.text)
        if key in seen:
            continue
        seen.add(key)
        statements.append(
            Statement(
                sid=sid,
                text=item.text,
                kind=item.kind,
                defs=item.defs,
                uses=item.uses,
                label=item.label,
                target=item.target,
                synthetic=item.synthetic,
            )
        )
        sid += 1
    return statements


def build_ir_with_clang(source: str) -> Program:
    """Build an Intermediate Representation for C++ using Clang CLI output."""
    if not isinstance(source, str):
        raise TypeError("source must be a string containing C++ code.")
    if not source.strip():
        return Program(statements=[], language="cpp", source=source)
    ast = _run_clang(source)
    statements = _parse_clang_ast(source, ast)
    if not statements:
        return parse_cpp(source)
    return Program(statements=statements, language="cpp", source=source)
