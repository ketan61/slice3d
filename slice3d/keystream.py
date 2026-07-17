"""Key-driven embedding path (randomsliced3d variant).

Two-stage random selection, both driven by a key-seeded PRNG so the receiver can
reproduce the exact path for blind extraction:

1. **Random slice selection.** The slices are visited in a key-seeded *random
   order*. Because the payload fills slices in that order and stops once the data
   is exhausted, only a random subset of slices actually carries data.
2. **Random point selection.** Within each selected slice, the X-Y plane vertices
   are visited in a key-seeded *random order*.

Concatenating stage 2 over the slices chosen in stage 1 yields a permutation of
vertex indices. The slicing axis is never modified, so slice assignment — and
therefore this whole path — is regenerated identically by the receiver.
"""

from __future__ import annotations

import hashlib
import random
from typing import List, Sequence

from slice3d.slicer import Z, assign_slices


def key_seed(key: str, num_slices: int) -> int:
    """Derive a stable 64-bit PRNG seed from the shared key and slice count."""
    material = f"{key}|{num_slices}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big")


def embedding_order(
    vertices: Sequence[Sequence[float]],
    key: str,
    num_slices: int,
    axis: int = Z,
) -> List[int]:
    """Return the key-seeded permutation of vertex indices to embed into.

    Slices are chosen in a random order (stage 1); within each, vertices are
    chosen in a random order (stage 2). Payload fills this list from the front,
    so a short message lands in a random subset of slices.
    """
    slices = assign_slices(vertices, num_slices, axis)
    rng = random.Random(key_seed(key, num_slices))

    buckets: List[List[int]] = [[] for _ in range(num_slices)]
    for index, s in enumerate(slices):
        buckets[s].append(index)

    # Stage 1: randomly select the order in which slices receive data.
    slice_order = list(range(num_slices))
    rng.shuffle(slice_order)

    # Stage 2: within each selected slice, randomly order its X-Y vertices.
    order: List[int] = []
    for s in slice_order:
        points = buckets[s]
        rng.shuffle(points)
        order.extend(points)
    return order
