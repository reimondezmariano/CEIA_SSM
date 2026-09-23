"""Simulated bone defects on intact meshes, for validating reconstruction.

A defect removes the bone within RADIUS of the surface point nearest an
anatomical landmark and caps the opening, as the real damaged meshes are
capped where the bone is missing.
"""

import csv

import numpy as np
import pandas as pd
import pyvista as pv
from scipy.spatial import cKDTree

from .manifest import LANDMARKS, SIDE
from .manifest import OUT as MANIFEST

RADII_MM = (20, 30, 40)
CAP_MAX_SIZE = 1e6  # fill every hole the cut leaves


def landmarks(subject):
    with MANIFEST.open() as f:
        row = next(r for r in csv.DictReader(f) if r["subject"] == subject)
    if not row["landmarks"]:
        return {}
    values = pd.read_csv(row["landmarks"]).iloc[0]
    points = {n: np.array([values[f"{n}_{SIDE}_{a}"] for a in "xyz"], dtype=float) for n in LANDMARKS}
    return {n: p for n, p in points.items() if np.isfinite(p).all()}


def centre(mesh, landmark):
    return mesh.points[cKDTree(mesh.points).query(landmark)[1]]


def cut(mesh, centre, radius):
    keep = np.linalg.norm(mesh.points - centre, axis=1) >= radius
    remaining = mesh.extract_points(keep, adjacent_cells=False).extract_surface()
    return remaining.fill_holes(CAP_MAX_SIZE).clean()
