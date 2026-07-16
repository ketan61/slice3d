"""Compare two meshes to demonstrate reversibility (input == restored)."""

from __future__ import annotations

from slice3d.mesh import PRECISION, Mesh

_Q = 10 ** PRECISION


def _quantise(v):
    return tuple(round(c * _Q) for c in v)


def diff_vertices(a: Mesh, b: Mesh) -> int:
    """Number of vertices that differ between two meshes at file precision.

    Zero means the two models are identical to the 6-decimal representation the
    tool reads and writes -- i.e. the restoration was exact.
    """
    if len(a.vertices) != len(b.vertices):
        return max(len(a.vertices), len(b.vertices))
    return sum(
        1 for va, vb in zip(a.vertices, b.vertices) if _quantise(va) != _quantise(vb)
    )


def max_coord_delta(a: Mesh, b: Mesh) -> float:
    """Largest absolute per-coordinate difference between two equal-size meshes."""
    if len(a.vertices) != len(b.vertices):
        raise ValueError("meshes have different vertex counts")
    best = 0.0
    for va, vb in zip(a.vertices, b.vertices):
        for ca, cb in zip(va, vb):
            best = max(best, abs(ca - cb))
    return best
