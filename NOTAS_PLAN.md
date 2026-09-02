
---
## Regreso a VAR: ruta 3D (2-3/09/2026, tras el rechazo de mesa)

Rechazo de VAR (editor Lerma): «lack of in-depth investigation», pide ≥5000
palabras + extensive literature review + contribución de *virtual* archaeology.
Puerta abierta. Plan: reencuadrar hacia análisis y VISUALIZACIÓN 3D.

HECHO esta sesión:
- **32 referencias** (25 nuevas verificadas en Crossref): results/candidatas_refs_var3d.json
- **Validación cruzada 99.92%** nuestro motor vs gdal:viewshed de QGIS (349k celdas,
  UTM 30m, cc=0.87); desacuerdos a 1984m medios, patrón Fisher 1993 cuantificado.
  scripts/p17_viewshed_cruzada.py → results/viewshed_cruzada.json
- **Render 3D por código** (matplotlib; pyvista/VTK descartado, sin OpenGL offscreen):
  scripts/p16_render3d.py, scripts/p18_fig3d_cuenca.py
- **Figura de cuenca desde la torre**: fig3d_planta.png — 0 de 16 tumbas visibles
  desde el funerario más alto (Gentilmoko Yacari, 4145m, Juli). Confirma p=0.526.
  La versión 3D con marcadores falla por z-order de matplotlib; la de planta es la buena.

PENDIENTE:
- Visor interactivo Qgis2threejs (requiere GUI de QGIS, con el usuario delante) → Zenodo+DOI
- Reescritura: antecedentes con 32 refs, ≥5500 palabras, título/resumen a 3D
- Reenvío como envío NUEVO a VAR
