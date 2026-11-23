"""Interactive wizard for randomsliced3d.

Guides a user through hiding or extracting a message without needing to
remember CLI flags. The wizard announces that it has started, asks what the
user wants to do, and explains every step in plain words (which object to
select, what the slice count and the key are for). A native file-explorer
dialog picks the models, with a typed path as a fallback when no graphical
dialog is available. After each operation it returns to the main menu until the
user chooses Exit.

Output is coloured only on a real terminal; when stdout is captured or piped
(tests, logs) or the ``NO_COLOR`` environment variable is set, the text is plain.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from slice3d.mesh import Mesh
from slice3d.reversible import capacity_bytes, embed, extract


# -- terminal styling -------------------------------------------------------

_ANSI = {
    "bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33",
    "blue": "34", "magenta": "35", "cyan": "36",
}


def _color_on() -> bool:
    """Colour only on an interactive terminal, and never when NO_COLOR is set."""
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _enable_windows_ansi() -> None:
    """Turn on ANSI colour processing in the Windows console (no-op elsewhere)."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT processing
    except Exception:
        pass


def _paint(text: str, *styles: str) -> str:
    if not styles or not _color_on():
        return text
    codes = ";".join(_ANSI[s] for s in styles)
    return f"\033[{codes}m{text}\033[0m"


def _sym(fancy: str, plain: str) -> str:
    """A Unicode symbol if stdout can print it, else an ASCII stand-in."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        fancy.encode(encoding)
        return fancy
    except (UnicodeEncodeError, LookupError):
        return plain


def _ok(msg: str) -> None:
    print(_paint(f"{_sym('✓', '[ok]')} {msg}", "green"))


def _err(msg: str) -> None:
    print(_paint(f"{_sym('✗', '[!]')} {msg}", "red"))


def _hint(msg: str) -> None:
    """A plain-language instruction telling the user what to do next."""
    print(_paint(f"{_sym('→', '->')} {msg}", "cyan"))


def _detail(label: str, value) -> None:
    print(f"    {_paint(f'{label:<9}', 'dim')}: {value}")


def _section(title: str) -> None:
    bar = _sym("─", "-") * 6
    print()
    print(_paint(f"{bar} {title} {bar}", "bold", "magenta"))
    print()


def _banner() -> None:
    width = 44
    if _sym("╔═║╚", "") == "╔═║╚":
        top, bottom, side = "╔" + "═" * width + "╗", "╚" + "═" * width + "╝", "║"
    else:
        top = bottom = "+" + "-" * width + "+"
        side = "|"
    frame = lambda s: _paint(s, "cyan", "bold")  # noqa: E731
    print(frame(top))
    print(frame(side) + "  " + _paint("randomsliced3d".ljust(width - 2), "bold") + frame(side))
    print(frame(side) + "  " + "Reversible data hiding in 3D models".ljust(width - 2) + frame(side))
    print(frame(bottom))


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

def _ask(label: str) -> str:
    return input(_paint(f"{label}: ", "yellow", "bold"))


def _prompt_int(label: str, minimum: int = 1) -> int:
    while True:
        raw = _ask(label).strip()
        try:
            value = int(raw)
        except ValueError:
            _err(f"Please enter a whole number (>= {minimum}).")
            continue
        if value < minimum:
            _err(f"The value must be at least {minimum}.")
            continue
        return value


def _prompt_nonempty(label: str) -> str:
    while True:
        value = _ask(label)
        if value.strip():
            return value
        _err("This cannot be empty.")


def _prompt_choice(label: str, choices: dict, question: Optional[str] = None) -> str:
    """Print the question (if any), then the numbered choices, then ask for one."""
    if question:
        print(_paint(question, "bold"))
    keys = list(choices)
    for i, key in enumerate(keys, 1):
        print(f"  {_paint(f'{i}.', 'cyan', 'bold')} {choices[key]}")
    while True:
        raw = _ask(label).strip()
        if raw in keys:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        _err(f"Please choose a number from 1 to {len(keys)}.")


def _prompt_yes_no(question: str) -> bool:
    """Ask a yes/no question: question first, then the options, then the choice."""
    return _prompt_choice("Choose an action", {"no": "No", "yes": "Yes"}, question) == "yes"


def _ask_input_model(kind: str) -> Optional[str]:
    """Pick an existing .obj via dialog (fallback: typed path). None on abort."""
    path = _pick_open_file(f"Choose the {kind} 3D model (.obj)")
    if path is None:
        path = _ask(f"Path to {kind} .obj model").strip().strip('"')
    if not path:
        _err("No model was chosen.")
        return None
    if not Path(path).is_file():
        _err(f"File not found: {path}")
        return None
    return path


_WINDOW_HINT = (
    "A file window will open. If you don't see it, check the taskbar; "
    "it can open behind VS Code."
)


# -- wizard -----------------------------------------------------------------

_MENU = {
    "hide": "Hide a message in a 3D model",
    "extract": "Extract a hidden message",
    "exit": "Exit",
}


def run_wizard() -> int:
    """Announce the tool, then loop: ask what to do, run it, come back."""
    _enable_windows_ansi()
    _banner()
    _ok("randomsliced3d has started.")
    while True:
        print()
        action = _prompt_choice("Choose an action", _MENU, "What would you like to do?")
        if action == "exit":
            print()
            _ok("Goodbye! randomsliced3d has closed.")
            return 0
        if action == "extract":
            run_extract_wizard()
        else:
            run_embed_wizard()
        print()
        _hint("Returning to the main menu.")


_TOO_BIG_MENU = {
    "shorter": "Type a shorter message",
    "cover": "Choose a different cover object",
    "menu": "Go back to the main menu",
}

_NO_CAPACITY_MENU = {
    "cover": "Choose a different cover object",
    "menu": "Go back to the main menu",
}


def _load_cover():
    """Ask for the cover object, load it and show its details.

    Returns ``(path, mesh, capacity_bytes)``, or None if no model was chosen.
    """
    _hint(
        "Please select the COVER object: the 3D model (.obj) you want to hide "
        "your secret message in."
    )
    _hint(_WINDOW_HINT)
    cover = _ask_input_model("cover")
    if cover is None:
        return None
    mesh = Mesh.load(cover)
    max_bytes = capacity_bytes(mesh)
    _ok(f"Cover object loaded: {Path(cover).name}")
    _detail("file", cover)
    _detail("vertices", len(mesh))
    _detail("faces", len(mesh.faces))
    _detail("capacity", f"{max_bytes} bytes")
    return cover, mesh, max_bytes


def _choose_usable_cover():
    """Load a cover that can hold data, offering to pick another one if it can't.

    Returns ``(path, mesh, capacity_bytes)``, or None to go back to the menu.
    """
    while True:
        loaded = _load_cover()
        if loaded is None:
            return None
        if loaded[2] > 0:
            return loaded
        _err(
            "This model cannot hold any data. The reversible scheme needs mesh "
            "connectivity (faces); please pick a denser model that includes faces."
        )
        print()
        choice = _prompt_choice(
            "Choose an action", _NO_CAPACITY_MENU, "What would you like to do?"
        )
        if choice == "menu":
            _hint("No message was hidden.")
            return None
        print()


def run_embed_wizard() -> int:
    """Drive an interactive embed session. Returns a process exit code."""
    _section("Hide a message")

    # 1. choose the cover model via file explorer (fallback: typed path)
    loaded = _choose_usable_cover()
    if loaded is None:
        return 1
    cover, mesh, max_bytes = loaded

    # 2. number of slices
    print()
    _hint(
        "How many slices should the model be cut into along the Z axis? "
        "(for example 256 or 512)"
    )
    num_slices = _prompt_int("Number of slices")

    # 3. the secret message. If it does not fit, let the user shorten it, pick a
    #    bigger cover object (keeping the message), or go back to the menu.
    print()
    _hint(f"Type the secret message you want to hide (up to {max_bytes} bytes).")
    message = _prompt_nonempty("Secret message")
    while True:
        size = len(message.encode("utf-8"))
        if size <= max_bytes:
            break
        _err(
            f"That message is {size} bytes, but this model can hold only "
            f"{max_bytes}."
        )
        print()
        choice = _prompt_choice(
            "Choose an action", _TOO_BIG_MENU, "What would you like to do?"
        )
        print()
        if choice == "menu":
            _hint("No message was hidden.")
            return 1
        if choice == "shorter":
            _hint(f"Type a shorter message (up to {max_bytes} bytes).")
            message = _prompt_nonempty("Secret message")
            continue
        # choice == "cover": keep the message and the slice count, swap the model
        loaded = _choose_usable_cover()
        if loaded is None:
            return 1
        cover, mesh, max_bytes = loaded
        if size <= max_bytes:
            _ok(f"Your message ({size} bytes) fits in this cover object.")

    # 4. the key (needed by the receiver to extract)
    print()
    _hint(
        "Choose a secret key. The receiver will need this exact key and the "
        "same number of slices to extract the message."
    )
    key = _prompt_nonempty("Secret key")

    # 5. where to save the stego model
    print()
    _hint(
        "Now choose where to save the STEGO object: the 3D model that will "
        "carry your hidden message."
    )
    default_name = Path(cover).stem + "_stego.obj"
    output = _pick_save_file("Save the stego model as...", default_name)
    if output is None:
        output = str(Path(cover).with_name(default_name))

    # 6. embed and save
    payload = message.encode("utf-8")
    print()
    _hint("Hiding your message ...")
    embed(mesh, payload, key=key, num_slices=num_slices)
    mesh.save(output)
    _ok("Hidden message embedded successfully.")
    _ok(f"Stego object saved -> {output}")

    print()
    print(_paint("To extract it later, the receiver needs BOTH:", "bold"))
    _detail("key", key)
    _detail("slices", num_slices)
    print(_paint(f'  randomsliced3d extract -i "{output}" -k "{key}" -n {num_slices}', "dim"))

    # 7. optionally save the ROI as a 3D object (green = data-carrying vertices)
    print()
    if _prompt_yes_no("Save the ROI object (data-carrying vertices in green) as an .obj?"):
        out = _pick_save_file("Save ROI object as...", Path(cover).stem + "_roi.obj")
        if out is None:
            out = _ask("Path to save ROI object").strip().strip('"')
        if out:
            from slice3d.visualize import export_roi_obj

            # Compute the ROI on the original cover (reloaded from disk), whose
            # prediction errors define which vertices carry data.
            export_roi_obj(Mesh.load(cover), key, num_slices, len(payload), out)
            _ok(f"ROI object saved -> {out}")
    return 0


def run_extract_wizard() -> int:
    """Drive an interactive extract session. Returns a process exit code."""
    _section("Extract a hidden message")

    # 1. choose the stego model
    _hint(
        "Please select the STEGO object: the 3D model (.obj) that contains the "
        "hidden message."
    )
    _hint(_WINDOW_HINT)
    stego = _ask_input_model("stego")
    if stego is None:
        return 1

    mesh = Mesh.load(stego)
    _ok(f"Stego object loaded: {Path(stego).name}")
    _detail("file", stego)
    _detail("vertices", len(mesh))

    # 2. the key and slice count used at embedding time
    print()
    _hint("Enter the secret key that was used when the message was hidden.")
    key = _prompt_nonempty("Secret key")
    print()
    _hint("Enter the number of slices that was used when the message was hidden.")
    num_slices = _prompt_int("Number of slices")

    # 3. recover the payload; extract() also restores the cover in place.
    print()
    _hint("Extracting the message and restoring the original model ...")
    try:
        data = extract(mesh, key=key, num_slices=num_slices)
    except ValueError as exc:
        _err(f"Could not extract: {exc}")
        _hint(
            "Check that the key and the number of slices are exactly the ones "
            "used when the message was hidden."
        )
        return 1

    # 4. show the recovered message
    try:
        text = data.decode("utf-8")
        _ok("Recovered message:")
        print("  " + _paint(text, "bold"))
    except UnicodeDecodeError:
        _ok(f"Recovered {len(data)} bytes of binary data (not UTF-8 text).")

    print()
    if _prompt_yes_no("Save recovered data (the secret message) to a file?"):
        out = _pick_save_file("Save recovered data as...", "recovered.txt")
        if out is None:
            out = _ask("Path to save recovered data").strip().strip('"')
        if out:
            with open(out, "wb") as fh:
                fh.write(data)
            _ok(f"Secret message saved ({len(data)} bytes) -> {out}")

    # 5. the decoded object -- the restored cover, identical to the input model.
    #    Default name derives from the object name (dropping a trailing _stego).
    base = Path(stego).stem
    if base.endswith("_stego"):
        base = base[: -len("_stego")]
    print()
    _ok("The cover model has been fully restored (reversible data hiding).")
    if _prompt_yes_no("Save the restored (decoded) object as an .obj?"):
        out = _pick_save_file("Save restored model as...", base + "_decoded.obj")
        if out is None:
            out = _ask("Path to save restored model").strip().strip('"')
        if out:
            mesh.save(out)
            _ok(f"Decoded object saved -> {out}")
    return 0
