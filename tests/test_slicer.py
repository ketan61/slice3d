import pytest

from slice3d.slicer import assign_slices, slice_bounds, X, Z


def make_column(n):
    """n vertices evenly spread along Z from 0..1, jittered in X/Y."""
    return [[i * 0.01, i * 0.02, i / (n - 1)] for i in range(n)]


def test_bounds():
    verts = make_column(10)
    lo, hi = slice_bounds(verts, Z)
    assert lo == 0.0
    assert hi == 1.0


def test_all_slices_in_range():
    verts = make_column(100)
    slices = assign_slices(verts, 8, axis=Z)
    assert len(slices) == 100
    assert min(slices) == 0
    assert max(slices) == 7
    assert all(0 <= s < 8 for s in slices)


def test_top_vertex_clamped_into_last_slice():
    verts = make_column(50)
    slices = assign_slices(verts, 10, axis=Z)
    # The maximum-Z vertex must land in the final band, not overflow to index 10.
    assert slices[-1] == 9


def test_assignment_invariant_to_non_slicing_axis():
    """Perturbing X (an embedding axis) must not change any slice assignment."""
    verts = make_column(64)
    before = assign_slices(verts, 12, axis=Z)
    for v in verts:
        v[X] += 0.123  # simulate embedding into X
    after = assign_slices(verts, 12, axis=Z)
    assert before == after


def test_degenerate_span_all_zero():
    verts = [[0.0, 0.0, 5.0] for _ in range(4)]
    assert assign_slices(verts, 3, axis=Z) == [0, 0, 0, 0]


def test_invalid_slice_count():
    with pytest.raises(ValueError):
        assign_slices(make_column(3), 0)
