#!/bin/bash
# Runs one stage of the SSM pipeline, or all of them. See README.md in this folder.
#
#   ./run_pipeline.sh env                 check the software
#   ./run_pipeline.sh export --landmarks RAW.csv --meshes RAW_DIR   raw STL + landmarks -> aligned set (data/export)
#   ./run_pipeline.sh manifest            list meshes and landmarks         -> data/manifest.csv
#   ./run_pipeline.sh clean               mirror lefts, clean, remesh       -> data/groomed/*.ply
#   ./run_pipeline.sh check               verify meshes and landmarks       -> data/check.csv (after clean)
#   ./run_pipeline.sh project             build the ShapeWorks project      -> data/shapeworks_project/pelvis.swproj
#   ./run_pipeline.sh optimize            particle correspondence (~10 min for 35 shapes)
#   ./run_pipeline.sh analyze             mean shape and PCA                -> mean_shape_0.vtk, analysis.json
#   ./run_pipeline.sh quality             coverage and roughness per shape
#   ./run_pipeline.sh validate [--reduced] [--sides R] [--eval-sides L] [--eval-shapes A,B]   simulated defects
#   ./run_pipeline.sh reconstruct DAMAGED.stl [--reference HEALTHY.stl]
#   ./run_pipeline.sh all                 manifest .. quality, then a reduced validation
#
# Settings, all optional (defaults in brackets):
#   SSM_MESH_DIR [~/DataSet]  SSM_LANDMARK_DIR [~/Landmarks_aligned]  SSM_DATA [~/SSM/data]
#   SSM_PROJECT [shapeworks_project]  SSM_SIDES [R]  SSM_HOLDOUT [none: subjects kept out of the model]
#   SHAPEWORKS_HOME [~/software/ShapeWorks-v6.7.0-linux]  SHAPEWORKS_ENV [~/miniconda3/envs/shapeworks]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SSM_DATA="${SSM_DATA:-$HOME/SSM/data}"
SHAPEWORKS_HOME="${SHAPEWORKS_HOME:-$HOME/software/ShapeWorks-v6.7.0-linux}"
SHAPEWORKS_ENV="${SHAPEWORKS_ENV:-$HOME/miniconda3/envs/shapeworks}"
# The project's own .venv cannot import shapeworks: use the ShapeWorks conda env.
export PATH="$SHAPEWORKS_HOME/bin:$SHAPEWORKS_ENV/bin:$PATH"
export PYTHONPATH="$REPO/src"
PROJECT_DIR="$SSM_DATA/${SSM_PROJECT:-shapeworks_project}"
LOGS="$SSM_DATA/logs"
cd "$REPO"

run() {  # run a stage, keeping its output in data/logs/<stage>.log
    local stage="$1"; shift
    mkdir -p "$LOGS"
    echo "== $stage ($(date +%H:%M:%S))"
    "$@" 2>&1 | tee "$LOGS/$stage.log"
}

stage_env() {
    command -v shapeworks >/dev/null || { echo "shapeworks not on PATH (SHAPEWORKS_HOME=$SHAPEWORKS_HOME)"; exit 1; }
    shapeworks --version | head -1
    python - <<'PY'
import sys
import numpy, scipy, pandas, pyvista, trimesh, vtk, shapeworks
print("python", sys.version.split()[0], "| numpy", numpy.__version__, "| scipy", scipy.__version__,
      "| pandas", pandas.__version__, "| pyvista", pyvista.__version__, "| trimesh", trimesh.__version__, "| vtk", vtk.vtkVersion.GetVTKVersion())
PY
    echo "cores: $(nproc), memory: $(free -g | awk '/Mem/{print $2}') GB"
}

stage_optimize() {
    [ -f "$PROJECT_DIR/pelvis.swproj" ] || { echo "no project at $PROJECT_DIR: run the project stage first"; exit 1; }
    shapeworks optimize --name "$PROJECT_DIR/pelvis.swproj" | tr '\r' '\n' | grep -vE "^(Loading meshes|Initializing|Optimizing)" || true
    # (the progress bar is left out of the log; add --progress to see it)
    [ -d "$PROJECT_DIR/pelvis_particles" ] || { echo "optimize produced no particles"; exit 1; }
    echo "$(ls "$PROJECT_DIR/pelvis_particles" | grep -c _world.particles) shapes optimized"
}

stage_analyze() {
    # analyze needs --output, and writes the mean shape into the working directory
    (cd "$PROJECT_DIR" && shapeworks analyze --name pelvis.swproj --output analysis.json)
    [ -f "$PROJECT_DIR/mean_shape_0.vtk" ] || { echo "analyze produced no mean shape"; exit 1; }
}

stage="${1:-}"; shift || true
case "$stage" in
    env)         stage_env ;;
    export)      run export python -m ssm.export "$@" ;;
    manifest)    run manifest python -m ssm.manifest ;;
    check)       run check python -m ssm.check ;;
    clean)       run clean python -m ssm.clean ;;
    project)     run project python -m ssm.project ;;
    optimize)    run optimize stage_optimize ;;
    analyze)     run analyze stage_analyze ;;
    quality)     run quality python -m ssm.quality ;;
    validate)    run validate python -m ssm.validate "$@" ;;
    reconstruct) python -m ssm.reconstruct "$@" ;;
    all)
        for s in manifest clean check project optimize analyze quality; do "$0" "$s"; done
        "$0" validate --reduced ;;
    *) sed -n '2,20p' "$0"; exit 1 ;;
esac
