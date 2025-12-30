# Static Program Analyzer User Manual

## Overview
The Static Program Analyzer scaffolds Java/C++ analysis. The current codebase contains stubs for the parser, IR, analyses, and reporting so your team can implement them.

## Requirements
- Python 3.10+
- Java JDK 17+ (for Soot)
- Soot (set `SOOT_CMD` or `SOOT_JAR`)
- LLVM/Clang (set `CLANG_CMD` if not in PATH)
- Graphviz (optional) for rendering DOT output

## Running the CLI
```bash
python -m main.cli examples/example.cpp --dot demo/example.dot
```

The CLI prints a textual report and optionally writes a DOT file.

## Running the GUI
```bash
python -m main.gui
```

## Tool Configuration
The parser frontend uses Soot and Clang via the command line.

- Java (Soot):
  - Set `SOOT_CMD` to the Soot executable, or
  - Set `SOOT_JAR` to the Soot jar path (e.g., `C:\tools\soot\soot.jar`)

- C++ (Clang):
  - Ensure `clang++` is on PATH, or
  - Set `CLANG_CMD` to the full path of `clang++`

Use the file picker to select a source file and click **Run Analysis** to see a stub notice until the analysis pipeline is implemented.

## Output Interpretation
- **Live Variables**: variables needed in the future (to be implemented).
- **Reaching Definitions**: definitions that can reach each statement (to be implemented).
- **Pointer Analysis**: points-to sets and alias sets per variable (to be implemented).
