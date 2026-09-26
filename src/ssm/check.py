"""Checks on the exported meshes and landmarks, run before anything is trained.

    python -m ssm.check

Writes check.csv next to the manifest and prints every shape with a flag. A flag
is a reason to look at the source mesh, not a verdict: the report cannot tell a
faulty export from an unusual bone, so excluding a shape stays a decision for
whoever knows the case (see ssm.project.EXCLUDE).

  side_ok        the mesh lies on the x side its file name says (right < 0), which
                 catches a mislabelled or unaligned export
  watertight     the raw mesh is a closed surface
  shells         connected pieces in the raw mesh; second_shell_fraction is the
                 share of faces in the second largest, and >= 0.1 is a severed bone
                 that ssm.clean skips
  landmark_mm    distance from each landmark to the groomed surface. ASIS, PSIS and
                 PT are on the bone; FH is the femoral head centre, about one
                 acetabular radius (~24 mm) away, so it has its own window
  lr_volume_ratio  left / right volume of the patient (repeated on both rows); 0.8
                 to 1.4 was seen, and dropping the extremes did not improve the model
"""

import csv

import numpy as np
import pyvista as pv
import trimesh
from scipy.spatial import cKDTree

from . import defects
from .clean import SEVERED_SHELL_FRACTION, GROOMED
from .manifest import LANDMARKS, OUT as MANIFEST

REPORT = MANIFEST.with_name("check.csv")

SURFACE_LANDMARK_MAX_MM = 8.0
FH_WINDOW_MM = (15.0, 35.0)


def raw_report(path, side):
    mesh = trimesh.load(path)
    shells = sorted(len(s.faces) for s in mesh.split(only_watertight=False))
    x = mesh.vertices[:, 0].mean()
    return {
        "watertight": bool(mesh.is_watertight),
        "shells": len(shells),
        "second_shell_fraction": shells[-2] / sum(shells) if len(shells) > 1 else 0.0,
        "raw_volume_cm3": abs(mesh.volume) / 1e3 if mesh.is_watertight else np.nan,
        "side_ok": bool(x < 0 if side == "R" else x > 0),
    }


def landmark_report(shape):
    groomed = GROOMED / f"{shape}.ply"
    if not groomed.exists():
        return {}
    tree = cKDTree(pv.read(str(groomed)).points)
    return {f"{n}_mm": float(tree.query(p)[0]) for n, p in defects.landmarks(shape).items()}


def flags(row):
    found = []
    if not row["side_ok"]:
        found.append("side does not match its x side")
    if row["second_shell_fraction"] >= SEVERED_SHELL_FRACTION:
        found.append("severed into pieces")
    elif row["shells"] > 1:
        found.append(f"{row['shells']} shells")
    if row["landmarks"] == "":
        found.append("no landmark file")
    for n in LANDMARKS:
        d = row.get(f"{n}_mm")
        if d is None or np.isnan(d):
            continue
        if n == "FH" and not FH_WINDOW_MM[0] <= d <= FH_WINDOW_MM[1]:
            found.append(f"FH {d:.0f} mm from the surface")
        if n != "FH" and d > SURFACE_LANDMARK_MAX_MM:
            found.append(f"{n} {d:.0f} mm from the surface")
    if row["groomed"] is False:
        found.append("no groomed mesh (run ssm.clean)")
    return found


def main():
    with MANIFEST.open() as f:
        shapes = list(csv.DictReader(f))
    rows = []
    for s in shapes:
        row = {"shape": s["shape"], "landmarks": s["landmarks"], **raw_report(s["mesh"], s["side"])}
        row["groomed"] = (GROOMED / f"{s['shape']}.ply").exists()
        row |= landmark_report(s["shape"])
        if row["groomed"]:
            row["groomed_volume_cm3"] = pv.read(str(GROOMED / f"{s['shape']}.ply")).extract_surface().triangulate().volume / 1e3
        rows.append(row)

    volume = {r["shape"]: r.get("groomed_volume_cm3", np.nan) for r in rows}
    for r in rows:
        patient = r["shape"].rsplit("_", 1)[0]
        left, right = volume.get(f"{patient}_L", np.nan), volume.get(f"{patient}_R", np.nan)
        r["lr_volume_ratio"] = left / right
        r["flags"] = "; ".join(flags(r))

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with REPORT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    flagged = [r for r in rows if r["flags"]]
    print(f"{len(rows)} shapes, {len(flagged)} with a flag -> {REPORT}")
    for r in flagged:
        print(f"  {r['shape']}: {r['flags']}")
    ratios = np.array([r["lr_volume_ratio"] for r in rows if r["shape"].endswith("_L")])
    ratios = ratios[np.isfinite(ratios)]
    if len(ratios):
        print(f"L/R volume ratio over {len(ratios)} patients: min {ratios.min():.2f}, median {np.median(ratios):.2f}, max {ratios.max():.2f}")


if __name__ == "__main__":
    main()
