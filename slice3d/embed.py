"""Reversible LSB embedding into vertex coordinates.

Data is written into the least significant bit of the fixed-point ``embed_axis``
coordinate of vertices, visited in the key-driven order. A fixed-width length
header precedes the payload so the extractor knows exactly how many bits to read.
The slicing axis is never touched, keeping slice assignment — and therefore the
extraction path — invariant.
"""

from __future__ import annotations

from slice3d.codec import (
    HEADER_BITS,
    bytes_to_bits,
    from_fixed,
    int_to_bits,
    set_lsb,
    to_fixed,
)
from slice3d.keystream import embedding_order
from slice3d.mesh import Mesh
from slice3d.slicer import X, Z


class CapacityError(ValueError):
    """Raised when the payload does not fit in the available carrier vertices."""


def capacity_bits(mesh: Mesh) -> int:
    """Total carrier bits (one LSB per vertex)."""
    return len(mesh.vertices)


def capacity_bytes(mesh: Mesh) -> int:
    """Maximum payload size in bytes, after reserving the length header."""
    usable = capacity_bits(mesh) - HEADER_BITS
    return max(0, usable // 8)


def embed(
    mesh: Mesh,
    data: bytes,
    key: str,
    num_slices: int,
    axis: int = Z,
    embed_axis: int = X,
) -> Mesh:
    """Embed ``data`` into ``mesh`` in place and return it.

    Args:
        mesh: the cover mesh (modified in place).
        data: raw bytes to hide.
        key: shared secret controlling the embedding path.
        num_slices: number of slices along ``axis``.
        axis: slicing axis (default Z); never modified.
        embed_axis: coordinate carrying the data (default X); must differ from axis.
    """
    if embed_axis == axis:
        raise ValueError("embed_axis must differ from the slicing axis")

    bits = int_to_bits(len(data), HEADER_BITS) + bytes_to_bits(data)
    order = embedding_order(mesh.vertices, key, num_slices, axis)

    if len(bits) > len(order):
        raise CapacityError(
            f"payload needs {len(bits)} carrier bits but mesh provides {len(order)} "
            f"(max {capacity_bytes(mesh)} bytes)"
        )

    for bit, vertex_index in zip(bits, order):
        coord = mesh.vertices[vertex_index][embed_axis]
        mesh.vertices[vertex_index][embed_axis] = from_fixed(set_lsb(to_fixed(coord), bit))

    return mesh
