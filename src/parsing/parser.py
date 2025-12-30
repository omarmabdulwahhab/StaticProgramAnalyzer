from __future__ import annotations

import re
from typing import Iterable

from ..intermediate_representation.ast import Program, Statement

# Captures identifiers for a lightweight variable extraction pass.
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

TYPE_KEYWORDS = {
    "bool",
    "byte",
    "char",
    "double",
    "float",
    "int",
    "long",
    "short",
    "void",
    "signed",
    "unsigned",
    "wchar_t",
    "size_t",
}

TYPE_LIKE_KEYWORDS = {"struct", "class", "enum", "interface"}

MODIFIERS = {
    "const",
    "final",
    "static",
    "volatile",
    "mutable",
    "register",
    "public",
    "private",
    "protected",
    "transient",
    "synchronized",
    "abstract",
    "inline",
    "virtual",
    "extern",
    "friend",
    "typename",
    "typedef",
    "constexpr",
    "override",
    "noexcept",
    "signed",
    "unsigned",
}

KEYWORDS = (
    TYPE_KEYWORDS
    | TYPE_LIKE_KEYWORDS
    | MODIFIERS
    | {
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "return",
        "goto",
        "new",
        "delete",
        "try",
        "catch",
        "throw",
        "this",
        "super",
        "null",
        "true",
        "false",
    }
)


def _strip_comments(source: str) -> str:
    """Remove line and block comments from the input source."""
    cleaned: list[str] = []
    i = 0
    in_line = False
    in_block = False
    in_single = False
    in_double = False
    escape = False
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if in_line:
            if ch == "\n":
                in_line = False
                cleaned.append(ch)
            i += 1
            continue
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
            else:
                i += 1
            continue
        if escape:
            cleaned.append(ch)
            escape = False
            i += 1
            continue
        if ch == "\\" and (in_single or in_double):
            cleaned.append(ch)
            escape = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cleaned.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cleaned.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if ch == "/" and nxt == "/":
                in_line = True
                i += 2
                continue
            if ch == "/" and nxt == "*":
                in_block = True
                i += 2
                continue
        cleaned.append(ch)
        i += 1
    return "".join(cleaned)


def _extract_identifiers(text: str) -> list[str]:
    """Extract identifier tokens from a string."""
    return IDENT_RE.findall(text)


def _filter_identifiers(identifiers: Iterable[str]) -> tuple[str, ...]:
    """Filter identifiers by removing language keywords."""
    return tuple(name for name in identifiers if name not in KEYWORDS)


def _extract_paren_content(text: str) -> str | None:
    """Return the substring inside the first matched parentheses."""
    start = text.find("(")
    if start == -1:
        return None
    depth = 0
    in_single = False
    in_double = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : idx].strip()
    return None


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split text on a separator outside of parentheses and strings."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    escape = False
    for ch in text:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            buf.append(ch)
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            continue
        if in_single or in_double:
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(depth - 1, 0)
            buf.append(ch)
            continue
        if ch == sep and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def _tokenize_statements(source: str) -> list[str]:
    """Split source into statement-sized tokens and brace markers."""
    tokens: list[str] = []
    buf: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    escape = False
    for ch in source:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            buf.append(ch)
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            continue
        if in_single or in_double:
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(depth - 1, 0)
            buf.append(ch)
            continue
        if ch in {"{", "}"} and depth == 0:
            part = "".join(buf).strip()
            if part:
                tokens.append(part)
            tokens.append(ch)
            buf = []
            continue
        if ch == ";" and depth == 0:
            part = "".join(buf).strip()
            if part:
                tokens.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        tokens.append(part)
    return tokens


def _find_matching_paren(text: str, start: int) -> int | None:
    """Return the index of the matching closing parenthesis."""
    depth = 0
    in_single = False
    in_double = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                return idx
    return None


def _split_control_token(token: str) -> list[str]:
    """Split control statements with inline bodies into separate tokens."""
    stripped = token.strip()
    if stripped in {"{", "}"}:
        return [stripped]
    lower = " ".join(stripped.split()).lower()

    if lower.startswith("else if") or lower.startswith("if") or lower.startswith("while") or lower.startswith("for"):
        paren_start = stripped.find("(")
        if paren_start == -1:
            return [stripped]
        paren_end = _find_matching_paren(stripped, paren_start)
        if paren_end is None:
            return [stripped]
        head = stripped[: paren_end + 1].strip()
        tail = stripped[paren_end + 1 :].strip()
        if tail and not tail.startswith("{"):
            return [head, tail]
        return [stripped]

    if lower.startswith("else"):
        tail = stripped[len("else") :].strip()
        if tail and not tail.startswith("{"):
            return ["else", tail]
        return [stripped]

    if lower.startswith("do"):
        tail = stripped[len("do") :].strip()
        if tail and not tail.startswith("{"):
            return ["do", tail]
        return [stripped]

    if lower.startswith("case "):
        colon = stripped.find(":")
        if colon != -1:
            head = stripped[: colon + 1].strip()
            tail = stripped[colon + 1 :].strip()
            if tail:
                return [head, tail]
        return [stripped]

    if lower.startswith("default"):
        colon = stripped.find(":")
        if colon != -1:
            head = stripped[: colon + 1].strip()
            tail = stripped[colon + 1 :].strip()
            if tail:
                return [head, tail]
        return [stripped]

    label_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", stripped)
    if label_match:
        head = f"{label_match.group(1)}:"
        tail = label_match.group(2).strip()
        if tail:
            return [head, tail]
        return [head]

    return [stripped]


def _find_assignment(text: str) -> tuple[str, str, str] | None:
    """Find the first assignment operator in a statement."""
    operators = ["<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "="]
    in_single = False
    in_double = False
    escape = False
    for idx in range(len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\" and (in_single or in_double):
            escape = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        for op in operators:
            if text.startswith(op, idx):
                if op == "=":
                    prev = text[idx - 1] if idx > 0 else ""
                    nxt = text[idx + 1] if idx + 1 < len(text) else ""
                    if prev in {"<", ">", "!", "="} or nxt == "=":
                        break
                lhs = text[:idx].strip()
                rhs = text[idx + len(op) :].strip()
                return lhs, rhs, op
    return None


def _looks_like_function_decl(text: str) -> bool:
    """Detect likely function declarations/definitions to avoid mis-parsing."""
    if "(" not in text:
        return False
    if "=" in text:
        return False
    pattern = re.compile(
        r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)+[A-Za-z_][A-Za-z0-9_]*\s*\("
    )
    return bool(pattern.search(text))


def _starts_with_type(text: str) -> bool:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    if not words:
        return False
    idx = 0
    while idx < len(words) and words[idx] in MODIFIERS:
        idx += 1
    if idx >= len(words):
        return False
    if words[idx] in TYPE_KEYWORDS or words[idx] in TYPE_LIKE_KEYWORDS:
        return True
    if words[idx][0].isupper() and len(words) > idx + 1:
        return True
    return False


def _parse_declaration(text: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Parse a declaration statement into defs/uses."""
    if not _starts_with_type(text) or _looks_like_function_decl(text):
        return None

    word_tokens = list(re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", text))
    if not word_tokens:
        return None
    idx = 0
    while idx < len(word_tokens):
        word = word_tokens[idx].group(0)
        if word in MODIFIERS or word in TYPE_KEYWORDS:
            idx += 1
            continue
        if word in TYPE_LIKE_KEYWORDS:
            idx += 2
            continue
        break
    if idx >= len(word_tokens):
        return None
    decl_start = word_tokens[idx].start()
    declarators = text[decl_start:]
    parts = _split_top_level(declarators, ",")
    defs: list[str] = []
    uses: list[str] = []
    for part in parts:
        assignment = _find_assignment(part)
        if assignment:
            lhs, rhs, _ = assignment
            lhs_ids = _filter_identifiers(_extract_identifiers(lhs))
            rhs_ids = _filter_identifiers(_extract_identifiers(rhs))
            if lhs_ids:
                defs.append(lhs_ids[0])
            uses.extend(rhs_ids)
        else:
            ids = _filter_identifiers(_extract_identifiers(part))
            if ids:
                defs.append(ids[0])
    return tuple(defs), tuple(uses)


def _parse_assignment(text: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    assignment = _find_assignment(text)
    if not assignment:
        return None
    lhs, rhs, _ = assignment
    defs = _filter_identifiers(_extract_identifiers(lhs))
    uses = _filter_identifiers(_extract_identifiers(rhs))
    return defs, uses


def _parse_expression(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ids = _filter_identifiers(_extract_identifiers(text))
    return tuple(), ids


def _parse_for_components(text: str) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    content = _extract_paren_content(text)
    if content is None:
        return tuple(), tuple(), None
    parts = _split_top_level(content, ";")
    while len(parts) < 3:
        parts.append("")
    init, cond, update = (part.strip() for part in parts[:3])
    defs: list[str] = []
    uses: list[str] = []
    if init:
        decl = _parse_declaration(init)
        if decl:
            d, u = decl
            defs.extend(d)
            uses.extend(u)
        else:
            assign = _parse_assignment(init)
            if assign:
                d, u = assign
                defs.extend(d)
                uses.extend(u)
            else:
                uses.extend(_filter_identifiers(_extract_identifiers(init)))
    if cond:
        uses.extend(_filter_identifiers(_extract_identifiers(cond)))
    if update:
        assign = _parse_assignment(update)
        if assign:
            d, u = assign
            defs.extend(d)
            uses.extend(u)
        else:
            uses.extend(_filter_identifiers(_extract_identifiers(update)))
    condition = cond.strip() if cond else None
    return tuple(defs), tuple(uses), condition


def _parse_statement(sid: int, text: str) -> Statement:
    """Parse a single token into a Statement with defs/uses and kind."""
    normalized = text.strip()
    collapsed = " ".join(normalized.split())
    lower = collapsed.lower()

    if normalized == "{":
        return Statement(sid=sid, text="{", kind="block_start", synthetic=True)
    if normalized == "}":
        return Statement(sid=sid, text="}", kind="block_end", synthetic=True)

    label_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$", normalized)
    if label_match:
        label = label_match.group(1)
        return Statement(sid=sid, text=normalized, kind="label", label=label)

    if lower.startswith("else if"):
        condition = _extract_paren_content(collapsed)
        uses = _filter_identifiers(_extract_identifiers(condition or ""))
        return Statement(
            sid=sid,
            text=normalized,
            kind="else_if",
            uses=uses,
            condition=condition,
        )

    if lower.startswith("if"):
        condition = _extract_paren_content(collapsed)
        uses = _filter_identifiers(_extract_identifiers(condition or ""))
        return Statement(
            sid=sid, text=normalized, kind="if", uses=uses, condition=condition
        )

    if lower.startswith("else"):
        return Statement(sid=sid, text=normalized, kind="else")

    if lower.startswith("while"):
        condition = _extract_paren_content(collapsed)
        uses = _filter_identifiers(_extract_identifiers(condition or ""))
        return Statement(
            sid=sid, text=normalized, kind="while", uses=uses, condition=condition
        )

    if lower.startswith("for"):
        defs, uses, condition = _parse_for_components(collapsed)
        return Statement(
            sid=sid,
            text=normalized,
            kind="for",
            defs=defs,
            uses=uses,
            condition=condition,
        )

    if lower.startswith("do"):
        return Statement(sid=sid, text=normalized, kind="do")

    if lower.startswith("switch"):
        condition = _extract_paren_content(collapsed)
        uses = _filter_identifiers(_extract_identifiers(condition or ""))
        return Statement(
            sid=sid,
            text=normalized,
            kind="switch",
            uses=uses,
            condition=condition,
        )

    case_match = re.match(r"^\s*case\s+(.+)\s*:\s*$", normalized, re.IGNORECASE)
    if case_match:
        value = case_match.group(1).strip()
        uses = _filter_identifiers(_extract_identifiers(value))
        return Statement(
            sid=sid,
            text=normalized,
            kind="case",
            uses=uses,
            target=value,
        )

    default_match = re.match(r"^\s*default\s*:\s*$", normalized, re.IGNORECASE)
    if default_match:
        return Statement(sid=sid, text=normalized, kind="default")

    if lower.startswith("break"):
        return Statement(sid=sid, text=normalized, kind="break")

    if lower.startswith("continue"):
        return Statement(sid=sid, text=normalized, kind="continue")

    if lower.startswith("return"):
        expr = normalized[len("return") :].strip()
        uses = _filter_identifiers(_extract_identifiers(expr))
        return Statement(sid=sid, text=normalized, kind="return", uses=uses)

    if lower.startswith("goto"):
        target = normalized[len("goto") :].strip()
        return Statement(sid=sid, text=normalized, kind="goto", target=target)

    if _looks_like_function_decl(normalized):
        return Statement(sid=sid, text=normalized, kind="func")

    decl = _parse_declaration(normalized)
    if decl:
        defs, uses = decl
        return Statement(sid=sid, text=normalized, kind="decl", defs=defs, uses=uses)

    assign = _parse_assignment(normalized)
    if assign:
        defs, uses = assign
        return Statement(sid=sid, text=normalized, kind="assign", defs=defs, uses=uses)

    defs, uses = _parse_expression(normalized)
    return Statement(sid=sid, text=normalized, kind="expr", defs=defs, uses=uses)


def parse_source(source: str, language: str | None = None) -> Program:
    """Parse source into a Program using line-based heuristics."""
    cleaned_source = _strip_comments(source)
    tokens = _tokenize_statements(cleaned_source)
    statements: list[Statement] = []
    sid = 1
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_split_control_token(token))
    for token in expanded:
        if not token.strip():
            continue
        statement = _parse_statement(sid, token)
        statements.append(statement)
        sid += 1
    return Program(statements=statements, language=language, source=source)


def parse_java(source: str) -> Program:
    """Parse Java source code into an IR Program."""
    return parse_source(source, language="java")


def parse_cpp(source: str) -> Program:
    """Parse C++ source code into an IR Program."""
    return parse_source(source, language="cpp")
