"""Fit the shape model to a surface that may be missing part of the bone.

The pose is rigid (rotation and translation, no scale) and the shape is
regularized towards the mean, so the missing region is filled with the most
plausible shape consistent with the bone that is present. Model particles
whose closest target point is far away or faces a different direction are
ignored: they sit over the missing region or over the cut surface that caps
it, neither of which is real bone.
"""

from dataclasses import dataclass

import numpy as np
import pyvista as pv
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree

from .project import PROJECT_DIR

MEAN_MESH = PROJECT_DIR / "mean_shape_0.vtk"
MEAN_PARTICLES = PROJECT_DIR / "mean_shape_0.pts"

MAX_DIST_MM = 10.0
MIN_NORMAL_COS = 0.5  # normals more than 60 degrees apart
TRIM = 0.9  # of the pairs that pass, keep the closest 90%
RIGID_ITERATIONS = 30
ITERATIONS = 100
TOL_MM = 1e-3
TPS_SMOOTHING = 1.0
# Also match target points to their nearest particle, so the model cannot
# slide along the bone while every particle still finds surface nearby.
SYMMETRIC = True
BACKWARD_SAMPLES = 3000


@dataclass
class Fit:
    b: np.ndarray  # coefficients, in standard deviations
    rotation: np.ndarray
    translation: np.ndarray
    particles: np.ndarray  # fitted particles in the target frame
    inliers: np.ndarray  # particles matched to the target surface
    rms: float  # over inliers, mm


@dataclass
class MeanSurface:
    mesh: pv.PolyData
    particles: np.ndarray
    particle_normals: np.ndarray


def load_mean_surface(mesh_path=MEAN_MESH, particles_path=MEAN_PARTICLES):
    mesh = pv.read(str(mesh_path)).extract_surface().triangulate().clean()
    mesh.clear_data()
    mesh = mesh.compute_normals(split_vertices=False, auto_orient_normals=True, cell_normals=False)
    particles = np.loadtxt(particles_path)
    nearest = cKDTree(mesh.points).query(particles)[1]
    return MeanSurface(mesh, particles, mesh.point_data["Normals"][nearest])


def surface_points(mesh):
    """Vertices and outward normals of a mesh, as the fit's target."""
    mesh = mesh.extract_surface().triangulate().clean()
    mesh = mesh.compute_normals(split_vertices=False, auto_orient_normals=True, cell_normals=False)
    return np.asarray(mesh.points), np.asarray(mesh.point_data["Normals"])


def kabsch(src, dst):
    """Rotation and translation taking src onto dst in the least-squares sense."""
    return weighted_kabsch(src, dst, np.ones(len(src)))


def weighted_kabsch(src, dst, w):
    w = w / w.sum()
    cs, cd = w @ src, w @ dst
    u, _, vt = np.linalg.svd((src - cs).T @ ((dst - cd) * w[:, None]))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1, 1, d]) @ u.T
    return rotation, cd - rotation @ cs


def fit(model, particle_normals, target_points, target_normals, n_modes, reg, symmetric=SYMMETRIC):
    tree = cKDTree(target_points)
    back = target_points[:: max(1, len(target_points) // BACKWARD_SAMPLES)]
    back_normals = target_normals[:: max(1, len(target_points) // BACKWARD_SAMPLES)]
    basis = (model.sd[:n_modes, None, None] * model.modes[:n_modes]).reshape(n_modes, model.mean.size).T
    b = np.zeros(n_modes)
    rotation = np.eye(3)
    translation = target_points.mean(0) - model.mean.mean(0)

    def trimmed(dist, agree, max_dist):
        ok = agree & (dist < max_dist)
        return ok & (dist <= np.quantile(dist[ok], TRIM))

    def match(particles, max_dist):
        moved = particles @ rotation.T + translation
        dist, idx = tree.query(moved)
        agree = (particle_normals @ rotation.T * target_normals[idx]).sum(1) > MIN_NORMAL_COS
        return target_points[idx], trimmed(dist, agree, max_dist), dist

    def pairs(particles, max_dist):
        """(particle index, target point, weight) for both matching directions."""
        matched, ok, dist = match(particles, max_dist)
        index, points, weights = np.flatnonzero(ok), matched[ok], np.ones(ok.sum())
        if symmetric:
            moved = particles @ rotation.T + translation
            bdist, bidx = cKDTree(moved).query(back)
            agree = (particle_normals[bidx] @ rotation.T * back_normals).sum(1) > MIN_NORMAL_COS
            bok = trimmed(bdist, agree, max_dist)
            index = np.concatenate([index, bidx[bok]])
            points = np.concatenate([points, back[bok]])
            # each direction carries equal total weight
            weights = np.concatenate([weights, np.full(bok.sum(), ok.sum() / max(bok.sum(), 1))])
        return index, points, weights, ok, dist

    rms = np.inf
    for it in range(RIGID_ITERATIONS + ITERATIONS):
        rigid_only = it < RIGID_ITERATIONS
        particles = model.shape(b)
        index, points, weights, ok, dist = pairs(particles, np.inf if rigid_only else MAX_DIST_MM)
        if not rigid_only and n_modes:
            residual = ((points - translation) @ rotation - model.mean[index]).ravel()
            a = basis.reshape(-1, 3, n_modes)[index].reshape(-1, n_modes)
            w = np.repeat(weights, 3)
            b = np.linalg.solve(a.T @ (a * w[:, None]) + reg * np.eye(n_modes), a.T @ (residual * w))
            particles = model.shape(b)
        rotation, translation = weighted_kabsch(particles[index], points, weights)
        new_rms = float(np.sqrt((dist[ok] ** 2).mean()))
        if not rigid_only and abs(rms - new_rms) < TOL_MM:
            break
        rms = new_rms

    particles = model.shape(b)
    _, ok, dist = match(particles, MAX_DIST_MM)
    return Fit(b, rotation, translation, particles @ rotation.T + translation, ok,
               float(np.sqrt((dist[ok] ** 2).mean())))


def dense_surface(mean_surface, result, model):
    """Mean mesh warped onto the fitted particles and placed in the target frame."""
    warp = RBFInterpolator(mean_surface.particles, model.shape(result.b) - mean_surface.particles,
                           kernel="thin_plate_spline", smoothing=TPS_SMOOTHING)
    mesh = mean_surface.mesh.copy()
    mesh.points = (mesh.points + warp(mesh.points)) @ result.rotation.T + result.translation
    return mesh
