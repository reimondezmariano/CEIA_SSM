# 01 · Exportación de las caderas

Es el punto de partida y ocurre **fuera de este repositorio**. Aquí se documenta lo que el pipeline
**exige** de los archivos exportados (deducido del código y comprobado con `ssm.check`) y se deja
marcada la parte que solo puede describir quien hace la exportación.

> ⚠️ **Pendiente de completar:** el procedimiento de exportación (software, cómo se segmenta cada
> hemipelvis, cómo se define el sistema de coordenadas «alineado», ajustes de exportación) no está
> registrado en ninguna parte del repositorio. La plantilla de la sección final debe rellenarla quien
> lo conoce. Todo lo demás en esta guía depende de que se cumpla lo de abajo.

## Qué hay que entregar por cada sujeto

1. **Una malla STL por hemipelvis** (izquierda y/o derecha) en una única carpeta (`SSM_MESH_DIR`,
   por defecto `~/DataSet`).
2. **Un CSV de landmarks por sujeto** en otra carpeta (`SSM_LANDMARK_DIR`, por defecto
   `~/Landmarks_aligned`). Solo se usa para validar y verificar; el modelo no lo necesita.

### Nombre de las mallas

El pipeline extrae dos cosas del nombre (`ssm.manifest`):

- el **identificador de sujeto**: lo que hay al principio, letras + `_` + dígitos (`TMR_000004`);
- el **lado**: la cadena `pelvis_left` o `pelvis_right` en cualquier lugar del nombre.

Ejemplos reales, todos válidos:

```
TMR_000004_raw_4_pelvis_left_aligned.stl
TMR_000004_raw_5_pelvis_right_aligned.stl
TMR_000008_raw_4_TMR_000008_pelvis_right_aligned.stl
```

El resto del nombre (`raw_4`, `aligned`…) es libre. Solo se leen los `*.stl`. Para las reconstrucciones
de casos dañados, el nombre solo necesita contener `pelvis_left` o `pelvis_right`.

### Sistema de coordenadas: lo más importante

Las mallas deben estar en el **mismo sistema «alineado»**, en **milímetros**, con el plano
**sagital medio en x = 0**:

- la hemipelvis **derecha queda en x < 0** y la **izquierda en x > 0**;
- los dos lados de un sujeto comparten el mismo sistema.

Por eso un lado izquierdo se convierte en derecho con el simple reflejo x → −x (`ssm.clean`), y por eso
después de reconstruir un izquierdo se vuelve a reflejar. `ssm.check` marca `side does not match its x
side` si el lado del nombre no coincide con el signo de x de la malla. La alineación fina entre sujetos
(rotación y traslación residuales) la resuelve el registro rígido de ShapeWorks; una diferencia
grosera de orientación no.

### Calidad esperable de cada malla

- **Una sola pieza cerrada.** `ssm.clean` conserva la mayor, rellena agujeros pequeños y descarta
  cascarones sueltos. Si la segunda pieza más grande tiene ≥ 10 % de las caras (`SEVERED_SHELL_FRACTION`),
  el hueso está cortado en trozos: la forma se **excluye** en vez de repararla (unirla exigiría un cierre
  volumétrico de ~25 min que además cuantiza toda la superficie).
- Malla de cualquier densidad (se remuestrea a 25 000 vértices), pero **sin defectos que no sean
  anatómicos**: si el hueso falta por un fallo de segmentación, el modelo lo aprende como forma.
- Tamaño del orden de 250 mm de largo por hemipelvis.

### CSV de landmarks

Una fila por sujeto (`ssm.manifest` usa la primera), archivo `<sujeto>_landmarks_aligned.csv`, con
columnas `<LANDMARK>_<L|R>_<x|y|z>`, en el mismo sistema que las mallas. Los usados son:

| Landmark | Dónde está | Relación con la superficie |
|---|---|---|
| `ASIS` | espina ilíaca anterosuperior | sobre el hueso |
| `PSIS` | espina ilíaca posterosuperior | sobre el hueso |
| `PT` | tubérculo púbico | sobre el hueso |
| `FH` | centro de la cabeza femoral | a ~24 mm de la superficie (el radio del acetábulo) |

`GT`, `LT` (femorales) y `Coccyx` (línea media) pueden estar en el archivo pero no se usan. Las celdas
vacías están permitidas: ese landmark simplemente no genera defectos simulados. Cada lado usa sus
columnas (`ASIS_L_…` para la izquierda, `ASIS_R_…` para la derecha).

Los defectos simulados de la validación se centran en estos puntos, así que un landmark mal colocado
hace que se valide en un sitio equivocado. `ssm.check` mide su distancia a la superficie.

## Casos dañados (los que se reconstruyen)

Van en otra carpeta (`~/DataSet_damaged`), con el mismo formato de nombre, y **no** entran en el
manifiesto ni en el entrenamiento: `RMR_000008_raw_1_pelvis_right_aligned.stl` (lado dañado),
`RMR_000008_raw_5_pelvis_left_aligned.stl` (lado sano, opcional, como referencia).

## Plantilla: procedimiento de exportación (a completar)

| Punto | Descripción |
|---|---|
| Origen de los datos (estudio, TC, resolución) | *pendiente* |
| Software y versión | *pendiente* |
| Cómo se obtiene cada hemipelvis (segmentación, revisión) | *pendiente* |
| Cómo se define el sistema «alineado» (qué puntos o planos fijan los ejes) | *pendiente* |
| Cómo se colocan los landmarks | *pendiente* |
| Ajustes de exportación STL (binario/ASCII, suavizado, decimación) | *pendiente* |
| Convención de nombres y numeración (`raw_4`, `raw_5`…) | *pendiente* |
| Comprobaciones antes de entregar | *pendiente* |
