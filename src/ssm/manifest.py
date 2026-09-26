import csv
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

HOME = Path.home()
# Where the exported meshes and landmarks live, and where every generated file goes.
# Override them to run the pipeline on another training set without touching this one.
MESH_DIR = Path(os.environ.get("SSM_MESH_DIR", HOME / "DataSet"))
LANDMARK_DIR = Path(os.environ.get("SSM_LANDMARK_DIR", HOME / "Landmarks_aligned"))
DATA = Path(os.environ.get("SSM_DATA", HOME / "SSM" / "data"))
OUT = DATA / "manifest.csv"

# GT and LT are femoral, Coccyx is midline: none lie on the hemipelvis surface.
LANDMARKS = ("ASIS", "PSIS", "PT", "FH")


def side_of(path):
    """'L' or 'R', from the pelvis_left/pelvis_right part of the file name."""
    return re.search(r"pelvis_(left|right)", Path(path).name).group(1)[0].upper()


def landmark_flags(path, side):
    if not path.exists():
        return {n: False for n in LANDMARKS}
    row = pd.read_csv(path).iloc[0]
    return {
        n: bool(np.isfinite([row[f"{n}_{side}_{a}"] for a in "xyz"]).all())
        for n in LANDMARKS
    }


def build():
    rows = []
    for mesh in sorted(MESH_DIR.glob("*.stl")):
        subject = re.match(r"([A-Za-z]+_\d+)", mesh.name).group(1)
        side = side_of(mesh)
        lm = LANDMARK_DIR / f"{subject}_landmarks_aligned.csv"
        flags = landmark_flags(lm, side)
        rows.append(
            {
                "shape": f"{subject}_{side}",
                "subject": subject,
                "side": side,
                "mesh": str(mesh),
                "landmarks": str(lm) if lm.exists() else "",
                **{f"has_{n}": flags[n] for n in LANDMARKS},
                "n_landmarks": sum(flags.values()),
            }
        )
    return rows


def main():
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} shapes of {len({r['subject'] for r in rows})} subjects -> {OUT}")


if __name__ == "__main__":
    main()
