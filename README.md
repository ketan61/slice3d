# slice3d

Slice-based **reversible data hiding** in 3D models.

`slice3d` treats a 3D mesh as a stack of planar slices. Fixing two axes (e.g. **X** and **Y**)
and slicing along the third (**Z**), the model is cut into a user-chosen number of slices. Secret
data is then embedded into vertices, slice by slice, along a **key-driven pseudo-random path** so
that the receiver — knowing only the shared key and slice count — can walk the exact same path and
recover the data (blind extraction). The slices are recombined into a *stego* 3D model that is
visually and structurally identical to the original.

```
                Z
                ^        original mesh            stego mesh
                |      ┌───────────┐            ┌───────────┐
   slice N-1 ···|····  │ · · · · · │            │ · ×· · · · │   × = key-selected
                |      │ · · · · · │   embed    │ · · · ·×·  │       vertex carrying
   slice  k  ···|····  │ · · · · · │  ───────▶  │ ×· · · · · │       one data bit
                |      │ · · · · · │            │ · · ×· · · │
   slice  0  ···|····  └───────────┘            └───────────┘
                |         X–Y plane
                +─────────────────▶  X (Y into the page)
```

## Design principles

Three invariants keep the scheme correct and blind:

1. **Reversible embedding (RDH).** Data is hidden by **prediction-error expansion**: each embed
   vertex's X is predicted from its unchanged neighbours and the small prediction error is expanded
   to carry a bit. Extraction recovers both the message **and** the exact original cover — the
   restored model is byte-identical to the input.
2. **Slicing axis is never modified.** We slice along Z, so embedding only perturbs **X**. A vertex
   can therefore never drift into a neighbouring slice, so the receiver's slice assignment always
   matches the sender's.
3. **All randomness is key-derived.** Slice and point selection come from a PRNG seeded by the
   shared secret key. The receiver regenerates the identical embedding order — no side channel or
   location map is transmitted.
4. **Vertex order and precision are preserved.** A dedicated order-preserving OBJ reader/writer
   avoids the silent vertex merging, reordering, and rounding that general mesh libraries perform
   and which would destroy hidden data.

## Status

Working end-to-end reversible pipeline:

- [x] Order/precision-preserving OBJ mesh I/O (`slice3d.mesh`)
- [x] Axis slicing & slice assignment (`slice3d.slicer`)
- [x] Key-driven embedding path (`slice3d.keystream`)
- [x] Reversible embed / extract via prediction-error expansion (`slice3d.reversible`)
- [x] Command-line interface (`slice3d.cli`)

## Usage

### Interactive wizard (easiest)

Run with no arguments (or `slice3d wizard`) to be guided through it. First choose
whether to **hide** or **extract**; a file-explorer dialog then opens to pick the
`.obj` model and you are prompted for the slice count, key, and (when hiding) the
secret message. Extraction prints the recovered message and can save it to a file.

```bash
slice3d            # or: python -m slice3d.cli wizard
```

### Command line

```bash
# Generate a sample mesh to play with (the tiny example cube is too small to carry a payload)
python examples/make_sample.py sphere.obj --stacks 40 --slices 40

# Inspect capacity and slice distribution
python -m slice3d.cli info -i sphere.obj -n 256

# Hide a message (sender)
python -m slice3d.cli embed -i sphere.obj -o stego.obj -k s3cret -n 256 \
    -m "reversible data hiding works!"

# Recover it (receiver) — needs only the same key and slice count
python -m slice3d.cli extract -i stego.obj -k s3cret -n 256

# Recover it AND restore the exact original cover, verifying reversibility
python -m slice3d.cli extract -i stego.obj -k s3cret -n 256 \
    --restore restored.obj --original sphere.obj
# -> prints "restored == original: True (0 vertices differ)"; restored.obj is
#    byte-identical to sphere.obj, while stego.obj differs (it carries the data)
```

### Visualise the embedding ROI

See exactly which vertices carry the hidden data, drawn as green dots on the model
(the 3D analogue of an ROI mask on a cover image). Requires the `viz` extra
(`pip install "slice3d[viz]"`).

```bash
# Save a figure sized to a given message (or use -f FILE / -b NBYTES)
slice3d visualize -i sphere.obj -k s3cret -n 256 -m "my secret" -o roi.png
```

Or from Python:

```python
from slice3d import Mesh, embed, extract

mesh = Mesh.load("sphere.obj")
embed(mesh, b"secret bytes", key="s3cret", num_slices=256)
mesh.save("stego.obj")

received = Mesh.load("stego.obj")
assert extract(received, key="s3cret", num_slices=256) == b"secret bytes"
```

## Development

```bash
python -m pytest        # run the test suite
```

## License

MIT — see [LICENSE](LICENSE).
