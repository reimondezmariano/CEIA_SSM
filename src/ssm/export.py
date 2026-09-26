"""Turn raw hemipelvis meshes and landmark CSVs into the aligned set the model trains on.

    python -m ssm.export --landmarks RAW_LANDMARKS(.csv|dir) --meshes RAW_MESH_DIR [--mapping case_mapping_log.csv] [--out DIR]

The raw files come from the automatic segmenter, in scanner coordinates and named
with the original case id (SA250167). For each row of the landmark CSV this finds the
patient's left and right STL, computes the anterior pelvic plane (APP) frame from
ASIS_L, ASIS_R, PT_L and PT_R, applies that rigid transform to every landmark and to
both meshes, renames the case with the pseudonym from the mapping file (TMR_000004),
and writes

    OUT/meshes/<new id>_..._pelvis_<left|right>_aligned.stl
    OUT/landmarks/<new id>_landmarks_aligned.csv
    OUT/export_log.csv, OUT/export_run.json

The frame reproduces the existing aligned set to 3e-14 mm (Pipeline SSM/docs/09).
Nothing is scaled: sizes stay in mm. Checks never reject a case, they mark it
`review` in the log so someone looks at the source: the landmarks are automatic, and
four of them decide the whole alignment. A patient without all four is `skipped`.

Only numpy, scipy, pandas and trimesh are needed, so this can run where the raw data live.
"""

import argparse
import csv
import hashlib
import json
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import trimesh
from scipy.spatial import cKDTree

from .manifest import DATA

FRAME_LANDMARKS = ("ASIS_L", "ASIS_R", "PT_L", "PT_R")

# Ranges seen in the 48 subjects of the first training set (Pipeline SSM/docs/09): a value
# outside is worth a look, not proof of an error.
DISTANCE_WINDOWS_MM = {
    "ASIS-ASIS": (190.0, 282.0),
    "PT-PT": (37.0, 73.0),
    "ASIS mid-PT mid": (68.0, 114.0),
    "FH-ASIS": (62.0, 114.0),
}
# Same limits as ssm.check, which stays the check on the prepared meshes.
SURFACE_LANDMARK_MAX_MM = 8.0
FH_WINDOW_MM = (15.0, 35.0)
SURFACE_SAMPLES = 100_000


def app_frame(asis_l, asis_r, pt_l, pt_r):
    """Rotation (rows are the new x, y, z axes) and origin of the APP frame.

    Origin is the centroid of the four points; x runs from ASIS_R to ASIS_L; z is the
    part of (ASIS midpoint - PT midpoint) perpendicular to x, so it points up inside
    the plane through both ASIS and the pubic midpoint; y = z × x points backwards.
    aligned = (point - origin) @ rotation.T is a proper rotation (det +1): a left
    hemipelvis becomes a right one by x -> -x.
    """
    asis_l, asis_r, pt_l, pt_r = (np.asarray(p, float) for p in (asis_l, asis_r, pt_l, pt_r))
    if not np.isfinite(np.concatenate([asis_l, asis_r, pt_l, pt_r])).all():
        raise ValueError("a frame landmark is missing")
    x = asis_l - asis_r
    if np.linalg.norm(x) < 1.0:
        raise ValueError("ASIS_L and ASIS_R coincide")
    x = x / np.linalg.norm(x)
    up = (asis_l + asis_r) / 2 - (pt_l + pt_r) / 2
    up = up - (up @ x) * x
    if np.linalg.norm(up) < 1.0:
        raise ValueError("ASIS and PT are collinear with the ASIS axis")
    z = up / np.linalg.norm(up)
    rotation = np.vstack([x, np.cross(z, x), z])
    return rotation, np.mean([asis_l, asis_r, pt_l, pt_r], axis=0)


def apply_frame(points, rotation, origin):
    return (np.asarray(points, float) - origin) @ rotation.T


def landmark_names(columns):
    """Landmarks with all three of <name>_x, <name>_y, <name>_z in the file."""
    names = {c[:-2] for c in columns if c.endswith("_x")}
    return [n for n in names if all(f"{n}_{a}" in columns for a in "xyz")]


def point(row, name):
    return np.array([row[f"{name}_{a}"] for a in "xyz"], float)


def align_row(row):
    """The row with every landmark in the APP frame; raises ValueError if it cannot be aligned."""
    rotation, origin = app_frame(*(point(row, n) for n in FRAME_LANDMARKS))
    aligned = row.copy()
    for name in landmark_names(row.index):
        p = point(row, name)
        if np.isfinite(p).all():
            aligned[[f"{name}_{a}" for a in "xyz"]] = apply_frame(p, rotation, origin)
    return aligned, rotation, origin


def landmark_flags(aligned):
    """Reasons to look at the landmarks of one aligned patient."""
    flags = []
    p = lambda n: point(aligned, n)
    checks = [
        ("ASIS-ASIS", "ASIS-ASIS", np.linalg.norm(p("ASIS_L") - p("ASIS_R"))),
        ("PT-PT", "PT-PT", np.linalg.norm(p("PT_L") - p("PT_R"))),
        ("ASIS mid-PT mid", "ASIS mid-PT mid",
         np.linalg.norm((p("ASIS_L") + p("ASIS_R")) / 2 - (p("PT_L") + p("PT_R")) / 2)),
    ]
    for side in "LR":
        if f"FH_{side}_x" in aligned.index and np.isfinite(p(f"FH_{side}")).all():
            checks.append((f"FH_{side}-ASIS_{side}", "FH-ASIS", np.linalg.norm(p(f"FH_{side}") - p(f"ASIS_{side}"))))
    for label, window, value in checks:
        low, high = DISTANCE_WINDOWS_MM[window]
        if not low <= value <= high:
            flags.append(f"{label} {value:.0f} mm outside {low:.0f}-{high:.0f}")
    return flags


def mesh_flags(mesh, side, aligned_row):
    """Reasons to look at one aligned hemipelvis: side, closure, landmarks off the surface."""
    flags = []
    x = mesh.vertices[:, 0].mean()
    if (side == "R") != (x < 0):
        flags.append(f"{side} side has mean x {x:+.0f} mm")
    if not mesh.is_watertight:
        flags.append("not watertight")
    surface = cKDTree(trimesh.sample.sample_surface(mesh, SURFACE_SAMPLES, seed=0)[0])
    for name in ("ASIS", "PSIS", "PT", "FH"):
        column = f"{name}_{side}_x"
        if column not in aligned_row.index:
            continue
        p = point(aligned_row, f"{name}_{side}")
        if not np.isfinite(p).all():
            continue
        d = surface.query(p)[0]
        if name == "FH":
            if not FH_WINDOW_MM[0] <= d <= FH_WINDOW_MM[1]:
                flags.append(f"FH {d:.0f} mm from the surface, expected {FH_WINDOW_MM[0]:.0f}-{FH_WINDOW_MM[1]:.0f}")
        elif d > SURFACE_LANDMARK_MAX_MM:
            flags.append(f"{name} {d:.0f} mm from the surface")
    return flags


def find_meshes(mesh_dir, original):
    """{'L': [paths], 'R': [paths]} for the STL files that start with the original id."""
    found = {"L": [], "R": []}
    for path in sorted(Path(mesh_dir).glob(f"{original}*.stl")):
        match = re.search(r"pelvis_(left|right)", path.name)
        if match:
            found[match.group(1)[0].upper()].append(path)
    return found


def output_name(path, original, new):
    stem = path.stem.replace(original, new, 1)
    return stem if stem.endswith("_aligned") else f"{stem}_aligned"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_landmarks(source):
    source = Path(source)
    files = sorted(source.glob("*.csv")) if source.is_dir() else [source]
    if not files:
        raise SystemExit(f"no landmark CSV in {source}")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def read_mapping(path):
    return dict(pd.read_csv(path)[["original_case_id", "new_case_id"]].itertuples(index=False))


def plan(landmarks, mesh_dir, mapping, out):
    """Every file the run would write, so that nothing is overwritten by accident."""
    targets = []
    for _, row in landmarks.iterrows():
        original = str(row["case_id"])
        new = mapping.get(original)
        if new is None:
            continue
        targets.append(out / "landmarks" / f"{new}_landmarks_aligned.csv")
        for side, paths in find_meshes(mesh_dir, original).items():
            if len(paths) == 1:
                targets.append(out / "meshes" / f"{output_name(paths[0], original, new)}.stl")
    return targets


def export_patient(row, mesh_dir, mapping, out):
    """Log rows for one patient (one for the landmarks, one per mesh)."""
    original = str(row["case_id"])
    new = mapping.get(original)
    log = lambda item, status, flags=(), source="", output="": {
        "original_id": original, "new_id": new or "", "item": item, "status": status,
        "flags": "; ".join(flags), "source": str(source), "output": str(output),
        "sha256": sha256(output) if output else "",
    }
    if new is None:
        return [log("patient", "skipped", ["not in the mapping file"])]
    try:
        aligned, rotation, origin = align_row(row)
    except ValueError as error:
        return [log("patient", "skipped", [str(error)])]

    (out / "landmarks").mkdir(parents=True, exist_ok=True)
    (out / "meshes").mkdir(parents=True, exist_ok=True)
    flags = landmark_flags(aligned)
    landmark_file = out / "landmarks" / f"{new}_landmarks_aligned.csv"
    aligned.to_frame().T.to_csv(landmark_file, index=False)
    rows = [log("landmarks", "review" if flags else "ok", flags, output=landmark_file)]

    for side, paths in find_meshes(mesh_dir, original).items():
        if not paths:
            continue
        if len(paths) > 1:
            rows.append(log(f"mesh {side}", "skipped", [f"{len(paths)} candidate files"], source=paths[0]))
            continue
        mesh = trimesh.load(paths[0])  # merges duplicate vertices, so watertight is meaningful
        mesh.vertices = apply_frame(mesh.vertices, rotation, origin)
        flags = mesh_flags(mesh, side, aligned)
        target = out / "meshes" / f"{output_name(paths[0], original, new)}.stl"
        mesh.export(target)
        rows.append(log(f"mesh {side}", "review" if flags else "ok", flags, source=paths[0], output=target))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--landmarks", required=True, help="raw landmark CSV, or a folder of them")
    parser.add_argument("--meshes", required=True, help="folder with the raw STL files")
    parser.add_argument("--mapping", default=str(DATA / "case_mapping_log.csv"),
                        help="CSV with original_case_id,new_case_id (default: %(default)s)")
    parser.add_argument("--out", default=str(DATA / "export"), help="output folder (default: %(default)s)")
    parser.add_argument("--overwrite", action="store_true", help="replace files that already exist")
    args = parser.parse_args(argv)

    out = Path(args.out)
    landmarks = read_landmarks(args.landmarks)
    mapping = read_mapping(args.mapping)
    existing = [t for t in plan(landmarks, args.meshes, mapping, out) if t.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"{len(existing)} output files already exist (first: {existing[0]}); use --overwrite")

    rows = []
    for _, row in landmarks.iterrows():
        rows.extend(export_patient(row, args.meshes, mapping, out))

    out.mkdir(parents=True, exist_ok=True)
    with (out / "export_log.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "export_run.json").write_text(json.dumps({
        "time": datetime.now().isoformat(timespec="seconds"),
        "arguments": vars(args),
        "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__,
        "trimesh": trimesh.__version__,
    }, indent=2))

    counts = pd.Series([r["status"] for r in rows]).value_counts().to_dict()
    print(f"{len(landmarks)} patients, {len(rows)} items: {counts} -> {out}")
    for r in rows:
        if r["status"] != "ok":
            print(f"  {r['status']:7s} {r['original_id']} {r['item']}: {r['flags']}")


if __name__ == "__main__":
    main()
