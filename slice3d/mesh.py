"""Order- and precision-preserving Wavefront OBJ mesh I/O.

General-purpose mesh libraries routinely merge coincident vertices, reorder them,
and round coordinates on load/save. Any of those silently destroys data hidden in
vertex coordinates. ``Mesh`` therefore does the minimum necessary: it records every
line of the source file verbatim, and for vertex (``v``) lines it stores the parsed
coordinates in original order. On write, non-vertex lines are re-emitted untouched
and vertex lines are formatted at a fixed decimal precision that round-trips exactly
with the fixed-point representation used by the embedding code.
"""

from __future__ import annotations

# Decimal places kept when writing vertices. Must match the fixed-point SCALE used
# by the embedding code so that write -> read is lossless for embedded bits.
PRECISION = 6

_NEG_ZERO = f"{-0.0:.{PRECISION}f}"  # "-0.000000"
_POS_ZERO = f"{0.0:.{PRECISION}f}"   # "0.000000"


def _fmt(x: float) -> str:
    """Format a coordinate, canonicalising -0.000000 to 0.000000.

    Degenerate coordinates that round to zero can carry a stray minus sign
    ("-0.000000"), which is numerically identical but breaks byte-level equality
    between a restored model and its original. Normalising keeps restoration
    byte-clean without changing any value.
    """
    s = f"{x:.{PRECISION}f}"
    return _POS_ZERO if s == _NEG_ZERO else s


class Mesh:
    """A triangle/polygon mesh loaded from an OBJ file.

    Attributes:
        vertices: list of ``[x, y, z]`` float coordinates, in file order.
    """

    def __init__(self) -> None:
        self.vertices: list[list[float]] = []
        # Playback records used to reconstruct the file faithfully on write.
        # Each entry is either ("v", vertex_index) or ("raw", original_line).
        self._records: list[tuple[str, object]] = []
        # Any trailing tokens on a vertex line beyond x/y/z (e.g. vertex colors),
        # keyed by vertex index, preserved verbatim.
        self._vertex_extra: dict[int, str] = {}
        # Faces as tuples of 0-based vertex indices, used only to derive vertex
        # adjacency (never modified; the original lines are re-emitted verbatim).
        self.faces: list[tuple[int, ...]] = []

    # -- construction ---------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "Mesh":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.loads(fh.read())

    @classmethod
    def loads(cls, text: str) -> "Mesh":
        mesh = cls()
        for line in text.splitlines():
            tokens = line.split()
            if tokens and tokens[0] == "v" and len(tokens) >= 4:
                idx = len(mesh.vertices)
                mesh.vertices.append(
                    [float(tokens[1]), float(tokens[2]), float(tokens[3])]
                )
                if len(tokens) > 4:
                    mesh._vertex_extra[idx] = " ".join(tokens[4:])
                mesh._records.append(("v", idx))
            else:
                if tokens and tokens[0] == "f" and len(tokens) >= 4:
                    mesh.faces.append(mesh._parse_face(tokens[1:]))
                mesh._records.append(("raw", line))
        return mesh

    @staticmethod
    def _parse_face(parts: list[str]) -> tuple[int, ...]:
        """Parse OBJ face vertex refs (``v``, ``v/vt``, ``v//vn``) to 0-based ids."""
        indices = []
        for part in parts:
            token = part.split("/", 1)[0]
            if not token:
                continue
            i = int(token)
            indices.append(i - 1 if i > 0 else i)  # negative = relative (rare)
        return tuple(indices)

    # -- serialization --------------------------------------------------------

    def dumps(self) -> str:
        out: list[str] = []
        for kind, value in self._records:
            if kind == "v":
                idx = value  # type: ignore[assignment]
                x, y, z = self.vertices[idx]
                line = f"v {_fmt(x)} {_fmt(y)} {_fmt(z)}"
                extra = self._vertex_extra.get(idx)
                if extra:
                    line += f" {extra}"
                out.append(line)
            else:
                out.append(value)  # type: ignore[arg-type]
        return "\n".join(out) + "\n"

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.dumps())

    # -- convenience ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self.vertices)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Mesh vertices={len(self.vertices)}>"
