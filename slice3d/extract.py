"""Blind extraction of data embedded by :mod:`slice3d.embed`.

Given the same key and slice count, the extractor regenerates the embedding path,
reads the length header to learn the payload size, then reads exactly that many
bits back out of the least significant bits of the carrier coordinate.
"""

from __future__ import annotations

from slice3d.codec import (
    HEADER_BITS,
    bits_to_bytes,
    bits_to_int,
    get_lsb,
    to_fixed,
)
from slice3d.keystream import embedding_order
from slice3d.mesh import Mesh
from slice3d.slicer import X, Z


def extract(
    mesh: Mesh,
    key: str,
    num_slices: int,
    axis: int = Z,
    embed_axis: int = X,
) -> bytes:
    """Recover the hidden bytes from a stego ``mesh``.

    Must be called with the same ``key``, ``num_slices``, ``axis`` and
    ``embed_axis`` used at embedding time.
    """
    if embed_axis == axis:
        raise ValueError("embed_axis must differ from the slicing axis")

    order = embedding_order(mesh.vertices, key, num_slices, axis)

    def read_bit(position: int) -> int:
        vertex_index = order[position]
        return get_lsb(to_fixed(mesh.vertices[vertex_index][embed_axis]))

    if len(order) < HEADER_BITS:
        raise ValueError("mesh too small to contain a length header")

    header_bits = [read_bit(i) for i in range(HEADER_BITS)]
    length = bits_to_int(header_bits)

    total_bits = HEADER_BITS + length * 8
    if total_bits > len(order):
        raise ValueError(
            "declared payload length exceeds mesh capacity; wrong key or slice count?"
        )

    payload_bits = [read_bit(i) for i in range(HEADER_BITS, total_bits)]
    return bits_to_bytes(payload_bits)
