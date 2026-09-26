# 05 · Validación

Mide cuánto se equivoca la reconstrucción en un caso en que **se conoce la respuesta**: se le quita un
trozo a un hueso sano, se reconstruye y se compara con el hueso original.

```bash
"Pipeline SSM/run_pipeline.sh" validate --reduced     # K = 34 y 50, reg 10: ~3 min con 35 formas
"Pipeline SSM/run_pipeline.sh" validate               # las 11 configuraciones (K = 0, 5, 10, 20, 34, 50 × reg 1, 10)
```

## Diseño

1. **Se deja fuera a un paciente entero** (sus dos lados) y se construye el PCA con el resto. Dejar fuera
   solo la forma probada filtraría información: el otro lado es casi su imagen especular.
2. **Se simulan defectos** (`ssm.defects`): para cada landmark de la forma (ASIS, PSIS, PT, FH) y cada
   radio (20, 30, 40 mm) se elimina el hueso a menos de ese radio del punto de la superficie más cercano
   al landmark y se tapa el hueco, como en las mallas dañadas reales. Hasta 13 casos por forma (uno sin
   defecto más 4 × 3).
3. **Se ajusta el modelo** a lo que queda (`ssm.fit`) con cada configuración (K modos, regularización).
4. **Error** = distancia de la superficie verdadera a la reconstrucción, medida dentro de la zona del
   defecto (`defect_*`) y en todo el hueso (`bone_*`). `K = 0` es la forma media ajustada rígidamente:
   la referencia que cualquier reconstrucción debe superar.

### Cómo ajusta `ssm.fit` (resumen)

- Pose rígida (rotación + traslación, sin escala) y forma regularizada hacia la media (`reg`): el hueco
  se rellena con la forma más plausible compatible con el hueso presente.
- Se ignoran las partículas cuyo punto más cercano del objetivo está lejos o mira en otra dirección
  (normales a más de 60°): están sobre la zona que falta o sobre la tapa del defecto, que no es hueso.
- Emparejamiento en los dos sentidos, para que el modelo no resbale a lo largo del hueso.
- El umbral de distancia se **recuece** de 40 a 10 mm: un hueso mucho mayor o menor que la media se
  acerca primero a su tamaño y luego se afina; con un umbral estrecho desde el principio el ajuste se
  queda cerca del tamaño medio.
- La superficie final es la malla media deformada (thin-plate spline) por las partículas ajustadas.

## Opciones de `ssm.validate`

| Opción | Efecto |
|---|---|
| `--reduced` | solo K = 34 y 50 con reg 10 (5 veces menos trabajo) |
| `--sides R` | entrena el PCA y evalúa solo con formas de ese lado |
| `--eval-sides L` | evalúa formas que **no** están en el modelo (p. ej. izquierdas reflejadas contra un modelo de derechas) |
| `--eval-shapes A,B` | evalúa esas formas por nombre, sin quitar ninguna del modelo: para pacientes reservados (`SSM_HOLDOUT`) |

El archivo de salida se nombra según la combinación, dentro de `data/reconstruction/` (más el nombre del
proyecto si `SSM_PROJECT` está definido):
`validation.csv`, `validation_reduced.csv`, `validation_sidesR.csv`, `validation_reduced_evalL.csv`…
Columnas: `shape, site, radius, modes, reg, bone_mean, bone_p95, defect_mean, defect_p95, defect_max`.
Al terminar imprime una tabla resumen.

**Duración** (8 procesos, un hilo cada uno): ~3 min la versión reducida con 35 formas y ~6 min con 66;
la completa, del orden de 15–20 min con 35 formas. Si tarda horas, casi seguro hay sobresuscripción de
hilos ([00](00-entorno.md)).

## Cifras del modelo actual (35 derechas, K = 34, reg 10)

Error medio en la zona del defecto, en mm:

| Sitio del defecto | 20 mm | 30 mm | 40 mm |
|---|---|---|---|
| ASIS (espina anterior) | 2,38 | 2,18 | 2,03 |
| **FH (acetábulo)** | **1,73** | **1,74** | **1,77** |
| PSIS (espina posterior) | 2,27 | 2,35 | 2,46 |
| PT (tubérculo púbico) | 2,59 | 2,41 | 2,53 |

- Todos los defectos: media **2,20 mm**, mediana 1,95, percentil 95 de 3,95; el peor defecto simulado
  tiene media 6,8 mm (máximo puntual de 19 mm). Sin defecto, el error de todo el hueso es de 1,36 mm.
- Sobre las 36 formas **izquierdas** reflejadas (que el modelo no vio): 2,23 mm de media.
- Referencia sin modelo (`K = 0`, medida con el modelo de ambos lados): 3,9 mm en la zona del defecto,
  frente a 2,3 mm del modelo: el error baja un ~40 %.
- Más modos casi no ayudan: en el modelo de ambos lados, K = 34 da 2,32 mm y K = 50 da 2,30 mm.
  La regularización (1 frente a 10) casi no cambia nada (2,31 frente a 2,32 mm). Por eso se usan K = 34 y
  reg 10 por defecto (`ssm.reconstruct`).

## Validación con pacientes reservados

La validación dejando un paciente fuera tiene un sesgo: la forma probada sí participó en la optimización de
partículas. Para medirlo se reservan pacientes **antes de entrenar**, de modo que el modelo (incluida la
optimización) no los ve nunca:

```bash
export SSM_PROJECT=shapeworks_project_holdout5
export SSM_HOLDOUT=TMR_000004,TMR_000018,TMR_000019,TMR_000021,TMR_000047      # uno o varios, separados por comas
for s in project optimize analyze quality; do "Pipeline SSM/run_pipeline.sh" $s; done      # ~12 min
"Pipeline SSM/run_pipeline.sh" validate --reduced --eval-shapes \
    TMR_000004_R,TMR_000004_L,TMR_000018_R,TMR_000018_L,TMR_000019_R,TMR_000019_L,TMR_000021_R,TMR_000021_L,TMR_000047_R,TMR_000047_L
python "Pipeline SSM/tools/holdout_report.py" \
    data/reconstruction/validation_reduced_evalshapes_holdout5.csv \
    data/reconstruction/validation_reduced_right.csv data/reconstruction/validation_reduced_evalL_right.csv
```

`SSM_HOLDOUT` excluye a los pacientes (los dos lados) al construir el proyecto; `--eval-shapes` los evalúa con
los mismos defectos simulados. El informe compara, para cada forma, el error reservado con el de dejar uno
fuera y dice dónde cae respecto al resto de formas. La validación tarda ~3 min con 10 formas.

**Cómo se eligieron los pacientes:** para no elegirlos por su resultado, se listaron los pacientes elegibles
(los dos lados con malla preparada, los 4 landmarks en cada lado, ninguna señal en `check`, lado derecho dentro
del modelo: 22 pacientes) y se sortearon con semilla fija. Primero salió `TMR_000018` (`random.Random(2026)`,
razón de volumen 1,01) y se usó como comprobación con un solo paciente. Después se ampliaron a 5 (14 % de los
35 pacientes con lado derecho en el modelo) sorteando 4 más entre los 21 restantes con
`random.Random(2027).sample`: `TMR_000004`, `TMR_000019`, `TMR_000021` y `TMR_000047`. Se decidieron antes de
ver ningún resultado. El modelo entrenado sin ellos tiene 30 formas derechas (cobertura mínima 0,94,
rugosidad mediana 2,8 mm).

**Resultado (K = 34, reg 10; error medio en la zona del defecto, 12 defectos por forma):**

| Forma | Paciente reservado | Dejando uno fuera |
|---|---|---|
| `TMR_000004_R` / `_L` | 2,48 / 2,23 mm | 2,20 / 2,16 mm |
| `TMR_000018_R` / `_L` | 2,60 / 2,66 mm | 2,52 / 2,90 mm |
| `TMR_000019_R` / `_L` | 2,12 / 1,32 mm | 2,03 / 1,26 mm |
| `TMR_000021_R` / `_L` | **4,76 / 5,13 mm** | 3,38 / 3,59 mm |
| `TMR_000047_R` / `_L` | 2,43 / 2,58 mm | 1,72 / 2,11 mm |
| **Media de las 10 formas** | **2,83 mm** | **2,39 mm** |
| Media sin `TMR_000021` (8 formas) | 2,30 mm | 2,11 mm |

(Las izquierdas están reflejadas sobre el modelo de derechas.)

- Media de las 10 formas: **2,83 mm reservado frente a 2,39 mm dejando uno fuera**; diferencia pareada
  +0,44 ± 0,19 mm (error estándar sobre 10 formas, que no son independientes: cada paciente aporta dos).
  Derechas 2,88 frente a 2,37 mm; izquierdas reflejadas 2,78 frente a 2,41 mm.
- Sin defecto, error en todo el hueso: 1,54 mm reservado frente a 1,35 mm dejando uno fuera.
- Por zona (media sobre las 10 formas y los tres radios): ASIS 3,10 frente a 2,65 mm, FH (acetábulo) 1,74
  frente a 1,50 mm, PSIS 2,30 frente a 2,16 mm, PT 4,18 frente a 3,25 mm. El acetábulo, que es lo que interesa
  reconstruir, se mantiene por debajo de 2 mm; el pubis (PT) es la zona más difícil.
- El defecto simulado peor tiene una media de 9,3 mm reservado (6,6 mm dejando uno fuera).

**Cómo leerlo:**
- El sesgo de dejar uno fuera es de **~0,2 mm para un paciente típico** (8 formas sin `TMR_000021`: 2,30 frente
  a 2,11 mm), coherente con la comprobación de un paciente. Una estimación honesta del error en un paciente
  nuevo es **2,3–2,8 mm** en la zona del defecto, frente a los 2,2 mm de dejar uno fuera sobre todo el set.
- **`TMR_000021` es la excepción** (4,8–5,1 mm; ya era de las peores dejando uno fuera: 3,4 mm, 3.ª de 35 derechas, y 3,6 mm,
  2.ª de 36 izquierdas) y explica la mayor parte de la diferencia. Es un hueso grande (478 y 501 cm³, frente a una mediana de
  313 cm³ y un máximo de 559 cm³ entre las 35 derechas); una posible explicación es que hay pocos huesos así en
  el entrenamiento, pero no se ha comprobado. No tiene señales en `check` ni razón de volumen extrema (1,05).
  Conviene que quien conoce la exportación revise esas dos mallas en origen.
- **Sigue siendo una muestra pequeña**: 5 pacientes, 10 formas muy correlacionadas dos a dos, y un solo caso
  atípico mueve la media 0,5 mm. Además, el modelo sin ellos tiene 30 formas en lugar de 35, así que es algo
  pesimista respecto al modelo final. Y una forma concreta cambia hasta 0,4 mm entre dos ejecuciones distintas
  de la optimización (`TMR_000018_L`: 3,05 mm con el modelo reservado de un paciente y 2,66 mm con el de cinco):
  las cifras por forma son ruidosas, solo las medias son útiles.
- Para estrechar la estimación hay que reservar más pacientes (≥ 10–15 % del set de entrenamiento, con
  el criterio de arriba); ampliar el set con pacientes nuevos es mejor todavía.

## Cómo leer los resultados y comparar modelos

Comparar dos validaciones sobre **las mismas formas** y con la diferencia acompañada de su error
estándar:

```bash
python "Pipeline SSM/tools/compare_validation.py" --side R --modes 34 \
    data/reconstruction/validation_71.csv  data/reconstruction/validation_reduced.csv
```

Imprime el error medio de cada archivo, la diferencia pareada con el primero (± error estándar sobre
las formas) y en cuántas formas mejora o empeora. Una diferencia menor que ~2 veces su error estándar no
se distingue del ruido con tan pocas formas.

## Limitaciones a tener presentes

- **Optimismo:** la forma dejada fuera participó en la optimización de partículas (solo se quita del
  PCA). Los errores son algo optimistas: con cinco pacientes reservados salió ~0,2 mm más para un paciente
  típico y 0,4 mm de media (ver arriba). Para
  formas que el modelo nunca vio, usar `--eval-sides` o `--eval-shapes` con `SSM_HOLDOUT`.
- **Techo de modos:** al dejar fuera un paciente, cada fold tiene como mucho *n* − 2 modos con varianza
  (33 con 35 formas): en el modelo actual K = 34 y K = 50 se recortan a 33 y dan el mismo resultado.
- **Defectos simulados:** cortes esféricos alrededor de landmarks. Los reales pueden ser irregulares y
  mayores (RMR_000002 rellena el 17 % de la superficie).
- **Tamaño:** un hueso fuera del rango de entrenamiento (RMR_000002 mide 250 mm y el mayor de
  entrenamiento 247 mm) se reconstruye algo más corto en los extremos (~4 % en la versión anterior).
