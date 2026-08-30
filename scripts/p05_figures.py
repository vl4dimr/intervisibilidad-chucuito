# -*- coding: utf-8 -*-
"""
Figuras del articulo.

Figura 1 — el area de estudio: relieve sombreado, sitios y aristas de la red de
intervisibilidad. Es la unica figura que muestra el objeto real; el resto son
resumenes numericos y sin ella el lector no puede juzgar si la red se parece al
territorio.

Figura 2 — perfiles de linea de vision de dos pares, uno despejado y otro
bloqueado, con el terreno, la correccion por curvatura y la recta de vision.
Hace visible el criterio que decide cada arista, que de otro modo queda oculto
dentro del algoritmo.

Figura 3 — densidad observada frente a las distribuciones nulas, por alcance.
Es el contraste del articulo.

Las imagenes no llevan titulo ni numero incrustados: el numero depende del orden
de aparicion en el manuscrito y el pie es texto del documento.
"""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import line_of_sight

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RES = os.path.join(BASE, "results")
FIG = os.path.join(RES, "figuras")

HUE = "#2a78d6"
HUE2 = "#eb6834"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#dedddb"
SURFACE = "#fcfcfb"


def load():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        dem = src.read(1).astype(float)
    d = np.load(os.path.join(RES, "red_observada.npz"))
    with open(os.path.join(RES, "nulos.json"), encoding="utf-8") as f:
        nul = json.load(f)
    rp = os.path.join(RES, "nulo_rigido.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            nul["nulos"]["rigido"] = {k: {"densidad_nula_media": v["nula_media"],
                                          "densidad_nula_sd": v["nula_sd"],
                                          "densidad_nula_p05": v["nula_p05"],
                                          "densidad_nula_p95": v["nula_p95"],
                                          "z": v["z"], "p_unilateral": v["p_unilateral"]}
                                      for k, v in json.load(open(rp, encoding="utf-8"))["por_alcance"].items()}
    with open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8") as f:
        log = json.load(f)
    return rows, dem, d["vis"], d["dist"], nul, log


def hillshade(dem, az=315, alt=45, res=30.0):
    x, y = np.gradient(dem, res)
    slope = np.pi / 2 - np.arctan(np.hypot(x, y))
    aspect = np.arctan2(-x, y)
    az, alt = np.radians(360 - az + 90), np.radians(alt)
    return (np.sin(alt) * np.sin(slope) +
            np.cos(alt) * np.cos(slope) * np.cos(az - aspect))


# ------------------------------------------------------------------ figura 1
def fig_mapa(rows, dem, vis, dist, alcance=5000.0, margen_km=3.0):
    """Mapa del area de estudio, con convenciones cartograficas completas.

    Se encuadra a los sitios mas un margen corto, no al DEM completo: el modelo
    de elevacion se amplio a 18 km alrededor para que el nulo rigido dispusiera
    de todas las orientaciones, pero esa es la region de muestreo, no el area de
    estudio. El recuadro de situacion muestra ambas.

    El lago se pinta aparte porque en un sombreado de relieve es indistinguible
    de una llanura —una superficie plana no proyecta sombra— y sin embargo
    condiciona el resultado a traves del modelo nulo.

    El tintado hipsometrico va sobre el sombreado y no al reves: el relieve del
    altiplano tiene poco rango altitudinal y un mapa de color plano no deja ver
    las quebradas que bloquean las lineas de vision, que es lo que el articulo
    mide.
    """
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch, Rectangle
    from matplotlib.ticker import FuncFormatter
    import rasterio as _rio

    with _rio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        tr = src.transform

    cols = np.array([int(r["col"]) for r in rows])
    fils = np.array([int(r["fila"]) for r in rows])
    fun = np.array([r["funerario"] == "True" for r in rows])
    dist_l = np.array([r["distrito"].strip().lower() for r in rows])

    m = int(margen_km * 1000 / 30)
    c0, c1 = max(0, cols.min() - m), min(dem.shape[1], cols.max() + m)
    f0, f1 = max(0, fils.min() - m), min(dem.shape[0], fils.max() + m)
    sub = dem[f0:f1, c0:c1]
    cc, ff = cols - c0, fils - f0
    agua = np.abs(sub - 3808.5) < 0.05

    fig, ax = plt.subplots(figsize=(10.0, 6.4), dpi=300, facecolor=SURFACE)

    tierra = np.where(agua, np.nan, sub)
    vmin = float(np.nanpercentile(tierra, 1))
    vmax = float(np.nanpercentile(tierra, 99))
    hips = mcolors.LinearSegmentedColormap.from_list(
        "altiplano", ["#eef2ea", "#d9dfc9", "#c3b795", "#a8875f", "#8a6a4a", "#7d6a63"])
    ax.imshow(np.ma.masked_invalid(tierra), cmap=hips, vmin=vmin, vmax=vmax, zorder=0)
    hs = hillshade(sub)
    ax.imshow(hs, cmap="Greys_r", vmin=np.percentile(hs, 2), vmax=np.percentile(hs, 98),
              alpha=0.45, zorder=1)

    if agua.any():
        capa = np.zeros(agua.shape + (4,))
        capa[agua] = (0.60, 0.74, 0.85, 1.0)
        ax.imshow(capa, zorder=2)

    n = len(rows)
    vm = (dist <= alcance) & vis
    seg = 0
    for i in range(n):
        for j in range(i + 1, n):
            if vm[i, j]:
                ax.plot([cc[i], cc[j]], [ff[i], ff[j]], color="#1c4f8f",
                        linewidth=0.28, alpha=0.30, zorder=3)
                seg += 1

    ax.scatter(cc[~fun], ff[~fun], s=15, c="white", edgecolors=INK, linewidths=0.55,
               zorder=4, label="sitio arqueológico (%d)" % int((~fun).sum()))
    ax.scatter(cc[fun], ff[fun], s=34, c=HUE2, edgecolors=INK, linewidths=0.55,
               zorder=5, marker="^", label="topónimo funerario (%d)" % int(fun.sum()))

    # toponimos de los dos distritos, en el centroide de cada grupo
    for d, etiq in (("juli", "JULI"), ("pomata", "POMATA")):
        k = dist_l == d
        if k.sum():
            ax.text(cc[k].mean(), ff[k].mean() - 26, etiq, fontsize=9,
                    color="#3a3a38", ha="center", va="bottom", zorder=6,
                    fontweight="bold", alpha=0.75)

    # --- reticula de coordenadas
    def lon_de(col):
        return tr.c + (c0 + col) * tr.a

    def lat_de(fil):
        return tr.f + (f0 + fil) * tr.e

    lon0, lon1 = lon_de(0), lon_de(sub.shape[1])
    lat1, lat0 = lat_de(sub.shape[0]), lat_de(0)
    paso = 0.05
    xt = [(v - tr.c) / tr.a - c0 for v in np.arange(np.ceil(lon0 / paso) * paso, lon1, paso)]
    yt = [(v - tr.f) / tr.e - f0 for v in np.arange(np.ceil(lat1 / paso) * paso, lat0, paso)]
    ax.set_xticks(xt); ax.set_yticks(yt)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%.2f°O" % abs(lon_de(v))))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%.2f°S" % abs(lat_de(v))))
    ax.tick_params(labelsize=7.5, colors=INK_SOFT, length=3, width=0.6, color=GRID)
    ax.grid(color="white", linewidth=0.5, alpha=0.45, zorder=2.5)
    ax.set_axisbelow(False)

    ax.set_xlim(0, sub.shape[1]); ax.set_ylim(sub.shape[0], 0)
    for sp in ax.spines.values():
        sp.set_color("#9a9a96"); sp.set_linewidth(0.8)

    # --- escala graduada
    px = 1000.0 / 30.0
    x0, y0, alto = 30, sub.shape[0] - 30, 7
    for i in range(5):
        ax.add_patch(Rectangle((x0 + i * px, y0 - alto), px, alto,
                               facecolor=INK if i % 2 == 0 else "white",
                               edgecolor=INK, linewidth=0.6, zorder=7))
    for i, v in ((0, "0"), (5, "5 km")):
        ax.text(x0 + i * px, y0 - alto - 4, v, fontsize=7.5, color=INK,
                ha="center", va="bottom", zorder=7)

    nx, ny = sub.shape[1] - 40, 30
    ax.annotate("", xy=(nx, ny), xytext=(nx, ny + 42),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5), zorder=7)
    ax.text(nx, ny + 58, "N", ha="center", va="top", fontsize=10,
            color=INK, zorder=7, fontweight="bold")

    h, l = ax.get_legend_handles_labels()
    h.append(plt.Line2D([], [], color="#1c4f8f", lw=1.1, alpha=0.7))
    l.append("intervisibilidad < 5 km")
    if agua.any():
        h.append(Patch(facecolor=(0.60, 0.74, 0.85), edgecolor="none"))
        l.append("lago Titicaca")
    leg = ax.legend(h, l, loc="lower right", fontsize=8, frameon=True, framealpha=0.95)
    leg.get_frame().set_edgecolor("#9a9a96")
    leg.get_frame().set_linewidth(0.6)
    for t in leg.get_texts():
        t.set_color("#3a3a38")

    # --- recuadro de situacion: area de estudio dentro de la region de muestreo
    ins = ax.inset_axes([0.012, 0.60, 0.20, 0.37])
    dz = np.where(np.abs(dem - 3808.5) < 0.05, np.nan, dem)
    ins.imshow(np.ma.masked_invalid(dz), cmap="Greys", alpha=0.5,
               vmin=np.nanpercentile(dz, 2), vmax=np.nanpercentile(dz, 98))
    lago_full = np.abs(dem - 3808.5) < 0.05
    capa2 = np.zeros(lago_full.shape + (4,))
    capa2[lago_full] = (0.60, 0.74, 0.85, 1.0)
    ins.imshow(capa2)
    ins.add_patch(Rectangle((c0, f0), c1 - c0, f1 - f0, fill=False,
                            edgecolor=HUE2, linewidth=1.3))
    ins.set_xticks([]); ins.set_yticks([])
    ins.set_title("región de muestreo", fontsize=6.5, color=INK_SOFT, pad=3)
    for sp in ins.spines.values():
        sp.set_color("#9a9a96"); sp.set_linewidth(0.7)

    fig.tight_layout()
    out = os.path.join(FIG, "fig_mapa.png")
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out, seg


# ------------------------------------------------------------------ figura 2
def fig_perfiles(rows, dem, vis, dist, log):
    res_x, res_y = log["dem_resolucion_m_aprox"]
    cols = np.array([int(r["col"]) for r in rows])
    fils = np.array([int(r["fila"]) for r in rows])

    # un par despejado y otro bloqueado, ambos de distancia parecida
    objetivo = 6000.0
    cand_v, cand_b = None, None
    best_v, best_b = 1e9, 1e9
    n = len(rows)
    for i in range(n):
        for j in range(i + 1, n):
            d = dist[i, j]
            if d < 3000 or d > 9000:
                continue
            e = abs(d - objetivo)
            if vis[i, j] and e < best_v:
                best_v, cand_v = e, (i, j)
            if not vis[i, j] and e < best_b:
                best_b, cand_b = e, (i, j)

    fig, axes = plt.subplots(2, 1, figsize=(9.0, 5.6), dpi=300, facecolor=SURFACE)
    for ax, par, titulo in ((axes[0], cand_v, "vista despejada"),
                            (axes[1], cand_b, "vista bloqueada")):
        i, j = par
        _, prof = line_of_sight(dem, res_x, res_y, cols[i], fils[i], cols[j], fils[j],
                                return_profile=True)
        km = prof["d"] / 1000.0
        ax.fill_between(km, prof["z_corr"], prof["z_corr"].min() - 20,
                        color="#d8d6d1", zorder=1, label="terreno con corrección")
        ax.plot(km, prof["z"], color=INK_SOFT, linewidth=0.9, linestyle=(0, (3, 2)),
                zorder=2, label="terreno sin corregir")
        ax.plot(km, prof["sight"], color=HUE, linewidth=2.0, zorder=3, label="línea de visión")
        blocked = prof["z_corr"] > prof["sight"]
        if blocked[1:-1].any():
            ax.fill_between(km, prof["sight"], prof["z_corr"], where=blocked,
                            color=HUE2, alpha=0.55, zorder=4, label="obstrucción")
        ax.set_ylabel("altitud (m)", fontsize=8.5, color=INK_SOFT)
        def limpio(t):
            return "".join(ch if ch.isprintable() and ord(ch) < 0x2010 or ch in "áéíóúñÁÉÍÓÚÑ-"
                           else "-" for ch in t)[:24]
        ax.set_title("%s | %s a %s | %.1f km"
                     % (titulo, limpio(rows[i]["nombre"]), limpio(rows[j]["nombre"]),
                        prof["D"] / 1000),
                     fontsize=9, color=INK, loc="left", pad=6)
        ax.tick_params(labelsize=8, colors=INK_SOFT, length=0)
        ax.grid(color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GRID)
        ax.set_facecolor(SURFACE)
    axes[1].set_xlabel("distancia (km)", fontsize=8.5, color=INK_SOFT)
    leg = axes[0].legend(fontsize=7.5, frameon=False, loc="upper right", ncol=2)
    for t in leg.get_texts():
        t.set_color(INK_SOFT)
    fig.tight_layout()
    out = os.path.join(FIG, "fig_perfiles.png")
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


# ------------------------------------------------------------------ figura 3
def fig_nulos(nul):
    alc = [float(a) for a in nul["parametros"]["alcances_m"]]
    nombres = {"uniforme": "nulo uniforme",
               "estratificado_altitud": "nulo estratificado por altitud",
               "rigido": "nulo rígido (misma configuración)"}
    fig, axes = plt.subplots(1, len(alc), figsize=(10.5, 3.4), dpi=300,
                             facecolor=SURFACE, sharey=False)
    for ax, a in zip(axes, alc):
        k = "%.0f" % a
        obs = nul["observado"][k]["densidad"]
        series = [("uniforme", "#c9c8c4"), ("estratificado_altitud", "#8e8d89"),
                  ("rigido", HUE)]
        for idx, (key, color) in enumerate(s_ for s_ in series if s_[0] in nul["nulos"]):
            d = nul["nulos"][key][k]
            mu, sd = d["densidad_nula_media"], d["densidad_nula_sd"]
            ax.errorbar([idx], [mu], yerr=[[mu - d["densidad_nula_p05"]],
                                           [d["densidad_nula_p95"] - mu]],
                        fmt="o", color=color, markersize=8, capsize=5, linewidth=1.8,
                        zorder=3, label=nombres[key] if a == alc[0] else None)
        ax.axhline(obs, color=HUE2, linewidth=2.0, zorder=4,
                   label="observado" if a == alc[0] else None)
        ax.set_xlim(-0.6, 2.6)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["unif.", "altitud", "rígido"], fontsize=8, color=INK_SOFT)
        ax.set_title("%.0f km" % (a / 1000), fontsize=9.5, color=INK, pad=6)
        ax.tick_params(axis="y", labelsize=8, colors=INK_SOFT, length=0)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right", "bottom"):
            ax.spines[s].set_visible(False)
        ax.spines["left"].set_color(GRID)
        ax.set_facecolor(SURFACE)
    axes[0].set_ylabel("densidad de intervisibilidad", fontsize=8.5, color=INK_SOFT)
    h, l = axes[0].get_legend_handles_labels()
    leg = fig.legend(h, l, fontsize=8, frameon=False, loc="lower center", ncol=3,
                     bbox_to_anchor=(0.5, -0.02))
    for t in leg.get_texts():
        t.set_color(INK_SOFT)
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    out = os.path.join(FIG, "fig_nulos.png")
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


def main():
    os.makedirs(FIG, exist_ok=True)
    rows, dem, vis, dist, nul, log = load()
    p, seg = fig_mapa(rows, dem, vis, dist)
    print("mapa      ->", p, "(%d aristas dibujadas)" % seg)
    print("perfiles  ->", fig_perfiles(rows, dem, vis, dist, log))
    print("nulos     ->", fig_nulos(nul))


if __name__ == "__main__":
    main()
