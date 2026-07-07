"""Partition a mesh into planar slices along one axis.

Slicing fixes two axes and cuts the model into ``num_slices`` equal bands along the
third. With the default ``axis=2`` (Z), each slice is an X-Y plane band. Slice
assignment depends *only* on the slicing-axis coordinate, so as long as embedding
leaves that coordinate untouched, a vertex never migrates between slices and the
receiver reproduces the sender's slice layout exactly.
"""

from __future__ import annotations

from typing import List, Sequence

# Axis indices into an [x, y, z] vertex.
X, Y, Z = 0, 1, 2

Vertex = Sequence[float]


def slice_bounds(vertices: Sequence[Vertex], axis: int = Z) -> tuple[float, float]:
    """Return ``(min, max)`` of the given axis across all vertices."""
    if not vertices:
        raise ValueError("cannot compute slice bounds of an empty mesh")
    values = [v[axis] for v in vertices]
    return min(values), max(values)


def assign_slices(
    vertices: Sequence[Vertex], num_slices: int, axis: int = Z
) -> List[int]:
    """Map every vertex to a slice index in ``[0, num_slices)``.

    Vertices are binned into ``num_slices`` equal-width bands spanning the axis
    range. The maximum-valued vertex is clamped into the last band so the index
    never equals ``num_slices``.
    """
    if num_slices < 1:
        raise ValueError("num_slices must be >= 1")

    lo, hi = slice_bounds(vertices, axis)
    span = hi - lo

    result: List[int] = []
    for v in vertices:
        if span == 0:
            result.append(0)
            continue
        t = (v[axis] - lo) / span
        s = int(t * num_slices)
        if s >= num_slices:
            s = num_slices - 1
        result.append(s)
    return result
