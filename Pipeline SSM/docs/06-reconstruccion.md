# 06 · Reconstrucción de una hemipelvis dañada

```bash
"Pipeline SSM/run_pipeline.sh" reconstruct DAMAGED.stl [--reference HEALTHY_OTHER_SIDE.stl] [--modes 34] [--reg 10]
```

Ejemplo real (lado derecho dañado, lado izquierdo sano como referencia):

```bash
D=~/DataSet_damaged
"Pipeline SSM/run_pipeline.sh" reconstruct $D/RMR_000008_raw_1_pelvis_right_aligned.stl \
                                           --reference $D/RMR_000008_raw_5_pelvis_left_aligned.stl
```

## Qué necesita

- La malla dañada en el **mismo sistema alineado** que el set de entrenamiento (ver
  [01](01-exportacion.md)) y con `pelvis_left` o `pelvis_right` en el nombre.
- Opcionalmente, el **lado sano del mismo paciente** como referencia (`--reference`).
- El modelo ya construido (`analyze` hecho): usa `data/shapeworks_project/`.

## Qué hace (`ssm.reconstruct`)

1. **Carga la malla dañada:** conserva todas las piezas reales (solo descarta las de menos del 1 % de las
   caras), la suaviza y remuestrea igual que las mallas de entrenamiento.
2. **Si es un lado izquierdo, la refleja** (x → −x) para llevarla al marco del modelo de derechas.
3. **Ajusta el modelo** a esa malla con `ssm.fit` (K = 34 modos, reg 10 por defecto; ver
   [05](05-validacion.md)).
4. **Construye la superficie completa** deformando la malla media y marca qué parte está a más de 5 mm de
   la entrada: es el **hueso rellenado**.
5. **Deshace el reflejo** si era izquierdo, de modo que la salida queda en el sistema de la entrada.
6. Con `--reference`, compara la reconstrucción con el lado sano reflejado.

## Salidas (`data/reconstruction/`)

- `<caso>_<lado>.stl`: la hemipelvis **completa** reconstruida (STL binario), p. ej. `RMR_000008_right.stl`.
- `<caso>_<lado>.png`: fila superior, la malla de entrada en gris con el hueso rellenado en naranja, vista
  desde ambos lados; con `--reference`, fila inferior con la reconstrucción coloreada por la distancia
  al lado sano reflejado (0–10 mm).
- En consola, un informe:

| Campo | Significado | Cómo leerlo |
|---|---|---|
| `pieces` | piezas reales en la malla de entrada | > 1 si el hueso dañado está partido |
| `fit_rms` | error cuadrático medio (mm) de las partículas emparejadas | 1,15–1,20 mm en los dos casos reales; no hay un umbral validado |
| `matched` | fracción de partículas que encontraron hueso | baja cuanto mayor es el defecto |
| `b` | primeros coeficientes, en desviaciones típicas | cuanto mayor, más se aleja el hueso de la media (primer modo en los dos casos reales: −0,9 y 1,5) |
| `filled_fraction` | parte de la superficie reconstruida a > 5 mm de la entrada | tamaño del hueso rellenado |
| `vs_reference_*` | distancia al lado sano reflejado (todo el hueso / zona rellenada: media y p95) | comprobación de plausibilidad |

Si se usa un modelo de un experimento (`SSM_PROJECT` definido), el nombre de salida lleva el nombre del
proyecto como sufijo para no pisar los resultados del modelo principal.

## Casos reconstruidos con el modelo actual

| Caso | Lado dañado | `fit_rms` | `matched` | `filled_fraction` | vs. sano (todo el hueso) | vs. sano (zona rellenada) |
|---|---|---|---|---|---|---|
| RMR_000008 | derecho | 1,20 mm | 84 % | 3 % | 3,11 mm | 4,93 mm (p95 11,8) |
| RMR_000002 | izquierdo | 1,15 mm | 75 % | 17 % | 2,87 mm | 2,37 mm (p95 6,2) |

## Cómo interpretar (y qué no afirmar)

- **La referencia sana no es la verdad.** La asimetría natural entre lados (los volúmenes izquierdo y
  derecho de un paciente difieren hasta un 37 % en este set) entra en `vs_reference`. Sirve para ver si
  la reconstrucción es plausible y dónde mirar con más atención, no para medir el error.
- **La precisión esperada** es la de la validación ([05](05-validacion.md)): ~2,2 mm de media en la zona
  del defecto, ~1,7 mm en el acetábulo. Un defecto real grande, como el de RMR_000002 (17 % de la
  superficie), es más exigente que los cortes simulados de hasta 40 mm.
- **Huesos fuera del rango de entrenamiento:** RMR_000002 (250 mm) supera al mayor de entrenamiento
  (247 mm). La versión anterior del modelo lo reconstruía ~4 % corto en los extremos; conviene revisar
  ahí el resultado.
- La reconstrucción rellena con la forma **más probable** dado el modelo, no con la real; conviene
  revisarla visualmente antes de usarla.
