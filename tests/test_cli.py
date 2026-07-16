import math

from slice3d.cli import main


def _write_sphere(path, stacks=20, slices=20):
    """A UV-sphere mesh (with faces) large enough to carry a small payload."""
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
        return i * slices + (j % slices) + 1  # OBJ is 1-indexed

    with open(path, "w", encoding="utf-8") as fh:
        for x, y, z in verts:
            fh.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for i in range(stacks):
            for j in range(slices):
                fh.write(
                    f"f {vid(i, j)} {vid(i, j + 1)} {vid(i + 1, j + 1)} {vid(i + 1, j)}\n"
                )


def test_cli_embed_extract_roundtrip(tmp_path, capsysbinary):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "stego.obj"
    _write_sphere(cover)

    rc = main(["embed", "-i", str(cover), "-o", str(stego),
               "-k", "key", "-n", "64", "-m", "hi there"])
    assert rc == 0
    capsysbinary.readouterr()  # discard embed's status output

    rc = main(["extract", "-i", str(stego), "-k", "key", "-n", "64"])
    assert rc == 0
    out = capsysbinary.readouterr().out
    assert out == b"hi there\n"


def test_cli_wrong_key_exits_cleanly(tmp_path, capsys):
    cover = tmp_path / "cover.obj"
    stego = tmp_path / "stego.obj"
    _write_sphere(cover)
    main(["embed", "-i", str(cover), "-o", str(stego),
          "-k", "right", "-n", "64", "-m", "secret payload"])

    rc = main(["extract", "-i", str(stego), "-k", "wrong", "-n", "64"])

    captured = capsys.readouterr()
    assert rc == 1                          # non-zero exit, not a crash
    assert captured.err.startswith("error:")  # clean message, no traceback
    assert "Traceback" not in captured.err


def test_cli_missing_input_exits_cleanly(tmp_path, capsys):
    rc = main(["info", "-i", str(tmp_path / "nope.obj"), "-n", "8"])
    assert rc == 1
    assert capsys.readouterr().err.startswith("error:")
