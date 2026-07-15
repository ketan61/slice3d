import math

from slice3d.codec import HEADER_BITS
from slice3d.embed import embed
from slice3d.extract import extract
from slice3d.mesh import Mesh
from slice3d.visualize import carrier_indices, payload_bits


def make_mesh(n):
    mesh = Mesh()
    for i in range(n):
        mesh.vertices.append([i * 0.013 + 0.5, i * 0.027 + 0.5, i / (n - 1)])
        mesh._records.append(("v", i))
    return mesh


def test_payload_bits_includes_header():
    assert payload_bits(0) == HEADER_BITS
    assert payload_bits(10) == HEADER_BITS + 80


def test_carrier_count_matches_payload():
    mesh = make_mesh(2000)
    idx = carrier_indices(mesh.vertices, key="k", num_slices=64, payload_bytes=20)
    assert len(idx) == HEADER_BITS + 20 * 8
    assert len(set(idx)) == len(idx)  # no vertex used twice


def test_carriers_are_clamped_to_capacity():
    mesh = make_mesh(50)
    idx = carrier_indices(mesh.vertices, key="k", num_slices=8, payload_bytes=10_000)
    assert len(idx) == 50  # cannot exceed the number of vertices


def test_carrier_indices_match_the_actual_embedding_path():
    """Vertices flagged as ROI must be exactly those whose X could change on embed."""
    key, slices = "secret", 64
    data = b"the quick brown fox"

    cover = make_mesh(2000)
    x_before = [v[0] for v in cover.vertices]

    roi = set(carrier_indices(cover.vertices, key, slices, len(data)))

    embed(cover, data, key=key, num_slices=slices)
    changed = {i for i, x0 in enumerate(x_before) if cover.vertices[i][0] != x0}

    # Every vertex that actually changed must be inside the ROI (the converse need
    # not hold: an LSB only flips when the data bit differs from the current bit).
    assert changed.issubset(roi)
    # And the payload still round-trips, confirming the path is the real one.
    assert extract(cover, key=key, num_slices=slices) == data
