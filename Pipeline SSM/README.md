# Pipeline SSM

Modelo estadístico de forma (SSM) de hemipelvis para reconstruir hueso acetabular perdido.
A partir de mallas 3D de caderas sanas se aprende la forma media y sus modos de variación
(ShapeWorks + PCA); después se ajusta ese modelo a una hemipelvis dañada y se rellena el
hueso que falta.

Esta carpeta explica **cómo se hizo, paso a paso, y cómo repetirlo con un set de
entrenamiento y validación nuevo**. El código vive en `../src/ssm/`; aquí está la
documentación, un script que encadena las etapas y una herramienta de comparación.

## El pipeline de un vistazo

```
 fuera del repo            ┌───────────────────────── este repositorio ─────────────────────────┐
                           │                                                                     │
 1. Exportar caderas ──▶ 2. Manifiesto ──▶ 3. Preparar y ──▶ 4. Modelo ──▶ 5. Validar ──▶ 6. Reconstruir
    (STL + landmarks)       (manifest)        verificar         (project,      (validate)      (reconstruct)
                                              (clean, check)     optimize,
                                                                 analyze,
                                                                 quality)
```

| # | Etapa | Comando (`./run_pipeline.sh …`) | Módulo | Salida (en `data/`) | Documento |
|---|-------|--------------------------------|--------|---------------------|-----------|
| 1 | Exportación de las caderas | — (fuera del repo) | — | `~/DataSet/*.stl`, `~/Landmarks_aligned/*.csv` | [01](docs/01-exportacion.md) |
| 2 | Manifiesto de datos | `manifest` | `ssm.manifest` | `manifest.csv` | [02](docs/02-datos-y-manifiesto.md) |
| 3a | Preparación de mallas | `clean` | `ssm.clean` | `groomed/*.ply` | [03](docs/03-verificacion-y-preparacion.md) |
| 3b | Verificación de mallas y landmarks | `check` | `ssm.check` | `check.csv` | [03](docs/03-verificacion-y-preparacion.md) |
| 4a | Proyecto ShapeWorks | `project` | `ssm.project` | `shapeworks_project/pelvis.swproj` | [04](docs/04-modelo.md) |
| 4b | Correspondencia de partículas | `optimize` | (ShapeWorks) | `pelvis_particles/` | [04](docs/04-modelo.md) |
| 4c | Forma media y PCA | `analyze` | (ShapeWorks) | `mean_shape_0.vtk`, `analysis.json` | [04](docs/04-modelo.md) |
| 4d | Calidad de la correspondencia | `quality` | `ssm.quality` | (consola) | [04](docs/04-modelo.md) |
| 5 | Validación con defectos simulados | `validate` | `ssm.validate` | `reconstruction/validation*.csv` | [05](docs/05-validacion.md) |
| 6 | Reconstrucción de un caso dañado | `reconstruct` | `ssm.reconstruct` | `reconstruction/*.stl`, `*.png` | [06](docs/06-reconstruccion.md) |

## Inicio rápido

```bash
cd ~/SSM
"Pipeline SSM/run_pipeline.sh" env          # comprueba ShapeWorks y las librerías
"Pipeline SSM/run_pipeline.sh" all          # etapas 2 a 4 y una validación reducida (~33 min)
"Pipeline SSM/run_pipeline.sh" reconstruct ~/DataSet_damaged/RMR_000008_raw_1_pelvis_right_aligned.stl \
        --reference ~/DataSet_damaged/RMR_000008_raw_5_pelvis_left_aligned.stl
```

Para repetirlo con otros datos sin tocar los actuales:

```bash
SSM_MESH_DIR=~/DataSet2 SSM_LANDMARK_DIR=~/Landmarks2 SSM_DATA=~/SSM/data_set2 \
    "Pipeline SSM/run_pipeline.sh" all
```

La guía completa, con las decisiones que hay que volver a tomar, está en
[docs/07-replicar-con-set-nuevo.md](docs/07-replicar-con-set-nuevo.md).

## Estado actual (2026-09-26)

- **Datos:** 85 mallas (45 izquierdas, 40 derechas) de 45 pacientes, más 2 casos dañados reales.
- **Modelo definitivo:** 35 hemipelvis **derechas**, 512 partículas, sin escalado (el tamaño
  absoluto en mm se conserva). Los lados izquierdos se reflejan (x → −x) sobre el modelo al
  reconstruir.
- **Precisión esperada** (validación dejando fuera al paciente, defectos simulados de 20–40 mm):
  error medio en la zona del defecto **2,2 mm** (2,2 en derechos, 2,2 en izquierdos espejados);
  1,7 mm si el defecto está en el acetábulo; el peor defecto simulado tiene una media de 6,8 mm.
  La referencia sin modelo (forma media rígida) da 3,9 mm.
- **Paciente reservado** (`TMR_000018`, sorteado, modelo entrenado sin él): 2,61 mm en derecha y 3,05 mm en izquierda
  reflejada, 0,1–0,2 mm más que dejando uno fuera para las mismas formas. Es un solo paciente: comprobación, no estimación.
- **Casos reales reconstruidos:** RMR_000008 (derecho dañado) y RMR_000002 (izquierdo dañado).

Por qué el modelo es solo de derechos y no de ambos lados, y qué otras cosas se probaron y
descartaron: [docs/08-historial-y-decisiones.md](docs/08-historial-y-decisiones.md).

## Contenido de la carpeta

```
Pipeline SSM/
├── README.md                    este documento
├── run_pipeline.sh              ejecuta una etapa (o todas) con el entorno correcto
├── tools/compare_validation.py  compara varias validaciones sobre las mismas formas
├── tools/holdout_report.py      paciente reservado frente a dejar uno fuera
└── docs/
    ├── 00-entorno.md            software, versiones, problemas conocidos
    ├── 01-exportacion.md        qué debe cumplir lo que se exporta
    ├── 02-datos-y-manifiesto.md nombres, carpetas, formato de landmarks
    ├── 03-verificacion-y-preparacion.md   ssm.clean, ssm.check y exclusiones
    ├── 04-modelo.md             proyecto ShapeWorks, optimización, PCA, calidad
    ├── 05-validacion.md         diseño, cifras y cómo leer los resultados
    ├── 06-reconstruccion.md     reconstruir un caso dañado
    ├── 07-replicar-con-set-nuevo.md   lista de pasos para repetirlo
    └── 08-historial-y-decisiones.md   cómo se llegó aquí
```

## Convenciones

- Una **forma** (`shape`) es una hemipelvis: `<sujeto>_<L|R>`, por ejemplo `TMR_000004_R`.
  Un **sujeto** o paciente tiene, como mucho, una forma por lado.
- Todo se mide en **milímetros**, en el sistema de coordenadas «alineado» de la exportación.
- `data/` no está en git (mallas y resultados generados); el código y esta documentación sí.
