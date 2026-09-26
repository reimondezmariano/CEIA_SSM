# 09 · Diseño de la exportación (borrador)

Estado: **borrador para acordar antes de escribir código**. Parte de que el material de origen son
**mallas STL ya generadas, sin alinear**, que están en otro equipo o en la nube. Sustituirá a la plantilla vacía
de [01](01-exportacion.md) cuando esté decidido.

## Lo que se sabe del sistema «alineado» (deducido de los 48 CSV de landmarks)

No estaba escrito en ninguna parte; se ha inferido de `~/Landmarks_aligned` y se cumple en los 48 sujetos
(con precisión de máquina, ~1e-14 mm):

| Propiedad | Valor observado |
|---|---|
| Origen | **centroide** de `ASIS_L`, `ASIS_R`, `PT_L`, `PT_R` (la suma de los cuatro es exactamente 0) |
| Eje x | paralelo a la línea `ASIS_R → ASIS_L` (las dos ASIS tienen la misma `y` y la misma `z`); **izquierda = +x** |
| Plano y = 0 | contiene `ASIS_L`, `ASIS_R` y el punto medio de `PT_L`/`PT_R`: es el **plano pélvico anterior** (APP) |
| Eje z | dentro del plano APP, perpendicular a x, **superior = +z** (ASIS ≈ +47 mm, PT ≈ −47 mm) |
| Eje y | normal al plano APP; **posterior = +y** (cóccix ≈ +122 mm, centro de la cabeza femoral ≈ +52 mm) |
| Lateralidad | terna directa (una rotación propia, sin reflejo): un lado izquierdo se convierte en derecho con x → −x |

**Comprobado con datos reales:** con `TMR_000004_landmarks_raw.csv` (coordenadas de origen) la definición siguiente
reproduce los 13 landmarks de `TMR_000004_landmarks_aligned.csv` con un error máximo de 3e-14 mm:

```
o  = (ASIS_L + ASIS_R + PT_L + PT_R) / 4
x  = unit(ASIS_L − ASIS_R)
v  = (ASIS_L + ASIS_R)/2 − (PT_L + PT_R)/2            # de púbico a espinas, dentro del plano APP
z  = unit(v − (v·x) x)                                 # superior
y  = z × x                                             # posterior
alineado = [x; y; z] · (punto − o)                     # rotación propia (det = +1), sin escalado
```

Es, por tanto, el sistema del **plano pélvico anterior** (APP, casi el plano frontal del paciente), como se
sospechaba.

Consecuencia para la documentación: «plano sagital medio en x = 0» es solo aproximado. El origen es el centroide
de cuatro puntos, no el punto medio de las ASIS, y el punto medio de las ASIS se desvía hasta 6 mm de x = 0.
Lo que exige el pipeline (derecha en x < 0, izquierda en x > 0) sí se cumple.

## Qué tendría que hacer la exportación

Por cada paciente, con la malla de origen y sus landmarks en el **mismo** sistema de coordenadas de origen:

1. **Identificar y renombrar.** El CSV usa el identificador original (`SA250167`) y las mallas el seudónimo
   (`TMR_000004`). La tabla de equivalencias es información identificable: debe quedar **fuera del repositorio**.
2. **Landmarks.** Alinear solo necesita `ASIS_L/R` y `PT_L/R`; la validación usa además `PSIS` y `FH`
   (`GT`, `LT`, `Coccyx` se guardan pero no se usan). Cómo se colocan es la decisión más importante (ver abajo).
3. **Calcular la transformación rígida** al sistema de arriba (sin escalado; el tamaño en mm se conserva).
4. **Aplicarla** a las mallas y a todos los landmarks del paciente.
5. **Separación en hemipelvis: no hace falta.** Las mallas de origen ya vienen separadas por hemipelvis
   (respuesta del usuario). Se exige que las dos hemipelvis de un paciente estén en el mismo sistema de origen
   que sus landmarks, para poder aplicarles la misma transformación.
6. **Escribir** `<ID>_raw_<n>_pelvis_<left|right>_aligned.stl` y `<ID>_landmarks_aligned.csv` según el contrato de [01](01-exportacion.md).
7. **Comprobar antes de entregar** con el mismo `ssm.check`: lado coherente con el signo de x, una sola pieza,
   landmarks sobre la superficie (ASIS/PSIS/PT < 8 mm; FH a 15–35 mm) y razón de volumen izquierda/derecha.
   Registrar versión del software, parámetros y suma de verificación de cada archivo.

## Propuesta técnica

- Un módulo `src/ssm/export.py` con dependencias mínimas (numpy y trimesh), para poder ejecutarlo donde estén los
  datos sin instalar ShapeWorks.
- **Alineación como función pura** `app_frame(asis_l, asis_r, pt_l, pt_r) -> (R, t)`: se prueba sin datos reales
  (a) reproduciendo las propiedades de la tabla de arriba con landmarks al azar y una transformación rígida
  cualquiera, y (b) comprobando que aplicada a los landmarks **ya alineados** de `~/Landmarks_aligned` devuelve la
  identidad. La (b) es la prueba de que la definición es la misma que se usó al crear el set actual.
- Entrada y salida en carpetas configurables (`SSM_EXPORT_IN`, `SSM_MESH_DIR`, `SSM_LANDMARK_DIR`), como el resto.
- Registro de exportación (`export_log.csv`): archivo de origen, transformación aplicada, resultado de las comprobaciones.

## Entrada de landmarks automáticos

Los landmarks los produce el autosegmentador (otro proyecto; aquí solo se consume su CSV, no su código).
Como **toda la alineación depende de cuatro de ellos** (`ASIS_L/R`, `PT_L/R`), un landmark automático erróneo
inclina el sistema entero y contamina esa hemipelvis y el modelo. Por eso la exportación no debe fiarse del CSV
sin comprobarlo. Comprobaciones propuestas, antes y después de alinear:

| Comprobación | Rango observado en los 48 sujetos actuales (mínimo – mediana – máximo) |
|---|---|
| Distancia `ASIS_L`–`ASIS_R` | 190 – 228 – 281 mm |
| Distancia `PT_L`–`PT_R` | 37 – 50 – 73 mm |
| Punto medio ASIS a punto medio PT | 69 – 95 – 113 mm |
| Distancia `FH` a `ASIS` del mismo lado | 62 – 96 – 113 mm |
| Landmarks sobre la superficie de su hemipelvis | ASIS/PSIS/PT < 8 mm; FH a 15–35 mm (`ssm.check`) |
| Lado coherente | el lado del nombre coincide con el signo de x tras alinear |

Son rangos observados en pocos sujetos, no umbrales validados: sirven para **marcar** casos a revisar a mano,
no para rechazarlos automáticamente. Los datos actuales tienen celdas vacías en los demás landmarks (`FH` 1,
`GT` 3–4, `LT` 2, `PSIS` 4, `Coccyx` 2 de 48), pero **ninguna** en las ASIS y PT: si faltara alguna de las cuatro,
esa hemipelvis no se puede alinear y se marca en lugar de exportarla.

Lo que necesito ver: **un CSV de ejemplo del autosegmentador** (cabecera y una fila, sin datos identificables si
prefieres): nombres de columnas, si hay un CSV por paciente o uno para todos, cómo se identifica al paciente
(`case_id`) y en qué coordenadas están (las mismas que sus STL).

## Decisiones abiertas (necesito tu respuesta)

1. ~~Origen: pelvis completa o hemipelvis~~ **Resuelto:** ya vienen separadas por hemipelvis. Queda confirmar
   que las dos de un mismo paciente comparten sistema de coordenadas de origen (si cada una está centrada por
   separado, no se puede alinear el par).
2. ~~Landmarks~~ **Resuelto en principio:** llegan listados en un CSV generado por el autosegmentador automático,
   en las coordenadas de origen. Falta ver un ejemplo de ese CSV (ver «Entrada de landmarks automáticos»).
3. **Casos dañados (`RMR_…`).** Los dos casos actuales se alinearon **con el mismo APP** y con los cuatro puntos
   (`RMR_000002`: 270 mm entre ASIS, `RMR_000008`: 199 mm; en ambos la suma de los cuatro puntos es 0 y las
   ASIS comparten y y z). Solo faltan landmarks en zonas dañadas (`FH_L` y `FH_R`, `GT_L`, `LT_L/R` en
   `RMR_000002`), no ASIS ni PT. Si el autosegmentador entrega las cuatro, no hace falta un método distinto. Si
   falta alguna (hueso perdido en la ASIS o el pubis), queda por decidir: estimarla reflejando la del lado sano
   (necesita una línea media) o alinear con otros puntos. Propuesta: marcar el caso, no inventar el punto.
4. **¿Pueden salir los datos de su equipo?** Si no, el módulo se ejecuta allí y aquí solo entra el resultado;
   condiciona las dependencias y cómo lo pruebo.
5. **Identificadores:** ¿quién mantiene la tabla original ↔ `TMR_`/`RMR_`, y qué numeración usan los archivos nuevos?
