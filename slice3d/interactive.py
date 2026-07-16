"""Interactive embedding wizard.

Guides a user through hiding a message without needing to remember CLI flags:
a native file-explorer dialog to choose the cover model, then terminal prompts
for the slice count, the secret message and the key. Falls back to typed paths
if a graphical file dialog is unavailable (e.g. headless environments).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from slice3d.mesh import Mesh
from slice3d.reversible import capacity_bytes, embed, extract


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


def _prompt_choice(label: str, choices: dict) -> str:
    """Prompt until the user picks one of the numbered ``choices`` keys."""
    keys = list(choices)
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {choices[key]}")
    while True:
        raw = input(f"{label}: ").strip()
        if raw in keys:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        print(f"  please choose 1-{len(keys)}")


def _ask_input_model(kind: str) -> Optional[str]:
    """Pick an existing .obj via dialog (fallback: typed path). None on abort."""
    path = _pick_open_file(f"Choose the {kind} 3D model (.obj)")
    if path is None:
        path = input(f"Path to {kind} .obj model: ").strip().strip('"')
    if not path:
        print("No model chosen. Aborting.")
        return None
    if not Path(path).is_file():
        print(f"error: file not found: {path}")
        return None
    return path


# -- wizard -----------------------------------------------------------------

def run_wizard() -> int:
    """Top-level menu: choose whether to hide or extract, then dispatch."""
    print("=== slice3d :: data hiding in 3D models ===\n")
    action = _prompt_choice(
        "Choose an action",
        {"hide": "Hide a message in a 3D model", "extract": "Extract a hidden message"},
    )
    print()
    if action == "extract":
        return run_extract_wizard()
    return run_embed_wizard()


def run_embed_wizard() -> int:
    """Drive an interactive embed session. Returns a process exit code."""
    print("--- Hide a message ---\n")

    # 1. choose the cover model via file explorer (fallback: typed path)
    cover = _ask_input_model("cover")
    if cover is None:
        return 1
    print(f"cover model : {cover}")

    mesh = Mesh.load(cover)
    max_bytes = capacity_bytes(mesh)
    print(f"vertices    : {len(mesh)}")
    print(f"faces       : {len(mesh.faces)}")
    print(f"capacity    : {max_bytes} bytes\n")

    if max_bytes <= 0:
        print(
            "error: no capacity. The reversible scheme needs mesh connectivity "
            "(faces); pick a denser model that includes faces."
        )
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

    # 7. optionally save the ROI as a 3D object (green = data-carrying vertices)
    if _prompt_choice(
        "Save the ROI object (data-carrying vertices in green) as an .obj?",
        {"no": "No", "yes": "Yes"},
    ) == "yes":
        out = _pick_save_file("Save ROI object as...", "roi.obj")
        if out is None:
            out = input("Path to save ROI object: ").strip().strip('"')
        if out:
            from slice3d.visualize import export_roi_obj

            # Compute the ROI on the original cover (reloaded from disk), whose
            # prediction errors define which vertices carry data.
            export_roi_obj(
                Mesh.load(cover), key, num_slices, len(message.encode("utf-8")), out
            )
            print(f"saved ROI object -> {out}")
    return 0


def run_extract_wizard() -> int:
    """Drive an interactive extract session. Returns a process exit code."""
    print("--- Extract a hidden message ---\n")

    # 1. choose the stego model
    stego = _ask_input_model("stego")
    if stego is None:
        return 1
    print(f"stego model : {stego}")

    mesh = Mesh.load(stego)

    # 2. the key and slice count used at embedding time
    key = _prompt_nonempty("Secret key")
    num_slices = _prompt_int("Number of slices")

    # 3. recover the payload; extract() also restores the cover in place.
    try:
        data = extract(mesh, key=key, num_slices=num_slices)
    except ValueError as exc:
        print(f"\nCould not extract: {exc}")
        return 1

    # 4. show it, and offer to save the raw bytes to a file
    try:
        text = data.decode("utf-8")
        print(f"\nRecovered message:\n  {text}")
    except UnicodeDecodeError:
        print(f"\nRecovered {len(data)} bytes of binary data (not UTF-8 text).")

    if _prompt_choice("Save recovered data to a file?", {"no": "No", "yes": "Yes"}) == "yes":
        out = _pick_save_file("Save recovered data as...", "recovered.txt")
        if out is None:
            out = input("Path to save recovered data: ").strip().strip('"')
        if out:
            with open(out, "wb") as fh:
                fh.write(data)
            print(f"saved {len(data)} bytes -> {out}")

    # 5. the decoded object -- the restored cover, identical to the input model.
    print("\nThe cover model has been fully restored (reversible data hiding).")
    if _prompt_choice(
        "Save the restored (decoded) object as an .obj?", {"no": "No", "yes": "Yes"}
    ) == "yes":
        out = _pick_save_file("Save restored model as...", "restored.obj")
        if out is None:
            out = input("Path to save restored model: ").strip().strip('"')
        if out:
            mesh.save(out)
            print(f"saved restored model -> {out}")
    return 0
