"""Command-line interface for slice3d.

Examples:
    slice3d info    -i model.obj -n 256
    slice3d embed   -i model.obj -o stego.obj -k s3cret -n 256 -m "hello world"
    slice3d extract -i stego.obj -k s3cret -n 256
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from slice3d.embed import capacity_bytes, embed
from slice3d.extract import extract
from slice3d.mesh import Mesh
from slice3d.slicer import Z, assign_slices, slice_bounds


def _load_payload(args: argparse.Namespace) -> bytes:
    if args.message is not None:
        return args.message.encode("utf-8")
    with open(args.data_file, "rb") as fh:
        return fh.read()


def _cmd_info(args: argparse.Namespace) -> int:
    mesh = Mesh.load(args.input)
    lo, hi = slice_bounds(mesh.vertices, Z)
    slices = assign_slices(mesh.vertices, args.slices, Z)
    counts = Counter(slices)
    print(f"vertices     : {len(mesh)}")
    print(f"Z range      : [{lo:.6f}, {hi:.6f}]")
    print(f"slices       : {args.slices}")
    print(f"capacity     : {capacity_bytes(mesh)} bytes")
    nonempty = sum(1 for s in range(args.slices) if counts.get(s))
    print(f"non-empty    : {nonempty}/{args.slices} slices")
    return 0


def _cmd_embed(args: argparse.Namespace) -> int:
    mesh = Mesh.load(args.input)
    data = _load_payload(args)
    embed(mesh, data, key=args.key, num_slices=args.slices)
    mesh.save(args.output)
    print(f"embedded {len(data)} bytes into {args.output}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    mesh = Mesh.load(args.input)
    data = extract(mesh, key=args.key, num_slices=args.slices)
    if args.output:
        with open(args.output, "wb") as fh:
            fh.write(data)
        print(f"recovered {len(data)} bytes -> {args.output}")
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.write(b"\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="slice3d", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="show mesh capacity and slice stats")
    p_info.add_argument("-i", "--input", required=True)
    p_info.add_argument("-n", "--slices", type=int, required=True)
    p_info.set_defaults(func=_cmd_info)

    p_embed = sub.add_parser("embed", help="hide data in a mesh")
    p_embed.add_argument("-i", "--input", required=True)
    p_embed.add_argument("-o", "--output", required=True)
    p_embed.add_argument("-k", "--key", required=True)
    p_embed.add_argument("-n", "--slices", type=int, required=True)
    src = p_embed.add_mutually_exclusive_group(required=True)
    src.add_argument("-m", "--message", help="payload as a UTF-8 string")
    src.add_argument("-f", "--data-file", help="payload read from a file")
    p_embed.set_defaults(func=_cmd_embed)

    p_extract = sub.add_parser("extract", help="recover hidden data from a mesh")
    p_extract.add_argument("-i", "--input", required=True)
    p_extract.add_argument("-k", "--key", required=True)
    p_extract.add_argument("-n", "--slices", type=int, required=True)
    p_extract.add_argument("-o", "--output", help="write bytes here (else stdout)")
    p_extract.set_defaults(func=_cmd_extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        # Expected, user-facing failures (wrong key/slice count, oversized
        # payload, missing files). Report cleanly instead of dumping a traceback;
        # unexpected exceptions still propagate for debugging.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
