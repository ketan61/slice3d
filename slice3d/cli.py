"""Command-line interface for randomsliced3d.

Examples:
    randomsliced3d info    -i model.obj -n 256
    randomsliced3d embed   -i model.obj -o stego.obj -k s3cret -n 256 -m "hello world"
    randomsliced3d extract -i stego.obj -k s3cret -n 256
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from slice3d.mesh import Mesh
from slice3d.reversible import capacity_bytes, embed, extract
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
    # extract() also restores the cover in place -- `mesh` becomes the original.
    mesh = Mesh.load(args.input)
    data = extract(mesh, key=args.key, num_slices=args.slices)
    if args.output:
        with open(args.output, "wb") as fh:
            fh.write(data)
        print(f"recovered {len(data)} bytes -> {args.output}")
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.write(b"\n")

    # The restored cover ("decoded object") -- identical to the original input.
    if args.restore:
        mesh.save(args.restore)
        print(f"restored cover -> {args.restore}")

    if args.original:
        from slice3d.compare import diff_vertices

        original = Mesh.load(args.original)
        n = diff_vertices(original, mesh)
        print(f"restored == original: {n == 0}  ({n} vertices differ)")

    if args.decoded or args.show_decoded:
        from slice3d.visualize import render_model

        render_model(
            mesh,
            title="Decoded object (restored cover, identical to input)",
            out=args.decoded,
            show=args.show_decoded or not args.decoded,
        )
        if args.decoded:
            print(f"saved decoded-object figure -> {args.decoded}")
    return 0


def _payload_size(args: argparse.Namespace) -> int:
    """Number of payload bytes implied by --message / --data-file / --bytes."""
    if args.message is not None:
        return len(args.message.encode("utf-8"))
    if args.data_file is not None:
        with open(args.data_file, "rb") as fh:
            return len(fh.read())
    return args.bytes


def _cmd_visualize(args: argparse.Namespace) -> int:
    mesh = Mesh.load(args.input)
    size = _payload_size(args)

    # A .obj output writes the ROI as a colour-tagged 3D object; otherwise a figure.
    if args.output and args.output.lower().endswith(".obj"):
        from slice3d.visualize import export_roi_obj

        export_roi_obj(mesh, args.key, args.slices, size, args.output)
        print(f"saved ROI object -> {args.output}")
        return 0

    from slice3d.visualize import render_roi

    render_roi(
        mesh,
        key=args.key,
        num_slices=args.slices,
        payload_bytes=size,
        out=args.output,
        show=args.show or not args.output,
    )
    if args.output:
        print(f"saved ROI visualisation -> {args.output}")
    return 0


def _cmd_wizard(args: argparse.Namespace) -> int:
    from slice3d.interactive import run_wizard

    return run_wizard()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="randomsliced3d", description=__doc__)
    # Running "slice3d" with no subcommand launches the interactive wizard.
    parser.set_defaults(func=_cmd_wizard)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "wizard", help="interactive guided embedding (choose file, slices, message)"
    ).set_defaults(func=_cmd_wizard)

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
    p_extract.add_argument(
        "--restore", metavar="OBJ",
        help="save the restored cover model (identical to the original input)",
    )
    p_extract.add_argument(
        "--original", metavar="OBJ",
        help="compare the restored cover against this original and report if identical",
    )
    p_extract.add_argument(
        "--decoded", metavar="PNG",
        help="save a figure of the decoded object (the restored model)",
    )
    p_extract.add_argument(
        "--show-decoded", action="store_true",
        help="open the decoded-object figure in an interactive window",
    )
    p_extract.set_defaults(func=_cmd_extract)

    p_viz = sub.add_parser(
        "visualize", help="show which vertices carry data (ROI) as green dots"
    )
    p_viz.add_argument("-i", "--input", required=True)
    p_viz.add_argument("-k", "--key", required=True)
    p_viz.add_argument("-n", "--slices", type=int, required=True)
    p_viz.add_argument("-o", "--output", help="save figure to this PNG (else show window)")
    p_viz.add_argument("--show", action="store_true", help="also open an interactive window")
    size = p_viz.add_mutually_exclusive_group(required=True)
    size.add_argument("-m", "--message", help="size the ROI to this UTF-8 message")
    size.add_argument("-f", "--data-file", help="size the ROI to this file's contents")
    size.add_argument("-b", "--bytes", type=int, help="size the ROI to this many bytes")
    p_viz.set_defaults(func=_cmd_visualize)

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
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
