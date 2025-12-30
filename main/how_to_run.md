# Demo Script

1. Configure tools:
   - Set `SOOT_CMD` or `SOOT_JAR` for Java analysis.
   - Ensure `clang++` is on PATH or set `CLANG_CMD`.
2. Launch the GUI:
   ```bash
   python -m main.gui
   ```
3. Select `examples/example.cpp` and click **Run Analysis**.
4. For a DOT report (once reporting is implemented):
   ```bash
   python -m main.cli examples/example.cpp --dot demo/example.dot
   ```
5. Render the DOT file with Graphviz:
   ```bash
   dot -Tpng demo/example.dot -o demo/example.png
   ```
