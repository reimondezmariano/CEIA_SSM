"""Held-out patient against leave-one-patient-out, shape by shape.

    python "Pipeline SSM/tools/holdout_report.py" HOLDOUT.csv LOPO.csv [LOPO2.csv ...] [--modes 34] [--reg 10]

HOLDOUT.csv comes from `ssm.validate --eval-shapes` on a model built without those patients
(SSM_HOLDOUT). Each LOPO.csv comes from a normal `ssm.validate` on the full model; the file
that contains a shape is used for it. For every held-out shape it prints the mean defect error
of both estimates, where the held-out value falls among the leave-one-out errors of all
shapes in that file, and the error by defect site and radius.

With one or two patients this is a plausibility check on the leave-one-out figures, not an
estimate of the model's error: the defects of a shape are strongly correlated and a single
patient can be easier or harder than most (compare with the percentile).
"""

import argparse

import pandas as pd


def defects(df, modes, reg):
    return df[(df.site != "none") & (df.modes == modes) & (df.reg == reg)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("holdout")
    parser.add_argument("lopo", nargs="+")
    parser.add_argument("--modes", type=int, default=34)
    parser.add_argument("--reg", type=float, default=10.0)
    args = parser.parse_args()

    held = pd.read_csv(args.holdout)
    lopo = {p: pd.read_csv(p) for p in args.lopo}
    for shape in sorted(held["shape"].unique()):
        source = next((p for p, df in lopo.items() if shape in set(df["shape"])), None)
        if source is None:
            print(f"{shape}: not in any leave-one-out file")
            continue
        h = defects(held[held["shape"] == shape], args.modes, args.reg)
        every = defects(lopo[source], args.modes, args.reg)
        l = every[every["shape"] == shape]
        per_shape = every.groupby("shape")["defect_mean"].mean()
        percentile = 100 * (per_shape < h["defect_mean"].mean()).mean()
        print(f"\n{shape}: held-out {h['defect_mean'].mean():.2f} mm   leave-one-out {l['defect_mean'].mean():.2f} mm   ({len(h)} defects)")
        print(f"  among {len(per_shape)} shapes of {source}: median {per_shape.median():.2f}, "
              f"10th-90th percentile {per_shape.quantile(.1):.2f}-{per_shape.quantile(.9):.2f}; "
              f"the held-out value is at percentile {percentile:.0f}")
        table = h.merge(l, on=["shape", "site", "radius"], suffixes=("_heldout", "_loo"))
        print(table.pivot_table(index="site", columns="radius", values=["defect_mean_heldout", "defect_mean_loo"]).round(2).to_string())


if __name__ == "__main__":
    main()
