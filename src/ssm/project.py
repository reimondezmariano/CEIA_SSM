import csv
from pathlib import Path

import shapeworks as sw

from .clean import GROOMED
from .manifest import OUT as MANIFEST

PROJECT_DIR = Path.home() / "SSM" / "data" / "shapeworks_project"
PROJECT = PROJECT_DIR / "pelvis.swproj"

ICP_ITERATIONS = 100

# Their right-side source meshes are faulty. Every optimizer setting tried left
# them with low particle coverage or scrambled correspondence (see ssm.quality),
# and they dominated PC1.
EXCLUDE = {"TMR_000009_R", "TMR_000022_R", "TMR_000043_R", "TMR_000045_R"}
# Landmarks that don't match the mesh; the user dropped both patients.
EXCLUDE |= {"TMR_000006_L", "TMR_000054_L", "TMR_000054_R"}
# Low particle coverage or rough correspondence in the first 80-shape run.
EXCLUDE |= {"TMR_000023_L", "TMR_000033_L", "TMR_000052_L", "TMR_000061_L"}
# Rough correspondence in the 73-shape run, and alone they drove PC2.
EXCLUDE |= {"TMR_000013_L", "TMR_000050_L"}

OPTIMIZE = {
    "number_of_particles": 512,
    # The iliac wing is thin; normals stop particles on opposite faces of it
    # from being treated as neighbours.
    "use_normals": 1,
    "normals_strength": 10.0,
    "checkpointing_interval": 200,
    "keep_checkpoints": 0,
    "iterations_per_split": 1000,
    "optimization_iterations": 1000,
    "starting_regularization": 100,
    "ending_regularization": 0.1,
    "relative_weighting": 10,
    "initial_relative_weighting": 0.1,
    # Rigid only: scaling would discard the absolute size in mm that group
    # comparison and reconstruction both depend on.
    "procrustes": 1,
    "procrustes_interval": 1,
    "procrustes_scaling": 0,
    "multiscale": 1,
    "multiscale_particles": 32,
    "save_init_splits": 0,
    "verbosity": 0,
}


def load_subjects():
    with MANIFEST.open() as f:
        rows = list(csv.DictReader(f))
    return [
        (row["shape"], row["mesh"], GROOMED / f"{row['shape']}.ply")
        for row in rows
        if row["shape"] not in EXCLUDE
        and (GROOMED / f"{row['shape']}.ply").exists()
    ]


def rigid_transforms(meshes):
    ref = sw.find_reference_mesh_index(meshes)
    return ref, [
        m.createTransform(meshes[ref], sw.Mesh.AlignmentType.Rigid, ICP_ITERATIONS)
        for m in meshes
    ]


def relative(path):
    return sw.utils.get_relative_paths([str(path)], str(PROJECT_DIR))


def build():
    subjects = load_subjects()
    meshes = [sw.Mesh(str(groomed)) for _, _, groomed in subjects]
    ref, transforms = rigid_transforms(meshes)

    project_subjects = []
    for (name, original, groomed), transform in zip(subjects, transforms):
        subject = sw.Subject()
        subject.set_number_of_domains(1)
        subject.set_display_name(name)
        subject.set_original_filenames(relative(original))
        subject.set_groomed_filenames(relative(groomed))
        subject.set_groomed_transforms([transform.flatten()])
        project_subjects.append(subject)

    parameters = sw.Parameters()
    for key, value in OPTIMIZE.items():
        parameters.set(key, sw.Variant([value]))

    project = sw.Project()
    project.set_subjects(project_subjects)
    project.set_parameters("optimize", parameters)
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    project.save(str(PROJECT))
    return subjects[ref][0], len(subjects)


def main():
    reference, n = build()
    print(f"{n} subjects, reference {reference} -> {PROJECT}")
    print(f"optimize with: shapeworks optimize --progress --name {PROJECT}")


if __name__ == "__main__":
    main()
