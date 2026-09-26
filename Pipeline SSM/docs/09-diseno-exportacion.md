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
5. **Separar en hemipelvis** izquierda y derecha, si el origen es una pelvis completa (ver abajo).
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

## Decisiones abiertas (necesito tu respuesta)

1. **¿Origen: pelvis completa o hemipelvis ya separadas?** El nombre actual (`raw_4_pelvis_left`) sugiere que
   ya vienen separadas. Si no, hay que definir el corte (la sínfisis no está en x = 0 exacto).
2. **¿Los landmarks ya existen en las coordenadas de origen, o hay que colocarlos?** Si hay que colocarlos:
   ¿a mano (3D Slicer, MeshLab…) o automáticamente? Es lo que más afecta a la calidad: un ASIS mal puesto
   inclina todo el sistema, y en el set actual ya hubo landmarks que no coincidían con su malla (`TMR_000006_L`,
   `TMR_000054_L`).
3. **¿Cómo se alinean los casos dañados (`RMR_…`)?** Si el hueso perdido incluye ASIS o PT, no se pueden usar
   esos puntos; habría que alinear con el lado sano (reflejando) o con los que sobrevivan.
4. **¿Pueden salir los datos de su equipo?** Si no, el módulo se ejecuta allí y aquí solo entra el resultado;
   condiciona las dependencias y cómo lo pruebo.
5. **Identificadores:** ¿quién mantiene la tabla original ↔ `TMR_`/`RMR_`, y qué numeración usan los archivos nuevos?
