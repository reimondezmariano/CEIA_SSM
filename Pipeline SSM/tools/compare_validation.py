"""Compare validation runs on the shapes they share.

    python "Pipeline SSM/tools/compare_validation.py" [--side R|L] [--modes 34] [--reg 10] BASE.csv OTHER.csv ...

Each CSV comes from `python -m ssm.validate`. The defect error of a shape is its
mean over every simulated defect (site and radius); only shapes present in every
file, on the chosen side, are compared. Each other run is reported against the
first (BASE) as a paired difference with its standard error over shapes, and as
the number of shapes that got better or worse. A difference under about twice its
standard error is not distinguishable from noise with this many shapes.
"""

import argparse

import numpy as np
import pandas as pd


def per_shape(path, side, modes, reg):
    df = pd.read_csv(path)
    if "shape" not in df:  # early right-only runs named the rows by patient
        df["shape"] = df["subject"] + "_R"
    df = df[(df.site != "none") & (df.modes == modes) & (df.reg == reg) & df["shape"].str.endswith(f"_{side}")]
    return df.groupby("shape")["defect_mean"].mean()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", nargs="+")
    parser.add_argument("--side", default="R", choices=["R", "L"])
    parser.add_argument("--modes", type=int, default=34)
    parser.add_argument("--reg", type=float, default=10.0)
    args = parser.parse_args()

    runs = {p: per_shape(p, args.side, args.modes, args.reg) for p in args.csv}
    empty = [p for p, v in runs.items() if v.empty]
    if empty:
        raise SystemExit(f"no {args.side} shapes at K={args.modes}, reg={args.reg:g} in: {', '.join(empty)}")
    common = sorted(set.intersection(*[set(v.index) for v in runs.values()]))
    if len(common) < 2:
        raise SystemExit(f"only {len(common)} shapes in common")
    print(f"K={args.modes}, reg {args.reg:g}, side {args.side}: mean defect error (mm) on {len(common)} common shapes")
    base = runs[args.csv[0]][common]
    for path, v in runs.items():
        v = v[common]
        line = f"  {v.mean():.3f}  {path}"
        if path != args.csv[0]:
            diff = v - base
            se = diff.std(ddof=1) / np.sqrt(len(common))
            line += f"   vs base {diff.mean():+.3f} +- {se:.3f}; better on {(diff < 0).sum()}, worse on {(diff > 0).sum()}"
        print(line)


if __name__ == "__main__":
    main()
