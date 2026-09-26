# 03 · Verificación y preparación de las mallas 3D

Dos etapas: **`clean`** convierte cada STL en una malla uniforme lista para el modelo, y **`check`**
señala las mallas y landmarks sospechosos. Se ejecutan en este orden (`check` mide los landmarks sobre
las mallas ya preparadas).

```bash
"Pipeline SSM/run_pipeline.sh" clean      # python -m ssm.clean   ->  data/groomed/<forma>.ply
"Pipeline SSM/run_pipeline.sh" check      # python -m ssm.check   ->  data/check.csv
```

## 3a · Preparación (`ssm.clean`)

Para cada fila del manifiesto:

1. **Reflejo de los lados izquierdos** (x → −x, con el sentido de las caras corregido). A partir de aquí
   todas las formas están en el marco de una hemipelvis derecha.
2. **Detección de hueso cortado en trozos:** si la segunda pieza más grande tiene ≥ 10 % de las
   caras, la forma se **omite** (`skipped, mesh is severed into pieces`). No se repara, porque unir las
   piezas requiere un cierre volumétrico de ~25 min que además cuantiza toda la superficie.
3. **Componente principal:** se conserva solo la pieza más grande (fuera restos y cascarones sueltos).
4. **Rellenado de agujeros.**
5. **Suavizado sinc** (10 iteraciones, banda de paso 0,05): quita el escalonado de la segmentación sin
   encoger el hueso.
6. **Remuestreo a 25 000 vértices** (`adaptivity` 0, malla uniforme). Todas las formas quedan con la
   misma densidad, requisito del cálculo de correspondencias y de la comparación posterior.

Salida: `data/groomed/<forma>.ply`. `clean` borra antes los `.ply` existentes para que no queden
mallas antiguas. Con los datos actuales: `84/85` (solo `TMR_000031_L` se omite por estar cortada).
Las constantes están al principio de `src/ssm/clean.py`.

## 3b · Verificación (`ssm.check`)

Genera `data/check.csv` (una fila por forma) y lista en consola las formas con alguna señal. **Una señal
es un motivo para mirar la malla original, no un veredicto**: el informe no distingue una exportación
defectuosa de un hueso inusual. Decidir qué se excluye queda en manos de quien conoce el caso.

| Comprobación | Umbral | Qué suele significar |
|---|---|---|
| `side_ok` | el signo medio de x coincide con el lado (derecho < 0) | lado mal etiquetado o malla sin alinear |
| `watertight` | malla cerrada | agujeros en la exportación (`clean` los rellena, pero conviene saberlo) |
| `shells`, `second_shell_fraction` | > 1 pieza avisa; ≥ 0,1 = cortada en trozos | restos de segmentación o hueso partido |
| `ASIS_mm`, `PSIS_mm`, `PT_mm` | > 8 mm de la superficie | landmark que no corresponde a esta malla |
| `FH_mm` | fuera de 15–35 mm | centro de la cabeza femoral mal colocado (lo normal son 20–28 mm) |
| `lr_volume_ratio` | solo informativo | volumen izquierdo/derecho del paciente (0,78–1,37 observado) |
| `groomed_volume_cm3` | informativo | volumen de la malla preparada |

Con los datos actuales avisa en 16 de 85 formas. Las más relevantes:

| Forma | Señal | Qué se hizo |
|---|---|---|
| `TMR_000006_L` | landmarks a 49–111 mm de la superficie, 1 825 cascarones | excluida junto con su paciente |
| `TMR_000054_L` | PSIS a 81 mm, 14 cascarones | excluida junto con `_R` (paciente descartado) |
| `TMR_000031_L` | cortada en trozos | `clean` la omite sola |
| `TMR_000009_R`, `022_R`, `043_R` | 6, 92 y 8 cascarones | excluidas (mallas fuente defectuosas) |
| `TMR_000033_L`, `052_L` | 50 y 1 633 cascarones | excluidas (mala correspondencia) |

Los cascarones sueltos por sí solos no invalidan una malla (`clean` los descarta), pero en este set casi
todas las formas que luego dieron problemas de correspondencia los tenían.

**Sobre la razón de volumen izquierdo/derecho.** Los extremos (< 0,90 o > 1,20) coincidían con las
formas excluidas, así que se probó a excluir también el lado más pequeño de los cinco pacientes más
asimétricos. **No mejoró el modelo** (error 2,34 frente a 2,31 mm sobre las mismas formas). Se deja como
dato informativo y no como criterio de exclusión.

## 3c · Revisión de las mallas señaladas y exclusiones

1. Abrir en un visor 3D (ParaView, MeshLab, 3D Slicer…) la malla **original** de cada forma señalada.
2. Decidir si el problema está en la exportación (se excluye o se vuelve a exportar) o si es una
   variante anatómica real (se conserva).
3. Registrar la exclusión, con el motivo, en **`<SSM_DATA>/exclude.txt`**: una forma por línea y `#` para
   comentarios (un archivo vacío no excluye nada). Si ese archivo no existe se usa la lista `EXCLUDE` de
   `src/ssm/project.py`, que corresponde al set con el que se desarrolló el repositorio (tabla de abajo).
   El filtro se aplica al construir el proyecto, no al preparar las mallas.

Para dejar de usar un paciente entero hay que excluir **sus dos lados**. Con el modelo solo de
derechos, las exclusiones de lados izquierdos no tienen efecto porque el filtro `SSM_SIDES=R` ya los
deja fuera.

`EXCLUDE` actual y su motivo:

| Formas | Motivo |
|---|---|
| `TMR_000009_R`, `022_R`, `043_R`, `045_R` | mallas fuente derechas defectuosas; ningún ajuste del optimizador logró buena cobertura o correspondencia, y dominaban PC1 |
| `TMR_000006_L`, `054_L`, `054_R` | landmarks que no corresponden a la malla; ambos pacientes se descartaron por decisión de quien gestiona los datos |
| `TMR_000023_L`, `033_L`, `052_L`, `061_L` | poca cobertura o correspondencia rugosa en el primer modelo de ambos lados |
| `TMR_000013_L`, `050_L` | correspondencia rugosa; por sí solas dominaban PC2 |

Efecto neto para el modelo de derechos: 40 derechas − 5 excluidas = **35 formas**.
