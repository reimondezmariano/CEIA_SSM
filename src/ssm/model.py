"""PCA shape model built from the optimized world particles."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .project import PROJECT_DIR

PARTICLES = PROJECT_DIR / "pelvis_particles"


def load_world(particles=PARTICLES):
    particles = Path(particles)
    names = sorted(p.name.removesuffix("_world.particles") for p in particles.glob("*_world.particles"))
    return names, np.stack([np.loadtxt(particles / f"{n}_world.particles") for n in names])


def load_local(name, particles=PARTICLES):
    return np.loadtxt(Path(particles) / f"{name}_local.particles")


@dataclass
class Model:
    mean: np.ndarray  # (particles, 3)
    modes: np.ndarray  # (modes, particles, 3), unit length
    sd: np.ndarray  # (modes,), standard deviation of each mode in mm

    @property
    def variance(self):
        return self.sd**2 / (self.sd**2).sum()

    def shape(self, b):
        """Particles for coefficients b, in standard deviations of the leading modes."""
        b = np.asarray(b)
        return self.mean + np.tensordot(b * self.sd[: len(b)], self.modes[: len(b)], axes=1)


def build(world):
    flat = world.reshape(len(world), -1)
    mean = flat.mean(0)
    _, s, vt = np.linalg.svd(flat - mean, full_matrices=False)
    keep = s > s[0] * 1e-9  # the last mode of a centred set is null
    return Model(mean.reshape(-1, 3), vt[keep].reshape(keep.sum(), -1, 3), s[keep] / np.sqrt(len(world) - 1))
