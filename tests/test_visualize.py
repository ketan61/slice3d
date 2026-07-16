import math

import matplotlib

matplotlib.use("Agg")  # headless rendering for tests

from slice3d.codec import HEADER_BITS
from slice3d.mesh import Mesh
from slice3d.reversible import capacity_bits, embed, extract
from slice3d.visualize import (
    carrier_indices,
    export_roi_obj,
    payload_bits,
    render_model,
    render_roi,
)


def make_sphere(stacks=24, slices=24):
    """An in-memory UV-sphere mesh with faces (so it has carriers)."""
    lines = ["# sphere"]
    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices):
            theta = 2 * math.pi * j / slices
            lines.append(
                "v {:.6f} {:.6f} {:.6f}".format(
                    math.sin(phi) * math.cos(theta),
                    math.sin(phi) * math.sin(theta),
                    math.cos(phi),
                )
            )

    def vid(i, j):
        return i * slices + (j % slices) + 1

    for i in range(stacks):
        for j in range(slices):
            lines.append(f"f {vid(i, j)} {vid(i, j + 1)} {vid(i + 1, j + 1)} {vid(i + 1, j)}")
    return Mesh.loads("\n".join(lines))


def test_payload_bits_includes_header():
    assert payload_bits(0) == HEADER_BITS
    assert payload_bits(10) == HEADER_BITS + 80


def test_carrier_count_matches_payload():
    mesh = make_sphere()
    idx = carrier_indices(mesh, key="k", num_slices=64, payload_bytes=10)
    assert len(idx) == HEADER_BITS + 10 * 8
    assert len(set(idx)) == len(idx)  # no vertex used twice


def test_carriers_are_clamped_to_capacity():
    mesh = make_sphere()
    idx = carrier_indices(mesh, key="k", num_slices=8, payload_bytes=10_000)
    assert len(idx) == capacity_bits(mesh)  # cannot exceed available carriers


def test_roi_is_the_data_carrying_subset_and_round_trips():
    """The ROI is exactly the data-carrying vertex set, and embedding round-trips."""
    key, slices = "secret", 64
    data = b"the quick brown fox"

    cover = make_sphere()
    roi = carrier_indices(cover, key, slices, len(data))
    assert len(roi) == payload_bits(len(data))  # header + payload vertices
    assert len(set(roi)) == len(roi)            # each used once

    embed(cover, data, key=key, num_slices=slices)  # cover is now stego
    # Round-trips and restores exactly (reversibility), via a serialize/reload.
    stego = Mesh.loads(cover.dumps())
    assert extract(stego, key=key, num_slices=slices) == data


def test_render_roi_saves_png(tmp_path):
    mesh = make_sphere()
    out = tmp_path / "roi.png"
    render_roi(mesh, key="k", num_slices=32, payload_bytes=5, out=str(out))
    assert out.exists() and out.stat().st_size > 0


def test_render_model_saves_png(tmp_path):
    mesh = make_sphere()
    out = tmp_path / "model.png"
    render_model(mesh, title="restored", out=str(out))
    assert out.exists() and out.stat().st_size > 0


def test_export_roi_obj_colours_carriers_and_keeps_faces(tmp_path):
    mesh = make_sphere()
    out = tmp_path / "roi.obj"
    export_roi_obj(mesh, key="k", num_slices=64, payload_bytes=10, out=str(out))

    reloaded = Mesh.loads(out.read_text())
    green = sum(1 for v in reloaded._vertex_extra.values() if v == "0.000 1.000 0.000")
    assert green == payload_bits(10)                     # exactly the ROI vertices
    assert len(reloaded.vertices) == len(mesh.vertices)  # geometry preserved
    assert len(reloaded.faces) == len(mesh.faces)        # faces preserved
