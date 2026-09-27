# -*- coding: utf-8 -*-
"""
Construye un proyecto QGIS listo para la vista 3D, sin tocar la GUI.

Carga el terreno proyectado (UTM 19S), la cuenca visual de GDAL y los sitios
arqueologicos (con los funerarios resaltados), les aplica estilo, fija el CRS
del proyecto y lo guarda como .qgz. El usuario solo abre ese fichero y ya tiene
todo cargado; la vista 3D se abre con dos clics (Ver -> Vistas de mapa 3D).

Se ejecuta con el Python de QGIS:
    "C:\\Program Files\\QGIS 3.44.13\\bin\\python-qgis-ltr.bat" scripts\\p19_proyecto_qgis.py
"""
import os

from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer,
                       QgsVectorLayer, QgsCoordinateReferenceSystem,
                       QgsColorRampShader, QgsRasterShader,
                       QgsSingleBandPseudoColorRenderer, QgsHillshadeRenderer,
                       QgsMarkerSymbol, QgsSingleSymbolRenderer,
                       QgsRuleBasedRenderer)
from qgis.PyQt.QtGui import QColor

BASE = r"C:\Users\LENOVO\Documents\LIBROS\paper4"
DATA = os.path.join(BASE, "data")
RES = os.path.join(BASE, "results")
UTM = "EPSG:32719"

QgsApplication.setPrefixPath(r"C:\Program Files\QGIS 3.44.13\apps\qgis-ltr", True)
app = QgsApplication([], False)
app.initQgis()

proj = QgsProject.instance()
proj.setCrs(QgsCoordinateReferenceSystem(UTM))

# --- terreno: tinte hipsometrico ------------------------------------------
ter = QgsRasterLayer(os.path.join(DATA, "terreno_utm.tif"), "Relieve (Chucuito)")
prov = ter.dataProvider()
stats = prov.bandStatistics(1)
zmin, zmax = stats.minimumValue, stats.maximumValue
paradas = [
    (zmin, "#eef2ea"), (zmin + (zmax - zmin) * 0.2, "#d9dfc9"),
    (zmin + (zmax - zmin) * 0.4, "#c3b795"),
    (zmin + (zmax - zmin) * 0.6, "#a8875f"),
    (zmin + (zmax - zmin) * 0.8, "#8a6a4a"), (zmax, "#7d6a63"),
]
ramp = QgsColorRampShader(zmin, zmax)
ramp.setColorRampType(QgsColorRampShader.Interpolated)
ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(v, QColor(c))
                           for v, c in paradas])
sh = QgsRasterShader()
sh.setRasterShaderFunction(ramp)
ter.setRenderer(QgsSingleBandPseudoColorRenderer(prov, 1, sh))
proj.addMapLayer(ter)

# --- terreno: una copia como sombreado, debajo, para dar volumen en 2D -----
hs = QgsRasterLayer(os.path.join(DATA, "terreno_utm.tif"), "Sombreado")
hr = QgsHillshadeRenderer(hs.dataProvider(), 1, 315.0, 45.0)
hr.setZFactor(3.0)
hs.setRenderer(hr)
hs.renderer().setOpacity(0.5)
proj.addMapLayer(hs)

# --- cuenca visual de GDAL: rojo semitransparente sobre lo visible ---------
vs = os.path.join(RES, "viewshed_gdal.tif")
if os.path.exists(vs):
    cap = QgsRasterLayer(vs, "Cuenca visual (torre 4145 m)")
    ramp2 = QgsColorRampShader()
    ramp2.setColorRampType(QgsColorRampShader.Exact)
    ramp2.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(255, QColor(185, 28, 28, 150), "visible"),
    ])
    sh2 = QgsRasterShader(); sh2.setRasterShaderFunction(ramp2)
    cap.setRenderer(QgsSingleBandPseudoColorRenderer(cap.dataProvider(), 1, sh2))
    proj.addMapLayer(cap)

# --- sitios: puntos, funerarios en rojo, el resto en gris ------------------
uri = ("file:///" + os.path.join(DATA, "sitios_chucuito.csv").replace("\\", "/")
       + "?delimiter=,&xField=lon&yField=lat&crs=EPSG:4326")
sit = QgsVectorLayer(uri, "Sitios arqueológicos", "delimitedtext")

s_fun = QgsMarkerSymbol.createSimple({"name": "triangle", "color": "#b91c1c",
                                      "outline_color": "white", "size": "3.4"})
s_otro = QgsMarkerSymbol.createSimple({"name": "circle", "color": "#3b4252",
                                       "outline_color": "white", "size": "2.2"})
raiz = QgsRuleBasedRenderer.Rule(None)
r1 = QgsRuleBasedRenderer.Rule(s_fun, 0, 0, "\"funerario\" = 'True'", "Torre funeraria")
r2 = QgsRuleBasedRenderer.Rule(s_otro, 0, 0, "\"funerario\" != 'True'", "Otros sitios")
raiz.appendChild(r1); raiz.appendChild(r2)
sit.setRenderer(QgsRuleBasedRenderer(raiz))
proj.addMapLayer(sit)

# --- guardar ---------------------------------------------------------------
out = os.path.join(BASE, "chucuito_3d.qgz")
proj.write(out)
print("PROYECTO GUARDADO ->", out)
print("capas:", [l.name() for l in proj.mapLayers().values()])
app.exitQgis()
