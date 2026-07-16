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


def data_carrier_indices(mesh: Mesh, key: str, num_slices: int, payload_bytes: int):
    """The vertices that actually carry data for a payload of the given size.

    Reproduces embedding's selection on the *cover* mesh: the lowest-error
    expandable vertices, in key order, up to ``header + payload`` of them. This is
    the true ROI -- where the secret data lives.
    """
    carriers, predictors = _ordered_carriers(mesh, key, num_slices)
    needed = min(HEADER_BITS + payload_bytes * 8, len(carriers))
    if needed <= 0:
        return []
    errors = {
        i: to_fixed(mesh.vertices[i][X]) - _predict(mesh, predictors[i])
        for i in carriers
    }
    threshold = sorted(abs(errors[i]) for i in carriers)[needed - 1]
    out = []
    for i in carriers:
        if abs(errors[i]) <= threshold:
            out.append(i)
            if len(out) == needed:
                break
    return out


# -- threshold side-info ----------------------------------------------------
#
# Embedding expands the prediction error (e' = 2e + b) only for vertices whose
# error is small (|e| <= T); vertices with larger errors are merely *shifted* by
# T+1 to keep the two cases distinguishable. This bounds every vertex's movement
# to at most T+1 fixed-point units, so the stego model stays visually identical
# to the cover. T is chosen as small as the payload allows and recorded in a one
# line marker in the stego file (the single piece of side information needed to
# decode); the marker is stripped again on extraction so the restored cover is
# byte-identical to the original.

_MARKER = "# slice3d-rdh"


def _set_threshold(mesh: Mesh, threshold: int) -> None:
    mesh._records = [
        r for r in mesh._records
        if not (r[0] == "raw" and isinstance(r[1], str) and r[1].startswith(_MARKER))
    ]
    mesh._records.insert(0, ("raw", f"{_MARKER} T={threshold}"))


def _pop_threshold(mesh: Mesh):
    """Read and remove the threshold marker; return T (or None if absent)."""
    threshold = None
    kept = []
    for r in mesh._records:
        if r[0] == "raw" and isinstance(r[1], str) and r[1].startswith(_MARKER):
            try:
                threshold = int(r[1].split("T=")[1].split()[0])
            except (IndexError, ValueError):
                threshold = None
        else:
            kept.append(r)
    mesh._records = kept
    return threshold


# -- embed / extract --------------------------------------------------------

def embed(mesh: Mesh, data: bytes, key: str, num_slices: int) -> Mesh:
    """Reversibly embed ``data`` into ``mesh`` in place and return it.

    Uses thresholded prediction-error expansion so the stego model stays close to
    the cover: only the lowest-error vertices carry data, and every vertex moves
    by at most ``T+1`` fixed-point units (1 unit = 1e-6 model units).
    """
    carriers, predictors = _ordered_carriers(mesh, key, num_slices)
    bits = int_to_bits(len(data), HEADER_BITS) + bytes_to_bits(data)
    if len(bits) > len(carriers):
        raise CapacityError(
            f"payload needs {len(bits)} carrier vertices but mesh provides "
            f"{len(carriers)} (max {capacity_bytes(mesh)} bytes)"
        )

    preds = {i: _predict(mesh, predictors[i]) for i in carriers}
    errors = {i: to_fixed(mesh.vertices[i][X]) - preds[i] for i in carriers}

    # Smallest threshold that makes at least len(bits) vertices expandable.
    threshold = sorted(abs(errors[i]) for i in carriers)[len(bits) - 1]

    bit_iter = iter(bits)
    for i in carriers:
        e = errors[i]
        if abs(e) <= threshold:
            b = next(bit_iter, 0)  # 0-pad expandable carriers beyond the payload
            e2 = 2 * e + b
        elif e > threshold:
            e2 = e + (threshold + 1)
        else:  # e < -threshold
            e2 = e - (threshold + 1)
        mesh.vertices[i][X] = from_fixed(preds[i] + e2)

    _set_threshold(mesh, threshold)
    return mesh


def extract(mesh: Mesh, key: str, num_slices: int) -> bytes:
    """Recover the hidden bytes AND restore the original cover in place.

    After this call ``mesh`` holds the exact original model (all embed vertices
    reverted and the side-info marker removed), demonstrating reversibility. Must
    use the same key/slice count.
    """
    threshold = _pop_threshold(mesh)
    if threshold is None:
        raise ValueError("not a slice3d stego model (missing threshold marker)")

    carriers, predictors = _ordered_carriers(mesh, key, num_slices)
    limit = 2 * threshold + 1

    bits = []
    for i in carriers:
        pred = _predict(mesh, predictors[i])
        e2 = to_fixed(mesh.vertices[i][X]) - pred
        if abs(e2) <= limit:  # expanded -> carries a bit
            b = e2 % 2
            e = (e2 - b) // 2
            bits.append(b)
        elif e2 > 0:  # shifted up
            e = e2 - (threshold + 1)
        else:  # shifted down
            e = e2 + (threshold + 1)
        mesh.vertices[i][X] = from_fixed(pred + e)  # restore original X

    if len(bits) < HEADER_BITS:
        raise ValueError("no length header; wrong key or slice count?")
    length = bits_to_int(bits[:HEADER_BITS])
    total = HEADER_BITS + length * 8
    if total > len(bits):
        raise ValueError(
            "declared payload length exceeds capacity; wrong key or slice count?"
        )
    return bits_to_bytes(bits[HEADER_BITS:total])
