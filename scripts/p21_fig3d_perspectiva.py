# -*- coding: utf-8 -*-
"""
Perspectiva 3D del paisaje visual desde una torre funeraria, por codigo.

La version con plot_surface de matplotlib (p18) no ordena en profundidad la
superficie y los marcadores, y las tumbas quedan tapadas por el relieve aunque
esten delante. Aqui se proyecta el terreno a mano y se dibuja con el algoritmo
del pintor: cada celda del modelo y cada marcador se ordenan por su distancia
a la camara y se pintan de atras hacia delante, de modo que un sitio solo queda
oculto cuando de verdad hay relieve entre el y la camara. Es la misma escena
que el visor interactivo (p20), congelada para la pagina impresa.

Entradas: data/terreno_utm.tif, results/viewshed_nuestro.npy,
          results/observador_3d.json, data/sitios_chucuito.csv
Salida:   results/figuras/fig3d_perspectiva.png (300 ppp)
"""
import csv
import json
import math
import os

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import LightSource, LinearSegmentedColormap
from matplotlib.lines import Line2D
from rasterio.warp import transform as tcoords

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
FIG = os.path.join(RES, "figuras")
UTM = "EPSG:32719"

VIS = "#b91c1c"
OCULTO = "#3b4252"
OBS_C = "#111827"
AGUA = (0.788, 0.847, 0.906)

PASO = 2            # submuestreo del DEM: 60 m por celda
RADIO_M = 7000      # semilado del recorte alrededor de la torre
EXAG = 2.5          # exageracion vertical
AZIMUT = 215.0      # rotacion de la escena; la camara queda al noreste, sobre el lago
ELEV = 34.0         # elevacion de la camara sobre el horizonte


def proyectar(x, y, z, az, el):
    """Proyeccion ortografica oblicua: devuelve (sx, sy, profundidad)."""
    a, e = math.radians(az), math.radians(el)
    xr = x * math.cos(a) - y * math.sin(a)
    yr = x * math.sin(a) + y * math.cos(a)
    sx = xr
    sy = yr * math.sin(e) + z * math.cos(e)
    prof = yr * math.cos(e) - z * math.sin(e)   # mayor = mas lejos de la camara
    return sx, sy, prof


def main():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))
    xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    ocf, off = ~tr * (xs[0], ys[0])
    oc, of = int(round(ocf)), int(round(off))

    r = int(RADIO_M / 30)
    f0, f1 = max(0, of - r), min(dem.shape[0], of + r)
    c0, c1 = max(0, oc - r), min(dem.shape[1], oc + r)
    z = dem[f0:f1:PASO, c0:c1:PASO]
    vcrop = vs[f0:f1:PASO, c0:c1:PASO]
    h, w = z.shape
    res = 30.0 * PASO
    # coordenadas en km: x hacia el este, y hacia el norte (la fila 0 es el norte)
    X = np.arange(w) * res / 1000.0
    Y = (h - 1 - np.arange(h)) * res / 1000.0
    XX, YY = np.meshgrid(X, Y)
    z0 = float(np.nanmin(z))
    ZZ = (z - z0) / 1000.0 * EXAG

    # colores: tinte hipsometrico + sombreado, agua y cuenca visual
    hips = LinearSegmentedColormap.from_list("h",
        ["#eef2ea", "#d9dfc9", "#c3b795", "#a8875f", "#8a6a4a", "#7d6a63"])
    ls = LightSource(azdeg=315, altdeg=42)
    rgb = ls.shade(z, cmap=hips, blend_mode="soft", vert_exag=4, dx=res, dy=res)[..., :3]
    agua = np.abs(z - 3808.5) < 0.05
    rgb[agua] = AGUA
    vis = vcrop == 1
    rgb[vis, 0] = 0.70 + 0.30 * rgb[vis, 0]
    rgb[vis, 1] = 0.12 + 0.30 * rgb[vis, 1]
    rgb[vis, 2] = 0.12 + 0.30 * rgb[vis, 2]

    SX, SY, PR = proyectar(XX, YY, ZZ, AZIMUT, ELEV)

    # un cuadrilatero por celda, con su color y su profundidad media
    q = np.stack([
        np.stack([SX[:-1, :-1], SY[:-1, :-1]], -1),
        np.stack([SX[:-1, 1:], SY[:-1, 1:]], -1),
        np.stack([SX[1:, 1:], SY[1:, 1:]], -1),
        np.stack([SX[1:, :-1], SY[1:, :-1]], -1)], axis=2)      # (h-1, w-1, 4, 2)
    quads = q.reshape(-1, 4, 2)
    cols = rgb[:-1, :-1].reshape(-1, 3)
    prof = (0.25 * (PR[:-1, :-1] + PR[:-1, 1:] + PR[1:, 1:] + PR[1:, :-1])).reshape(-1)

    # marcadores: sitios funerarios dentro del recorte, con su profundidad
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    marcas = []
    for row in rows:
        if row["funerario"] != "True":
            continue
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        cc, ff = ~tr * (ux[0], uy[0]); cc, ff = int(round(cc)), int(round(ff))
        if not (f0 <= ff < f1 and c0 <= cc < c1):
            continue
        i, j = min((ff - f0) // PASO, h - 1), min((cc - c0) // PASO, w - 1)
        zk = (dem[ff, cc] - z0) / 1000.0 * EXAG
        sx, sy, pr = proyectar(X[j], Y[i], zk, AZIMUT, ELEV)
        marcas.append((pr, sx, sy, int(row["id"]) == int(obs["id"]), vs[ff, cc] == 1))

    # pintor: de atras hacia delante, intercalando los marcadores. Todos los
    # artistas comparten zorder, de modo que el orden de insercion es el de
    # dibujo y una celda cercana tapa al marcador que tiene detras.
    orden = np.argsort(-prof)
    quads, cols, prof = quads[orden], cols[orden], prof[orden]
    marcas.sort(key=lambda m: -m[0])
    Z = 1

    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    ax.set_aspect("equal")

    def bloque(a, b):
        if b > a:
            ax.add_collection(PolyCollection(quads[a:b], facecolors=cols[a:b],
                                             edgecolors=cols[a:b], linewidths=0.3,
                                             antialiased=True, zorder=Z))

    k = 0
    n_vis = n_oc = 0
    for (pr, sx, sy, es_obs, visible) in marcas:
        k2 = int(np.searchsorted(-prof, -pr))
        bloque(k, k2); k = k2
        if es_obs:
            ax.plot([sx, sx], [sy, sy + 0.05], color=OBS_C, lw=1.3, zorder=Z)
            ax.plot(sx, sy + 0.05, "^", ms=13, color=OBS_C, mec="white", mew=1.1, zorder=Z)
        elif visible:
            ax.plot([sx, sx], [sy, sy + 0.03], color=VIS, lw=0.9, zorder=Z)
            ax.plot(sx, sy + 0.03, "o", ms=7.5, color=VIS, mec="white", mew=0.8, zorder=Z)
            n_vis += 1
        else:
            ax.plot([sx, sx], [sy, sy + 0.03], color=OCULTO, lw=0.9, zorder=Z)
            ax.plot(sx, sy + 0.03, "o", ms=6.5, color=OCULTO, mec="white", mew=0.7, zorder=Z)
            n_oc += 1
    bloque(k, len(quads))

    ax.autoscale_view()
    ax.set_axis_off()
    leg = [Line2D([0], [0], marker="^", color="w", markerfacecolor=OBS_C, markersize=12,
                  label="Torre observadora (%s, %s m)"
                        % (" ".join(obs["nombre"].split()), "{:,}".format(round(obs["altitud"])).replace(",", "202f"))),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=VIS, markersize=9,
                  label="Sitio funerario dentro de la cuenca visual (%d)" % n_vis),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=OCULTO, markersize=8,
                  label="Sitio funerario oculto a la torre (%d)" % n_oc),
           Line2D([0], [0], marker="s", color="w", markerfacecolor="#d98080", markersize=9,
                  label="Cuenca visual de la torre (alcance 10 km)"),
           Line2D([0], [0], marker="s", color="w", markerfacecolor=AGUA, markersize=9,
                  label="Lago Titicaca (3 808.5 m)")]
    ax.legend(handles=leg, loc="upper left", frameon=False, fontsize=8.2)
    ax.text(0.99, 0.02, "Exageración vertical ×%.1f · Copernicus DEM GLO-30 · vista desde el noreste"
            % EXAG, transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5,
            color="#4a463f")
    fig.tight_layout(pad=0.3)
    out = os.path.join(FIG, "fig3d_perspectiva.png")
    fig.savefig(out, dpi=300, facecolor="white")
    plt.close(fig)
    print("-> %s | celdas %d | visibles %d, ocultos %d" % (out, len(quads), n_vis, n_oc))


if __name__ == "__main__":
    main()
