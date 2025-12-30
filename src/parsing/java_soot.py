from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..intermediate_representation.ast import Program, Statement
from .parser import parse_java

_CLASS_RE = re.compile(r"\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_JAVA_KEYWORDS = {
    "abstract","assert","boolean","break","byte","case","catch","char","class","const","continue",
    "default","do","double","else","enum","extends","final","finally","float","for","goto","if",
    "implements","import","instanceof","int","interface","long","native","new","null","package",
    "private","protected","public","return","short","static","strictfp","super","switch",
    "synchronized","this","throw","throws","transient","try","void","volatile","while","true","false",
}

_JIMPLE_KEYWORDS = {
    "staticinvoke","virtualinvoke","specialinvoke","interfaceinvoke","dynamicinvoke",
    "newarray","newmultiarray","lengthof","cast","instanceof",
}


def _guess_class_name(source: str) -> str:
    m = _CLASS_RE.search(source)
    return m.group(2) if m else "TempClass"


def _extract_identifiers(text: str) -> tuple[str, ...]:
    return tuple(
        x for x in _IDENT_RE.findall(text)
        if x not in _JAVA_KEYWORDS and x not in _JIMPLE_KEYWORDS
    )


def _split_assignment(text: str):
    for op in (":=", "="):
        if op in text:
            return [p.strip() for p in text.split(op, 1)]
    return None


def _parse_jimple(lines: list[str]) -> list[Statement]:
    """
    Minimal Jimple parser (best-effort). It is not intended to be a full Jimple frontend;
    it only extracts enough structure for Part 1 (defs/uses + control statements).
    """
    stmts: list[Statement] = []
    sid = 1
    i = 0

    while i < len(lines):
        raw = lines[i].strip()
        i += 1

        if not raw or raw.startswith("//") or raw.startswith("."):
            continue
        if raw in ("{", "}"):
            continue

        # label
        if raw.endswith(":") and " " not in raw:
            label = raw[:-1]
            stmts.append(Statement(sid=sid, text=raw, kind="label", label=label))
            sid += 1
            continue

        # if ... goto Lx;
        if raw.startswith("if ") and " goto " in raw:
            cond, _, tgt = raw.partition(" goto ")
            cond = cond[len("if "):].strip()
            tgt = tgt.rstrip(";").strip()
            stmts.append(
                Statement(
                    sid=sid,
                    text=raw,
                    kind="if_goto",
                    condition=cond,
                    target=tgt,
                    uses=_extract_identifiers(cond),
                )
            )
            sid += 1
            continue

        # goto Lx;
        if raw.startswith("goto "):
            tgt = raw[len("goto "):].rstrip(";").strip()
            stmts.append(Statement(sid=sid, text=raw, kind="goto", target=tgt))
            sid += 1
            continue

        # tableswitch / lookupswitch blocks:
        # tableswitch(x) { ... goto L1; ... default: goto Ld; }
        if raw.startswith("tableswitch") or raw.startswith("lookupswitch"):
            block_targets: list[str] = []
            # read until matching "}"
            while i < len(lines):
                line = lines[i].strip()
                i += 1
                if line == "}":
                    break
                if "goto " in line:
                    # ex: "case 1: goto label1;" OR "default: goto label2;"
                    tgt = line.split("goto", 1)[1].rstrip(";").strip()
                    if tgt:
                        block_targets.append(tgt)
            stmts.append(
                Statement(
                    sid=sid,
                    text=raw,
                    kind="switch_goto",
                    uses=_extract_identifiers(raw),
                    targets=tuple(block_targets),
                )
            )
            sid += 1
            continue

        # return / return <val>;
        if raw.startswith("return"):
            expr = raw[len("return"):].rstrip(";").strip()
            stmts.append(
                Statement(
                    sid=sid,
                    text=raw,
                    kind="return",
                    uses=_extract_identifiers(expr),
                )
            )
            sid += 1
            continue

        # invoke
        if "invoke" in raw:
            stmts.append(
                Statement(
                    sid=sid,
                    text=raw,
                    kind="invoke",
                    uses=_extract_identifiers(raw),
                )
            )
            sid += 1
            continue

        # assignment / identity
        assignment = _split_assignment(raw.rstrip(";"))
        if assignment:
            lhs, rhs = assignment
            lhs_ids = _extract_identifiers(lhs)
            rhs_ids = _extract_identifiers(rhs)
            defs = (lhs_ids[0],) if lhs_ids else ()
            kind = "identity" if rhs.strip().startswith("@") else "assign"
            stmts.append(
                Statement(
                    sid=sid,
                    text=raw,
                    kind=kind,
                    defs=defs,
                    uses=rhs_ids,
                )
            )
            sid += 1
            continue

        # fallback expression
        stmts.append(
            Statement(
                sid=sid,
                text=raw,
                kind="expr",
                uses=_extract_identifiers(raw),
            )
        )
        sid += 1

    return stmts


def _resolve_java_home() -> Path:
    home = os.environ.get("SOOT_JAVA_HOME") or os.environ.get("JAVA_HOME")
    if not home:
        raise RuntimeError("Set SOOT_JAVA_HOME (recommended) or JAVA_HOME to a full JDK (e.g., JDK 21).")
    p = Path(home)
    if not p.exists():
        raise RuntimeError(f"JDK home does not exist: {p}")
    return p


def _resolve_java_cmd() -> str:
    home = _resolve_java_home()
    exe = "java.exe" if os.name == "nt" else "java"
    p = home / "bin" / exe
    return str(p) if p.exists() else "java"


def _resolve_javac_cmd() -> str:
    home = _resolve_java_home()
    exe = "javac.exe" if os.name == "nt" else "javac"
    p = home / "bin" / exe
    if not p.exists():
        raise RuntimeError(f"javac not found under JDK: {p}")
    return str(p)


def _resolve_soot_jar() -> str:
    jar = os.environ.get("SOOT_JAR")
    if jar and Path(jar).exists():
        return jar
    raise RuntimeError("SOOT_JAR is not set or invalid. Point it to soot-*-jar-with-dependencies.jar")


def soot_available() -> bool:
    try:
        _resolve_soot_jar()
        _resolve_java_cmd()
        _resolve_javac_cmd()
        return True
    except Exception:
        return False


def _compile_java_to_classes(src_dir: Path, classes_dir: Path) -> None:
    javac = _resolve_javac_cmd()
    classes_dir.mkdir(parents=True, exist_ok=True)

    java_files = list(src_dir.glob("*.java"))
    if not java_files:
        raise RuntimeError("No .java files to compile.")

    cmd = [
        javac,
        "-g",
        "-d", str(classes_dir),
        *[str(f) for f in java_files],
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "javac failed:\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDERR:\n{(r.stderr or '').strip()}\n\n"
            f"STDOUT:\n{(r.stdout or '').strip()}\n"
        )


def _run_soot_on_classes(classes_dir: Path, out_dir: Path) -> list[str]:
    java = _resolve_java_cmd()
    soot_jar = _resolve_soot_jar()

    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        java,
        "-cp", soot_jar,
        "soot.Main",
        "-pp",
        "-allow-phantom-refs",
        "-src-prec", "class",
        "-process-dir", str(classes_dir),
        "-f", "J",
        "-d", str(out_dir),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            "Soot failed:\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDERR:\n{(r.stderr or '').strip()}\n\n"
            f"STDOUT:\n{(r.stdout or '').strip()}\n"
        )

    jimple_files = list(out_dir.rglob("*.jimple"))
    if not jimple_files:
        raise RuntimeError(
            "Soot ran but produced no .jimple output.\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDERR:\n{(r.stderr or '').strip()}\n\n"
            f"STDOUT:\n{(r.stdout or '').strip()}\n"
        )

    lines: list[str] = []
    for f in sorted(jimple_files):
        lines.extend(f.read_text(encoding="utf-8", errors="replace").splitlines())
    return lines


def _run_soot(source: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="soot-src-") as tmp:
        tmp_path = Path(tmp)
        cls = _guess_class_name(source)

        src_dir = tmp_path / "src"
        classes_dir = tmp_path / "classes"
        out_dir = tmp_path / "sootOut"

        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / f"{cls}.java").write_text(source, encoding="utf-8")

        _compile_java_to_classes(src_dir, classes_dir)
        return _run_soot_on_classes(classes_dir, out_dir)


def build_ir_with_soot(source: str) -> Program:
    """Build Java IR using javac -> Soot(bytecode) -> Jimple."""
    if not isinstance(source, str):
        raise TypeError("source must be a string containing Java code.")
    if not source.strip():
        return Program(statements=[], language="java", source=source)

    jimple_lines = _run_soot(source)
    statements = _parse_jimple(jimple_lines)

    if not statements:
        # keep the project’s fallback behavior
        return parse_java(source)

    return Program(statements=statements, language="java", source=source)
