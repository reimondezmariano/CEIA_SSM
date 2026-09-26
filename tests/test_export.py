"""python -m unittest discover tests   (needs the shapeworks environment: numpy, pandas, trimesh)"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import trimesh
from scipy.spatial.transform import Rotation

from ssm import export

# Landmarks already in the APP frame: centroid 0, ASIS on the line y = 0 at equal z, PT midpoint at y = 0.
ALIGNED = {
    "ASIS_L": (102.0, 0.0, 40.0), "ASIS_R": (-104.0, 0.0, 40.0),
    "PT_L": (24.0, -1.0, -41.0), "PT_R": (-22.0, 1.0, -39.0),
    "FH_L": (82.0, 48.0, -30.0), "FH_R": (-81.0, 48.0, -28.0),
    "PSIS_L": (42.0, 133.0, 47.0), "PSIS_R": (-50.0, 134.0, 50.0),
}
REAL = Path(__file__).resolve().parents[1] / "data"


def raw_row(rotation, shift, case_id="SA000001", drop=()):
    row = {"case_id": case_id}
    for name, p in ALIGNED.items():
        moved = rotation.apply(p) + shift
        for a, v in zip("xyz", moved):
            row[f"{name}_{a}"] = np.nan if name in drop else v
    return pd.Series(row)


class Frame(unittest.TestCase):
    def setUp(self):
        self.rotation = Rotation.from_euler("xyz", [37, -51, 112], degrees=True)
        self.shift = np.array([310.0, -95.0, 1200.0])

    def test_recovers_the_aligned_landmarks_from_any_rigid_motion(self):
        aligned, _, _ = export.align_row(raw_row(self.rotation, self.shift))
        for name, p in ALIGNED.items():
            np.testing.assert_allclose(export.point(aligned, name), p, atol=1e-9)

    def test_defining_properties(self):
        row = raw_row(self.rotation, self.shift)
        rotation, origin = export.app_frame(*(export.point(row, n) for n in export.FRAME_LANDMARKS))
        self.assertAlmostEqual(np.linalg.det(rotation), 1.0, places=12)
        aligned, _, _ = export.align_row(row)
        pts = {n: export.point(aligned, n) for n in export.FRAME_LANDMARKS}
        np.testing.assert_allclose(sum(pts.values()), 0, atol=1e-9)
        self.assertAlmostEqual(pts["ASIS_L"][1], pts["ASIS_R"][1], places=9)
        self.assertAlmostEqual(pts["ASIS_L"][2], pts["ASIS_R"][2], places=9)
        self.assertAlmostEqual((pts["PT_L"][1] + pts["PT_R"][1]) / 2, 0, places=9)
        self.assertGreater(pts["ASIS_L"][0], 0)  # left is +x
        self.assertGreater(pts["ASIS_L"][2], pts["PT_L"][2])  # superior is +z

    def test_aligned_input_is_a_fixed_point(self):
        aligned, rotation, origin = export.align_row(raw_row(Rotation.identity(), np.zeros(3)))
        np.testing.assert_allclose(rotation, np.eye(3), atol=1e-9)
        np.testing.assert_allclose(origin, 0, atol=1e-9)

    def test_missing_or_degenerate_frame_landmark_is_refused(self):
        with self.assertRaises(ValueError):
            export.align_row(raw_row(self.rotation, self.shift, drop=("PT_L",)))
        row = raw_row(self.rotation, self.shift)
        for a in "xyz":
            row[f"ASIS_R_{a}"] = row[f"ASIS_L_{a}"]
        with self.assertRaises(ValueError):
            export.align_row(row)

    def test_other_missing_landmarks_stay_missing(self):
        aligned, _, _ = export.align_row(raw_row(self.rotation, self.shift, drop=("FH_L",)))
        self.assertTrue(np.isnan(export.point(aligned, "FH_L")).all())
        np.testing.assert_allclose(export.point(aligned, "FH_R"), ALIGNED["FH_R"], atol=1e-9)

    @unittest.skipUnless((REAL / "TMR_000004_landmarks_raw.csv").exists(), "real pair not on this machine")
    def test_reproduces_the_real_aligned_landmarks(self):
        raw = pd.read_csv(REAL / "TMR_000004_landmarks_raw.csv").iloc[0]
        expected = pd.read_csv(REAL / "TMR_000004_landmarks_aligned.csv").iloc[0]
        aligned, _, _ = export.align_row(raw)
        for name in export.landmark_names(raw.index):
            np.testing.assert_allclose(export.point(aligned, name), export.point(expected, name), atol=1e-8)


class Run(unittest.TestCase):
    """End to end on two spheres standing in for the hemipelves."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rotation = Rotation.from_euler("xyz", [10, 200, -75], degrees=True)
        self.shift = np.array([-40.0, 500.0, 90.0])
        self.mesh_dir = self.tmp / "raw"
        self.mesh_dir.mkdir()
        self.truth = {}
        for side, centre in (("left", (75, 45, -5)), ("right", (-75, 45, -5))):
            sphere = trimesh.creation.icosphere(subdivisions=3, radius=60)
            sphere.vertices += centre
            self.truth[side] = sphere.vertices.copy()
            sphere.vertices = self.rotation.apply(sphere.vertices) + self.shift
            sphere.export(self.mesh_dir / f"SA000001_raw_4_pelvis_{side}.stl")
        raw_row(self.rotation, self.shift).to_frame().T.to_csv(self.tmp / "raw.csv", index=False)
        pd.DataFrame({"original_case_id": ["SA000001"], "new_case_id": ["TMR_000099"]}).to_csv(
            self.tmp / "mapping.csv", index=False)
        self.out = self.tmp / "out"
        self.args = ["--landmarks", str(self.tmp / "raw.csv"), "--meshes", str(self.mesh_dir),
                     "--mapping", str(self.tmp / "mapping.csv"), "--out", str(self.out)]

    def test_writes_renamed_aligned_files(self):
        export.main(self.args)
        names = sorted(p.name for p in (self.out / "meshes").iterdir())
        self.assertEqual(names, ["TMR_000099_raw_4_pelvis_left_aligned.stl", "TMR_000099_raw_4_pelvis_right_aligned.stl"])
        for side in ("left", "right"):
            mesh = trimesh.load(self.out / "meshes" / f"TMR_000099_raw_4_pelvis_{side}_aligned.stl")
            # STL stores float32 and the vertex order changes: compare loosely and sorted.
            np.testing.assert_allclose(np.sort(mesh.vertices, axis=0), np.sort(self.truth[side], axis=0), atol=1e-2)
        landmarks = pd.read_csv(self.out / "landmarks" / "TMR_000099_landmarks_aligned.csv").iloc[0]
        np.testing.assert_allclose(export.point(landmarks, "ASIS_L"), ALIGNED["ASIS_L"], atol=1e-6)
        log = pd.read_csv(self.out / "export_log.csv")
        self.assertEqual(set(log.item), {"landmarks", "mesh L", "mesh R"})
        self.assertTrue(log.sha256.str.len().eq(64).all())

    def test_a_swapped_side_is_flagged_not_dropped(self):
        for side, other in (("left", "right"), ("right", "left")):
            (self.mesh_dir / f"SA000001_raw_4_pelvis_{side}.stl").rename(self.mesh_dir / f"tmp_{side}.stl")
        (self.mesh_dir / "tmp_left.stl").rename(self.mesh_dir / "SA000001_raw_4_pelvis_right.stl")
        (self.mesh_dir / "tmp_right.stl").rename(self.mesh_dir / "SA000001_raw_4_pelvis_left.stl")
        export.main(self.args)
        log = pd.read_csv(self.out / "export_log.csv")
        meshes = log[log.item.str.startswith("mesh")]
        self.assertTrue(meshes.status.eq("review").all())
        self.assertTrue(meshes["flags"].str.contains("side has mean x").all())

    def test_unmapped_patient_is_skipped(self):
        pd.DataFrame({"original_case_id": ["SA999999"], "new_case_id": ["TMR_000098"]}).to_csv(
            self.tmp / "mapping.csv", index=False)
        export.main(self.args)
        log = pd.read_csv(self.out / "export_log.csv")
        self.assertEqual(log.status.tolist(), ["skipped"])
        self.assertFalse((self.out / "meshes").exists())

    def test_refuses_to_overwrite(self):
        export.main(self.args)
        with self.assertRaises(SystemExit):
            export.main(self.args)
        export.main(self.args + ["--overwrite"])


if __name__ == "__main__":
    unittest.main()
