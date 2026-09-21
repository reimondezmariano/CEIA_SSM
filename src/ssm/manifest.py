import csv
import re
from pathlib import Path

import numpy as np
import pandas as pd

HOME = Path.home()
MESH_DIR = HOME / "DataSet"
LANDMARK_DIR = HOME / "Landmarks_aligned"
OUT = HOME / "SSM" / "data" / "manifest.csv"

# GT and LT are femoral, Coccyx is midline: none lie on the hemipelvis surface.
LANDMARKS = ("ASIS", "PSIS", "PT", "FH")
SIDE = "R"


def landmark_flags(path):
    if not path.exists():
        return {n: False for n in LANDMARKS}
    row = pd.read_csv(path).iloc[0]
    return {
        n: bool(np.isfinite([row[f"{n}_{SIDE}_{a}"] for a in "xyz"]).all())
        for n in LANDMARKS
    }


def build():
    rows = []
    for mesh in sorted(MESH_DIR.glob("*.stl")):
        subject = re.match(r"(TMR_\d+)", mesh.name).group(1)
        lm = LANDMARK_DIR / f"{subject}_landmarks_aligned.csv"
        flags = landmark_flags(lm)
        rows.append(
            {
                "subject": subject,
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
    print(f"{len(rows)} subjects -> {OUT}")


if __name__ == "__main__":
    main()
