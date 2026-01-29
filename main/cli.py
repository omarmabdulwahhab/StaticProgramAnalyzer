import argparse
import sys
from pathlib import Path

# Add project root to PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.parsing.parser import parse_java, parse_cpp
from src.intermediate_representation.cfg import build_cfg
from src.analysis.live_variables import compute_live_variables
from src.analysis.pointer_analysis import compute_pointer_analysis
from src.analysis.reaching_definitions import compute_reaching_definitions


def main():
    parser = argparse.ArgumentParser(
        description="Static Program Analyzer CLI"
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to the source code file (Java or C++)"
    )

    parser.add_argument(
        "--lang",
        required=True,
        choices=["java", "cpp"],
        help="Programming language"
    )

    parser.add_argument(
        "--analysis",
        nargs="+",
        choices=["pointer", "live", "reaching"],
        required=True,
        help="Analyses to run"
    )

    args = parser.parse_args()

    source_path = Path(args.file)
    if not source_path.exists():
        print(f"[ERROR] File not found: {source_path}")
        return

    source_code = source_path.read_text(encoding="utf-8")

    # --- Parsing ---
    if args.lang == "java":
        program = parse_java(source_code)
    else:
        program = parse_cpp(source_code)

    print("=== PARSING SUCCESSFUL ===")
    print("Language:", program.language)
    print("Number of statements:", len(program.statements))

    # --- CFG ---
    cfg = build_cfg(program.statements)
    num_edges = sum(len(node.successors) for node in cfg)

    print("\n=== CFG CONSTRUCTED ===")
    print("CFG entry node:", cfg.entry)
    print("CFG exit node:", cfg.exit)
    print("CFG nodes:", len(cfg.nodes))
    print("CFG edges:", num_edges)

    # --- Analyses ---
    print("\n=== ANALYSIS RESULTS ===")

    if "live" in args.analysis:
        print("\n[Live Variable Analysis]")
        try:
            result = compute_live_variables(cfg)
            print(result)
        except NotImplementedError as e:
            print("Live variable analysis not implemented yet.")
            print(f"Reason: {e}")

    if "pointer" in args.analysis:
        print("\n[Pointer Analysis]")
        try:
            result = compute_pointer_analysis(program)
            print(result)
        except NotImplementedError as e:
            print("Pointer analysis not implemented yet.")
            print(f"Reason: {e}")

    if "reaching" in args.analysis:
        print("\n[Reaching Definitions Analysis]")
        try:
            result = compute_reaching_definitions(cfg)
            print(result)
        except NotImplementedError as e:
            print("Reaching definitions analysis not implemented yet.")
            print(f"Reason: {e}")

    print("\nRequested analyses:", args.analysis)


if __name__ == "__main__":
    main()
