"""Visualise the embedding ROI: which vertices carry the hidden data.

The embedder selects vertices along a key-driven path (see
:mod:`slice3d.keystream`) and writes the payload bits into their coordinates.
This module highlights exactly those "region of interest" vertices in green on
top of the full mesh, so the embedder can *see* where the secret data lives in
the 3D model -- the 3D analogue of an ROI mask on a cover image.

matplotlib is an optional dependency; install it with ``pip install slice3d[viz]``.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from slice3d.codec import HEADER_BITS
from slice3d.keystream import embedding_order
from slice3d.mesh import Mesh
from slice3d.slicer import X, Z


def payload_bits(payload_bytes: int) -> int:
    """Total carrier bits used for a payload: the length header plus its bytes."""
    return HEADER_BITS + payload_bytes * 8


def carrier_indices(
    vertices: Sequence[Sequence[float]],
    key: str,
    num_slices: int,
    payload_bytes: int,
    axis: int = Z,
) -> List[int]:
    """Return the vertex indices that carry data for a payload of the given size.

    These are the first ``header + payload`` positions of the key-driven
    embedding order -- i.e. the ROI. Clamped to the mesh's capacity.
    """
    order = embedding_order(vertices, key, num_slices, axis)
    return order[: min(payload_bits(payload_bytes), len(order))]


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "matplotlib is required for visualisation. "
            "Install it with: pip install \"slice3d[viz]\""
        ) from exc
    return plt


def render_roi(
    mesh: Mesh,
    key: str,
    num_slices: int,
    payload_bytes: int,
    axis: int = Z,
    out: Optional[str] = None,
    show: bool = False,
    title: Optional[str] = None,
    role: str = "embedding",
):
    """Render the mesh with data-carrying vertices highlighted in green.

    Args:
        mesh: the cover (or stego) model.
        key, num_slices, axis: the embedding parameters that define the path.
        payload_bytes: size of the payload, to size the ROI.
        out: if given, save the figure to this path (e.g. ``roi.png``).
        show: if True, open an interactive window.
        title: optional plot title (overrides the role-based default).
        role: ``"embedding"`` (ROI, sender side) or ``"decoded"`` (receiver side).
    """
    plt = _require_matplotlib()

    verts = mesh.vertices
    carriers = set(carrier_indices(verts, key, num_slices, payload_bytes, axis))

    cx, cy, cz = [], [], []  # carrier vertices (green)
    ox, oy, oz = [], [], []  # other vertices (grey)
    for i, (x, y, z) in enumerate(verts):
        if i in carriers:
            cx.append(x); cy.append(y); cz.append(z)
        else:
            ox.append(x); oy.append(y); oz.append(z)

    if role == "decoded":
        default_title = (
            f"Decoded object\n{len(carriers)} vertices the message was read "
            f"from  (key-driven, {num_slices} slices)"
        )
        carrier_label = f"decoded vertices ({len(carriers)})"
    else:
        default_title = (
            f"ROI selected for embedding\n{len(carriers)} of {len(verts)} "
            f"vertices carry data  (key-driven, {num_slices} slices)"
        )
        carrier_label = f"data-carrying ({len(carriers)})"

    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(ox, oy, oz, c="0.6", s=5, alpha=0.5, linewidths=0,
               label="model vertices")
    ax.scatter(cx, cy, cz, c="limegreen", s=20, depthshade=False,
               edgecolors="darkgreen", linewidths=0.3, label=carrier_label)

    ax.set_title(title or default_title)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z (slicing axis)")
    ax.legend(loc="upper right", fontsize=8)
    _set_equal_aspect(ax, verts)
    fig.tight_layout()

    if out:
        fig.savefig(out, dpi=150)
    if show:
        plt.show()
    else:
        plt.close(fig)
    return out


def render_decoded(
    mesh: Mesh,
    key: str,
    num_slices: int,
    payload_bytes: int,
    axis: int = Z,
    out: Optional[str] = None,
    show: bool = False,
):
    """Render the *decoded* object: the model the message was read from,
    with the decoded vertices highlighted (receiver-side analogue of the ROI)."""
    return render_roi(
        mesh, key, num_slices, payload_bytes,
        axis=axis, out=out, show=show, role="decoded",
    )


def _set_equal_aspect(ax, verts: Sequence[Sequence[float]]) -> None:
    """Give the 3D axes equal scale so the model is not distorted."""
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    ranges = [max(a) - min(a) for a in (xs, ys, zs)]
    radius = (max(ranges) or 1.0) / 2
    mids = [(max(a) + min(a)) / 2 for a in (xs, ys, zs)]
    ax.set_xlim(mids[0] - radius, mids[0] + radius)
    ax.set_ylim(mids[1] - radius, mids[1] + radius)
    ax.set_zlim(mids[2] - radius, mids[2] + radius)
