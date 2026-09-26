# 04 · El modelo estadístico de forma

Cuatro sub-etapas: construir el proyecto de ShapeWorks, optimizar las correspondencias, calcular la forma
media y el PCA, y medir la calidad. Todas leen las mallas de `data/groomed/` y la lista de formas del
manifiesto, filtrada por `EXCLUDE` y por `SSM_SIDES` (por defecto solo derechas).

```bash
"Pipeline SSM/run_pipeline.sh" project      # python -m ssm.project
"Pipeline SSM/run_pipeline.sh" optimize     # shapeworks optimize     (unos 10 min con 35 formas)
"Pipeline SSM/run_pipeline.sh" analyze      # shapeworks analyze
"Pipeline SSM/run_pipeline.sh" quality      # python -m ssm.quality
```

## Idea

ShapeWorks coloca en cada malla el **mismo número de partículas (512)** de modo que la partícula *i*
represente el mismo punto anatómico en todos los huesos. Con esas correspondencias, cada hueso es un
vector de 512 × 3 coordenadas; el **PCA** de esos vectores da la forma media y los modos de variación
(`ssm.model`). Reconstruir es encontrar la combinación de modos que mejor encaja con el hueso que sí
está.

## 4a · Proyecto (`ssm.project`)

Crea `data/shapeworks_project/pelvis.swproj`:

- toma las formas del manifiesto (menos `EXCLUDE`, solo los lados de `SSM_SIDES`, solo las que tienen
  malla preparada);
- elige como **referencia** la malla más representativa (`find_reference_mesh_index`) y calcula para cada
  forma una transformación **rígida** (ICP, 100 iteraciones) hacia ella; sirve de punto de partida a la
  optimización;
- guarda los parámetros de optimización de la tabla siguiente.

Con `SSM_PROJECT=<nombre>` el proyecto se crea en `data/<nombre>/`, para hacer experimentos sin pisar el
modelo principal.

## 4b · Optimización (`shapeworks optimize`)

| Parámetro | Valor | Por qué |
|---|---|---|
| `number_of_particles` | 512 | compromiso entre detalle y coste; con 35 formas ya reproduce la superficie con cobertura ≥ 0,92 |
| `use_normals`, `normals_strength` | 1, 10 | el ala ilíaca es delgada; las normales evitan que partículas de las dos caras opuestas se traten como vecinas |
| `multiscale`, `multiscale_particles` | 1, 32 | empieza con pocas partículas y las va dividiendo |
| `iterations_per_split`, `optimization_iterations` | 1000, 1000 | |
| `starting_regularization` → `ending_regularization` | 100 → 0,1 | |
| `relative_weighting`, `initial_relative_weighting` | 10, 0,1 | |
| `procrustes`, `procrustes_interval`, `procrustes_scaling` | 1, 1, **0** | alineación rígida **sin escalado**: el escalado descartaría el tamaño absoluto en mm, del que dependen la comparación entre grupos y la reconstrucción |
| `checkpointing_interval`, `keep_checkpoints`, `verbosity` | 200, 0, 0 | |

No se usa la distancia geodésica (agota la RAM; ver [00](00-entorno.md)). Los valores no han cambiado
desde la primera versión del proyecto (2026-09-22, modelo de solo derechos): no se han vuelto a afinar para
el modelo actual, y con ellos se recupera la precisión de aquel primer modelo (ver
[08](08-historial-y-decisiones.md)).

Salida: `pelvis_particles/<forma>_{world,local,wptsFeatures}.particles`. Las partículas *world* son las
que usa el PCA.

Duración medida: ~9 min con 35 formas, ~26 min con 66.

## 4c · Forma media y PCA (`shapeworks analyze`)

Escribe en la carpeta del proyecto la **forma media** (`mean_shape_0.vtk` con su `mean_shape_0.pts`),
`analysis.json` y muestras de cada modo de variación. Es imprescindible: la malla media es la superficie
que `ssm.fit` deforma para reconstruir. **Debe ejecutarse desde la carpeta del proyecto y con
`--output analysis.json`** (`run_pipeline.sh analyze` lo hace).

`ssm.model.build` recalcula el PCA a partir de las partículas cuando hace falta (sobre un subconjunto en
la validación): media, modos unitarios y desviación típica de cada modo en mm. Con *n* formas hay como
máximo *n* − 1 modos con varianza.

## 4d · Calidad de la correspondencia (`ssm.quality`)

Una correspondencia mala no se ve en el error de reconstrucción hasta mucho después, así que se mide antes:

- **Cobertura:** fracción de la superficie con una partícula a menos de 10 mm. Baja cobertura = partículas
  amontonadas en una parte del hueso.
- **Rugosidad:** mediana, entre partículas, de cuánto se mueve una partícula de forma distinta a sus 6
  vecinas más cercanas, respecto a la forma media (por forma) o a +3 SD (por modo). Los intercambios de
  correspondencia se ven como vecinos que se mueven en direcciones distintas aunque la cobertura sea buena.
- Se marca una forma si **cobertura < 0,85** o **rugosidad > 2 × la mediana**. Por modo, se cuentan las
  partículas que se mueven > 15 mm.

Con el modelo actual (35 formas derechas): cobertura mínima **0,92**, mediana 0,98; rugosidad mediana
**3,0 mm**, máxima 6,6 mm (`TMR_000015_R`, única marcada); PC1 51,0 % de la varianza, PC2 11,0 %, PC3 10,7 %.

**Qué hacer si algo se marca:** mirar la forma en `check.csv` y en un visor; si su malla es defectuosa,
añadirla a `EXCLUDE` y repetir `project → optimize → analyze → quality`. Así se llegó a la lista de
exclusiones ([03](03-verificacion-y-preparacion.md)). Excluir de más también cuesta: cada forma menos
son menos modos disponibles.

## Por qué el modelo es solo de derechos

Se entrenó primero con ambos lados (izquierdos reflejados sobre el modelo derecho) esperando más
datos y mejor modelo. No fue así:

| Modelo | Error en las mismas 35 formas derechas | En las 36 izquierdas reflejadas |
|---|---|---|
| Ambos lados (71 formas) | 2,397 mm | 2,229 mm |
| **Solo derechos (35 formas)** | **2,195 mm** | 2,233 mm |
| Correspondencia de ambos lados, PCA solo con derechos | 2,473 mm | 2,336 mm |

El modelo de solo derechos gana 0,20 ± 0,05 mm en derechos y **empata en izquierdos, que además nunca
vio**. Optimizar las correspondencias con ambos lados a la vez las empeoró; añadir los izquierdos
reflejados solo al PCA no perjudica. Detalles y el resto de pruebas en [08](08-historial-y-decisiones.md).
