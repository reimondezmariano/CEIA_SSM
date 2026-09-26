"""Leave-one-out validation of reconstruction on simulated defects.

Each shape is held out of the model in turn, together with the other side of
the same patient (a near mirror image, which would otherwise leak into the
model), a defect is cut at each landmark site and radius, and the model is
fitted to what remains. Error is
the distance from the true surface to the reconstruction, inside the defect
and over the whole bone. K = 0 is the rigidly fitted mean shape, the baseline
any reconstruction must beat. The held-out subject still took part in the
particle optimization, so errors are slightly optimistic.
"""

import csv
import os
import sys
from multiprocessing import Pool

# One thread per worker. Otherwise each worker's BLAS and VTK open a thread per
# CPU and the pool spins ~60 runnable threads on 8 CPUs, about 10x slower. Must
# be set before numpy and vtk load.
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VTK_SMP_MAX_THREADS"):
    os.environ.setdefault(var, "1")


import numpy as np
import pyvista as pv

from . import defects, fit, model
from .clean import GROOMED
from .project import PROJECT_DIR

OUT = PROJECT_DIR.parent / "reconstruction" / "validation.csv"

CONFIGS = [(0, 0.0)] + [(k, reg) for k in (5, 10, 20, 34, 50) for reg in (1.0, 10.0)]
# --reduced: the two settings that matter for comparing models, a fifth of the cost.
REDUCED_CONFIGS = [(34, 10.0), (50, 10.0)]


def distance(points, surface):
    return np.abs(pv.PolyData(points).compute_implicit_distance(surface)["implicit_distance"])


def cases(mesh, name):
    yield "none", 0, mesh, None
    for site, landmark in defects.landmarks(name).items():
        centre = defects.centre(mesh, landmark)
        for radius in defects.RADII_MM:
            yield site, radius, defects.cut(mesh, centre, radius), centre


def patient(shape):
    return shape.rsplit("_", 1)[0]


def run_subject(args):
    name, names, world = args
    keep = [patient(n) != patient(name) for n in names]
    held_out = model.build(world[keep])
    mean_surface = fit.load_mean_surface()
    truth = pv.read(str(GROOMED / f"{name}.ply")).extract_surface().triangulate()
    rows = []
    for site, radius, target, centre in cases(truth, name):
        points, normals = fit.surface_points(target)
        region = (np.linalg.norm(truth.points - centre, axis=1) < radius) if centre is not None else None
        for k, reg in CONFIGS:
            result = fit.fit(held_out, mean_surface.particle_normals, points, normals, min(k, len(held_out.sd)), reg)
            error = distance(truth.points, fit.dense_surface(mean_surface, result, held_out))
            row = {"shape": name, "site": site, "radius": radius, "modes": k, "reg": reg,
                   "bone_mean": error.mean(), "bone_p95": np.percentile(error, 95)}
            if region is not None:
                row |= {"defect_mean": error[region].mean(), "defect_p95": np.percentile(error[region], 95),
                        "defect_max": error[region].max()}
            rows.append(row)
    return rows


def summarize(rows):
    def table(select, metric):
        groups = {}
        for r in rows:
            if select(r):
                groups.setdefault((r["modes"], r["reg"]), []).append(r[metric])
        return {key: float(np.median(v)) for key, v in groups.items()}

    print("No defect, whole-bone error (median over subjects, mm):")
    for (k, reg), v in table(lambda r: r["site"] == "none", "bone_mean").items():
        print(f"  K={k:2d} reg={reg:4.1f}: {v:.2f}")
    print("Defect-region mean error (median over subjects, mm), by site and radius:")
    keys = sorted({(r["site"], r["radius"]) for r in rows if r["site"] != "none"})
    print("  config        " + " ".join(f"{s}{rad:>3}" .rjust(8) for s, rad in keys))
    for k, reg in CONFIGS:
        cells = [table(lambda r, s=s, rad=rad: (r["site"], r["radius"]) == (s, rad), "defect_mean")[(k, reg)]
                 for s, rad in keys]
        print(f"  K={k:2d} reg={reg:4.1f} " + " ".join(f"{c:8.2f}" for c in cells))


def main():
    names, world = model.load_world()
    global CONFIGS, OUT
    tag = PROJECT_DIR.name.removeprefix("shapeworks_project").strip("_")
    parts = ["validation"]
    if "--reduced" in sys.argv:
        CONFIGS = REDUCED_CONFIGS
        parts.append("reduced")
    if "--sides" in sys.argv:
        # Train the PCA on, and evaluate, only these sides of the optimized particles.
        sides = sys.argv[sys.argv.index("--sides") + 1]
        keep = [n[-1] in sides for n in names]
        names, world = [n for n, k in zip(names, keep) if k], world[keep]
        parts.append(f"sides{sides}")
    if tag:
        parts.append(tag)
    OUT = OUT.with_name("_".join(parts) + ".csv")
    rows = []
    with Pool() as pool:
        for done, subject in enumerate(pool.imap_unordered(run_subject, [(n, names, world) for n in names]), 1):
            rows.extend(subject)
            print(f"{done}/{len(names)} {subject[0]['shape']}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} fits over {len(names)} shapes -> {OUT}")
    summarize(rows)


if __name__ == "__main__":
    main()
