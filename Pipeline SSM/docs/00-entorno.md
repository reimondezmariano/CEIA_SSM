# 00 · Entorno

## Equipo en el que se hizo

| | |
|---|---|
| CPU | Intel Core i7-7700K, 4 núcleos / 8 hilos |
| RAM | 16 GB (WSL2, Ubuntu, kernel 6.18) |
| GPU | No se usa. Todo el código corre en CPU |
| Disco | ~2,1 GB generados en `data/` con el modelo actual (mallas preparadas 320 MB, proyecto ShapeWorks 1,7 GB con muestras de PCA, reconstrucciones 37 MB) |

## Software

Todo lo que necesita el pipeline viene con **ShapeWorks 6.7.0**; no hay que instalar nada más.

1. Descargar `ShapeWorks-v6.7.0-linux.tar.gz` y extraerlo (aquí: `~/software/ShapeWorks-v6.7.0-linux`).
2. Instalar Miniconda si no está (`~/miniconda3`).
3. Dentro de la carpeta extraída:
   ```bash
   cd ~/software/ShapeWorks-v6.7.0-linux
   source install_shapeworks.sh          # crea el entorno conda «shapeworks»
   ```
   El instalador crea el entorno con Python 3.12.3 y las dependencias de
   `python_requirements.txt`, incluido el paquete Python `shapeworks`. En este equipo se instaló el 2026-09-19
   (registro: `install_shapeworks_20260919_154528.log`).

Versiones con las que se obtuvieron todos los resultados:

| Paquete | Versión |
|---|---|
| ShapeWorks | 6.7.0 |
| Python | 3.12.3 |
| numpy / scipy / pandas | 2.3.3 / 1.16.2 / 2.3.2 |
| pyvista / vtk | 0.46.3 / 9.5.1 |
| trimesh | 4.8.1 |
| scikit-learn / matplotlib | 1.7.2 / 3.10.6 |

## Cómo se activa

`run_pipeline.sh` lo hace solo. A mano, desde `~/SSM`:

```bash
export PATH=$HOME/software/ShapeWorks-v6.7.0-linux/bin:$HOME/miniconda3/envs/shapeworks/bin:$PATH
export PYTHONPATH=src
python -m ssm.manifest        # etc.
```

Comprobación: `"Pipeline SSM/run_pipeline.sh" env` imprime las versiones, los núcleos y la memoria.

**No usar el `.venv` del proyecto** (uv, Python 3.14): no puede importar `shapeworks`. El
`pyproject.toml` es solo el esqueleto inicial del repositorio y no declara dependencias; el entorno
real es el de conda.

## Variables de entorno (todas opcionales)

| Variable | Por defecto | Para qué |
|---|---|---|
| `SSM_MESH_DIR` | `~/DataSet` | Carpeta con los STL exportados |
| `SSM_LANDMARK_DIR` | `~/Landmarks_aligned` | Carpeta con los CSV de landmarks |
| `SSM_DATA` | `~/SSM/data` | Dónde se escribe todo lo generado |
| `SSM_PROJECT` | `shapeworks_project` | Subcarpeta del proyecto ShapeWorks dentro de `SSM_DATA` (para experimentos) |
| `SSM_SIDES` | `R` | Lados con los que se entrena el modelo (`R`, `L` o `LR`) |
| `SHAPEWORKS_HOME`, `SHAPEWORKS_ENV` | `~/software/ShapeWorks-v6.7.0-linux`, `~/miniconda3/envs/shapeworks` | Solo para `run_pipeline.sh` |

## Problemas conocidos (y su solución)

- **`rtree` no está instalado.** `trimesh.proximity` falla. El código usa `scipy.spatial.cKDTree` y
  `pyvista.compute_implicit_distance`; hay que seguir haciéndolo así.
- **La optimización con distancia geodésica** (`use_geodesic_distance`) agota los 16 GB de RAM con ~40
  mallas de 25 000 vértices. No se usa.
- **`shapeworks analyze` exige `--output`** y escribe la forma media en el directorio actual, así que
  debe ejecutarse desde la carpeta del proyecto (`run_pipeline.sh analyze` ya lo hace). Sin la forma
  media (`mean_shape_0.vtk`) no funcionan ni `ssm.validate` ni `ssm.reconstruct`.
- **Validación 10 veces más lenta de lo debido.** Con 8 procesos, BLAS y VTK abren cada uno 8 hilos y se
  acumulan ~60 hilos activos en 8 CPU lógicas. `ssm.validate` fija un hilo por proceso al arrancar; si
  se escribe otro script con `multiprocessing`, hay que hacer lo mismo (`OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `VTK_SMP_MAX_THREADS=1`, antes de importar numpy).
- **`WARNING: Trying to save mesh with new field`** al ejecutar `clean`: inofensivo.
- **Esperar a un proceso con `pgrep -f "texto"`** desde un script se encuentra a sí mismo y no termina
  nunca; usar un patrón con corchetes (`pgrep -f "ssm[.]validate"`).
