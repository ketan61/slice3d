import math

import matplotlib

matplotlib.use("Agg")  # headless: figures render to file, never open a window

import slice3d.interactive as interactive
from slice3d.interactive import run_embed_wizard, run_extract_wizard, run_wizard
from slice3d.mesh import Mesh
from slice3d.reversible import extract


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

    def vid(i, j):
        return i * slices + (j % slices) + 1

    with open(path, "w", encoding="utf-8") as fh:
        for x, y, z in verts:
            fh.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for i in range(stacks):
            for j in range(slices):
                fh.write(
                    f"f {vid(i, j)} {vid(i, j + 1)} {vid(i + 1, j + 1)} {vid(i + 1, j)}\n"
                )


def _feed_inputs(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(it))


# -- embed wizard -----------------------------------------------------------

def test_embed_wizard_embeds_and_is_extractable(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "cover_stego.obj"
    _write_sphere(cover)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    _feed_inputs(monkeypatch, ["64", "hello wizard", "mykey", "no"])

    assert run_embed_wizard() == 0
    assert stego.exists()
    assert extract(Mesh.load(str(stego)), key="mykey", num_slices=64) == b"hello wizard"


def test_embed_wizard_falls_back_to_typed_path_when_no_dialog(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    _write_sphere(cover)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: None)
    monkeypatch.setattr(interactive, "_pick_save_file", lambda title, initialfile: None)
    _feed_inputs(monkeypatch, [str(cover), "32", "typed path works", "k", "no"])

    assert run_embed_wizard() == 0
    default_out = cover.with_name(cover.stem + "_stego.obj")
    assert default_out.exists()
    assert extract(Mesh.load(str(default_out)), key="k", num_slices=32) == b"typed path works"


def test_embed_wizard_reprompts_when_message_too_large(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "out.obj"
    _write_sphere(cover, stacks=12, slices=12)  # small mesh, tiny capacity

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    from slice3d.reversible import capacity_bytes

    cap = capacity_bytes(Mesh.load(str(cover)))
    oversized = "x" * (cap + 5)
    ok = "y" * max(1, cap - 1)
    _feed_inputs(monkeypatch, ["8", oversized, ok, "key", "no"])

    assert run_embed_wizard() == 0
    assert extract(Mesh.load(str(stego)), key="key", num_slices=8) == ok.encode()


# -- top-level menu ---------------------------------------------------------

def test_run_wizard_menu_dispatches_to_embed(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "cover_stego.obj"
    _write_sphere(cover)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    # First answer picks "hide" from the menu, then the embed prompts follow.
    _feed_inputs(monkeypatch, ["hide", "64", "menu works", "kk", "no"])

    assert run_wizard() == 0
    assert extract(Mesh.load(str(stego)), key="kk", num_slices=64) == b"menu works"


# -- extract wizard ---------------------------------------------------------

def _make_stego(tmp_path, monkeypatch, message, key, slices):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "stego.obj"
    _write_sphere(cover)
    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(stego)
    )
    _feed_inputs(monkeypatch, [str(slices), message, key, "no"])
    assert run_embed_wizard() == 0
    return stego


def test_extract_wizard_recovers_message(tmp_path, monkeypatch, capsys):
    stego = _make_stego(tmp_path, monkeypatch, "find me", "pw", 48)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(stego))
    # key, slices, then no to: save recovered data, save restored obj.
    _feed_inputs(monkeypatch, ["pw", "48", "no", "no"])

    assert run_extract_wizard() == 0
    assert "find me" in capsys.readouterr().out


def test_extract_wizard_can_save_to_file(tmp_path, monkeypatch):
    stego = _make_stego(tmp_path, monkeypatch, "save me", "pw", 48)
    recovered = tmp_path / "recovered.txt"

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(stego))
    monkeypatch.setattr(
        interactive, "_pick_save_file", lambda title, initialfile: str(recovered)
    )
    # save recovered data = yes; save restored obj = no.
    _feed_inputs(monkeypatch, ["pw", "48", "yes", "no"])

    assert run_extract_wizard() == 0
    assert recovered.read_bytes() == b"save me"


def test_extract_wizard_wrong_key_reports_cleanly(tmp_path, monkeypatch, capsys):
    stego = _make_stego(tmp_path, monkeypatch, "secret", "right", 48)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(stego))
    _feed_inputs(monkeypatch, ["wrong", "48"])

    assert run_extract_wizard() == 1
    assert "Could not extract" in capsys.readouterr().out


def test_embed_wizard_saves_roi_object_without_a_window(tmp_path, monkeypatch):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "cover_stego.obj"
    roi = tmp_path / "roi.obj"
    _write_sphere(cover)

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(cover))
    saves = iter([str(stego), str(roi)])  # stego save, then ROI object save
    monkeypatch.setattr(interactive, "_pick_save_file", lambda title, initialfile: next(saves))
    # slices, message, key, then "yes" to saving the ROI object.
    _feed_inputs(monkeypatch, ["64", "hello", "key", "yes"])

    assert run_embed_wizard() == 0
    assert roi.exists()
    roi_mesh = Mesh.loads(roi.read_text())
    # ROI object keeps the geometry and marks carriers green (32 header + 5*8 bits).
    green = sum(1 for v in roi_mesh._vertex_extra.values() if v == "0.000 1.000 0.000")
    assert green == 32 + len("hello") * 8
    assert len(roi_mesh.faces) == len(Mesh.load(str(cover)).faces)


def test_extract_wizard_saves_restored_object(tmp_path, monkeypatch):
    stego = _make_stego(tmp_path, monkeypatch, "restore me", "pw", 48)
    restored = tmp_path / "restored.obj"

    monkeypatch.setattr(interactive, "_pick_open_file", lambda title: str(stego))
    monkeypatch.setattr(interactive, "_pick_save_file", lambda title, initialfile: str(restored))
    # key, slices, save recovered data = no, save restored obj = yes.
    _feed_inputs(monkeypatch, ["pw", "48", "no", "yes"])

    assert run_extract_wizard() == 0
    from slice3d.compare import diff_vertices

    cover = tmp_path / "cover.obj"  # the original, written by _make_stego
    assert restored.exists()
    assert diff_vertices(Mesh.load(str(cover)), Mesh.load(str(restored))) == 0
