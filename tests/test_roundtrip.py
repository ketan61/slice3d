import pytest

from slice3d.embed import CapacityError, capacity_bytes, embed
from slice3d.extract import extract
from slice3d.mesh import Mesh


def make_mesh(n):
    """A mesh of n vertices spread along Z, with distinct X/Y."""
    mesh = Mesh()
    for i in range(n):
        z = i / (n - 1)
        mesh.vertices.append([i * 0.013 + 0.5, i * 0.027 + 0.5, z])
        mesh._records.append(("v", i))
    return mesh


def stego_reload(mesh):
    """Serialize and parse back, mimicking a real send over the wire."""
    return Mesh.loads(mesh.dumps())


def test_roundtrip_recovers_payload():
    mesh = make_mesh(2000)
    secret = b"reversible data hiding in 3d models"
    embed(mesh, secret, key="alpha", num_slices=128)
    received = stego_reload(mesh)
    assert extract(received, key="alpha", num_slices=128) == secret


def test_roundtrip_empty_payload():
    mesh = make_mesh(200)
    embed(mesh, b"", key="k", num_slices=16)
    assert extract(stego_reload(mesh), key="k", num_slices=16) == b""


def test_wrong_key_does_not_recover_payload():
    mesh = make_mesh(2000)
    secret = b"top secret bits"
    embed(mesh, secret, key="right-key", num_slices=64)
    received = stego_reload(mesh)
    # A wrong key yields either garbage or a length/capacity failure -- never the
    # original secret.
    try:
        recovered = extract(received, key="wrong-key", num_slices=64)
    except ValueError:
        return
    assert recovered != secret


def test_wrong_slice_count_does_not_recover_payload():
    mesh = make_mesh(2000)
    secret = b"slice-bound secret"
    embed(mesh, secret, key="key", num_slices=100)
    received = stego_reload(mesh)
    try:
        recovered = extract(received, key="key", num_slices=101)
    except ValueError:
        return
    assert recovered != secret


def test_capacity_error_when_payload_too_large():
    mesh = make_mesh(64)
    too_big = b"x" * (capacity_bytes(mesh) + 1)
    with pytest.raises(CapacityError):
        embed(mesh, too_big, key="k", num_slices=8)


def test_embed_only_touches_x_not_z():
    mesh = make_mesh(500)
    z_before = [v[2] for v in mesh.vertices]
    embed(mesh, b"payload here", key="k", num_slices=32)
    z_after = [v[2] for v in mesh.vertices]
    assert z_before == z_after  # slicing axis untouched


def test_embed_axis_cannot_equal_slicing_axis():
    mesh = make_mesh(100)
    with pytest.raises(ValueError):
        embed(mesh, b"x", key="k", num_slices=8, axis=2, embed_axis=2)
