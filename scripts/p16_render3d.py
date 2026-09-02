# -*- coding: utf-8 -*-
"""
Render 3D del terreno de Chucuito, generado por codigo (matplotlib).

Primer bloque del eje virtual para la version VAR-3D del articulo: superficie
con tinte hipsometrico + sombreado, lago plano en azul, exageracion vertical
visual. pyvista/VTK quedo descartado en esta maquina (sin contexto OpenGL
fuera de pantalla: fotograma vacio con dos construcciones de malla distintas);
matplotlib es mas lento pero fiable y mantiene todo en el mismo stack
reproducible del resto de figuras.

Pendiente para la figura definitiva: sitios como marcadores 3D, cuenca visual
drapeada desde una chullpa, y encuadres (panoramica + escala humana).
"""
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap

import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with rasterio.open(os.path.join(BASE, "data", "terreno_chucuito.tif")) as s:
    dem = s.read(1).astype(np.float32)
    tr = s.transform

z = np.flipud(dem[::3, ::3])
h, w = z.shape
x = np.arange(w) * tr.a * 3 / 1000.0
y = np.arange(h) * (-tr.e) * 3 / 1000.0
X, Y = np.meshgrid(x, y)

hips = LinearSegmentedColormap.from_list("hips",
    ["#eef2ea", "#d9dfc9", "#c3b795", "#a8875f", "#8a6a4a", "#7d6a63"])
ls = LightSource(azdeg=315, altdeg=40)
rgb = ls.shade(z, cmap=hips, blend_mode="soft", vert_exag=8,
               dx=tr.a * 3, dy=-tr.e * 3)
agua = np.abs(z - 3808.5) < 0.05
rgb[agua] = (0.788, 0.847, 0.906, 1.0)

fig = plt.figure(figsize=(9, 6))
ax = fig.add_subplot(111, projection="3d")
ax.plot_surface(X, Y, z, facecolors=rgb, rstride=1, cstride=1,
                linewidth=0, antialiased=False, shade=False)
ax.set_zlim(z.min(), z.min() + (z.max() - z.min()) * 3)
ax.view_init(elev=42, azim=-115)
ax.set_axis_off()
ax.set_box_aspect((w / h, 1, 0.22))
fig.tight_layout(pad=0)
out = os.path.join(BASE, "results", "figuras", "prueba_3d.png")
fig.savefig(out, dpi=200)
print("->", out)
