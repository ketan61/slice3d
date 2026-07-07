from slice3d.mesh import Mesh, PRECISION

SAMPLE_OBJ = """\
# a tiny textured cube fragment
o cube
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 1.0 1.0 0.0 0.5 0.5 0.5
vn 0.0 0.0 1.0
vt 0.0 0.0
f 1//1 2//1 3//1
"""


def test_load_parses_only_vertex_lines():
    mesh = Mesh.loads(SAMPLE_OBJ)
    assert len(mesh) == 3
    assert mesh.vertices[0] == [0.0, 0.0, 0.0]
    assert mesh.vertices[1] == [1.0, 0.0, 0.0]
    assert mesh.vertices[2] == [1.0, 1.0, 0.0]


def test_roundtrip_preserves_non_vertex_lines():
    mesh = Mesh.loads(SAMPLE_OBJ)
    out = mesh.dumps()
    # Comments, object name, normals, texcoords and faces survive verbatim.
    assert "# a tiny textured cube fragment" in out
    assert "o cube" in out
    assert "vn 0.0 0.0 1.0" in out
    assert "vt 0.0 0.0" in out
    assert "f 1//1 2//1 3//1" in out


def test_roundtrip_preserves_vertex_extra_tokens():
    mesh = Mesh.loads(SAMPLE_OBJ)
    out = mesh.dumps()
    # Trailing per-vertex tokens (e.g. vertex colors) are kept verbatim.
    assert "0.5 0.5 0.5" in out


def test_reload_is_stable_to_precision():
    mesh = Mesh.loads(SAMPLE_OBJ)
    reloaded = Mesh.loads(mesh.dumps())
    assert len(reloaded) == len(mesh)
    for a, b in zip(mesh.vertices, reloaded.vertices):
        for ca, cb in zip(a, b):
            assert round(ca, PRECISION) == round(cb, PRECISION)
