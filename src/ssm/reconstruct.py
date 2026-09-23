"""Reconstruct a hemipelvis with missing bone by fitting the shape model.

    python -m ssm.reconstruct DAMAGED.stl [--reference HEALTHY_OTHER_SIDE.stl]

A left side is mirrored onto the right-sided model (x -> -x in the aligned
pelvic frame) and the result mirrored back, so the output is in the input's
own frame. With --reference, the patient's healthy other side is mirrored
onto the same side and compared with the reconstruction; natural left/right
asymmetry means this is a plausibility check, not ground truth.
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pyvista as pv
import shapeworks as sw
import trimesh

from . import fit, model
from .clean import ADAPTIVITY, N_VERTICES, SMOOTH_ITERATIONS, SMOOTH_PASSBAND
from .project import PROJECT_DIR

OUT = PROJECT_DIR.parent / "reconstruction"

# Chosen from ssm.validate
MODES = 34
REG = 10.0

# A damaged bone may be in several real pieces; only specks smaller than
# this fraction of the mesh are dropped.
MIN_PIECE_FRACTION = 0.01
# Reconstruction further than this from the input is filled-in bone. On intact
# held-out bones 95% of the surface fits within ~4 mm (ssm.validate), so a
# tighter threshold would flag ordinary fit error as filled bone.
FILLED_MM = 5.0


def side_of(path):
    return re.search(r"pelvis_(left|right)", Path(path).name).group(1)


def mirror(mesh):
    mesh = mesh.copy()
    mesh.points[:, 0] *= -1
    return mesh.flip_faces() if hasattr(mesh, "flip_faces") else mesh.flip_normals()


def load(path):
    """Mesh in the model's right-sided frame, cleaned like the training meshes but keeping every piece."""
    raw = trimesh.load(path)
    pieces = [p for p in raw.split(only_watertight=False) if len(p.faces) >= MIN_PIECE_FRACTION * len(raw.faces)]
    kept = trimesh.util.concatenate(pieces)
    mesh = sw.Mesh(np.asarray(kept.vertices, dtype=float), np.asarray(kept.faces, dtype=np.int32))
    mesh.smoothSinc(iterations=SMOOTH_ITERATIONS, passband=SMOOTH_PASSBAND)
    mesh.remesh(numVertices=N_VERTICES, adaptivity=ADAPTIVITY)
    poly = pv.PolyData(mesh.points(), np.hstack([np.full((len(mesh.faces()), 1), 3), mesh.faces()]).ravel())
    return (mirror(poly) if side_of(path) == "left" else poly), len(pieces)


def distance(points, surface):
    return np.abs(pv.PolyData(points).compute_implicit_distance(surface)["implicit_distance"])


def render(path, reconstruction, damaged, reference=None):
    """Top row: the damaged input with the filled-in bone overlaid. Bottom row
    (with a reference): the reconstruction coloured by distance from the
    mirrored healthy side."""
    pv.OFF_SCREEN = True
    rows = 2 if reference is not None else 1
    plotter = pv.Plotter(shape=(rows, 2), window_size=(1200, 620 * rows), border=False)
    plotter.set_background("white")
    centre = np.array(reconstruction.center)
    filled = reconstruction.threshold(FILLED_MM, scalars="from_input")
    for col, sign in enumerate((1, -1)):
        camera = [tuple(centre + sign * np.array([500.0, 0, 0])), tuple(centre), (0, 0, 1)]
        plotter.subplot(0, col)
        plotter.add_mesh(damaged, color="#d9d4c7", smooth_shading=True)
        if filled.n_points:
            plotter.add_mesh(filled, color="#e8702a", opacity=0.85, smooth_shading=True)
        plotter.add_text("input (grey) + filled-in bone (orange)", font_size=10, color="black")
        plotter.camera_position = camera
        if rows == 2:
            plotter.subplot(1, col)
            plotter.add_mesh(reconstruction, scalars="from_reference", cmap="magma_r", clim=(0, 10),
                             smooth_shading=True, show_scalar_bar=col == 1,
                             scalar_bar_args={"title": "mm", "color": "black", "position_x": 0.3, "width": 0.4})
            plotter.add_text("reconstruction: distance from mirrored healthy side", font_size=10, color="black")
            plotter.camera_position = camera
    plotter.screenshot(str(path))
    plotter.close()


def reconstruct(path, reference=None, n_modes=MODES, reg=REG):
    damaged, pieces = load(path)
    shape_model = model.build(model.load_world()[1])
    mean_surface = fit.load_mean_surface()
    points, normals = fit.surface_points(damaged)
    result = fit.fit(shape_model, mean_surface.particle_normals, points, normals, n_modes, reg)
    surface = fit.dense_surface(mean_surface, result, shape_model)
    surface["from_input"] = distance(surface.points, damaged)
    filled = surface["from_input"] > FILLED_MM

    report = {"pieces": pieces, "fit_rms": result.rms, "matched": result.inliers.mean(),
              "b": np.round(result.b[:3], 2).tolist(), "filled_fraction": filled.mean()}
    if reference is not None:
        healthy, _ = load(reference)
        surface["from_reference"] = distance(surface.points, healthy)
        report |= {"vs_reference_mean": surface["from_reference"].mean(),
                   "vs_reference_filled_mean": surface["from_reference"][filled].mean() if filled.any() else np.nan,
                   "vs_reference_filled_p95": np.percentile(surface["from_reference"][filled], 95) if filled.any() else np.nan}

    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{Path(path).name.split('_raw')[0]}_{side_of(path)}"
    render(OUT / f"{stem}.png", surface, damaged, reference)
    output = mirror(surface) if side_of(path) == "left" else surface
    output.clear_data()
    output.save(str(OUT / f"{stem}.ply"))
    return stem, report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("damaged")
    parser.add_argument("--reference")
    parser.add_argument("--modes", type=int, default=MODES)
    parser.add_argument("--reg", type=float, default=REG)
    args = parser.parse_args()
    stem, report = reconstruct(args.damaged, args.reference, args.modes, args.reg)
    print(f"{stem} -> {OUT / stem}.ply")
    for key, value in report.items():
        print(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
