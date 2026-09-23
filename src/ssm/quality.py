"""Correspondence quality of an optimized project.

coverage: fraction of the groomed surface with a particle within COVER_MM.
    Low coverage means particles bunched on part of the bone.
roughness: median over particles of how differently a particle moves from
    its nearest neighbours, for a subject's offset from the mean
    (per subject) or for a mode at +3 SD (per mode). Correspondence swaps
    show up as neighbours moving in different directions, even when
    coverage is fine; smooth anatomical variation keeps it low.
"""

import sys
from pathlib import Path

import numpy as np
import shapeworks as sw
from scipy.spatial import cKDTree

from .clean import GROOMED

COVER_MM = 10.0
NEIGHBOURS = 6
MODES = 3


def roughness(displacement, neighbours):
    return np.linalg.norm(displacement[:, None] - displacement[neighbours], axis=2).mean(1)


def evaluate(project_dir):
    particles = Path(project_dir) / "pelvis_particles"
    names = sorted(p.name.removesuffix("_world.particles") for p in particles.glob("*_world.particles"))
    world = np.stack([np.loadtxt(particles / f"{n}_world.particles") for n in names])
    mean = world.mean(0)
    neighbours = cKDTree(mean).query(mean, k=NEIGHBOURS + 1)[1][:, 1:]

    subjects = []
    for name, w in zip(names, world):
        surface = sw.Mesh(str(GROOMED / f"{name}.ply")).points()
        local = np.loadtxt(particles / f"{name}_local.particles")
        subjects.append({
            "subject": name,
            "coverage": float((cKDTree(local).query(surface)[0] < COVER_MM).mean()),
            "roughness": float(np.median(roughness(w - mean, neighbours))),
        })

    flat = world.reshape(len(world), -1)
    _, s, vt = np.linalg.svd(flat - flat.mean(0), full_matrices=False)
    variance = s**2 / (s**2).sum()
    modes = []
    for k in range(MODES):
        d = (3 * s[k] / np.sqrt(len(world) - 1) * vt[k]).reshape(-1, 3)
        r = roughness(d, neighbours)
        modes.append({"mode": k + 1, "variance": float(variance[k]),
                      "roughness": float(np.median(r)), "rough_particles": int((r > 15).sum())})
    return subjects, modes


def main(project_dir):
    subjects, modes = evaluate(project_dir)
    cov = np.array([s["coverage"] for s in subjects])
    rough = np.array([s["roughness"] for s in subjects])
    print(f"{len(subjects)} subjects: coverage min {cov.min():.2f} median {np.median(cov):.2f}; "
          f"roughness median {np.median(rough):.1f} max {rough.max():.1f} mm")
    flagged = [s for s in subjects if s["coverage"] < 0.85 or s["roughness"] > 2 * np.median(rough)]
    for s in flagged:
        print(f"  flagged {s['subject']}: coverage {s['coverage']:.2f}, roughness {s['roughness']:.1f} mm")
    for m in modes:
        print(f"  PC{m['mode']}: {100 * m['variance']:.1f}% variance, roughness {m['roughness']:.1f} mm, "
              f"{m['rough_particles']} particles > 15 mm")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "SSM" / "data" / "shapeworks_project")
