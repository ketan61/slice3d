"""Interactive embedding wizard.

Guides a user through hiding a message without needing to remember CLI flags:
a native file-explorer dialog to choose the cover model, then terminal prompts
for the slice count, the secret message and the key. Falls back to typed paths
if a graphical file dialog is unavailable (e.g. headless environments).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from slice3d.embed import capacity_bytes, embed
from slice3d.mesh import Mesh


# -- file dialogs (isolated so tests can monkeypatch them) ------------------

def _pick_open_file(title: str) -> Optional[str]:
    """Open a native "open file" dialog; return None if unavailable/cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title=title,
        filetypes=[("Wavefront OBJ", "*.obj"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


def _pick_save_file(title: str, initialfile: str) -> Optional[str]:
    """Open a native "save file" dialog; return None if unavailable/cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        title=title,
        initialfile=initialfile,
        defaultextension=".obj",
        filetypes=[("Wavefront OBJ", "*.obj"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


# -- prompt helpers ---------------------------------------------------------

def _prompt_int(label: str, minimum: int = 1) -> int:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            value = int(raw)
        except ValueError:
            print(f"  please enter a whole number (>= {minimum})")
            continue
        if value < minimum:
            print(f"  value must be at least {minimum}")
            continue
        return value


def _prompt_nonempty(label: str) -> str:
    while True:
        value = input(f"{label}: ")
        if value.strip():
            return value
        print("  this cannot be empty")


# -- wizard -----------------------------------------------------------------

def run_wizard() -> int:
    """Drive an interactive embed session. Returns a process exit code."""
    print("=== slice3d :: hide a message in a 3D model ===\n")

    # 1. choose the cover model via file explorer (fallback: typed path)
    cover = _pick_open_file("Choose the cover 3D model (.obj)")
    if cover is None:
        cover = input("Path to cover .obj model: ").strip().strip('"')
    if not cover:
        print("No cover model chosen. Aborting.")
        return 1
    if not Path(cover).is_file():
        print(f"error: file not found: {cover}")
        return 1
    print(f"cover model : {cover}")

    mesh = Mesh.load(cover)
    max_bytes = capacity_bytes(mesh)
    print(f"vertices    : {len(mesh)}")
    print(f"capacity    : {max_bytes} bytes\n")

    if max_bytes <= 0:
        print("error: this model is too small to hide any data. Pick a denser mesh.")
        return 1

    # 2. number of slices
    num_slices = _prompt_int("Number of slices")

    # 3. the secret message (re-prompt if it will not fit)
    while True:
        message = _prompt_nonempty("Secret message")
        size = len(message.encode("utf-8"))
        if size <= max_bytes:
            break
        print(f"  message is {size} bytes but capacity is {max_bytes}; shorten it")

    # 4. the key (needed by the receiver to extract)
    key = _prompt_nonempty("Secret key")

    # 5. where to save the stego model
    default_name = Path(cover).stem + "_stego.obj"
    output = _pick_save_file("Save the stego model as...", default_name)
    if output is None:
        output = str(Path(cover).with_name(default_name))
    print(f"output      : {output}")

    # 6. embed and save
    embed(mesh, message.encode("utf-8"), key=key, num_slices=num_slices)
    mesh.save(output)

    print("\nDone! Hidden message embedded.")
    print("To extract it later, the receiver needs BOTH:")
    print(f"  key    = {key}")
    print(f"  slices = {num_slices}")
    print(f"\n  slice3d extract -i \"{output}\" -k \"{key}\" -n {num_slices}")
    return 0
