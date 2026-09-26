# SSM: modelo estadístico de forma de hemipelvis

Reconstrucción de hueso acetabular perdido a partir de un modelo estadístico de forma (ShapeWorks + PCA).

La documentación completa, paso a paso y con la guía para repetir el proceso con un set nuevo, está en
[`Pipeline SSM/`](Pipeline%20SSM/README.md).

```bash
"Pipeline SSM/run_pipeline.sh" env      # comprobar el entorno
"Pipeline SSM/run_pipeline.sh" all      # manifiesto, preparación, verificación, modelo y validación reducida
```

El código está en `src/ssm/`; `data/` (mallas y resultados generados) no se versiona.
