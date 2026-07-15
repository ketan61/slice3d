"""Reversible data hiding via prediction-error expansion (PEE).

Unlike LSB replacement (which destroys the original bit), PEE is *reversible*:
extraction recovers both the hidden message **and** the exact original cover
model. This is what makes the scheme genuine RDH -- the receiver can restore the
input object bit-for-bit after reading the data.

How it works
------------
1. Vertices are 2-coloured over the mesh adjacency graph into a **reference** set
   and an **embed** set. Reference vertices are never modified.
2. Each embed vertex's X coordinate is *predicted* from its reference-set
   neighbours (whose values never change), giving a small integer prediction
   error ``e = x - pred``.
3. A bit ``b`` is embedded by expanding the error: ``e' = 2*e + b``. Because the
   predictor depends only on unmodified reference vertices, it is identical on
   both sides, so ``e`` and ``b`` -- and thus the original ``x`` -- are exactly
   recoverable: ``b = e' mod 2``, ``e = (e' - b) / 2``, ``x = pred + e``.

Only the first ``header + payload`` carriers (in the key-driven order) are
touched, so distortion is confined to exactly the vertices needed. The slicing
axis (Z) is never modified, keeping slice assignment -- and the whole path --
reproducible.

Reversibility is with respect to the mesh's 6-decimal fixed-point representation
(see :data:`slice3d.mesh.PRECISION`); models written by this tool round-trip
exactly.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Sequence, Tuple

from slice3d.codec import (
    HEADER_BITS,
    bits_to_bytes,
    bits_to_int,
    bytes_to_bits,
    from_fixed,
    int_to_bits,
    to_fixed,
)
from slice3d.keystream import embedding_order
from slice3d.mesh import Mesh
from slice3d.slicer import X, Z


class CapacityError(ValueError):
    """Raised when the payload does not fit in the available carrier vertices."""


# -- mesh structure ---------------------------------------------------------

def _adjacency(mesh: Mesh) -> List[set]:
    """Undirected vertex adjacency derived from the mesh faces."""
    adj: List[set] = [set() for _ in range(len(mesh.vertices))]
    n = len(mesh.vertices)
    for face in mesh.faces:
        k = len(face)
        for a in range(k):
            i, j = face[a], face[(a + 1) % k]
            if 0 <= i < n and 0 <= j < n and i != j:
                adj[i].add(j)
                adj[j].add(i)
    return adj


def _two_colour(adj: List[set]) -> List[int]:
    """Deterministic BFS 2-colouring (by distance parity) of the adjacency graph.

    Not necessarily a proper colouring (meshes have odd cycles), but stable given
    the structure -- which is all reversibility needs.
    """
    n = len(adj)
    colour = [-1] * n
    for start in range(n):
        if colour[start] != -1:
            continue
        colour[start] = 0
        queue = deque([start])
        while queue:
            v = queue.popleft()
            for w in sorted(adj[v]):
                if colour[w] == -1:
                    colour[w] = colour[v] ^ 1
                    queue.append(w)
    return colour


def _carrier_plan(mesh: Mesh) -> Tuple[Dict[int, List[int]], List[int]]:
    """Return (predictors, carrier_set).

    predictors[i] is the list of reference-set neighbours used to predict embed
    vertex ``i``; carrier_set is the embed vertices that have at least one such
    neighbour (only these can be predicted, hence used).
    """
    adj = _adjacency(mesh)
    colour = _two_colour(adj)
    predictors: Dict[int, List[int]] = {}
    carriers: List[int] = []
    for i, c in enumerate(colour):
        if c != 1:
            continue  # reference vertices are never modified
        refs = [j for j in adj[i] if colour[j] == 0]
        if refs:
            predictors[i] = sorted(refs)
            carriers.append(i)
    return predictors, set(carriers)


def _ordered_carriers(mesh: Mesh, key: str, num_slices: int) -> Tuple[List[int], Dict[int, List[int]]]:
    """Carrier vertex indices in key-driven order, plus their predictors."""
    predictors, carrier_set = _carrier_plan(mesh)
    order = embedding_order(mesh.vertices, key, num_slices, Z)
    ordered = [i for i in order if i in carrier_set]
    return ordered, predictors


def _predict(mesh: Mesh, refs: Sequence[int]) -> int:
    """Integer prediction of a vertex's fixed-point X from its reference neighbours."""
    total = sum(to_fixed(mesh.vertices[j][X]) for j in refs)
    return round(total / len(refs))


# -- capacity ---------------------------------------------------------------

def capacity_bits(mesh: Mesh) -> int:
    _, carrier_set = _carrier_plan(mesh)
    return len(carrier_set)


def capacity_bytes(mesh: Mesh) -> int:
    return max(0, (capacity_bits(mesh) - HEADER_BITS) // 8)


# -- embed / extract --------------------------------------------------------

def embed(mesh: Mesh, data: bytes, key: str, num_slices: int) -> Mesh:
    """Reversibly embed ``data`` into ``mesh`` in place and return it."""
    carriers, predictors = _ordered_carriers(mesh, key, num_slices)
    bits = int_to_bits(len(data), HEADER_BITS) + bytes_to_bits(data)
    if len(bits) > len(carriers):
        raise CapacityError(
            f"payload needs {len(bits)} carrier vertices but mesh provides "
            f"{len(carriers)} (max {capacity_bytes(mesh)} bytes)"
        )

    for bit, i in zip(bits, carriers):
        pred = _predict(mesh, predictors[i])
        e = to_fixed(mesh.vertices[i][X]) - pred
        expanded = 2 * e + bit
        mesh.vertices[i][X] = from_fixed(pred + expanded)
    return mesh


def extract(mesh: Mesh, key: str, num_slices: int) -> bytes:
    """Recover the hidden bytes AND restore the original cover in place.

    After this call ``mesh`` holds the exact original model (all embed vertices
    reverted), demonstrating reversibility. Must use the same key/slice count.
    """
    carriers, predictors = _ordered_carriers(mesh, key, num_slices)

    def read_and_restore(i: int) -> int:
        pred = _predict(mesh, predictors[i])
        expanded = to_fixed(mesh.vertices[i][X]) - pred
        bit = expanded % 2
        e = (expanded - bit) // 2
        mesh.vertices[i][X] = from_fixed(pred + e)  # restore original X
        return bit

    if len(carriers) < HEADER_BITS:
        raise ValueError("mesh too small to contain a length header")

    header = [read_and_restore(carriers[p]) for p in range(HEADER_BITS)]
    length = bits_to_int(header)

    total = HEADER_BITS + length * 8
    if total > len(carriers):
        raise ValueError(
            "declared payload length exceeds mesh capacity; wrong key or slice count?"
        )

    payload_bits = [read_and_restore(carriers[p]) for p in range(HEADER_BITS, total)]
    return bits_to_bytes(payload_bits)
