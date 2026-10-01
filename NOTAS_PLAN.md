
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

---
## Reescritura completa para VAR (26/09/2026)

HECHO:
- **Manuscrito reescrito** (`p08_manuscript.py`): título nuevo («El paisaje visual de los sitios
  arqueológicos de Chucuito…»), highlights ≤150 caracteres, abstract/resumen ≤300, extended
  abstract 600–900, sección 2 «Antecedentes» en cinco apartados (visibilidad, redes y nulos,
  incertidumbre del cálculo, SIG 3D/arqueología virtual, chullpas), 3.4 validación cruzada,
  3.6 visualización 3D, 4.8 paisaje visual desde la torre, discusión en cinco apartados.
  **7 252 palabras de cuerpo, 56 referencias (todas verificadas en Crossref), 5 figuras, 3 tablas.**
- **Figura 5, perspectiva 3D por algoritmo del pintor** (`p21_fig3d_perspectiva.py`): resuelve el
  z-order de matplotlib pintando celdas y marcadores de atrás hacia delante. La cámara queda al
  noreste, sobre el lago. WebGL sin ventana (Edge/Chrome headless) no renderiza aquí: descartado.
- `p18` guarda `results/cuenca_torre.json` (0 de 16 tumbas visibles) para que el texto lo lea.
- **Auditoría** (`p12`): 5 figuras, highlights a 150, cuerpo ≥5 500, ≥30 refs, antecedentes 2.1–2.5,
  cifras de la validación cruzada y de la torre; anonimato por «Mamani Calisaya» (un autor ajeno
  del reconocimiento de 1997 se apellida Onofre Mamani). **63 OK, 0 fallos.**
- **Carta VAR** (`p15`): contribución reescrita, nota al editor que declara que sustituye al
  27046 y qué se ha añadido, declaración de uso de IA según la política de la revista, fecha.
- Se descartó citar a Lerma et al. (2010): el editor jefe es Lerma y parecería halago.

PENDIENTE (usuario):
1. `git push` y release v1.2.0 en GitHub → Zenodo acuña la versión con visor, .qgz, p15–p21 y
   figuras nuevas. El manuscrito dice que están depositados: hacerlo ANTES de enviar.
2. Enviar a VAR como envío nuevo: `VAR_intervisibilidad.docx` (anónimo) +
   `VAR_CoverLetter_cumplimentado.docx`. Firma y cuatro autores como en la carta.
3. Procedencia: contrastada con el catálogo oficial del Ministerio (p24, 1/10/2026).
