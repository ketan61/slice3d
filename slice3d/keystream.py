"""Key-driven embedding path.

The scheme repeatedly picks a random slice and then a random point within it. To
make extraction *blind*, that sequence must be reproducible by the receiver from
shared secrets alone. We derive a PRNG seed from ``(key, num_slices)`` and use it
to build a deterministic permutation of vertex indices:

1. assign every vertex to a slice (depends only on the unmodified slicing axis);
2. shuffle the points within each slice — "a random point on the plane";
3. shuffle a visitation list holding each slice once per point it owns — "a random
   slice each step".

The result visits every vertex exactly once, distributing embedding across slices
in a key-dependent order that the receiver regenerates identically.
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
    """Return the key-seeded permutation of vertex indices to embed into."""
    slices = assign_slices(vertices, num_slices, axis)
    rng = random.Random(key_seed(key, num_slices))

    buckets: List[List[int]] = [[] for _ in range(num_slices)]
    for index, s in enumerate(slices):
        buckets[s].append(index)

    for bucket in buckets:
        rng.shuffle(bucket)  # random point order within the slice

    visits: List[int] = []
    for s, bucket in enumerate(buckets):
        visits.extend([s] * len(bucket))
    rng.shuffle(visits)  # random slice to visit at each step

    cursors = [0] * num_slices
    order: List[int] = []
    for s in visits:
        order.append(buckets[s][cursors[s]])
        cursors[s] += 1
    return order
