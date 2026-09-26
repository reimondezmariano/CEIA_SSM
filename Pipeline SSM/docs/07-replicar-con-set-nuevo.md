# 07 · Repetir el proceso con un set nuevo

Lista de pasos para construir y validar un modelo con **otros pacientes**, sin tocar el actual. Cada paso
indica cómo saber que salió bien. Se comprobó ejecutando todo de cero sobre los datos actuales
(`SSM_DATA` aparte) y dio un resultado idéntico al original (ver «Tiempos y cifras de control»).

## 0 · Antes de empezar

- [ ] Entorno listo: `"Pipeline SSM/run_pipeline.sh" env` ([00](00-entorno.md)).
- [ ] Espacio en disco: ~2 GB por modelo de 35 formas, más las mallas preparadas.
- [ ] Decidir un nombre para el set y **no reutilizar** `~/SSM/data` (contiene el modelo actual).

## 1 · Exportar y colocar los datos

1. Exportar las caderas y los landmarks cumpliendo [01](01-exportacion.md): STL por hemipelvis en el sistema
   alineado (derecha en x < 0, izquierda en x > 0, mm), un CSV de landmarks por sujeto.
2. Copiarlos a carpetas nuevas, por ejemplo `~/DataSet2/` y `~/Landmarks2/`.
3. Definir las variables (en cada terminal, o delante de cada comando):

   ```bash
   export SSM_MESH_DIR=~/DataSet2 SSM_LANDMARK_DIR=~/Landmarks2 SSM_DATA=~/SSM/data_set2
   ```

   Con `SSM_DATA` distinto, todo lo generado queda separado del modelo actual.

## 2 · Manifiesto

```bash
"Pipeline SSM/run_pipeline.sh" manifest
```

- [ ] Coincide el número de formas y de sujetos con lo esperado (`N shapes of M subjects`).
- [ ] Si el prefijo de los identificadores no es `TMR_`, sigue funcionando (vale cualquier `letras_dígitos`).

## 3 · Preparar y verificar las mallas

```bash
"Pipeline SSM/run_pipeline.sh" clean       # unos 12 s por malla
"Pipeline SSM/run_pipeline.sh" check
```

- [ ] `clean` termina con `N/M meshes`; anotar cuáles se omitieron por estar cortadas en trozos.
- [ ] Revisar `check.csv` y la lista impresa ([03](03-verificacion-y-preparacion.md)). **Ninguna forma señalada se
  excluye sin mirar su malla original**.
- [ ] Ninguna forma con `side does not match its x side`: si aparece, el sistema de coordenadas de la
  exportación no es el esperado y hay que resolverlo antes de seguir.
- [ ] Crear `$SSM_DATA/exclude.txt` con las formas descartadas y su motivo (`TMR_000009_R  # malla
  defectuosa`). **Crearlo siempre en un set nuevo, aunque esté vacío**: sin ese archivo se aplica la lista
  del set actual, con pacientes que no tienen por qué existir (o coincidir) en el nuevo.

## 4 · Modelo

```bash
"Pipeline SSM/run_pipeline.sh" project
"Pipeline SSM/run_pipeline.sh" optimize
"Pipeline SSM/run_pipeline.sh" analyze
"Pipeline SSM/run_pipeline.sh" quality
```

- [ ] `project`: `N subjects, reference …` con el N esperado.
- [ ] `optimize`: `N shapes optimized`.
- [ ] `analyze`: existen `mean_shape_0.vtk` y `analysis.json`.
- [ ] `quality`: **cobertura mínima ≥ 0,85** y sin formas marcadas. Si hay formas marcadas, revisar su malla
  con `check.csv`, excluirlas si su malla es defectuosa y repetir desde `project`.

Criterio de referencia: en el set actual, cobertura mínima 0,92, mediana 0,98 y rugosidad mediana 3,0 mm.

## 5 · Validación

```bash
"Pipeline SSM/run_pipeline.sh" validate --reduced     # K = 34 y 50, reg 10
"Pipeline SSM/run_pipeline.sh" validate               # todas las configuraciones
```

- [ ] Comparar con la referencia sin modelo (`K = 0`): el modelo debe reducir claramente el error (en el
  set actual, de 3,9 a ~2,3 mm).
- [ ] Mirar el error por sitio y radio ([05](05-validacion.md)); comparar con las cifras de referencia de arriba.
- [ ] Si se comparan dos versiones del modelo, usar `tools/compare_validation.py` (mismas formas, diferencia
  con su error estándar).

## 6 · Reconstruir

```bash
"Pipeline SSM/run_pipeline.sh" reconstruct DAMAGED.stl --reference HEALTHY_OTHER_SIDE.stl
```

Ver [06](06-reconstruccion.md).

## Decisiones que hay que volver a tomar con un set nuevo

| Decisión | Qué hicimos y qué revisar |
|---|---|
| **Lados del modelo** (`SSM_SIDES`) | Con este set, solo derechas rindió más que ambos lados ([08](08-historial-y-decisiones.md)). Con otro set no está garantizado: si tiene muchas más formas, repetir la comparación (`SSM_SIDES=LR` frente a `R` y `--eval-sides`). |
| **Exclusiones** | Empezar con un `exclude.txt` vacío y rellenarlo a partir de `check` y `quality`. |
| **Nº de partículas (512)** | Elegido para ~35–40 formas; con muchas más o menos formas, revisar la cobertura. |
| **Modos K y regularización** | K = 34, reg 10 dieron el mismo resultado que valores mayores; con otro tamaño de set, repetir la validación completa y elegir K (limitado a *n* − 2). |
| **Parámetros del optimizador** | Sin cambios desde 2026-09-22; no se afinaron para este set. Si `quality` sale peor que las referencias, es lo primero que hay que tocar. |
| **Radios y sitios de los defectos** | 20/30/40 mm alrededor de ASIS, PSIS, PT y FH; ajustarlos al tipo de defecto real esperado (`src/ssm/defects.py`). |
| **Umbrales de `check`** | Deducidos de este set (landmarks superficiales ≤ 8 mm, FH 15–35 mm); revisar la distribución en el set nuevo antes de fiarse. |

## Limitación: no hay un set de validación independiente

La validación es **dejar un paciente fuera** dentro del propio set de entrenamiento (con la salvedad de que
la forma dejada fuera sí participa en la optimización de partículas; ver [05](05-validacion.md)). El único
caso realmente ajeno al modelo es evaluar izquierdas reflejadas contra un modelo de derechas
(`--eval-sides L`). Si se dispone de pacientes reservados solo para validar, hoy habría que añadirlos a un
set aparte y no hay una opción para evaluarlos con un modelo ya entrenado; sería el siguiente cambio de
código a hacer.

## Tiempos y cifras de control (35 formas derechas, 8 procesos)

Repetición completa de cero, con los datos actuales en `SSM_DATA` separado:

| Etapa | Duración medida |
|---|---|
| `manifest` | < 1 s |
| `clean` (85 mallas) | 17,7 min |
| `check` | 1,4 min |
| `project` | 43 s |
| `optimize` | 8,8 min |
| `analyze` | 1,5 min |
| `quality` | 4 s |
| `validate --reduced` | 2,8 min (886 ajustes) |
| **Total** | ~33 min |

**Resultado de la repetición:** el pipeline es determinista. Las partículas del modelo repetido son
**idénticas** a las del modelo original (diferencia máxima de 0,0000 mm en las 35 formas), el manifiesto y
`check.csv` son idénticos byte a byte, y la validación da el mismo **2,195 mm**. Si al repetir con los
mismos datos algo difiere, hay un cambio en el entorno o en el código.

Cifras que deben salir: `85 shapes of 45 subjects`; `84/85 meshes` (solo `TMR_000031_L` omitida); `16` formas con
señal en `check`; `35 subjects, reference TMR_000014_R`; `coverage min 0.92 median 0.98; roughness median 3.0 max
6.6 mm` con `TMR_000015_R` como única marcada.
