import math

import slice3d.interactive as interactive
from slice3d.extract import extract
from slice3d.interactive import run_wizard
from slice3d.mesh import Mesh


def _write_sphere(path, stacks=20, slices=20):
    verts = []
    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices):
            theta = 2 * math.pi * j / slices
            verts.append(
                (
                    math.sin(phi) * math.cos(theta),
                    math.sin(phi) * math.sin(theta),
                    math.cos(phi),
                )
            )
    with open(path, "w", encoding="utf-8") as fh:
        for x, y, z in verts:
            fh.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")


def _feed_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(it))


def test_wizard_embeds_and_is_extractable(tmp_path, monkeypatch, capsys):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "cover_stego.obj"
    _write_sphere(cover)

    # Simulate the file-explorer dialogs choosing paths.
    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    # Simulate typed answers: slices, message, key.
    _feed_inputs(monkeypatch, ["64", "hello wizard", "mykey"])

    rc = run_wizard()
    assert rc == 0
    assert stego.exists()

    recovered = extract(Mesh.load(str(stego)), key="mykey", num_slices=64)
    assert recovered == b"hello wizard"


def test_wizard_falls_back_to_typed_path_when_no_dialog(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    _write_sphere(cover)

    # No graphical dialog available -> pickers return None.
    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: None)
    monkeypatch.setattr(interactive, "_pick_save_file", lambda title, initialfile: None)
    # First typed input is the cover path (dialog fallback), then slices/message/key.
    _feed_inputs(monkeypatch, [str(cover), "32", "typed path works", "k"])

    rc = run_wizard()
    assert rc == 0
    # Default output lands next to the cover when the save dialog is unavailable.
    default_out = cover.with_name(cover.stem + "_stego.obj")
    assert default_out.exists()
    assert extract(Mesh.load(str(default_out)), key="k", num_slices=32) == b"typed path works"


def test_wizard_reprompts_when_message_too_large(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "out.obj"
    _write_sphere(cover, stacks=6, slices=6)  # small mesh, tiny capacity

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    from slice3d.embed import capacity_bytes

    cap = capacity_bytes(Mesh.load(str(cover)))
    oversized = "x" * (cap + 5)
    ok = "y" * max(1, cap - 1)
    # slices, oversized message (rejected), then a fitting message, key.
    _feed_inputs(monkeypatch, ["8", oversized, ok, "key"])

    rc = run_wizard()
    assert rc == 0
    assert extract(Mesh.load(str(stego)), key="key", num_slices=8) == ok.encode()
