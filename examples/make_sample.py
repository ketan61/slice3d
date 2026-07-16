"""Generate a UV-sphere OBJ with enough vertices to carry a real payload.

Usage:
    python examples/make_sample.py sphere.obj --stacks 40 --slices 40
"""

from __future__ import annotations

import argparse
import math


def uv_sphere(stacks: int, slices: int, radius: float = 1.0):
    vertices = []
    faces = []
    for i in range(stacks + 1):
        phi = math.pi * i / stacks  # 0..pi
        for j in range(slices):
            theta = 2 * math.pi * j / slices
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            vertices.append((x, y, z))

    def vid(i, j):
        return i * slices + (j % slices) + 1  # OBJ is 1-indexed

    for i in range(stacks):
        for j in range(slices):
            a, b, c, d = vid(i, j), vid(i, j + 1), vid(i + 1, j + 1), vid(i + 1, j)
            faces.append((a, b, c, d))
    return vertices, faces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--stacks", type=int, default=40)
    parser.add_argument("--slices", type=int, default=40)
    args = parser.parse_args()

    vertices, faces = uv_sphere(args.stacks, args.slices)
    # Write through the canonical Mesh writer so a generated cover and a later
    # restored cover are byte-identical (same -0.000000 normalisation, etc.).
    from slice3d.mesh import Mesh

    mesh = Mesh()
    lines = ["# slice3d sample UV sphere"]
    for x, y, z in vertices:
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for a, b, c, d in faces:
        lines.append(f"f {a} {b} {c} {d}")
    mesh = Mesh.loads("\n".join(lines))
    mesh.save(args.output)
    print(f"wrote {len(vertices)} vertices, {len(faces)} faces to {args.output}")


if __name__ == "__main__":
    main()
