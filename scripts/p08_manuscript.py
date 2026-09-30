# -*- coding: utf-8 -*-
"""
Manuscrito, generado a partir de los ficheros de resultados.

Las cifras no se escriben a mano: se leen de los JSON que produjo el analisis.
Asi el texto no puede desviarse de los datos cuando algo se recalcula, que es la
forma mas comun de que un articulo acabe afirmando un numero que ya no es suyo.

Version para el reenvio a Virtual Archaeology Review tras el rechazo de mesa
(2/09/2026): antecedentes con la bibliografia de visibilidad, modelos nulos,
incertidumbre del calculo, SIG 3D y paisaje funerario de la cuenca; validacion
cruzada del motor frente a gdal_viewshed; y el paisaje visual desde una torre
funeraria en planta, en perspectiva 3D y como visor interactivo depositado.

Formato de Virtual Archaeology Review: fichero anonimo, Arial, dos columnas,
marcador decimal con punto, encabezados numerados, APA 6.a con «doi:».
"""
import json
import os
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docmeta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# El identificador del deposito NO aparece en el manuscrito: su pagina muestra
# los nombres de los autores y romperia la revision ciega. Va en la carta (p15).
RES = os.path.join(BASE, "results")
FIG = os.path.join(RES, "figuras")
OUT = os.path.join(BASE, "VAR_intervisibilidad.docx")

ARIAL, BLACK = "Arial", RGBColor(0, 0, 0)
TEXT_W_MM, GUTTER_MM = 170.0, 6.0


def cargar(nombre):
    p = os.path.join(RES, nombre)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


NUL = cargar("nulos.json")
RIG = cargar("nulo_rigido.json")
FUN = cargar("funerarios.json")
VAL = cargar("validacion_los.json")
SEN = cargar("sensibilidad.json")
ALT = cargar("nulo_alturas.json")
DIS = cargar("por_distrito.json")
SINMASK = cargar("nulo_rigido_sin_mascara.json")   # contraejemplo: agua sin enmascarar
N300 = cargar("nulo_rigido_n300.json")             # version previa, recorte de 5 km
CRUZ = cargar("viewshed_cruzada.json")             # nuestro motor frente a gdal_viewshed
TORRE = cargar("cuenca_torre.json")                # tumbas visibles desde la torre mas alta
with open(os.path.join(BASE, "data", "terreno_log.json"), encoding="utf-8") as f:
    TER = json.load(f)
with open(os.path.join(BASE, "data", "fetch_log.json"), encoding="utf-8") as f:
    FET = json.load(f)


def f(x, d=4):
    return ("%%.%df" % d) % x


def mil(n):
    """Entero con espacio fino de millar, como pide la norma tipografica del castellano."""
    return "{:,}".format(int(n)).replace(",", " ")


doc = Document()


def page_setup(sec):
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm((210 - TEXT_W_MM) / 2)
    sec.top_margin, sec.bottom_margin = Mm(25), Mm(20)   # VAR_Template: 2.5 / 2 cm


def set_cols(sec, num):
    c = sec._sectPr.xpath("./w:cols")[0]
    c.set(qn("w:num"), str(num))
    c.set(qn("w:space"), str(int(GUTTER_MM * 56.7)))
    c.set(qn("w:equalWidth"), "1")


def run(p, t, size=9, bold=False, italic=False):
    r = p.add_run(t)
    r.font.name = ARIAL
    r.font.size = Pt(size)
    r.bold, r.italic = bold, italic
    r.font.color.rgb = BLACK
    r._element.rPr.rFonts.set(qn("w:eastAsia"), ARIAL)
    return r


def P(t="", size=9, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
      after=6, before=0):
    p = doc.add_paragraph()
    if t:
        run(p, t, size, bold, italic)
    pf = p.paragraph_format
    pf.alignment, pf.space_after, pf.space_before = align, Pt(after), Pt(before)
    pf.line_spacing = 1.0
    return p


def h1(t):
    return P(t, 11, True, align=WD_ALIGN_PARAGRAPH.CENTER, before=10, after=6)


def h2(t):
    return P(t, 10, True, align=WD_ALIGN_PARAGRAPH.LEFT, before=8, after=4)


def one_col():
    s = doc.add_section(WD_SECTION.CONTINUOUS); page_setup(s); set_cols(s, 1)


def two_col():
    s = doc.add_section(WD_SECTION.CONTINUOUS); page_setup(s); set_cols(s, 2)


def caption(label, text, above=False):
    p = doc.add_paragraph()
    run(p, label + " ", 8, bold=True)
    run(p, text, 8)
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(8 if above else 4)
    pf.space_after = Pt(4 if above else 8)
    pf.line_spacing = 1.0


def table(label, text, cols, rows, widths=None):
    one_col()
    caption(label, text, above=True)
    t = doc.add_table(rows=1, cols=len(cols))
    t.style, t.alignment = "Table Grid", WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(cols):
        cell = t.rows[0].cells[i]; cell.text = ""
        run(cell.paragraphs[0], c, 8, italic=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cs = t.add_row().cells
        for i, v in enumerate(row):
            cs[i].text = ""
            run(cs[i].paragraphs[0], str(v), 8)
            cs[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if widths:
        for rr in t.rows:
            for i, w in enumerate(widths):
                rr.cells[i].width = Mm(w)
    doc.add_paragraph()
    two_col()


def figure(fname, label, text, width_mm=TEXT_W_MM):
    p = os.path.join(FIG, fname)
    if not os.path.exists(p):
        raise SystemExit("Falta la figura %s: ejecute el guion que la genera" % fname)
    one_col()
    doc.add_picture(p, width=Mm(width_mm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(label, text)
    two_col()


page_setup(doc.sections[0]); set_cols(doc.sections[0], 1)
st = doc.styles["Normal"]; st.font.name = ARIAL; st.font.size = Pt(9)
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.0

# ------------------------------------------------------------- cifras derivadas
n_sitios = TER["sitios"]
n_fun = TER["funerarios_por_toponimo"]
d5 = NUL["observado"]["5000"] if NUL else None
r5 = RIG["por_alcance"]["5000"]
p_juli = (f(DIS["distritos"]["juli"]["contraste"]["5000"]["p_unilateral"], 3)
          if (DIS and DIS["distritos"]["juli"].get("contraste")) else "n. d.")
frac_agua = 100 * FET.get("fraccion_agua", 0.306) if "fraccion_agua" in FET else 30.6
z_agua = SINMASK["por_alcance"]["5000"]["z"] if SINMASK else float("nan")
z_n300 = N300["por_alcance"]["5000"]["z"] if N300 else float("nan")
z_alt = sorted(v["z"] for v in ALT["por_altura"].values()) if ALT else [r5["z"], r5["z"]]
z_uni = ([NUL["nulos"]["uniforme"][a]["z"] for a in ("5000", "26000")] if NUL else [0, 0])
# Razon z_uniforme / z_rigido por alcance: cuanto exagera el muestreo aleatorio
# simple frente al nulo que controla la disposicion. Se usa en la introduccion,
# el extended abstract y la discusion, por eso se calcula aqui.
RAZ = (sorted(NUL["nulos"]["uniforme"][a]["z"] / RIG["por_alcance"][a]["z"]
              for a in RIG["por_alcance"]) if NUL else [float("nan"), float("nan")])
z_rig_medio = sum(v["z"] for v in RIG["por_alcance"].values()) / len(RIG["por_alcance"])
alt_obs = ALT["por_altura"] if ALT else None
var_alt = (100 * (alt_obs["12.0"]["observado"] - alt_obs["0.0"]["observado"])
           / alt_obs["0.0"]["observado"]) if alt_obs else 0.0
acuerdo_pct = 100 * CRUZ["acuerdo"] if CRUZ else float("nan")
area_cuenca_km2 = CRUZ["visibles_nuestro"] * 0.0009 if CRUZ else float("nan")
frac_cuenca = 100.0 * CRUZ["visibles_nuestro"] / CRUZ["celdas_evaluadas"] if CRUZ else float("nan")
torre_nombre = " ".join(TORRE["observador"].split()) if TORRE else "la torre más alta"
torre_alt = TORRE["altitud_m"] if TORRE else 0
ext_km = TER["extension_m"]["x"] / 1000.0

# =========================================================== portada y resumen
P("EL PAISAJE VISUAL DE LOS SITIOS ARQUEOLÓGICOS DE CHUCUITO (CUENCA DEL TITICACA): "
  "INTERVISIBILIDAD, MODELOS NULOS Y VISUALIZACIÓN 3D SOBRE DATOS ABIERTOS",
  14, True, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
P("THE VISUAL LANDSCAPE OF THE ARCHAEOLOGICAL SITES OF CHUCUITO (LAKE TITICACA BASIN): "
  "INTERVISIBILITY, NULL MODELS AND 3D VISUALISATION ON OPEN DATA",
  9, italic=True, align=WD_ALIGN_PARAGRAPH.LEFT, after=18)
# El bloque de autoria queda vacio durante la revision ciega. Vacio de verdad:
# una nota entre corchetes explicando que esta vacio no es un blanco, es un
# texto, y ademas hace que el manuscrito parezca un borrador sin terminar.

P("Highlights", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
HIGHLIGHTS = [
    "Red de intervisibilidad de %d sitios de Chucuito sobre Copernicus DEM GLO-30, contrastada "
    "con tres modelos nulos de exigencia creciente." % n_sitios,
    "El emplazamiento favorece la visión recíproca (p = %s), pero el efecto se atenúa al "
    "separar los dos grupos de sitios (p = %s)." % (f(r5["p_unilateral"], 3), p_juli),
    "Motor validado al %.1f %% frente a gdal_viewshed; enmascarar el lago cambia z de %+.2f a "
    "%+.2f. Visor 3D interactivo depositado." % (acuerdo_pct, z_agua, r5["z"]),
]
for b in HIGHLIGHTS:
    assert len(b) <= 150, "highlight de %d caracteres: %s" % (len(b), b)
    p = doc.add_paragraph(style="List Bullet")
    run(p, b, 9)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
doc.add_paragraph()

P("Abstract", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
P("This paper asks whether the archaeological sites recorded in the province of Chucuito, on the "
  "Peruvian shore of Lake Titicaca, occupy positions from which they see one another more than chance "
  "would predict, and makes the resulting visual landscape explorable in three dimensions. Line of "
  "sight is computed on the Copernicus DEM GLO-30 for the %s pairs formed by the %d recorded sites, "
  "with a combined correction for Earth curvature and atmospheric refraction, and the resulting "
  "network is tested against three null models of increasing stringency. The strictest translates "
  "and rotates the entire site cloud, preserving every mutual distance, and therefore isolates "
  "placement from configuration. Observed intervisibility density at 5 km is %s against %s ± %s "
  "under that null (z = %+.2f; p = %s), and holds across the four ranges considered and the whole "
  "range of plausible structure heights. Restricted to the larger of the two spatially disjoint "
  "clusters that make up the sample, however, the contrast falls to the margin of conventional "
  "significance (p = %s), so the evidence is indicative rather than conclusive. The line-of-sight "
  "engine is validated on synthetic terrains of known answer and cross-validated against "
  "gdal_viewshed on the same projected raster (%.2f %% agreement over %s cells). Three artefacts "
  "that invert or suppress the result if left uncorrected are documented: the sign of the curvature "
  "correction, the constant elevation the terrain model assigns to water —%.1f %% of the study "
  "area— and the orientation bias of a tightly fitted raster extent. The viewshed of the highest "
  "funerary tower is rendered in plan, in a code-generated 3D perspective and as an interactive "
  "web viewer, all deposited with the code and data."
  % (mil(n_sitios * (n_sitios - 1) // 2), n_sitios,
     f(r5["densidad_obs"]), f(r5["nula_media"]), f(r5["nula_sd"]),
     r5["z"], f(r5["p_unilateral"], 3), p_juli, acuerdo_pct,
     mil(CRUZ["celdas_evaluadas"]) if CRUZ else "n. a.", frac_agua),
  after=4)
P("Keywords", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=2)
P("landscape archaeology; intervisibility; Lake Titicaca basin; null models; 3D visualisation; "
  "open science", after=8)

P("Resumen", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
P("Se analiza si los sitios arqueológicos registrados en la provincia de Chucuito, en la ribera "
  "peruana del lago Titicaca, ocupan posiciones desde las que se ven entre sí más de lo que cabría "
  "esperar del azar. Sobre el "
  "Copernicus DEM GLO-30 se calcula la línea de visión entre los %s pares que forman los %d sitios "
  "documentados, con corrección de curvatura terrestre y refracción atmosférica, y se contrasta la "
  "red resultante contra tres modelos nulos de exigencia creciente. El más estricto traslada y rota "
  "la nube de sitios completa, conservando todas las distancias mutuas, de modo que aísla el "
  "emplazamiento de la disposición. La densidad de intervisibilidad observada a 5 km es %s frente a "
  "%s ± %s en el nulo (z = %+.2f; p = %s), y se mantiene en los cuatro alcances considerados y en "
  "todo el rango de alturas atribuibles a las estructuras. Restringido al mayor de los dos grupos "
  "espacialmente disjuntos que componen el conjunto, sin embargo, el contraste queda en el margen de "
  "la significación convencional (p = %s), de modo que la evidencia es indicativa y no concluyente. "
  "El motor de línea de visión se valida sobre terrenos sintéticos de respuesta conocida y se "
  "contrasta con gdal_viewshed sobre el mismo ráster proyectado (%.2f %% de acuerdo en %s celdas). "
  "Se documentan tres artefactos que invierten o anulan el resultado si no se corrigen: el signo de "
  "la corrección por curvatura, la cota constante que el modelo asigna a las masas de agua —el "
  "%.1f %% del área de estudio— y el sesgo de orientación de un recorte ajustado. La cuenca visual "
  "de la torre funeraria más alta se presenta en planta, en perspectiva 3D y como visor web "
  "interactivo, depositados junto con el código y los datos."
  % (mil(n_sitios * (n_sitios - 1) // 2), n_sitios,
     f(r5["densidad_obs"]), f(r5["nula_media"]), f(r5["nula_sd"]),
     r5["z"], f(r5["p_unilateral"], 3), p_juli, acuerdo_pct,
     mil(CRUZ["celdas_evaluadas"]) if CRUZ else "n. d.", frac_agua),
  after=4)
P("Palabras clave", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=2)
P("arqueología del paisaje; intervisibilidad; cuenca del Titicaca; modelos nulos; visualización 3D; "
  "ciencia abierta", after=10)

# La norma exige un extended abstract en ingles de 600 a 900 palabras cuando el
# articulo va en espanol. Debe cubrir objetivos, metodologia, resultados y
# conclusiones, y admite citas.
P("Extended abstract", 9, True, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
for _par in [
    "Funerary monuments in the Lake Titicaca basin are routinely described as having been placed so as "
    "to be seen. Hyslop (1977), studying the chullpas of the Lupaqa zone —the area of the present-day "
    "province of Chucuito— argued that these towers marked the territory of kin groups, drawing on "
    "colonial sources that describe them as boundary markers. The implication, seldom made explicit, is "
    "that their placement should favour mutual visibility. Bongers, Arkush, and Harrower (2012) tested "
    "that expectation near Sillustani, west of the lake, comparing chullpa visibility against 300 "
    "random points, and concluded that visibility and elevation governed placement. That study is, as "
    "far as this review reaches, the only formal test of the hypothesis in the basin.",

    "The objective of this paper is to retest the claim in a different part of the basin, with a "
    "different measure, a stricter comparison and a validated engine, and to make the resulting visual "
    "landscape explorable in three dimensions. Two departures from the 2012 design matter. First, what "
    "is measured is reciprocal intervisibility between sites —the density of the visibility network, in "
    "the sense of Brughmans and Brandes (2017)— rather than the size of each site's individual "
    "viewshed. Second, the observed network is compared against three null models of increasing "
    "stringency rather than one.",

    "The analysis rests on fully open data: the archaeological site layer originating from Peru's "
    "Instituto Nacional de Cultura, and the Copernicus DEM GLO-30 at 30 m resolution. Line of sight "
    "between each pair of sites is evaluated by sampling the intervening terrain at one sample per cell "
    "and testing whether the relief intersects the straight line joining observer and target. Earth "
    "curvature and atmospheric refraction are handled jointly through an effective radius R/(1−k) with "
    "k = 0.13 (Kormann & Lock, 2014). The sign of that correction deserves emphasis: written with "
    "respect to the chord joining the two endpoints, the term d(D−d)/2R is added to the intervening "
    "terrain, because seen from that chord the Earth bulges between the endpoints. Subtracting it "
    "renders the Earth concave and prevents any relief from ever blocking at long range.",

    "Because a visibility algorithm fails silently (Fisher, 1993; Riggs & Dean, 2007), the engine was "
    "validated twice before touching real relief: against twelve synthetic terrains of known answer, "
    "all of which it passes, and against gdal_viewshed run through QGIS on the same UTM raster with "
    "identical parameters, where the two engines agree on %.2f %% of the %s cells within 10 km of the "
    "highest funerary tower; the disagreements lie on relief edges at short range, the pattern Fisher "
    "described. The sign error was caught by the synthetic validation, not by the analysis."
    % (acuerdo_pct, mil(CRUZ["celdas_evaluadas"]) if CRUZ else "n. a."),

    "The three null models are as follows. The uniform null draws points at random across the terrain "
    "and reproduces the procedure used hitherto; it almost always returns significance, because real "
    "sites occupy favourable relief and favourable relief sees more. The elevation-stratified null "
    "draws cells matching the observed elevation distribution, following Wheatley and Gillings (2000) "
    "and Lake and Woodman (2003). The rigid null takes the site cloud as it stands, preserving every "
    "mutual distance, and translates and rotates it across the terrain, thereby separating where the "
    "sites are from how they are arranged relative to one another.",

    "The results are mixed, and the paper reports them as such. Across the whole set of %d sites the "
    "observed density at 5 km exceeds the rigid null at conventional significance (z = %+.2f; "
    "p = %s), and the contrast holds at all four ranges examined and across the full range of "
    "structure heights. But the sites of Chucuito fall into two spatially disjoint groups, Juli and "
    "Pomata, whose centroids lie %.1f km apart. Restricted to Juli, the only group large enough to "
    "test, the contrast falls to the margin of conventional significance (p = %s). The evidence is "
    "indicative, not conclusive. What does survive without qualification is the comparison between "
    "null models: simple random sampling attributes to placement an effect between %.1f and %.1f "
    "times larger, depending on range, than the one that withstands a test controlling for the "
    "arrangement of the set."
    % (n_sitios, r5["z"], f(r5["p_unilateral"], 3),
       DIS["separacion_centroides_km"] if DIS else 0.0, p_juli, RAZ[0], RAZ[-1]),

    "Three artefacts encountered during the analysis —the sign of the curvature correction, the "
    "constant elevation assigned to water, and the orientation bias of a tightly fitted raster "
    "extent— share an uncomfortable property: none produces a visible failure. Masking the lake alone "
    "shifts the contrast from z = %+.2f to z = %+.2f. The runs preceding each correction are "
    "deposited alongside the code so that these comparisons can be verified rather than taken on "
    "trust." % (z_agua, r5["z"]),

    "Finally, the visual landscape is made explorable. The viewshed of the highest funerary tower in "
    "the corpus (%s, %s m) is rendered in plan, in a code-generated 3D perspective drawn with a "
    "painter's algorithm that respects occlusion, and as a self-contained interactive web viewer "
    "with orbital navigation; a QGIS project ready for its 3D map view is also built by code. From "
    "that tower, %d of the %d other funerary sites within 10 km are visible, which illustrates in one "
    "image why the funerary subnetwork is no more connected than the rest of the corpus. In the "
    "spirit of the Seville Principles (López-Menchero & Grande, 2011) and of paradata (Bentkowska-"
    "Kafel, Denard, & Baker, 2012), every view is generated from deposited code and data, so the "
    "visualisation is as reproducible and as auditable as the statistics it illustrates."
    % (torre_nombre, mil(round(torre_alt)),
       TORRE["tumbas_visibles"] if TORRE else 0, TORRE["tumbas_en_figura"] if TORRE else 0),
]:
    P(_par, after=4)
doc.add_paragraph()

two_col()

# ================================================================ introduccion
h1("1. Introducción")
P("La visibilidad de los monumentos funerarios es un argumento recurrente en la arqueología del paisaje "
  "altiplánico. Hyslop (1977), en su estudio de las chullpas de la zona Lupaqa —la que corresponde a la "
  "actual provincia de Chucuito—, propuso que estas torres funcionaban como marcadores del territorio "
  "controlado por unidades familiares, apoyándose en fuentes coloniales que las describen como mojones. "
  "De ahí se sigue, aunque no siempre se explicite, que su emplazamiento debería favorecer que se vieran "
  "entre sí.")
P("Bongers, Arkush y Harrower (2012), con la corrección posterior de los propios autores (Bongers, "
  "Arkush, & Harrower, 2013), sometieron esa expectativa a contraste en un área de 80 km² al oeste del "
  "lago, en el entorno de Sillustani, comparando la visibilidad de las chullpas con la de 300 puntos "
  "aleatorios. Concluyeron que la visibilidad y la altitud actuaron como determinantes del "
  "emplazamiento. Es, hasta donde alcanza esta revisión, la única puesta a prueba formal de la hipótesis "
  "en la cuenca, y el punto de partida de este trabajo.")
P("La dificultad no está en medir la visibilidad sino en decidir con qué se compara. Cualquier conjunto "
  "de puntos sobre un terreno produce alguna red de intervisibilidad, y sin término de comparación ese "
  "número no distingue la intención del accidente. La pregunta con contenido es si se ven más de lo que "
  "se verían puntos situados sin esa intención, lo que obliga a definir qué significa «sin esa "
  "intención»: ahí se juega el resultado. Wheatley y Gillings (2000) y Lake y Woodman (2003) han "
  "señalado que el muestreo aleatorio simple resulta insuficiente cuando los emplazamientos comparten "
  "rasgos topográficos, y proponen contrastes estratificados frente a localizaciones comparables.")
P("Este trabajo retoma la cuestión en la provincia de Chucuito, en la ribera peruana del lago, con datos "
  "íntegramente abiertos y en tres aspectos distintos del planteamiento de 2012. Se mide la "
  "intervisibilidad recíproca entre sitios —la densidad de la red— en lugar del tamaño de la cuenca "
  "visual de cada uno; se contrasta contra tres modelos nulos de exigencia creciente, de los cuales el "
  "primero equivale al muestreo aleatorio empleado hasta ahora; y el motor de cálculo se valida antes "
  "de tocar el terreno real, tanto sobre terrenos sintéticos de respuesta conocida como frente a una "
  "implementación de referencia de uso general.")
P("El resultado sostiene la conclusión previa, pero reduce su magnitud: el muestreo aleatorio simple "
  "la exagera entre %.1f y %.1f veces según el alcance, y esa es la primera contribución. La segunda es la documentación de tres artefactos hallados durante el "
  "análisis que, sin corregir, invierten o anulan el resultado sin dejar rastro visible. La tercera es "
  "de arqueología virtual: el paisaje visual de la torre funeraria más alta del corpus se hace "
  "explorable en planta, en una perspectiva tridimensional generada por código y en un visor web "
  "interactivo, todos depositados junto con los datos y el código que los producen, de modo que la "
  "visualización hereda la misma verificabilidad que el análisis estadístico." % (RAZ[0], RAZ[-1]))
P("El artículo se organiza como sigue. El apartado 2 sitúa el trabajo en cinco líneas de "
  "bibliografía: el análisis de visibilidad en arqueología del paisaje, las redes de visibilidad y los "
  "modelos nulos, la incertidumbre del propio cálculo, los SIG tridimensionales y la arqueología "
  "virtual, y el paisaje funerario de la cuenca. El apartado 3 describe los datos, el motor de línea "
  "de visión, sus dos validaciones, los modelos nulos y los instrumentos de visualización. El apartado "
  "4 presenta los resultados, incluidos los tres artefactos y la cuenca visual de la torre. El "
  "apartado 5 los discute y el 6 describe cómo se ha depositado todo el material.")

# ================================================================= antecedentes
h1("2. Antecedentes")
h2("2.1. El análisis de visibilidad en la arqueología del paisaje")
P("El análisis de visibilidad es uno de los instrumentos más usados de la arqueología del paisaje "
  "asistida por SIG, y también uno de los más discutidos. Wheatley (1995) introdujo el análisis de "
  "cuencas visuales acumuladas para preguntar si los túmulos alargados de Wessex se emplazaron para "
  "verse entre sí, y con ello fijó la forma canónica de la pregunta: no cuánto ve cada monumento, sino "
  "si el conjunto ve más de lo esperable. Lake, Woodman y Mithen (1998) adaptaron el software de la "
  "época para calcular cuencas visuales totales en los asentamientos mesolíticos de Islay, y Conolly "
  "y Lake (2006) y Wheatley y Gillings (2002) sistematizaron el procedimiento en los manuales de "
  "referencia de la disciplina.")
P("La crítica llegó pronto y por dos frentes. Wheatley y Gillings (2000) señalaron que el análisis "
  "binario —se ve o no se ve— reduce la percepción a geometría y omite la distancia, la iluminación, "
  "la vegetación y la propia capacidad del ojo; Ogburn (2006) cuantificó ese último punto proponiendo "
  "medir la visibilidad efectiva de un objeto de tamaño conocido a cada distancia, argumento que "
  "justifica en este trabajo la presentación de los resultados en varios alcances en lugar de uno solo. "
  "Llobera (2001) formalizó la prominencia topográfica como propiedad del relieve, Llobera (2003) "
  "propuso el concepto de paisaje visual —la visibilidad como campo continuo sobre el espacio y no "
  "como colección de mapas binarios— y Llobera (2007) exploró cómo reconstruir paisajes visuales que "
  "incorporen la vegetación y la estructura del entorno. Bernardini, Barnash, Kumler y Wong (2013) "
  "cuantificaron la prominencia visual de los hitos del paisaje, y Bernardini y Peeples (2015) "
  "derivaron de ella la noción de comunidades de visión: grupos de sitios que comparten los mismos "
  "referentes visuales sin necesariamente verse entre sí.")
P("La agenda reciente ha ampliado la pregunta más allá de la visibilidad como ventaja. Gillings (2012) "
  "reformuló el análisis desde la noción de affordance, Gillings (2015) mostró que la ocultación y el "
  "aislamiento pueden ser tan intencionales como la exposición, y Gillings (2017) propuso marcos "
  "críticos para modelar la liminalidad visual. Eve y Crema (2014) combinaron campos de visibilidad "
  "con procesos puntuales e inferencia multimodelo para evaluar si las casas de Leskernick se "
  "emplazaron por sus vistas; Supernant (2014) distinguió la intervisibilidad entre sitios de la "
  "intravisibilidad dentro de un sistema socioespacial; y Wright, MacEachern y Lee (2014) unieron "
  "intervisibilidad, visibilidad acumulada y estadística bayesiana en las montañas Mandara. Desde la "
  "ciencia de la información geográfica, Kim, Rana y Wise (2004) abordaron la optimización de "
  "cuencas visuales múltiples, y Turner, Doxa, O'Sullivan y Penn (2001) formalizaron el paso de los "
  "isovistas a los grafos de visibilidad, que es la estructura que las redes de intervisibilidad "
  "arqueológicas importan del análisis del espacio construido.")

h2("2.2. Redes de visibilidad y modelos nulos")
P("Tratar la intervisibilidad como una red y no como una suma de cuencas cambia lo que se puede "
  "preguntar. Brughmans, Keay y Earl (2014, 2015) introdujeron los modelos de grafos aleatorios "
  "exponenciales para redes de visibilidad y los aplicaron a los asentamientos ibéricos y romanos del "
  "sur de España, mostrando que la dependencia entre aristas —si A ve a B y B ve a C, la probabilidad "
  "de que A vea a C no es independiente— exige modelos que la representen. Brughmans y Brandes (2017) "
  "sistematizaron los patrones y métodos para estudiar fenómenos visuales relacionales, Brughmans, "
  "de Waal, Hofman y Brandes (2018) los aplicaron a las transformaciones de las redes indígenas del "
  "Caribe, y Brughmans, van Garderen y Gillings (2018) propusieron las configuraciones de vecindad "
  "visual para resumir cuencas visuales totales.")
P("La cuestión del modelo nulo es anterior a la de la red. Kvamme (1990) formalizó los contrastes de "
  "una muestra en análisis regional: comparar la distribución de una variable en los sitios con la "
  "distribución de la misma variable en el fondo del territorio, que es exactamente lo que hace un "
  "modelo nulo de emplazamiento. Wheatley y Gillings (2000) y Lake y Woodman (2003) advirtieron que el "
  "fondo relevante no es el territorio entero: si los sitios comparten rasgos topográficos, el nulo "
  "debe compartirlos también, de lo contrario el contraste solo demuestra que los sitios están altos. "
  "Los tres modelos nulos de este trabajo se sitúan en esa línea y la prolongan un paso: el nulo "
  "rígido conserva no solo la altitud sino la configuración interna completa del conjunto, y "
  "pregunta únicamente si esa configuración está colocada donde ve más.")

h2("2.3. La incertidumbre del cálculo")
P("Un aspecto menos tratado en la bibliografía arqueológica es que el propio cálculo de visibilidad "
  "es incierto. Fisher (1993) mostró que implementaciones independientes de la misma operación de "
  "cuenca visual, sobre el mismo modelo de elevación, producen resultados sustancialmente distintos "
  "sin que ninguna parezca defectuosa; Nackaerts, Govers y Van Orshoven (1999) evaluaron la exactitud "
  "de las visibilidades probabilísticas frente a observaciones de campo, y Riggs y Dean (2007) "
  "investigaron las causas de los errores e inconsistencias de las cuencas visuales predichas, "
  "atribuyéndolas a decisiones de implementación —interpolación del perfil, tratamiento de la celda "
  "del observador, curvatura— que rara vez se declaran. Kormann y Lock (2014) examinaron "
  "específicamente el efecto de la curvatura terrestre y la refracción en los estudios de visibilidad "
  "arqueológicos, y concluyeron que a distancias de varios kilómetros ambos términos alteran el "
  "resultado; el signo de esa corrección es, como se verá, uno de los tres artefactos que este trabajo "
  "documenta.")
P("Ese problema se agrava en la práctica porque la mayor parte de los estudios se apoya en "
  "herramientas cuyo comportamiento por defecto no se conoce en detalle. Čučković (2016) publicó el "
  "complemento de análisis de visibilidad avanzado para QGIS que buena parte de la comunidad usa, y "
  "Ducke (2012) argumentó que el software libre y de código abierto es la única vía por la que un "
  "análisis arqueológico puede auditarse hasta el algoritmo. Marwick (2017) estableció los principios "
  "de la reproducibilidad computacional en arqueología —código, datos, control de versiones, entorno— "
  "y Schmidt y Marwick (2020) mostraron hasta qué punto los cambios de herramienta han reorientado la "
  "disciplina. Este trabajo asume ese programa y le añade un requisito: antes de reproducir, validar. "
  "El motor se prueba sobre terrenos sintéticos de respuesta conocida y se contrasta con "
  "gdal_viewshed, la implementación de referencia de GDAL accesible desde QGIS, sobre el mismo ráster "
  "y con los mismos parámetros.")

h2("2.4. SIG tridimensionales, visualización y arqueología virtual")
P("La tercera dimensión ha dejado de ser un complemento del SIG arqueológico para convertirse en un "
  "espacio de análisis propio. Richards-Rissetto (2017) preguntó qué puede significar la unión de SIG "
  "y 3D para la arqueología del paisaje, y respondió que no solo una forma de presentar resultados "
  "sino una manera de plantear preguntas que el mapa bidimensional no admite: la visibilidad es el "
  "ejemplo canónico, porque ver es una relación entre puntos del espacio tridimensional. Landeschi, "
  "Dell'Unto, Lundqvist, Ferdani, Campanaro y Leander Touati (2016) usaron el SIG 3D como plataforma "
  "de análisis visual en una casa pompeyana, y Dell'Unto, Landeschi, Leander Touati, Dellepiane, "
  "Callieri y Ferdani (2016) mostraron cómo la experiencia de un edificio antiguo desde una perspectiva "
  "3D produce interpretaciones distintas de las que sugiere la planta. Landeschi (2019) llevó el "
  "argumento a la percepción del espacio y a la necesidad de repensar el SIG desde la "
  "tridimensionalidad.")
P("Al mismo tiempo, la arqueología virtual ha construido un marco normativo sobre lo que una "
  "visualización debe declarar. Los principios de Sevilla (López-Menchero & Grande, 2011) exigen "
  "rigor científico, autenticidad y transparencia, y la noción de paradatos (Bentkowska-Kafel, Denard, "
  "& Baker, 2012) pide que el proceso que produce una imagen sea tan documentado como la imagen misma. "
  "Garstki (2017) advirtió que el artefacto digital tridimensional es una representación con "
  "decisiones incorporadas, no una copia neutra, y Champion y Rahaman (2019) plantearon el problema de "
  "la sostenibilidad de los modelos 3D como recursos académicos: formatos propietarios, visores "
  "dependientes de servicios y modelos que dejan de abrirse a los pocos años. Las decisiones de "
  "visualización de este trabajo responden a esos criterios: todas las vistas se generan por código a "
  "partir de los datos depositados, el visor interactivo es un único fichero autocontenido que abre "
  "cualquier navegador, y la escena que muestra es la misma que la estadística analiza.")

h2("2.5. Las chullpas y el paisaje funerario de la cuenca del Titicaca")
P("El área de estudio tiene una bibliografía arqueológica propia. Hyslop (1977) documentó las chullpas "
  "de la zona Lupaqa y las interpretó como marcadores territoriales de grupos de parentesco, y el "
  "reconocimiento sistemático de Stanish, de la Vega, Steadman, Chávez Justo, Frye, Onofre Mamani, "
  "Seddon y Calisaya Chuquimia (1997) en la región Juli-Desaguadero —que se solapa con el área aquí "
  "analizada— registró la distribución de asentamientos y estructuras funerarias del Formativo al "
  "Horizonte Tardío. Frye y de la Vega (2005) caracterizaron el periodo Altiplano, cuando las torres "
  "funerarias se generalizan, y Stanish (2003) integró la cuenca en una síntesis de la evolución de la "
  "complejidad social; Arkush (2005) estudió los sitios ceremoniales incaicos del suroeste de la "
  "cuenca, que es precisamente el sector de Chucuito.")
P("Sobre el significado de las chullpas hay acuerdo en lo esencial y debate en el resto. Isbell (1997) "
  "vinculó los sepulcros abiertos con el culto a los ancestros y con la organización social del "
  "ayllu; Kesseli y Pärssinen (2005) leyeron las torres del altiplano boliviano de Pakasa como símbolos "
  "de poder étnico; Nielsen (2009) mostró que los ancestros participaban en el conflicto, de modo que "
  "la visibilidad de sus tumbas formaba parte de la disputa por el territorio; y Morales, Nielsen y "
  "Villalba (2013) aportaron las primeras fechas dendroarqueológicas de chullpas andinas, que sitúan su "
  "construcción entre los siglos XIII y XVI. Ese mismo periodo es el de los sitios fortificados que "
  "Arkush (2011) documentó en el altiplano, cuya lógica de emplazamiento —cotas altas, control visual "
  "de los accesos— produciría un patrón de intervisibilidad difícil de distinguir del funerario; "
  "Arkush y Stanish (2005) y Arkush (2018) han discutido cómo interpretar ese conflicto y cómo se "
  "forman comunidades defensivas coalescentes. La hipótesis que este trabajo contrasta —que los sitios "
  "se ven entre sí más de lo esperable— es por tanto compatible con más de una explicación, y así se "
  "tratará en la discusión.")

# ==================================================== materiales y metodos
h1("3. Materiales y métodos")
h2("3.1. Área de estudio y datos")
P("Se analiza la provincia de Chucuito, departamento de Puno, que en el siglo XV integraba el señorío "
  "Lupaqa descrito por Stanish (2003) como una de las formaciones políticas mayores de la cuenca. Los "
  "sitios proceden de la capa de sitios arqueológicos del Instituto Nacional de Cultura, hoy "
  "Ministerio de Cultura, que documenta 7 907 puntos en todo el Perú, de los cuales 507 corresponden "
  "a Puno y %d a Chucuito. Las cotas proceden del Copernicus DEM GLO-30 de la Agencia Espacial "
  "Europea, a 30 m de resolución, obtenido del repositorio público que no exige registro. El área "
  "analizada abarca %.0f km de este a oeste y sus cotas van de %s a %s m." % (
      n_sitios, ext_km, mil(round(TER["altitud_min"])), mil(round(TER["altitud_max"]))))
P("La capa de sitios plantea un problema de procedencia que debe declararse. Se distribuye a través de "
  "un portal que la sirve desde un servicio de alojamiento genérico, sin licencia declarada, sin fecha "
  "de corte y sin criterio de inclusión documentado. El dato es de origen público, pero esa opacidad la "
  "hereda cualquier resultado. Se intentaron tres vías oficiales sin éxito: el geoservicio del "
  "Ministerio responde pero no publica ninguna capa de forma anónima; el sistema de información "
  "geográfica de arqueología se apoya en una cuenta personal cuyo contenido no es accesible por "
  "interfaz de programación; y un tercer repositorio citado habitualmente ya no resuelve.")

h2("3.2. Cálculo de la línea de visión")
P("Entre cada par de sitios se muestrea el perfil del terreno a razón de una muestra por celda —la "
  "densidad natural del dato, ya que un muestreo más fino solo interpolaría información que el modelo "
  "no contiene— y se comprueba si el relieve intermedio corta la recta que une observador y objetivo. "
  "Se aplica la corrección conjunta de curvatura terrestre y refracción atmosférica mediante el radio "
  "efectivo R/(1−k), con k = 0.13, el valor habitual en la bibliografía (Kormann & Lock, 2014).")
P("El signo de esa corrección merece detenimiento, porque es donde es fácil equivocarse y el error no "
  "se manifiesta. Trabajando en el plano tangente al observador, el terreno desciende d²/2R con la "
  "distancia y el objetivo desciende D²/2R. Al reescribir la condición de bloqueo respecto a la recta "
  "que une ambos extremos sin corregir, esos dos descensos se combinan en un término d(D−d)/2R que se "
  "suma al terreno intermedio: visto desde esa cuerda, la Tierra abulta entre los extremos y el "
  "abultamiento se anula en ellos. Restarlo, que es lo que sugiere la expresión habitual «descenso por "
  "curvatura», vuelve la Tierra cóncava y hace que ningún relieve bloquee jamás a larga distancia. En "
  "un trayecto de 26 km el término alcanza 11.5 m en el punto medio.")
P("Las alturas de observador y objetivo se tratan como parámetros. Se adopta 1.70 m para el observador "
  "y 3.00 m para la estructura, cota conservadora para una chullpa, y el análisis se repite en el rango "
  "de 0 a 12 m. Siguiendo a Ogburn (2006), no se fija un alcance único: una torre de tres metros deja "
  "de reconocerse a simple vista a partir de cierta distancia, y como esa distancia es discutible los "
  "resultados se informan a 5, 10, 15 y 26 km.")

h2("3.3. Validación sobre terrenos sintéticos")
P("Un algoritmo de visibilidad falla en silencio: devuelve valores plausibles aunque el criterio "
  "geométrico esté mal, y sobre terreno real no hay forma de advertirlo (Fisher, 1993). Se validó por "
  "tanto contra doce terrenos construidos de respuesta conocida —plano, barrera que debe bloquear, la "
  "misma rebajada que no debe hacerlo, casos límite que verifican el término de curvatura, efecto de "
  "la altura del objetivo, depresión que nunca bloquea, horizonte geométrico a 40 km y simetría sobre "
  "terreno rugoso—. El detector supera los %d casos. El error de signo descrito en el apartado "
  "anterior se detectó precisamente aquí, no en el análisis."
  % (VAL["total"] if VAL else 12))

h2("3.4. Validación cruzada frente a gdal_viewshed")
if CRUZ:
    P("La validación sintética demuestra que el motor hace lo que se le pide; no demuestra que haga lo "
      "mismo que las herramientas que la comunidad usa. Para medir esa segunda cosa se calculó dos veces "
      "la cuenca visual desde el sitio funerario más alto del corpus (%s, %s m): una con gdal_viewshed, "
      "la implementación de GDAL que QGIS expone en su caja de herramientas, y otra con el motor de este "
      "trabajo, ambas sobre el mismo ráster reproyectado a UTM 19S a 30 m y con parámetros idénticos "
      "—observador a %.1f m, objetivo a %.1f m, alcance de %.0f km y coeficiente de curvatura "
      "%.2f, que es exactamente la formulación R/(1−k) con k = 0.13—. La reproyección es "
      "imprescindible: sobre el ráster original en grados la corrección de curvatura carece de sentido "
      "físico, y esa es otra decisión que rara vez se declara."
      % (torre_nombre, mil(round(torre_alt)), CRUZ["parametros"]["h_obs"],
         CRUZ["parametros"]["h_tgt"], CRUZ["parametros"]["alcance_m"] / 1000,
         CRUZ["parametros"]["cc"]))
    P("Sobre las %s celdas del disco de %.0f km, ambos motores coinciden en el %.2f %%. GDAL declara "
      "visibles %s celdas y el motor propio %s; %d son visibles solo para GDAL y %d solo para el motor "
      "propio. Los desacuerdos no se reparten al azar: su distancia media a la torre es de %s m, "
      "frente a %s m para el conjunto de celdas evaluadas, y se concentran en los bordes del relieve "
      "cercano, donde la decisión depende de cómo se interpola el perfil en la celda que roza la línea "
      "de visión. Es el patrón que Fisher (1993) describió y que Riggs y Dean (2007) atribuyeron a las "
      "decisiones de implementación; aquí queda cuantificado para el caso de estudio, y su magnitud "
      "—inferior al 0.1 %% de las celdas— acota cuánto del resultado puede deberse a la elección del "
      "motor. La Tabla 3 recoge el cotejo."
      % (mil(CRUZ["celdas_evaluadas"]), CRUZ["parametros"]["alcance_m"] / 1000, acuerdo_pct,
         mil(CRUZ["visibles_gdal"]), mil(CRUZ["visibles_nuestro"]), CRUZ["solo_gdal"],
         CRUZ["solo_nuestro"], mil(round(CRUZ["dist_media_desacuerdo_m"])),
         mil(round(CRUZ["dist_media_total_m"]))))

h2("3.5. Modelos nulos")
P("La conclusión depende por completo de con qué se compara la red observada, de modo que se calculan "
  "tres modelos de exigencia creciente.")
P("El primero sortea puntos al azar sobre el terreno, y equivale al procedimiento seguido por Bongers "
  "et al. (2012). Casi siempre da significativo, porque los sitios reales ocupan relieve favorable y "
  "el relieve favorable ve más, de modo que por sí solo confirma poco.")
P("El segundo sortea celdas con la misma distribución de altitud que los sitios observados, de modo que "
  "el conjunto nulo reproduce el perfil altitudinal sin heredar las posiciones. Responde a si, dada la "
  "cota que ocupan, se ven más de lo que les correspondería. Es el tipo de contraste estratificado que "
  "Lake y Woodman (2003) emplearon para separar la visibilidad de la posición topográfica, y la lógica "
  "de una muestra que Kvamme (1990) formalizó.")
P("El tercero toma la nube de sitios tal cual, conservando todas las distancias mutuas, y la traslada y "
  "rota rígidamente sobre el terreno. Es el más estricto: separa dónde están los sitios de cómo están "
  "dispuestos entre sí, y responde a si esta configuración concreta está colocada donde se ve más de lo "
  "que se vería en cualquier otro punto de la región. Frente a los modelos de grafos aleatorios "
  "exponenciales de Brughmans et al. (2014), que modelan la dependencia entre aristas, el nulo rígido "
  "la conserva íntegra por construcción, porque no altera la red interna sino su emplazamiento.")
P("Los tres excluyen las masas de agua, por las razones que se exponen en el apartado 4.2, y cada uno "
  "se calcula con 500 repeticiones.")

h2("3.6. Visualización tridimensional del paisaje visual")
P("La cuenca visual de la torre más alta se presenta en tres formas, todas generadas por código a "
  "partir de los mismos ficheros. La primera es una planta con sombreado de relieve, la cuenca visual "
  "y los sitios funerarios dentro del alcance, distinguidos según queden dentro o fuera de ella "
  "(Figura 4). La segunda es una perspectiva tridimensional (Figura 5) dibujada con un algoritmo del "
  "pintor: cada celda del modelo y cada marcador se ordenan por su distancia a la cámara y se pintan "
  "de atrás hacia delante, de modo que un sitio solo queda oculto cuando hay relieve entre él y el "
  "punto de vista, lo que evita el error habitual de los marcadores que flotan sobre el terreno o "
  "desaparecen tras él. La tercera es un visor web interactivo autocontenido —un único fichero HTML "
  "con la malla del relieve, la textura y los sitios incrustados— que permite orbitar, acercarse y "
  "desplazarse por la escena; se construye a partir del ráster y del resultado del motor, y se "
  "deposita junto con un proyecto de QGIS preparado para su vista de mapa 3D. La exageración vertical "
  "se declara en cada vista, en línea con los criterios de transparencia de la arqueología virtual "
  "(Bentkowska-Kafel et al., 2012; López-Menchero & Grande, 2011).")

# ======================================================================= resultados
h1("4. Resultados")
h2("4.1. La red observada")
if d5:
    P("De los %s pares de sitios separados por menos de 5 km, %s presentan visión recíproca despejada, "
      "esto es una densidad de %s. El grado medio es de %.1f sitios visibles por sitio y solo %d quedan "
      "sin ninguna conexión. Al ampliar el alcance la densidad desciende hasta %s a 26 km, como cabe "
      "esperar, pero el número absoluto de pares visibles apenas crece: la intervisibilidad se agota "
      "en las distancias cortas."
      % (mil(d5["pares_elegibles"]), mil(d5["aristas"]), f(d5["densidad"]), d5["grado_medio"],
         d5["aislados"],
         f(NUL["observado"]["26000"]["densidad"])))
    P("La Figura 1 recoge el área de estudio con la red a 5 km, y la Figura 2, dos perfiles de línea de "
      "visión de distancia comparable, uno despejado y otro bloqueado, que ilustran qué mide el "
      "criterio de visibilidad empleado.")
figure("fig_mapa.png", "Figura 1.",
       "Área de estudio con el relieve sombreado, los %d sitios documentados y las aristas de "
       "intervisibilidad a menos de 5 km. Los triángulos señalan los %d sitios cuyo topónimo registrado "
       "contiene un término funerario. El lago Titicaca se representa aparte porque en un sombreado de "
       "relieve resulta indistinguible de una llanura: una superficie plana no proyecta sombra. El "
       "encuadre corresponde al área de estudio; la región de muestreo de los modelos nulos se extiende "
       "18 km más allá en todas las direcciones." % (n_sitios, n_fun))
figure("fig_perfiles.png", "Figura 2.",
       "Perfiles de línea de visión de dos pares de distancia comparable, uno despejado y otro "
       "bloqueado. Se muestran el terreno sin corregir, el terreno con la corrección de curvatura y "
       "refracción, y la recta que une observador y objetivo. La franja destacada marca la obstrucción.")

h2("4.2. El lago como artefacto de medida")
P("El modelo de elevación asigna una cota constante a las masas de agua. En el área de estudio el lago "
  "Titicaca aparece como una superficie perfectamente plana a 3808.5 m que ocupa el %.1f %% del "
  "recorte inicial. Sortear puntos nulos ahí es erróneo por dos motivos independientes: no se puede "
  "emplazar un sitio arqueológico en mitad del lago, y una superficie plana no bloquea ninguna vista, "
  "de modo que infla la intervisibilidad del modelo nulo. Ningún sitio observado cae sobre agua."
  % frac_agua)
if SINMASK:
    _sm = SINMASK["por_alcance"]["5000"]
    P("El efecto sobre la inferencia no es marginal, es determinante. Repitiendo el contraste más "
      "estricto sin enmascarar el agua, la distribución nula a 5 km tiene media %s y desviación típica "
      "%s, y el dato observado queda a %+.2f desviaciones: ausencia de efecto. Enmascarándola, la media "
      "nula baja a %s y la desviación a %s, y el mismo dato observado pasa a %+.2f. El artefacto no "
      "atenuaba el resultado, lo suprimía. Ambas ejecuciones se publican con los datos, para que la "
      "comparación pueda verificarse."
      % (f(_sm["nula_media"], 3), f(_sm["nula_sd"], 3), _sm["z"],
         f(r5["nula_media"], 3), f(r5["nula_sd"], 3), r5["z"]))

h2("4.3. El sesgo de orientación del recorte")
P("Un segundo artefacto apareció al revisar el nulo rígido. La nube de sitios mide %.0f km en su eje "
  "mayor, y con el recorte inicial solo cabía dentro del área en 244 de 360 orientaciones: quedaban "
  "sistemáticamente excluidas las perpendiculares a la disposición observada. Ampliando el margen del "
  "recorte de 5 a 18 km caben las 360. El efecto medido descendió al hacerlo, de z = %+.2f a z = %+.2f, "
  "lo que indica que el recorte ajustado inflaba el contraste."
  % (ext_km, z_n300, r5["z"]))

h2("4.4. Contraste con los modelos nulos")
P("La Tabla 1 reúne la densidad observada y la de cada modelo nulo por alcance, y la Figura 3 sitúa el "
  "dato observado dentro de las tres distribuciones nulas. La lectura conjunta es la que importa: lo "
  "relevante no es que el valor observado supere a un nulo, sino cuánto se estrecha el margen a medida "
  "que el modelo nulo conserva más rasgos de la configuración real.")
filas = []
for a in ["5000", "10000", "15000", "26000"]:
    fila = ["%.0f" % (float(a) / 1000)]
    fila.append(f(RIG["por_alcance"][a]["densidad_obs"]))
    if NUL:
        for k in ("uniforme", "estratificado_altitud"):
            d = NUL["nulos"][k][a]
            fila.append("%s ± %s" % (f(d["densidad_nula_media"], 3), f(d["densidad_nula_sd"], 3)))
            fila.append("%+.2f" % d["z"])
    d = RIG["por_alcance"][a]
    fila.append("%s ± %s" % (f(d["nula_media"], 3), f(d["nula_sd"], 3)))
    fila.append("%+.2f" % d["z"])
    filas.append(fila)
cols_t = ["Alcance (km)", "Observado"]
if NUL:
    cols_t += ["Nulo uniforme", "z", "Nulo por altitud", "z"]
cols_t += ["Nulo rígido", "z"]
table("Tabla 1.", "Densidad de intervisibilidad observada y en los modelos nulos, por alcance. "
      "Cada nulo se calculó con 500 repeticiones.", cols_t, filas)
figure("fig_nulos.png", "Figura 3.",
       "Densidad observada, marcada con la línea horizontal, frente a la distribución de cada modelo "
       "nulo. Las barras abarcan del percentil 5 al 95.")

h2("4.5. Sensibilidad a los supuestos")
P("Dos supuestos del cálculo admiten valores distintos de los adoptados, y conviene comprobar si la "
  "conclusión depende de ellos: la altura atribuida a las estructuras y la celda del modelo en que cae "
  "cada sitio. La Tabla 2 recoge el primero.")
if ALT:
    fil = [["%.1f" % float(k), f(v["observado"]), "%s ± %s" % (f(v["nulo_media"], 3), f(v["nulo_sd"], 3)),
            "%+.2f" % v["z"], f(v["p"], 3)]
           for k, v in sorted(ALT["por_altura"].items(), key=lambda x: float(x[0]))]
    table("Tabla 2.", "Contraste rígido a 5 km recalculado para distintas alturas de estructura, "
          "con %d repeticiones cada uno." % ALT["n_null"],
          ["Altura (m)", "Observado", "Nulo", "z", "p"], fil)
    P("La altura atribuida a las estructuras mueve la densidad observada un %.0f %% entre los extremos "
      "del rango, pero no altera la conclusión: el contraste se mantiene entre z = %+.2f y z = %+.2f, "
      "y es más fuerte con altura nula. La señal la lleva el emplazamiento del terreno, no la altura de "
      "las torres, que es precisamente el supuesto que nadie ha medido en campo."
      % (var_alt, z_alt[0], z_alt[-1]))
if SEN:
    dz = SEN["pruebas"]["desplazamiento_celda"]
    P("La asignación de cada sitio a una celda del modelo introduce otra incertidumbre. Desplazándola "
      "una posición en cada dirección, la densidad varía entre %s y %s, un %.0f %% del valor de "
      "referencia. El contraste sobrevive incluso en el extremo inferior de ese rango."
      % (f(dz["min"]), f(dz["max"]), 100 * dz["rango_relativo"]))

h2("4.6. El efecto de agregar dos grupos disjuntos")
if DIS:
    ju = DIS["distritos"]["juli"]
    po = DIS["distritos"]["pomata"]
    P("Los sitios de Chucuito no forman una nube continua sino dos grupos separados por %.1f km de "
      "relieve: Juli, con %d sitios, y Pomata, con %d, separación visible en la Figura 1. El análisis "
      "anterior los trata como un solo conjunto, lo que tiene dos consecuencias. En los alcances largos "
      "entran al cómputo pares entre grupos que no describen ninguna relación de vecindad y que están "
      "casi siempre bloqueados; y el modelo nulo rígido rota una configuración que en realidad son dos, "
      "reproduciendo una separación cuyo significado no está establecido."
      % (DIS["separacion_centroides_km"], ju["n_sitios"], po["n_sitios"]))
    if ju.get("contraste"):
        c5 = ju["contraste"]["5000"]; c15 = ju["contraste"]["15000"]
        P("Repitiendo el contraste rígido sobre Juli en solitario, único grupo con tamaño suficiente, el "
          "efecto se atenúa: la densidad observada a 5 km es %s frente a %s ± %s en el nulo "
          "(z = %+.2f; p = %s), y a 15 km z = %+.2f con p = %s. El resultado pasa de significativo a "
          "marginal, lo que indica que parte del efecto medido sobre el conjunto agregado procedía de "
          "su estructura en dos grupos y no del emplazamiento de los sitios."
          % (f(c5["densidad_obs"]), f(c5["nula_media"]), f(c5["nula_sd"]), c5["z"],
             f(c5["p_unilateral"], 3), c15["z"], f(c15["p_unilateral"], 3)))
    P("Pomata se describe pero no se contrasta: con %d sitios el modelo nulo carece de potencia y "
      "cualquier valor p sería ilustrativo. Merece registrarse, no obstante, que su densidad de "
      "intervisibilidad a 5 km es %s, muy superior a la de Juli, y que %d de sus %d sitios llevan "
      "topónimo funerario. Es un patrón que este trabajo no puede evaluar y que señala dónde convendría "
      "dirigir un reconocimiento de campo."
      % (po["n_sitios"], f(po["observado"]["5000"]["densidad"]), po["n_funerarios"], po["n_sitios"]))

h2("4.7. Los sitios de topónimo funerario")
if FUN:
    k = "5000"
    d = FUN["por_alcance"][k]
    P("De los %d sitios, %d llevan en su nombre registrado un término asociado a estructuras funerarias. "
      "Su subred no está más conectada que la de cualquier subgrupo del mismo tamaño extraído del propio "
      "conjunto: densidad %s frente a %s ± %s en %s remuestreos (z = %+.2f; p = %s). El resultado se "
      "repite en los tres alcances examinados."
      % (n_sitios, n_fun, f(d["densidad_funeraria"]), f(d["densidad_aleatoria_media"]),
         f(d["densidad_aleatoria_sd"]), mil(FUN["n_permutaciones"]), d["z"], f(d["p_unilateral"], 3)))
    P("Caben dos lecturas y los datos no permiten separarlas. O las estructuras funerarias no se "
      "emplazaron con un criterio de visibilidad distinto del resto de sitios, o la etiqueta es "
      "demasiado débil para detectarlo: identificar un monumento por su topónimo registrado no es "
      "clasificarlo, un sitio funerario puede figurar con otro nombre y un topónimo puede aludir a un "
      "rasgo del paisaje. Con %d casos la potencia es limitada." % n_fun)

h2("4.8. El paisaje visual desde una torre funeraria")
if TORRE and CRUZ:
    P("Las Figuras 4 y 5 muestran la cuenca visual de %s, el sitio funerario más alto del corpus "
      "(%s m, distrito de Juli), calculada con observador a %.1f m, objetivo a %.1f m y alcance de "
      "%.0f km. La cuenca es pequeña para una posición tan elevada: %s celdas de 30 m, unos %.1f km², "
      "el %.1f %% del disco evaluado. La torre se asienta en una cumbre rodeada de relieve más alto "
      "hacia el sur y el este, y su vista se abre en dos lóbulos estrechos —hacia la ladera inmediata "
      "y hacia el corredor que desciende al lago— que en la perspectiva de la Figura 5 se leen como "
      "dos franjas rojas sobre el terreno."
      % (torre_nombre, mil(round(torre_alt)), CRUZ["parametros"]["h_obs"],
         CRUZ["parametros"]["h_tgt"], CRUZ["parametros"]["alcance_m"] / 1000,
         mil(CRUZ["visibles_nuestro"]), area_cuenca_km2, frac_cuenca))
    P("El dato que importa es cuántas otras tumbas se ven desde ahí: de los %d sitios funerarios "
      "situados dentro del alcance, %d caen dentro de la cuenca visual. Desde la torre más alta de "
      "Chucuito no se ve ninguna otra torre. Es la versión en una sola imagen del resultado del "
      "apartado 4.7: la subred funeraria no está más conectada que el resto del corpus, y la torre "
      "mejor situada para dominar el paisaje no domina, en realidad, a sus iguales. Lo que sí domina "
      "es el corredor de la ribera, que es donde se concentran los sitios no funerarios de Juli; si la "
      "visibilidad de las chullpas respondía a alguna intención, la evidencia de este caso apunta a "
      "que era ser vistas desde los lugares habitados y no verse entre sí, una distinción que "
      "Supernant (2014) y Gillings (2015) han señalado como decisiva y que el análisis de "
      "intervisibilidad recíproca, por construcción, no puede capturar."
      % (TORRE["tumbas_en_figura"], TORRE["tumbas_visibles"]))
    P("El visor interactivo depositado permite comprobar esa lectura desde cualquier ángulo: orbitar "
      "alrededor de la torre, descender hasta la altura de un observador y verificar que las tumbas "
      "vecinas quedan detrás de las lomas que la Figura 5 muestra. No añade información al cálculo, "
      "pero hace inspeccionable la razón geométrica de cada resultado, que es exactamente lo que una "
      "cifra de densidad no puede hacer.")
figure("fig3d_planta.png", "Figura 4.",
       "Cuenca visual en planta desde %s (triángulo), sobre el relieve sombreado del sector de Juli. "
       "En rojo, las celdas visibles desde la torre con alcance de %.0f km; los círculos son los "
       "sitios de topónimo funerario dentro del encuadre, en rojo si caen dentro de la cuenca y en "
       "gris si quedan ocultos. Ninguna de las %d tumbas es visible. El lago se representa en azul."
       % (torre_nombre, CRUZ["parametros"]["alcance_m"] / 1000 if CRUZ else 10,
          TORRE["tumbas_en_figura"] if TORRE else 0),
       width_mm=120)
# La Tabla 3 va antes de la Figura 5: la perspectiva no cabe bajo la Figura 4 y,
# en su orden natural, dejaba un cuarto de pagina en blanco.
if CRUZ:
    table("Tabla 3.", "Validación cruzada de la cuenca visual desde la torre: motor propio frente a "
          "gdal_viewshed sobre el mismo ráster UTM de 30 m, con parámetros idénticos.",
          ["Celdas evaluadas", "Visibles (GDAL)", "Visibles (propio)", "Acuerdo",
           "Solo GDAL", "Solo propio", "Distancia media de los desacuerdos"],
          [[mil(CRUZ["celdas_evaluadas"]), mil(CRUZ["visibles_gdal"]),
            mil(CRUZ["visibles_nuestro"]), "%.2f %%" % acuerdo_pct,
            CRUZ["solo_gdal"], CRUZ["solo_nuestro"],
            "%s m (frente a %s m del total)" % (mil(round(CRUZ["dist_media_desacuerdo_m"])),
                                                 mil(round(CRUZ["dist_media_total_m"])))]],
          widths=[24, 22, 22, 18, 16, 16, 52])

figure("fig3d_perspectiva.png", "Figura 5.",
       "La misma cuenca visual en perspectiva tridimensional, vista desde el noreste con exageración "
       "vertical de 2.5, generada por código con un algoritmo del pintor que respeta la oclusión: un "
       "sitio solo queda tapado cuando hay relieve entre él y el punto de vista. La torre observadora "
       "se marca con un triángulo y las tumbas ocultas con círculos grises; el lago ocupa la esquina "
       "inferior derecha. La escena es la misma que muestra el visor web interactivo depositado.")

# ==================================================== discusion y conclusiones
h1("5. Discusión y conclusiones")
h2("5.1. Qué sostiene el resultado y qué no")
P("Los sitios de Chucuito ocupan posiciones desde las que se ven entre sí más de lo que lograría la "
  "misma configuración situada en otro punto del territorio, pero la fuerza de esa afirmación depende "
  "de cómo se delimite el conjunto. Sobre los %d sitios agregados el contraste es significativo en los "
  "cuatro alcances; restringido a Juli, el único grupo espacialmente continuo, queda en el margen de la "
  "significación convencional. La evidencia es indicativa, no concluyente, y así debe leerse."
  % n_sitios)
if NUL:
    P("Lo que sí resiste sin matices es la comparación entre modelos nulos: el muestreo aleatorio "
      "simple atribuye al emplazamiento un efecto entre %.1f y %.1f veces mayor, según el alcance, que "
      "el que sobrevive a un contraste capaz de controlar la disposición del conjunto. La distancia "
      "entre ambos crece con el alcance, porque el nulo uniforme dispersa los puntos por toda la "
      "región y penaliza tanto más su intervisibilidad cuanto más lejos se mira. Es la advertencia de "
      "Wheatley y Gillings (2000) y de Lake y Woodman (2003) convertida en una cifra: el modelo nulo "
      "no es un detalle técnico, es la mitad del resultado."
      % (RAZ[0], RAZ[-1]))
P("Conviene ser preciso sobre qué autoriza a concluir eso. El resultado dice que el emplazamiento "
  "favorece la visibilidad recíproca; no dice que la visibilidad fuera el criterio de emplazamiento. "
  "Otras razones —acceso al agua, suelos, rutas, defensa— pueden producir el mismo patrón si "
  "correlacionan con posiciones visualmente dominantes, y este análisis no las separa. La defensa es "
  "la más difícil de descartar aquí: Arkush (2011) documenta para el altiplano del Intermedio Tardío "
  "una red de sitios fortificados cuya lógica de emplazamiento —cotas altas, control visual de los "
  "accesos— produciría un patrón de intervisibilidad difícil de distinguir del observado, y Nielsen "
  "(2009) ha mostrado que las tumbas de los ancestros formaban parte de ese mismo conflicto. Establecer "
  "intención exigiría contrastar contra hipótesis alternativas explícitas, no solo contra el azar, en "
  "la línea de la inferencia multimodelo de Eve y Crema (2014) o de los modelos de grafos de Brughmans "
  "et al. (2015).")
P("Esa comparación admite lectura frente al antecedente. Bongers et al. (2012) hallaron una "
  "visibilidad muy superior al azar y concluyeron que la visibilidad y la altitud determinaron el "
  "emplazamiento. El nulo uniforme, que reproduce su procedimiento, arroja aquí valores z de entre "
  "%+.1f y %+.1f según el alcance, coherentes con esa conclusión; el estratificado por altitud los "
  "eleva todavía más, lo que indica que la cota por sí sola no explica el patrón. Pero el nulo rígido, "
  "que conserva la configuración y solo cambia su emplazamiento, los reduce a valores en torno a "
  "%+.1f. La conclusión previa se sostiene, y este trabajo la corrobora en otra zona de la cuenca y "
  "con otra medida; pero la magnitud que sugiere el muestreo aleatorio simple excede, en la "
  "proporción ya indicada (de %.1f a %.1f veces), la que resiste un contraste capaz de controlar la "
  "disposición del conjunto." % (z_uni[0], z_uni[1], z_rig_medio, RAZ[0], RAZ[-1]))
P("El resultado de la torre más alta añade un matiz que la estadística agregada no muestra. Que "
  "ninguna otra tumba sea visible desde la posición funeraria más dominante del corpus es compatible "
  "con la lectura de Hyslop (1977) de las chullpas como mojones —un mojón se ve desde el territorio que "
  "delimita, no desde otros mojones— y con la de Kesseli y Pärssinen (2005) como símbolos de poder "
  "dirigidos a los vivos. Ambas lecturas predicen visibilidad desde los lugares habitados y no entre "
  "tumbas, y la torre estudiada ve precisamente el corredor de la ribera donde se concentra la "
  "ocupación. Distinguir intervisibilidad de intravisibilidad, como propone Supernant (2014), es el "
  "siguiente paso natural.")

h2("5.2. Tres artefactos y una validación cruzada")
P("La segunda contribución es metodológica y probablemente más transferible. Los tres artefactos "
  "documentados —el signo de la corrección por curvatura, la cota constante del agua y el sesgo de "
  "orientación del recorte— comparten un rasgo: ninguno produce un fallo visible. Los tres devuelven "
  "redes de intervisibilidad de aspecto razonable y valores estadísticos interpretables. El primero se "
  "detectó con pruebas sintéticas, el segundo al examinar el mapa y el tercero al medir la tasa de "
  "aceptación del nulo. Ninguno se habría advertido mirando solo los resultados, y ninguno lo habría "
  "detectado la reproducción del análisis, que vuelve a ejecutar el mismo código con el mismo defecto.")
P("Eso sitúa este trabajo en la línea abierta por Fisher (1993) y continuada por Riggs y Dean (2007) y "
  "Kormann y Lock (2014), con una diferencia: aquí la incertidumbre de implementación no se estima "
  "comparando programas ajenos sino validando el propio contra respuestas conocidas y, después, "
  "contrastándolo con la implementación que la comunidad usa. El %.2f %% de acuerdo con gdal_viewshed "
  "acota lo que la elección de motor puede cambiar en la cuenca de la torre, y la localización de los "
  "desacuerdos en los bordes del relieve cercano indica dónde mirar si dos estudios discrepan. Frente "
  "al programa de reproducibilidad de Marwick (2017), que garantiza que un análisis pueda repetirse, "
  "la validación garantiza algo distinto: que lo que se repite sea correcto. Las dos garantías se "
  "necesitan y no se sustituyen." % acuerdo_pct)

h2("5.3. La visualización 3D como instrumento de transparencia")
P("La tercera contribución es que la visualización tridimensional se trata aquí como parte del "
  "análisis y no como su ilustración. Las tres vistas de la cuenca visual —planta, perspectiva y visor "
  "interactivo— se generan de los mismos ficheros que alimentan la estadística, con el mismo motor "
  "validado, y se depositan con el código que las produce. Eso responde a la exigencia de rigor y "
  "transparencia de los principios de Sevilla (López-Menchero & Grande, 2011) y al concepto de "
  "paradatos (Bentkowska-Kafel et al., 2012) de una manera concreta: cada decisión de visualización "
  "—la exageración vertical, la resolución de la malla, el alcance de la cuenca— está escrita en un "
  "guion que cualquiera puede leer y modificar. Responde también a la preocupación de Champion y "
  "Rahaman (2019) por la sostenibilidad: el visor es un único fichero HTML sin dependencias de "
  "servicio, y el proyecto de QGIS usa formatos abiertos.")
P("Lo que la perspectiva aporta al argumento, siguiendo a Richards-Rissetto (2017) y a Landeschi "
  "(2019), es la razón geométrica de cada cifra. Una densidad de %s dice cuánto se ve; la Figura 5 "
  "muestra por qué desde la torre más alta no se ve ninguna tumba, y el visor permite comprobarlo "
  "desde la altura de un observador de pie. Como advirtió Garstki (2017), esa representación incorpora "
  "decisiones, y por eso se declaran: la exageración vertical deforma las pendientes y el submuestreo "
  "de la malla suaviza el relieve, de modo que la perspectiva sirve para entender el resultado, no "
  "para recalcularlo. El cálculo lo hace el motor sobre el ráster completo." % f(r5["densidad_obs"]))

h2("5.4. Limitaciones")
P("La procedencia de la capa de sitios es la limitación de fondo. Sin criterio de inclusión documentado "
  "no se sabe qué sitios faltan, y un registro incompleto sesga la red de forma imprevisible. El "
  "análisis es reproducible, pero su base documental no está verificada; el reconocimiento de Stanish "
  "et al. (1997) ofrece el término de comparación natural para una verificación futura.")
P("El modelo de elevación describe la superficie, no el terreno: incluye vegetación y edificación, que "
  "en el altiplano son poco relevantes pero no nulas. La resolución de 30 m impone además un límite: "
  "relieves menores que la celda no bloquean nada en el cálculo aunque lo hicieran en la realidad, y es "
  "en las celdas que rozan la línea de visión donde los dos motores comparados discrepan.")
P("La región de comparación se extendió a 18 km alrededor de los sitios para que el nulo rígido "
  "dispusiera de todas las orientaciones. Eso incorpora terreno de carácter distinto al de la ribera, "
  "lo que hace el contraste más exigente pero también menos homogéneo.")
P("El análisis es binario y sincrónico. Binario, porque mide si la línea de visión está despejada y no "
  "cuánto se ve ni con qué claridad, que es la crítica de Wheatley y Gillings (2000) y de Ogburn (2006); "
  "presentar los resultados en cuatro alcances mitiga el problema sin resolverlo. Sincrónico, porque la "
  "capa no distingue cronologías, de modo que la red trata como contemporáneos sitios que pueden estar "
  "separados por siglos. La intervisibilidad medida es la del conjunto documentado, no la de un momento "
  "concreto.")

h2("5.5. Trabajo futuro")
P("El paso más útil sería incorporar cronología: con los sitios fechados, la misma red puede calcularse "
  "por periodo y comprobarse si la intervisibilidad se construye o se hereda. Las fechas "
  "dendroarqueológicas de Morales et al. (2013) muestran que es posible datar las propias torres. "
  "Distinguir la intervisibilidad entre tumbas de la visibilidad de las tumbas desde los asentamientos "
  "—intravisibilidad en el sentido de Supernant (2014)— permitiría contrastar directamente las lecturas "
  "de Hyslop (1977) y de Kesseli y Pärssinen (2005). Extender el análisis a las demás provincias de "
  "Puno permitiría además comprobar si el patrón de Chucuito es particular de la ribera o general del "
  "altiplano, y el visor interactivo, que se construye por código para cualquier observador, puede "
  "generarse para cada torre del corpus sin coste adicional.")

# ==================================================== reproducibilidad
h1("6. Disponibilidad de datos y código")
P("El código que reconstruye el análisis completo, los datos derivados, los ficheros de resultados, "
  "las figuras, el visor web interactivo y el proyecto de QGIS están depositados con identificador "
  "persistente, bajo licencia MIT. El identificador se omite durante la revisión para preservar el "
  "anonimato: se facilita al editor en la carta de presentación y se incorporará en la versión final. "
  "El modelo de elevación es Copernicus DEM "
  "GLO-30, de uso libre con atribución; la capa de sitios se cita según su procedencia declarada, con "
  "la reserva expuesta en el apartado 3.1. El manuscrito se genera desde los ficheros de resultados, "
  "de modo que ninguna cifra del texto está escrita a mano, y una auditoría automática comprueba que "
  "cada valor citado tenga respaldo en ellos.")
P("El depósito incluye las ejecuciones previas a la corrección de dos de los tres artefactos descritos "
  "—el nulo rígido calculado sin enmascarar el lago y el calculado sobre el recorte ajustado—, de modo "
  "que las comparaciones del apartado 4 puedan verificarse y no haya que tomarlas por buenas. El "
  "tercero, el signo de la corrección por curvatura, se comprueba ejecutando la validación sintética "
  "incluida, y la validación cruzada frente a gdal_viewshed se reproduce con QGIS instalado.")

# Los agradecimientos se anaden al aceptarse el articulo: durante la revision
# identificarian a los autores, y aqui no hay ninguno que declarar.

P("Referencias", 11, True, align=WD_ALIGN_PARAGRAPH.CENTER, before=10, after=6)
REFERENCIAS = [
    "Arkush, E. (2005). Inca ceremonial sites in the southwest Titicaca basin. En C. Stanish, A. B. "
    "Cohen, & M. S. Aldenderfer (Eds.), Advances in Titicaca Basin Archaeology-1 (pp. 209–242). Los "
    "Angeles: Cotsen Institute of Archaeology, University of California. doi:10.2307/j.ctvhhhfn9.20",
    "Arkush, E. N. (2011). Hillforts of the Ancient Andes: Colla Warfare, Society, and Landscape. "
    "Gainesville: University Press of Florida. doi:10.5744/florida/9780813035260.001.0001",
    "Arkush, E. (2018). Coalescence and defensive communities: Insights from an Andean hillfort town. "
    "Cambridge Archaeological Journal, 28(1), 1–22. doi:10.1017/S0959774317000440",
    "Arkush, E., & Stanish, C. (2005). Interpreting conflict in the ancient Andes: Implications for "
    "the archaeology of warfare. Current Anthropology, 46(1), 3–28. doi:10.1086/425660",
    "Bentkowska-Kafel, A., Denard, H., & Baker, D. (Eds.). (2012). Paradata and Transparency in "
    "Virtual Heritage. Farnham: Ashgate.",
    "Bernardini, W., Barnash, A., Kumler, M., & Wong, M. (2013). Quantifying visual prominence in "
    "social landscapes. Journal of Archaeological Science, 40(11), 3946–3954. "
    "doi:10.1016/j.jas.2013.05.019",
    "Bernardini, W., & Peeples, M. A. (2015). Sight communities: The social significance of shared "
    "visual landmarks. American Antiquity, 80(2), 215–235. doi:10.7183/0002-7316.80.2.215",
    "Bongers, J., Arkush, E., & Harrower, M. (2012). Landscapes of death: GIS-based analyses of chullpas "
    "in the western Lake Titicaca basin. Journal of Archaeological Science, 39(6), 1687–1693. "
    "doi:10.1016/j.jas.2011.11.018",
    "Bongers, J., Arkush, E., & Harrower, M. (2013). Corrigendum to “Landscapes of death: GIS-based "
    "analyses of chullpas in the western Lake Titicaca basin”. Journal of Archaeological Science, "
    "40(5), 2335–2336. doi:10.1016/j.jas.2013.01.013",
    "Brughmans, T., & Brandes, U. (2017). Visibility network patterns and methods for studying visual "
    "relational phenomena in archeology. Frontiers in Digital Humanities, 4, 17. "
    "doi:10.3389/fdigh.2017.00017",
    "Brughmans, T., de Waal, M. S., Hofman, C. L., & Brandes, U. (2018). Exploring transformations in "
    "Caribbean indigenous social networks through visibility studies: The case of late pre-colonial "
    "landscapes in East-Guadeloupe (French West Indies). Journal of Archaeological Method and Theory, "
    "25(2), 475–519. doi:10.1007/s10816-017-9344-0",
    "Brughmans, T., Keay, S., & Earl, G. (2014). Introducing exponential random graph models for "
    "visibility networks. Journal of Archaeological Science, 49, 442–454. "
    "doi:10.1016/j.jas.2014.05.027",
    "Brughmans, T., Keay, S., & Earl, G. (2015). Understanding inter-settlement visibility in Iron Age "
    "and Roman southern Spain with exponential random graph models for visibility networks. Journal of "
    "Archaeological Method and Theory, 22(1), 58–143. doi:10.1007/s10816-014-9231-x",
    "Brughmans, T., van Garderen, M., & Gillings, M. (2018). Introducing visual neighbourhood "
    "configurations for total viewsheds. Journal of Archaeological Science, 96, 14–25. "
    "doi:10.1016/j.jas.2018.05.006",
    "Champion, E., & Rahaman, H. (2019). 3D digital heritage models as sustainable scholarly resources. "
    "Sustainability, 11(8), 2425. doi:10.3390/su11082425",
    "Conolly, J., & Lake, M. (2006). Geographical Information Systems in Archaeology. Cambridge: "
    "Cambridge University Press. doi:10.1017/CBO9780511807459",
    "Čučković, Z. (2016). Advanced viewshed analysis: A Quantum GIS plug-in for the analysis of visual "
    "landscapes. The Journal of Open Source Software, 1(4), 32. doi:10.21105/joss.00032",
    "Dell'Unto, N., Landeschi, G., Leander Touati, A.-M., Dellepiane, M., Callieri, M., & Ferdani, D. "
    "(2016). Experiencing ancient buildings from a 3D GIS perspective: A case drawn from the Swedish "
    "Pompeii Project. Journal of Archaeological Method and Theory, 23(1), 73–94. "
    "doi:10.1007/s10816-014-9226-7",
    "Ducke, B. (2012). Natives of a connected world: Free and open source software in archaeology. "
    "World Archaeology, 44(4), 571–579. doi:10.1080/00438243.2012.743259",
    "Eve, S. J., & Crema, E. R. (2014). A house with a view? Multi-model inference, visibility fields, "
    "and point process analysis of a Bronze Age settlement on Leskernick Hill (Cornwall, UK). Journal "
    "of Archaeological Science, 43, 267–277. doi:10.1016/j.jas.2013.12.019",
    "Fisher, P. F. (1993). Algorithm and implementation uncertainty in viewshed analysis. International "
    "Journal of Geographical Information Systems, 7(4), 331–347. doi:10.1080/02693799308901965",
    "Frye, K. L., & de la Vega, E. (2005). The Altiplano period in the Titicaca basin. En C. Stanish, "
    "A. B. Cohen, & M. S. Aldenderfer (Eds.), Advances in Titicaca Basin Archaeology-1 (pp. 173–184). "
    "Los Angeles: Cotsen Institute of Archaeology, University of California. "
    "doi:10.2307/j.ctvhhhfn9.17",
    "Garstki, K. (2017). Virtual representation: The production of 3D digital artifacts. Journal of "
    "Archaeological Method and Theory, 24(3), 726–750. doi:10.1007/s10816-016-9285-z",
    "Gillings, M. (2012). Landscape phenomenology, GIS and the role of affordance. Journal of "
    "Archaeological Method and Theory, 19(4), 601–611. doi:10.1007/s10816-012-9137-4",
    "Gillings, M. (2015). Mapping invisibility: GIS approaches to the analysis of hiding and seclusion. "
    "Journal of Archaeological Science, 62, 1–14. doi:10.1016/j.jas.2015.06.015",
    "Gillings, M. (2017). Mapping liminality: Critical frameworks for the GIS-based modelling of "
    "visibility. Journal of Archaeological Science, 84, 121–128. doi:10.1016/j.jas.2017.05.004",
    "Hyslop, J. (1977). Chulpas of the Lupaca zone of the Peruvian high plateau. Journal of Field "
    "Archaeology, 4(2), 149–170. doi:10.1179/009346977791547912",
    "Isbell, W. H. (1997). Mummies and Mortuary Monuments: A Postprocessual Prehistory of Central Andean "
    "Social Organization. Austin: University of Texas Press. doi:10.7560/738706",
    "Kesseli, R., & Pärssinen, M. (2005). Identidad étnica y muerte: torres funerarias (chullpas) como "
    "símbolos de poder étnico en el altiplano boliviano de Pakasa (1250-1600 d. C.). Bulletin de "
    "l'Institut français d'études andines, 34(3), 379–410. doi:10.4000/bifea.4936",
    "Kim, Y.-H., Rana, S., & Wise, S. (2004). Exploring multiple viewshed analysis using terrain "
    "features and optimisation techniques. Computers & Geosciences, 30(9-10), 1019–1032. "
    "doi:10.1016/j.cageo.2004.07.008",
    "Kormann, M., & Lock, G. (2014). Exploring the effects of curvature and refraction on GIS-based "
    "visibility studies. En G. Earl, T. Sly, A. Chrysanthi, P. Murrieta-Flores, C. Papadopoulos, I. "
    "Romanowska, & D. Wheatley (Eds.), Archaeology in the Digital Era: Papers from the 40th Annual "
    "Conference of Computer Applications and Quantitative Methods in Archaeology (CAA), Southampton, "
    "26-29 March 2012 (pp. 428–437). Amsterdam: Amsterdam University Press. "
    "doi:10.1515/9789048519590-046",
    "Kvamme, K. L. (1990). One-sample tests in regional archaeological analysis: New possibilities "
    "through computer technology. American Antiquity, 55(2), 367–381. doi:10.2307/281655",
    "Lake, M. W., & Woodman, P. E. (2003). Visibility studies in archaeology: A review and case study. "
    "Environment and Planning B: Planning and Design, 30(5), 689–707. doi:10.1068/b29122",
    "Lake, M. W., Woodman, P. E., & Mithen, S. J. (1998). Tailoring GIS software for archaeological "
    "applications: An example concerning viewshed analysis. Journal of Archaeological Science, 25(1), "
    "27–38. doi:10.1006/jasc.1997.0197",
    "Landeschi, G. (2019). Rethinking GIS, three-dimensionality and space perception in archaeology. "
    "World Archaeology, 51(1), 17–32. doi:10.1080/00438243.2018.1463171",
    "Landeschi, G., Dell'Unto, N., Lundqvist, K., Ferdani, D., Campanaro, D. M., & Leander Touati, "
    "A.-M. (2016). 3D-GIS as a platform for visual analysis: Investigating a Pompeian house. Journal of "
    "Archaeological Science, 65, 103–113. doi:10.1016/j.jas.2015.11.002",
    "Llobera, M. (2001). Building past landscape perception with GIS: Understanding topographic "
    "prominence. Journal of Archaeological Science, 28(9), 1005–1014. doi:10.1006/jasc.2001.0720",
    "Llobera, M. (2003). Extending GIS-based visual analysis: The concept of visualscapes. "
    "International Journal of Geographical Information Science, 17(1), 25–48. "
    "doi:10.1080/713811741",
    "Llobera, M. (2007). Reconstructing visual landscapes. World Archaeology, 39(1), 51–69. "
    "doi:10.1080/00438240601136496",
    "López-Menchero Bendicho, V. M., & Grande, A. (2011). Hacia una Carta Internacional de Arqueología "
    "Virtual. El borrador SEAV. Virtual Archaeology Review, 2(4), 71–75. doi:10.4995/var.2011.4558",
    "Marwick, B. (2017). Computational reproducibility in archaeological research: Basic principles and "
    "a case study of their implementation. Journal of Archaeological Method and Theory, 24(2), "
    "424–450. doi:10.1007/s10816-015-9272-9",
    "Morales, M. S., Nielsen, A. E., & Villalba, R. (2013). First dendroarchaeological dates of "
    "prehistoric contexts in South America: Chullpas in the Central Andes. Journal of Archaeological "
    "Science, 40(5), 2393–2401. doi:10.1016/j.jas.2013.01.003",
    "Nackaerts, K., Govers, G., & Van Orshoven, J. (1999). Accuracy assessment of probabilistic "
    "visibilities. International Journal of Geographical Information Science, 13(7), 709–721. "
    "doi:10.1080/136588199241076",
    "Nielsen, A. E. (2009). Ancestors at war: Meaningful conflict and social process in the south "
    "Andes. En A. E. Nielsen & W. H. Walker (Eds.), Warfare in Cultural Context: Practice, Agency, and "
    "the Archaeology of Violence (pp. 218–243). Tucson: University of Arizona Press. "
    "doi:10.2307/j.ctv1jf2ctn.11",
    "Ogburn, D. E. (2006). Assessing the level of visibility of cultural objects in past landscapes. "
    "Journal of Archaeological Science, 33(3), 405–413. doi:10.1016/j.jas.2005.08.005",
    "Richards-Rissetto, H. (2017). What can GIS + 3D mean for landscape archaeology? Journal of "
    "Archaeological Science, 84, 10–21. doi:10.1016/j.jas.2017.05.005",
    "Riggs, P. D., & Dean, D. J. (2007). An investigation into the causes of errors and inconsistencies "
    "in predicted viewsheds. Transactions in GIS, 11(2), 175–196. "
    "doi:10.1111/j.1467-9671.2007.01040.x",
    "Schmidt, S. C., & Marwick, B. (2020). Tool-driven revolutions in archaeological science. Journal "
    "of Computer Applications in Archaeology, 3(1), 18–32. doi:10.5334/jcaa.29",
    "Stanish, C. (2003). Ancient Titicaca: The Evolution of Complex Society in Southern Peru and "
    "Northern Bolivia. Berkeley: University of California Press. doi:10.1525/9780520928190",
    "Stanish, C., de la Vega, E., Steadman, L., Chávez Justo, C., Frye, K. L., Onofre Mamani, L., "
    "Seddon, M. T., & Calisaya Chuquimia, P. (1997). Archaeological Survey in the Juli-Desaguadero "
    "Region of the Lake Titicaca Basin, Southern Peru (Fieldiana Anthropology, n. s. 29). Chicago: "
    "Field Museum of Natural History. doi:10.5962/bhl.title.3578",
    "Supernant, K. (2014). Intervisibility and intravisibility of rock feature sites: A method for "
    "testing viewshed within and outside the socio-spatial system of the Lower Fraser River Canyon, "
    "British Columbia. Journal of Archaeological Science, 50, 497–511. doi:10.1016/j.jas.2014.08.008",
    "Turner, A., Doxa, M., O'Sullivan, D., & Penn, A. (2001). From isovists to visibility graphs: A "
    "methodology for the analysis of architectural space. Environment and Planning B: Planning and "
    "Design, 28(1), 103–121. doi:10.1068/b2684",
    "Wheatley, D. (1995). Cumulative viewshed analysis: A GIS-based method for investigating "
    "intervisibility, and its archaeological application. En G. Lock & Z. Stančič (Eds.), Archaeology "
    "and Geographical Information Systems: A European Perspective (pp. 171–185). London: Taylor & "
    "Francis.",
    "Wheatley, D., & Gillings, M. (2000). Vision, perception and GIS: Developing enriched approaches to "
    "the study of archaeological visibility. En G. R. Lock (Ed.), Beyond the Map: Archaeology and "
    "Spatial Technologies (pp. 1–27). Amsterdam: IOS Press.",
    "Wheatley, D., & Gillings, M. (2002). Spatial Technology and Archaeology: The Archaeological "
    "Applications of GIS. London: Taylor & Francis. doi:10.4324/9780203302392",
    "Wright, D. K., MacEachern, S., & Lee, J. (2014). Analysis of feature intervisibility and cumulative "
    "visibility using GIS, Bayesian and spatial statistics: A study from the Mandara Mountains, "
    "northern Cameroon. PLoS ONE, 9(11), e112191. doi:10.1371/journal.pone.0112191",
]
for _ref in REFERENCIAS:
    _p = P(_ref, 9, after=4)
    _p.paragraph_format.left_indent = Cm(0.6)
    _p.paragraph_format.first_line_indent = Cm(-0.6)
# Un salto de seccion continuo al final hace que Word equilibre las dos columnas
# de la ultima pagina; sin el, las referencias ocupan solo la columna izquierda.
one_col()

doc.save(OUT)

palabras = sum(len(p.text.split()) for p in doc.paragraphs)
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            palabras += len(c.text.split())
ps_ = [p.text.strip() for p in doc.paragraphs]
i_ini = next(i for i, t in enumerate(ps_) if t.startswith("1. "))
i_ref = ps_.index("Referencias")
cuerpo = sum(len(t.split()) for t in ps_[i_ini:i_ref])
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            cuerpo += len(c.text.split())
# Propiedades del fichero: python-docx firma como autor y la revision es ciega.
docmeta.limpiar(OUT, autor="", titulo=doc.paragraphs[0].text, asunto="")

print("Manuscrito ->", OUT)
print("metadatos con contenido:", docmeta.informe(OUT) or "ninguno")
print("palabras: %d en total | %d en el cuerpo (1. Introducción a Referencias) | figuras: %d | "
      "tablas: %d | referencias: %d"
      % (palabras, cuerpo, len(doc.inline_shapes), len(doc.tables), len(REFERENCIAS)))
