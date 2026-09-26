# 08 · Historial y decisiones

Cómo se llegó al pipeline actual, en orden, con lo que se probó y **lo que no funcionó**. Las fechas son
las de los commits del repositorio (2026). Sirve para no repetir pruebas y para saber qué decisiones
volver a tomar con un set nuevo.

## Cronología

| Fecha | Qué se hizo |
|---|---|
| 09-19 | Instalación de ShapeWorks 6.7.0 y del entorno conda ([00](00-entorno.md)) |
| 09-21 | Esqueleto del repositorio; **manifiesto** de sujetos (`ssm.manifest`); **limpieza** de mallas (`ssm.clean`); las mallas cortadas en trozos se excluyen en vez de repararse |
| 09-22 | **Proyecto de ShapeWorks** con alineación rígida (`ssm.project`); primer modelo de solo derechos (36 formas) |
| 09-23 | Se excluyen formas con cobertura de partículas incompleta |
| 09-24 (madrugada) | **Puntuación de calidad** de la correspondencia (`ssm.quality`); se excluyen las formas derechas con mallas fuente defectuosas; **ajuste del modelo a huesos parciales** con validación dejando uno fuera (`ssm.fit`, `ssm.validate`); **reconstrucción de casos dañados** (`ssm.reconstruct`); primeros STL enviados |
| 09-24 (tarde) | Se **añaden los lados izquierdos** reflejados: modelo de ambos lados de 80 formas; la validación deja fuera a los dos lados de cada paciente |
| 09-24/25 | Exclusiones sucesivas de formas y pacientes (landmarks que no corresponden, correspondencias rugosas): 80 → 73 → 71 formas |
| 09-25 | Validación con 50 modos |
| 09-26 | Se acelera la validación (un hilo por proceso); **experimentos** para entender por qué ambos lados no mejoran; **modelo definitivo de solo derechos**; reconstrucciones nuevas enviadas; se estructura el pipeline (`ssm.check`, `run_pipeline.sh`, variables de entorno, esta documentación) |

## Decisiones y su razón

**Sin escalado (`procrustes_scaling 0`).** El tamaño absoluto en mm importa para reconstruir y para
comparar grupos; el escalado lo descartaría.

**512 partículas, con normales (fuerza 10).** El ala ilíaca es fina y sin normales se emparejan
partículas de caras opuestas.

**Un hilo por proceso en la validación.** Sin eso era ~10 veces más lenta (8 procesos × 8 hilos en 8 CPU
lógicas). Una validación completa llegó a pasar de 5 h; en realidad son minutos.

**Formas excluidas.** Cada exclusión se decidió por una señal concreta (cobertura, rugosidad, componente
dominante de PC1/PC2, landmarks que no corresponden a la malla) y se revisó con quien conoce los casos;
la lista y los motivos están en [03](03-verificacion-y-preparacion.md). La validación deja de ser
comparable cada vez que cambia el conjunto de formas, por eso se compara siempre sobre las formas comunes.

**Modelo solo de derechos** (la decisión más importante, tomada con los experimentos de abajo).

## Experimentos y resultados

Todas las cifras son el error medio en la zona del defecto (mm), con K = 34 y reg 10, validando dejando
fuera al paciente.

### 1. ¿Entrenar con ambos lados mejora el modelo? — No

Modelo de ambos lados (71 formas) frente al primer modelo de solo derechos (36 formas), sobre las 35
formas derechas comunes: **2,40 frente a 2,19 mm**. Con 50 modos, 2,30 en todo el conjunto: tampoco ayuda.
No había diferencia sistemática entre lados (desplazamiento medio L − R de 0,93 mm frente a 1,16 mm entre
mitades al azar) y la distancia entre los dos lados de un mismo paciente (2,9 mm) es mucho menor que entre
pacientes (7,4 mm), por lo que el reflejo es válido; la causa era otra.

### 2. ¿Se debe a las formas con asimetría de volumen extrema? — No

Todas las formas excluidas estaban en un extremo de la razón de volumen izquierdo/derecho del paciente
(0,78–1,37). Se excluyó el lado más pequeño de los cinco pacientes más asimétricos (66 formas): **2,34 frente
a 2,31 mm** sobre las mismas formas; en 27 formas mejoró y en 39 empeoró. Descartado.

### 3. Separar «datos» de «optimización» — la correspondencia es la causa

Sobre las mismas 35 formas derechas:

| Modelo | Correspondencia entrenada con | PCA con | Error |
|---|---|---|---|
| A | solo derechas | solo derechas | **2,195** |
| B | ambos lados | solo derechas | 2,473 |
| 71 | ambos lados | ambos lados | 2,397 |
| 36 (antiguo) | solo derechas | solo derechas | 2,190 |

- A iguala al modelo antiguo → los ajustes de hoy, las mallas y el código de ajuste **no** son el problema
  (las mallas «verdad» de tres formas comprobadas son idénticas en ambos modelos, y `fit.py` no cambió).
- A frente a 71: −0,20 ± 0,05 mm (mejor en 25 de 35 formas): **optimizar las correspondencias con ambos
  lados a la vez las empeora**.
- B frente a 71: +0,08 ± 0,03 mm: añadir izquierdos reflejados al PCA solo no perjudica (ayuda algo).

### 4. ¿Sirve el modelo de derechos para izquierdos? — Sí

Sobre las 36 formas izquierdas reflejadas, que A nunca vio: **A 2,233 mm frente a 2,229 del modelo de ambos
lados** (diferencia +0,005 ± 0,051). Empatan, y la comparación favorecía al de ambos lados (esas formas
participaron en su optimización). Con eso, un solo modelo de derechos cubre los dos lados.

### 5. ¿Están inflados los resultados por dejar uno fuera? — Poco (con un solo paciente)

Se reservó un paciente antes de entrenar (`TMR_000018`, sorteado entre 22 elegibles) y se reconstruyó el
modelo sin él, con optimización incluida. Error en la zona del defecto: **2,61 mm** (derecha) y **3,05 mm**
(izquierda reflejada), frente a 2,52 y 2,90 mm que daba dejar uno fuera para las mismas formas, es decir,
0,1–0,2 mm más. Este paciente es más difícil que la mediana (percentil 86–89 de las formas), y es solo uno:
comprobación de plausibilidad, no estimación ([05](05-validacion.md)).

## Cómo repetir los experimentos

Con el modelo definitivo como modelo por defecto (`data/shapeworks_project`) y el de ambos lados archivado
en `data/shapeworks_project_71`:

```bash
# A: modelo de derechas evaluado sobre derechas (es el modelo por defecto)
"Pipeline SSM/run_pipeline.sh" validate --reduced
# A sobre izquierdas reflejadas, que el modelo nunca vio
"Pipeline SSM/run_pipeline.sh" validate --reduced --eval-sides L
# B: correspondencia de ambos lados, PCA y evaluación solo con derechas
SSM_PROJECT=shapeworks_project_71 SSM_SIDES=LR "Pipeline SSM/run_pipeline.sh" validate --reduced --sides R
# Comparar (mismas formas, diferencia con su error estándar)
python "Pipeline SSM/tools/compare_validation.py" --side R --modes 34 ARCHIVO_BASE.csv OTRO.csv
```

Los archivos de esa época en `data/reconstruction/` conservan su nombre original:

| Archivo | Contenido |
|---|---|
| `validation_36.csv` | primer modelo de solo derechas (36 formas), K hasta 34 |
| `validation_71.csv` | modelo de ambos lados (71 formas), todas las configuraciones |
| `validation_reduced_66.csv` | experimento de la razón de volumen (66 formas) |
| `validation_reduced_right.csv` | **A** sobre derechas (modelo actual) |
| `validation_reduced_evalL_right.csv` | A sobre izquierdas reflejadas |
| `validation_reduced_sidesR.csv` (y `_sidesR_71.csv`, repetición con los nombres actuales) | **B** sobre derechas |
| `validation_reduced_sidesR_evalL.csv` | B sobre izquierdas reflejadas |
| `validation_reduced_evalshapes_holdout.csv` | paciente reservado `TMR_000018` (modelo sin él) |

## Lo que no funcionó (o no se usa) y por qué

| Intento | Resultado |
|---|---|
| Distancia geodésica en la optimización | se queda sin memoria (16 GB) con ~40 mallas de 25 000 vértices |
| Reparar mallas cortadas en trozos con cierre volumétrico | ~25 min por malla y cuantiza toda la superficie: se excluyen |
| Ajustar los parámetros del optimizador para «salvar» las formas derechas defectuosas | ninguno logró buena cobertura o correspondencia: se excluyeron |
| Modelo de ambos lados (71 formas) | peor en derechos que el de solo derechos |
| Excluir por razón de volumen izquierdo/derecho | sin mejora |
| Más de 34 modos | casi sin mejora (2,32 → 2,30 mm) |
| Regularización 1 frente a 10 | sin diferencia apreciable (2,31 frente a 2,32 mm) |

## Preguntas abiertas

- **Por qué la correspondencia de ambos lados es peor.** Se sabe que lo es, no por qué (por ejemplo, si
  ShapeWorks separa los dos lados en dos «clústeres» dentro del mismo modelo). No se ha investigado.
- **Los parámetros del optimizador** no se han vuelto a ajustar desde el 2026-09-22.
- **Validación independiente con más pacientes.** Solo se ha reservado un paciente; una estimación fiable
  necesita reservar varios (≥ 10–15 % del set). Además de eso, los izquierdos reflejados frente a un modelo
  de derechas y los dos casos reales (sin verdad conocida) son lo único que el modelo no vio.
- **El procedimiento de exportación** de las mallas no está documentado en el repositorio ([01](01-exportacion.md)).
