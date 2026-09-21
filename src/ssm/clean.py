import csv
from pathlib import Path

import shapeworks as sw
import trimesh

from .manifest import OUT as MANIFEST

GROOMED = Path.home() / "SSM" / "data" / "groomed"

N_VERTICES = 25000
ADAPTIVITY = 0.0
SMOOTH_ITERATIONS = 10
SMOOTH_PASSBAND = 0.05

# Bridges a surface split into disjoint pieces by a segmentation cut plane.
# The radius must exceed half the gap width; finer spacing costs cubically
# and already runs to ~15 min per transform here.
CLOSING_RADIUS_MM = 1.5
CLOSING_SPACING = [0.8, 0.8, 0.8]
CLOSING_PADDING = [6, 6, 6]

# A shell this large relative to the whole is a severed piece of the bone,
# not debris, so dropping it would discard real anatomy.
SEVERED_SHELL_FRACTION = 0.1


def second_shell_fraction(mesh):
    shells = trimesh.Trimesh(
        vertices=mesh.points(), faces=mesh.faces(), process=True
    ).split(only_watertight=False)
    if len(shells) < 2:
        return 0.0
    sizes = sorted(len(s.faces) for s in shells)
    return sizes[-2] / sum(sizes)


def close_gaps(mesh, radius=CLOSING_RADIUS_MM):
    # ShapeWorks distance transforms are positive inside, so a negative
    # isovalue dilates and a positive one erodes. Reversing these two calls
    # yields an opening, which severs the smaller piece instead of joining it.
    dilated = mesh.toDistanceTransform(
        spacing=CLOSING_SPACING, padding=CLOSING_PADDING
    ).toMesh(-radius)
    return dilated.toDistanceTransform(
        spacing=CLOSING_SPACING, padding=CLOSING_PADDING
    ).toMesh(radius)


def clean(path, n_vertices=N_VERTICES):
    mesh = sw.Mesh(str(path))
    severed = second_shell_fraction(mesh) >= SEVERED_SHELL_FRACTION
    if severed:
        mesh = close_gaps(mesh)
    mesh.extractLargestComponent()
    mesh.fillHoles()
    mesh.smoothSinc(iterations=SMOOTH_ITERATIONS, passband=SMOOTH_PASSBAND)
    mesh.remesh(numVertices=n_vertices, adaptivity=ADAPTIVITY)
    return mesh, severed


def main():
    GROOMED.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open() as f:
        subjects = list(csv.DictReader(f))
    for row in subjects:
        out = GROOMED / f"{row['subject']}.ply"
        mesh, severed = clean(row["mesh"])
        mesh.write(str(out))
        note = " (closed severed shells)" if severed else ""
        print(f"{row['subject']} -> {out.name}{note}")
    print(f"{len(subjects)} meshes -> {GROOMED}")


if __name__ == "__main__":
    main()
