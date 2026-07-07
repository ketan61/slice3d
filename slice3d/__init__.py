"""slice3d — slice-based reversible data hiding in 3D models."""

from slice3d.mesh import Mesh
from slice3d.slicer import assign_slices, slice_bounds

__version__ = "0.1.0"

__all__ = ["Mesh", "assign_slices", "slice_bounds", "__version__"]
