from __future__ import annotations

import tkinter as tk
from tkinter import messagebox


def run_gui() -> None:
    """GUI stub.

    How to implement:
    - Add file picker for Java/C/C++ sources and optional DOT output path.
    - Call the same analysis pipeline as the CLI.
    - Present the text report in a scrollable widget and show errors.
    """
    root = tk.Tk()
    root.title("Static Program Analyzer")
    root.geometry("700x400")

    messagebox.showinfo(
        "Not Implemented",
        "GUI stub: wiring to analysis pipeline is not implemented yet.",
    )
    root.destroy()


if __name__ == "__main__":
    run_gui()
