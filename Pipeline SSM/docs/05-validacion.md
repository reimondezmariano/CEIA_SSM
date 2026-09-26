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
  PCA). Los errores son algo optimistas. Para formas que el modelo nunca vio, usar `--eval-sides`.
- **Techo de modos:** al dejar fuera un paciente, cada fold tiene como mucho *n* − 2 modos con varianza
  (33 con 35 formas): en el modelo actual K = 34 y K = 50 se recortan a 33 y dan el mismo resultado.
- **Defectos simulados:** cortes esféricos alrededor de landmarks. Los reales pueden ser irregulares y
  mayores (RMR_000002 rellena el 17 % de la superficie).
- **Tamaño:** un hueso fuera del rango de entrenamiento (RMR_000002 mide 250 mm y el mayor de
  entrenamiento 247 mm) se reconstruye algo más corto en los extremos (~4 % en la versión anterior).
