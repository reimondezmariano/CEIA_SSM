# 02 · Datos y manifiesto

## Dónde está cada cosa

```
~/DataSet/                 STL exportados (85 mallas: 45 izquierdas, 40 derechas, 45 pacientes)
~/Landmarks_aligned/       <sujeto>_landmarks_aligned.csv (48 archivos)
~/DataSet_damaged/         casos dañados reales (RMR_000002, RMR_000008) y sus landmarks
~/SSM/                     el repositorio
~/SSM/data/                todo lo generado (fuera de git)
    manifest.csv             lista de formas (etapa 2)
    check.csv                informe de verificación (etapa 3b)
    groomed/                 mallas preparadas, una por forma (etapa 3a)
    shapeworks_project/      proyecto, partículas, forma media y PCA (etapa 4)
    reconstruction/          validaciones y reconstrucciones (etapas 5 y 6)
    logs/                    salida de cada etapa lanzada con run_pipeline.sh
```

Los modelos y experimentos antiguos se conservan al lado con sufijo (`shapeworks_project_71`, la
versión de ambos lados; `shapeworks_project_36`, la primera versión solo de derechos…). Las
reconstrucciones enviadas antes del cambio de modelo están en `reconstruction/sent_2026-09-24/`.

## El manifiesto

```bash
"Pipeline SSM/run_pipeline.sh" manifest      # python -m ssm.manifest
```

Recorre `SSM_MESH_DIR`, extrae sujeto y lado del nombre y busca el CSV de landmarks del sujeto.
Escribe `data/manifest.csv`, una fila por malla:

| Columna | Contenido |
|---|---|
| `shape` | `<sujeto>_<L\|R>`, el nombre que se usa en todas las etapas |
| `subject`, `side` | paciente y lado |
| `mesh` | ruta al STL |
| `landmarks` | ruta al CSV del sujeto (vacío si no existe) |
| `has_ASIS`, `has_PSIS`, `has_PT`, `has_FH` | el landmark existe y es finito para el lado de esta malla |
| `n_landmarks` | cuántos de los cuatro |

Es la **única fuente de la lista de sujetos**: `clean`, `project`, `check` y `validate` la leen. Si se
añade o quita una malla, hay que volver a ejecutar `manifest` y todo lo que va detrás.

Salida esperada con los datos actuales: `85 shapes of 45 subjects`.

## Reglas que conviene saber

- Un paciente es un **sujeto**: `TMR_000004`. Sus dos lados (`_L`, `_R`) son casi imágenes
  especulares, así que la validación **deja fuera a los dos a la vez**; si no, un lado revelaría al
  otro al modelo.
- Un sujeto puede tener un solo lado (por ejemplo `TMR_000005` solo tiene izquierdo). Es válido.
- Sin CSV de landmarks el sujeto entra igualmente al modelo, pero no genera defectos simulados y
  `ssm.check` avisa (`no landmark file`).
