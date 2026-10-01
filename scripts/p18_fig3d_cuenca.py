# -*- coding: utf-8 -*-
"""
Figura 3D: el paisaje visual desde una torre funeraria.

Sobre el relieve real de Chucuito (UTM, exageracion vertical), se drapea la
cuenca visual calculada desde el sitio funerario mas alto del corpus
(Gentilmoko Yacari, 4 145 m) y se situan los demas sitios funerarios: los que
caen dentro de la cuenca se marcan distinto de los ocultos. Es la pregunta del
articulo hecha imagen: desde donde se enterraba a los ancestros, ¿que otras
tumbas se veian?

Todo por codigo, en el mismo stack reproducible del resto. Salida a 300 ppp.
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
import matplotlib.patheffects
from matplotlib.colors import LightSource, LinearSegmentedColormap
from rasterio.warp import transform as tcoords

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
FIG = os.path.join(RES, "figuras")
UTM = "EPSG:32719"

VIS = "#b91c1c"       # cuenca visible, el rojo del sistema
OCULTO = "#3b4252"    # sitios fuera de la cuenca
OBS_C = "#111827"


def main():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))

    # recorte centrado en el observador, ~12 km de lado, para que la escena
    # sea legible y la torre domine
    oc, of = None, None
    xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    ocf, off = ~tr * (xs[0], ys[0])
    oc, of = int(round(ocf)), int(round(off))
    r = int(6000 / 30)
    f0, f1 = max(0, of - r), min(dem.shape[0], of + r)
    c0, c1 = max(0, oc - r), min(dem.shape[1], oc + r)
    z = dem[f0:f1:2, c0:c1:2]
    vcrop = vs[f0:f1:2, c0:c1:2]
    h, w = z.shape
    X, Y = np.meshgrid(np.arange(w) * 60 / 1000.0, np.arange(h) * 60 / 1000.0)

    # tinte hipsometrico + sombreado, y la cuenca en rojo translucido encima
    hips = LinearSegmentedColormap.from_list("h",
        ["#eef2ea", "#d9dfc9", "#c3b795", "#a8875f", "#8a6a4a", "#7d6a63"])
    ls = LightSource(azdeg=315, altdeg=42)
    rgb = ls.shade(z, cmap=hips, blend_mode="soft", vert_exag=6, dx=60, dy=60)
    agua = np.abs(z - 3808.5) < 0.05
    rgb[agua] = (0.788, 0.847, 0.906, 1.0)
    vis = vcrop == 1
    rgb[vis, 0] = 0.72 + 0.28 * rgb[vis, 0]
    rgb[vis, 1] = 0.10 + 0.30 * rgb[vis, 1]
    rgb[vis, 2] = 0.10 + 0.30 * rgb[vis, 2]

    fig = plt.figure(figsize=(9, 6.2))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, z, facecolors=rgb, rstride=1, cstride=1,
                    linewidth=0, antialiased=False, shade=False)

    # los sitios funerarios sobre el relieve
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    n_vis, n_oc = 0, 0
    for row in rows:
        if row["funerario"] != "True":
            continue
        gx, gy = float(row["x_m"]), float(row["y_m"])  # placeholders; usamos lon/lat
        lon, lat = float(row["lon"]), float(row["lat"])
        ux, uy = tcoords("EPSG:4326", UTM, [lon], [lat])
        cc, ff = ~tr * (ux[0], uy[0])
        cc, ff = int(round(cc)), int(round(ff))
        if not (f0 <= ff < f1 and c0 <= cc < c1):
            continue
        xk = (cc - c0) * 30 / 1000.0
        yk = (ff - f0) * 30 / 1000.0
        zk = dem[ff, cc]
        visible = vs[ff, cc] == 1
        if int(row["id"]) == int(obs["id"]):
            ax.scatter([xk], [yk], [zk + 60], s=90, marker="^",
                       color=OBS_C, edgecolor="white", linewidth=0.8, zorder=10)
        elif visible:
            ax.scatter([xk], [yk], [zk + 30], s=34, marker="o",
                       color=VIS, edgecolor="white", linewidth=0.5, zorder=9)
            n_vis += 1
        else:
            ax.scatter([xk], [yk], [zk + 30], s=24, marker="o",
                       color=OCULTO, edgecolor="white", linewidth=0.4, zorder=8)
            n_oc += 1

    ax.set_zlim(z.min(), z.min() + (z.max() - z.min()) * 3)
    ax.view_init(elev=38, azim=-118)
    ax.set_axis_off()
    ax.set_box_aspect((w / h, 1, 0.28))

    # leyenda manual
    from matplotlib.lines import Line2D
    leg = [Line2D([0], [0], marker="^", color="w", markerfacecolor=OBS_C,
                  markersize=11, label="Observing tower (Gentilmoko Yacari, 4145 m)"),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=VIS,
                  markersize=9, label="Funerary site within the viewshed"),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=OCULTO,
                  markersize=8, label="Funerary site hidden from the tower")]
    ax.legend(handles=leg, loc="upper left", frameon=False, fontsize=8.5,
              bbox_to_anchor=(0.02, 0.98))
    fig.tight_layout(pad=0.4)
    out = os.path.join(FIG, "fig3d_cuenca.png")
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print("-> %s | funerarios visibles %d, ocultos %d" % (out, n_vis, n_oc))


if __name__ == "__main__":
    main()


def figura_planta():
    """Version en planta: hillshade + cuenca + las 24 tumbas.

    En 3D matplotlib no ordena en profundidad superficie y marcadores, y las
    tumbas quedan tapadas por el relieve. En planta el dato se lee sin ambiguedad:
    la torre mas alta y que tumbas ve y cuales no.
    """
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))
    xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    ocf, off = ~tr * (xs[0], ys[0]); oc, of = int(round(ocf)), int(round(off))
    r = int(10500 / 30)
    f0, f1 = max(0, of - r), min(dem.shape[0], of + r)
    c0, c1 = max(0, oc - r), min(dem.shape[1], oc + r)
    z = dem[f0:f1, c0:c1]; vcrop = vs[f0:f1, c0:c1]
    ext = [0, (c1 - c0) * 30 / 1000, 0, (f1 - f0) * 30 / 1000]

    # Fondo: ortoimagen Sentinel-2 de estacion seca (p22) en la misma ventana,
    # con un sombreado de relieve suave multiplicado para leer la topografia.
    from rasterio.windows import from_bounds
    from rasterio.enums import Resampling as Rs
    x0, y0 = tr.c + c0 * tr.a, tr.f + f0 * tr.e
    x1, y1 = tr.c + c1 * tr.a, tr.f + f1 * tr.e
    with rasterio.open(os.path.join(DATA, "ortofoto_s2.tif")) as so:
        win = from_bounds(x0, y1, x1, y0, transform=so.transform)
        orto = so.read(window=win, out_shape=(3, 3 * (f1 - f0), 3 * (c1 - c0)),
                       resampling=Rs.bilinear, boundless=True).transpose(1, 2, 0) / 255.0
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(z, vert_exag=3, dx=30, dy=30)
    hs = np.kron(hs, np.ones((3, 3)))
    rgb = np.clip(orto * (0.55 + 0.6 * hs[..., None]), 0, 1)

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    ax.imshow(np.flipud(rgb), extent=ext, origin="lower")
    vis_m = np.ma.masked_where(vcrop != 1, np.ones_like(z))
    ax.imshow(np.flipud(vis_m), extent=ext, origin="lower",
              cmap=matplotlib.colors.ListedColormap([VIS]), alpha=0.5)
    ax.contour(np.flipud((vcrop == 1).astype(float)), levels=[0.5], extent=ext,
               origin="lower", colors=[VIS], linewidths=0.9)

    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    n_vis = n_oc = 0
    for row in rows:
        if row["funerario"] != "True":
            continue
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        cc, ff = ~tr * (ux[0], uy[0]); cc, ff = int(round(cc)), int(round(ff))
        if not (f0 <= ff < f1 and c0 <= cc < c1):
            continue
        # el eje y crece hacia el norte y las filas hacia el sur: hay que invertirlas
        xk = (cc - c0 + 0.5) * 30 / 1000; yk = (f1 - ff - 0.5) * 30 / 1000
        if int(row["id"]) == int(obs["id"]):
            ax.plot(xk, yk, "^", ms=15, color=OBS_C, mec="white", mew=1.2, zorder=6)
        elif vs[ff, cc] == 1:
            ax.plot(xk, yk, "o", ms=8, color=VIS, mec="white", mew=0.8, zorder=5); n_vis += 1
        else:
            ax.plot(xk, yk, "o", ms=7, color=OCULTO, mec="white", mew=0.6, zorder=5); n_oc += 1

    from matplotlib.lines import Line2D
    leg = [Line2D([0], [0], marker="^", color="w", markerfacecolor=OBS_C, markersize=13,
                  label="Torre observadora (%s m)"
                        % "{:,}".format(round(obs["altitud"])).replace(",", " ")),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=VIS, markersize=9,
                  label="Tumba dentro de la cuenca visual (%d)" % n_vis),
           Line2D([0], [0], marker="o", color="w", markerfacecolor=OCULTO, markersize=8,
                  label="Tumba oculta a la torre (%d)" % n_oc)]
    ax.legend(handles=leg, loc="upper right", frameon=True, framealpha=0.9,
              fontsize=8.5, edgecolor="#c7cdd6")
    # barra de escala
    ax.plot([1, 6], [1, 1], color="white", lw=4.5, solid_capstyle="butt")
    ax.plot([1, 6], [1, 1], color="#111827", lw=2.5, solid_capstyle="butt")
    ax.text(3.5, 1.35, "5 km", ha="center", fontsize=8.5, color="white",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="#111827")])
    # norte
    ax.annotate("N", xy=(ext[0] + 1.0, ext[3] - 0.8), xytext=(ext[0] + 1.0, ext[3] - 2.4),
                ha="center", va="center", fontsize=9, fontweight="bold", color="white",
                arrowprops=dict(arrowstyle="-|>", color="white", lw=1.4),
                path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="#111827")])
    meta_o = json.load(open(os.path.join(RES, "ortofoto_s2.json"), encoding="utf-8"))
    ax.text(ext[1] - 0.3, 0.3, "Imagen: Copernicus Sentinel-2, %s" % meta_o["fecha"],
            ha="right", va="bottom", fontsize=6.5, color="white",
            path_effects=[matplotlib.patheffects.withStroke(linewidth=1.5, foreground="#111827")])
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Cuenca visual desde la torre funeraria más alta (Juli): %d de %d "
                 "tumbas al alcance son visibles" % (n_vis, n_vis + n_oc),
                 fontsize=9.5, loc="left", color="#111827")
    fig.tight_layout(pad=0.6)
    out = os.path.join(FIG, "fig3d_planta.png")
    fig.savefig(out, dpi=300)
    plt.close(fig)
    # El recuento va a un JSON para que el manuscrito lo lea en lugar de
    # escribirlo a mano: es la misma disciplina que el resto de cifras.
    # Que mas ve la torre: sitios no funerarios a menos de 10 km dentro de la
    # cuenca, celdas de lago en ella, y en que direcciones se abre.
    import math
    ox_, oy_ = xs[0], ys[0]
    nf_tot = nf_vis = 0
    for row in rows:
        if row["funerario"] == "True":
            continue
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        if math.hypot(ux[0] - ox_, uy[0] - oy_) > 10000:
            continue
        cc, ff = ~tr * (ux[0], uy[0])
        nf_tot += 1
        nf_vis += int(vs[int(round(ff)), int(round(cc))] == 1)
    lago_vis = int(((np.abs(dem - 3808.5) < 0.05) & (vs == 1)).sum())
    json.dump({"observador": obs["nombre"].strip(), "altitud_m": round(float(obs["altitud"]), 1),
               "alcance_m": 10000, "radio_figura_m": 10500,
               "tumbas_en_figura": n_vis + n_oc, "tumbas_visibles": n_vis,
               "tumbas_ocultas": n_oc,
               "no_funerarios_a_10km": nf_tot, "no_funerarios_visibles": nf_vis,
               "celdas_lago_visibles": lago_vis},
              open(os.path.join(RES, "cuenca_torre.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("-> %s | visibles %d, ocultos %d" % (out, n_vis, n_oc))


if os.environ.get("PLANTA"):
    figura_planta()
