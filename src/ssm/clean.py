import csv

import shapeworks as sw
import trimesh

from .manifest import DATA
from .manifest import OUT as MANIFEST

GROOMED = DATA / "groomed"

N_VERTICES = 25000
ADAPTIVITY = 0.0
SMOOTH_ITERATIONS = 10
SMOOTH_PASSBAND = 0.05

# A shell this large relative to the whole is a severed piece of the bone,
# not debris, so keeping only the largest would silently discard real anatomy.
# Such a subject is excluded rather than repaired: rejoining it needs a voxel
# closing that costs ~25 min and quantizes the whole surface.
SEVERED_SHELL_FRACTION = 0.1


def second_shell_fraction(mesh):
    shells = trimesh.Trimesh(
        vertices=mesh.points(), faces=mesh.faces(), process=True
    ).split(only_watertight=False)
    if len(shells) < 2:
        return 0.0
    sizes = sorted(len(s.faces) for s in shells)
    return sizes[-2] / sum(sizes)


def clean(path, side="R", n_vertices=N_VERTICES):
    """Groomed mesh in the model's right-sided frame: a left side is mirrored
    x -> -x in the aligned pelvic frame (reflect also fixes the winding)."""
    mesh = sw.Mesh(str(path))
    if side == "L":
        mesh.reflect(sw.Axis.X)
    if second_shell_fraction(mesh) >= SEVERED_SHELL_FRACTION:
        return None
    mesh.extractLargestComponent()
    mesh.fillHoles()
    mesh.smoothSinc(iterations=SMOOTH_ITERATIONS, passband=SMOOTH_PASSBAND)
    mesh.remesh(numVertices=n_vertices, adaptivity=ADAPTIVITY)
    return mesh


def main():
    GROOMED.mkdir(parents=True, exist_ok=True)
    for stale in GROOMED.glob("*.ply"):
        stale.unlink()
    with MANIFEST.open() as f:
        subjects = list(csv.DictReader(f))
    written = 0
    for row in subjects:
        mesh = clean(row["mesh"], row["side"])
        if mesh is None:
            print(f"{row['shape']}: skipped, mesh is severed into pieces")
            continue
        out = GROOMED / f"{row['shape']}.ply"
        mesh.write(str(out))
        written += 1
        print(f"{row['shape']} -> {out.name}")
    print(f"{written}/{len(subjects)} meshes -> {GROOMED}")


if __name__ == "__main__":
    main()
