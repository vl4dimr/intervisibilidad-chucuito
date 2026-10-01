# -*- coding: utf-8 -*-
"""
Perspectiva 3D realista del paisaje visual desde la torre funeraria mas alta.

Sustituye a la proyeccion ortografica de colores planos (p21). La escena se
renderiza con VTK (PyVista) en la GPU:

  relieve     Copernicus DEM GLO-30, malla de 30 m, exageracion vertical moderada
  textura     ortoimagen Sentinel-2 L2A de estacion seca a 10 m (p22), con la
              cuenca visual calculada por el motor drapeada en rojo translucido
              y su contorno en rojo pleno
  luz         un sol direccional, colocado en el mismo
              azimut y elevacion que el sol de la escena Sentinel-2, de modo que
              las sombras del render y las de la fotografia no se contradicen;
              luz ambiente suave para que las laderas en sombra no se vuelvan negras
  camara      perspectiva baja desde el lago, mirando hacia la torre
  atmosfera   perspectiva aerea calculada con el bufer de profundidad del propio
              render: cada pixel se funde con el color de la bruma segun su
              distancia real a la camara, y el cielo es un degradado
  sitios      la torre como un hito vertical y las tumbas como marcadores sobre
              un mastil; los oculta el relieve, no el orden de dibujo, porque
              VTK resuelve la oclusion con el bufer de profundidad

Se renderiza al doble de resolucion y se reduce (supermuestreo 2x2). Los
rotulos y la leyenda se componen despues con matplotlib, en espanol.

Entradas: data/terreno_utm.tif, data/ortofoto_s2.tif, results/ortofoto_s2.json,
          results/viewshed_nuestro.npy, results/observador_3d.json,
          data/sitios_chucuito.csv, results/cuenca_torre.json
Salidas:  results/figuras/fig3d_perspectiva.png (300 ppp, 170 mm)
          results/render3d.json (camara, sol, exageracion, tumbas en pantalla)
"""
import csv
import json
import math
import os

import numpy as np
import pyvista as pv
import rasterio
from PIL import Image
from rasterio.warp import transform as tcoords
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
FIG = os.path.join(RES, "figuras")
UTM = "EPSG:32719"

EXAG = 1.8                 # exageracion vertical
SEMILADO = 11000.0         # m alrededor de la torre que entran en la escena
ANCHO_PX, ALTO_PX = 2008, 1250          # 170 mm a 300 ppp
SS = 2                     # supermuestreo
BRUMA = np.array([0.80, 0.85, 0.90])   # color de la bruma, gris azulado claro
L_BRUMA = 42000.0          # m: distancia a la que la bruma alcanza 1 - 1/e
ROJO = np.array([0.80, 0.07, 0.07])
LAGO_Z = 3808.5

pv.OFF_SCREEN = True


def cargar():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float64)
        tr = s.transform
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))
    with rasterio.open(os.path.join(DATA, "ortofoto_s2.tif")) as s:
        orto = s.read().transpose(1, 2, 0)
        otr = s.transform
    meta_o = json.load(open(os.path.join(RES, "ortofoto_s2.json"), encoding="utf-8"))
    return dem, tr, vs, obs, orto, otr, meta_o


def main():
    dem, tr, vs, obs, orto, otr, meta_o = cargar()
    ox, oy = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    ox, oy = ox[0], oy[0]

    # --- recorte del DEM alineado con la ortofoto ------------------------------
    c0 = int(round((otr.c - tr.c) / tr.a))
    f0 = int(round((otr.f - tr.f) / tr.e))
    n = int(round(orto.shape[1] * otr.a / tr.a))
    # se recorta un poco mas para que la malla y la textura coincidan con holgura
    marg = int((orto.shape[1] * otr.a / 2 - SEMILADO) / tr.a)
    c0, f0, n = c0 + marg, f0 + marg, n - 2 * marg
    z = dem[f0:f0 + n, c0:c0 + n]
    vcrop = vs[f0:f0 + n, c0:c0 + n]
    x0, y0 = tr.c + c0 * tr.a, tr.f + f0 * tr.e     # esquina superior izquierda
    # ortofoto del mismo recorte
    k = int(round(tr.a / otr.a))
    oc0 = int(round((x0 - otr.c) / otr.a))
    of0 = int(round((y0 - otr.f) / otr.e))
    tex = orto[of0:of0 + n * k, oc0:oc0 + n * k].astype(np.float64) / 255.0

    # --- cuenca visual sobre la textura -----------------------------------------
    v = np.kron(vcrop == 1, np.ones((k, k), bool))
    v = ndimage.binary_opening(v, iterations=1)
    borde = v & ~ndimage.binary_erosion(v, iterations=2)
    tex[v] = 0.50 * tex[v] + 0.50 * ROJO
    tex[borde] = ROJO
    tex_img = (np.clip(tex, 0, 1) * 255).astype(np.uint8)
    textura = pv.Texture(tex_img)    # pyvista ya invierte las filas: la fila 0 es el norte

    # --- malla ------------------------------------------------------------------
    xs = (np.arange(n) + 0.5) * tr.a                # m desde la esquina oeste
    ys = (np.arange(n)[::-1] + 0.5) * tr.a          # m desde la esquina sur
    X, Y = np.meshgrid(xs, ys)
    zref = float(np.nanmin(z))
    Z = (z - zref) * EXAG
    malla = pv.StructuredGrid(X, Y, Z)
    tc = np.c_[(X.ravel(order="F") / (n * tr.a)), (Y.ravel(order="F") / (n * tr.a))]
    malla.active_texture_coordinates = tc

    def local(xu, yu, zu):
        return (xu - x0, yu - (y0 - n * tr.a), (zu - zref) * EXAG)

    # --- sitios -----------------------------------------------------------------
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    tumbas, torre = [], None
    for row in rows:
        if row["funerario"] != "True":
            continue
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        cc, ff = ~tr * (ux[0], uy[0])
        cc, ff = int(cc), int(ff)
        if not (f0 <= ff < f0 + n and c0 <= cc < c0 + n):
            continue
        p = local(ux[0], uy[0], dem[ff, cc])
        if int(row["id"]) == int(obs["id"]):
            torre = p
        elif math.hypot(ux[0] - ox, uy[0] - oy) <= 10000:
            tumbas.append({"id": row["id"], "p": p, "visible_desde_torre": bool(vs[ff, cc] == 1)})

    # --- escena -----------------------------------------------------------------
    pl = pv.Plotter(off_screen=True, window_size=(ANCHO_PX * SS, ALTO_PX * SS), lighting="none")
    pl.add_mesh(malla, texture=textura, smooth_shading=True, ambient=0.55, diffuse=0.55,
                specular=0.0)

    # torre: mastil oscuro con remate conico; tumbas: mastil fino y esfera
    alto_torre = 420.0
    pl.add_mesh(pv.Cylinder(center=(torre[0], torre[1], torre[2] + alto_torre / 2),
                            direction=(0, 0, 1), radius=38, height=alto_torre, resolution=24),
                color="#111827", ambient=0.5)
    pl.add_mesh(pv.Cone(center=(torre[0], torre[1], torre[2] + alto_torre + 70),
                        direction=(0, 0, -1), height=140, radius=110, resolution=24),
                color="#111827", ambient=0.5)
    for t in tumbas:
        x, y, zz = t["p"]
        pl.add_mesh(pv.Cylinder(center=(x, y, zz + 110), direction=(0, 0, 1), radius=14,
                                height=220, resolution=12), color="#e5e7eb", ambient=0.6)
        pl.add_mesh(pv.Sphere(center=(x, y, zz + 250), radius=75, theta_resolution=24,
                              phi_resolution=24), color="#334155", ambient=0.45, specular=0.3)

    # sol en la misma posicion que en la escena Sentinel-2
    az, el = math.radians(meta_o["sol_azimut"]), math.radians(meta_o["sol_elevacion"])
    c = np.array([n * tr.a / 2, n * tr.a / 2, 0.0])
    dir_sol = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
    sol = pv.Light(position=tuple(c + dir_sol * 60000), focal_point=tuple(c),
                   light_type="scene light", intensity=1.05, color=(1.0, 0.97, 0.92))
    pl.add_light(sol)
    # Sin mapa de sombras: la ortoimagen ya lleva las sombras reales del sol de la
    # escena, y el mapa de sombras de VTK a esta escala produce franjas falsas.

    # camara: desde el norte-noreste, sobre el lago, baja, mirando a la torre
    cam_az = math.radians(28.0)                    # de donde viene la mirada
    dist_h, alt_cam = 14000.0, 5200.0
    foco = np.array([torre[0] - 600, torre[1] - 1800, torre[2] * 0.75])
    pos = foco + np.array([math.sin(cam_az) * dist_h, math.cos(cam_az) * dist_h, alt_cam])
    pl.camera_position = [tuple(pos), tuple(foco), (0, 0, 1)]
    pl.camera.view_angle = 34.0
    pl.camera.clipping_range = (500, 120000)
    pl.set_background((0.82, 0.86, 0.90), top=(0.47, 0.62, 0.80))

    img = pl.screenshot(return_img=True).astype(np.float64) / 255.0
    prof = pl.get_image_depth(fill_value=np.nan)          # distancia (negativa) a la camara
    # posiciones en pantalla de torre y tumbas, para rotular y para comprobar oclusion
    ren = pl.renderer

    def a_pantalla(p):
        ren.SetWorldPoint(p[0], p[1], p[2], 1.0)
        ren.WorldToDisplay()
        dx, dy, _ = ren.GetDisplayPoint()
        return dx, img.shape[0] - dy

    pt_torre = a_pantalla((torre[0], torre[1], torre[2] + alto_torre + 160))
    # rotulo del lago: la celda de agua (cota constante) mas cercana al centro de la imagen
    agua = np.argwhere(np.abs(z - LAGO_Z) < 0.05)
    pt_lago = None
    if len(agua):
        cand = []
        for fi, ci in agua[::max(1, len(agua) // 4000)]:
            sx, sy = a_pantalla((xs[ci], ys[fi], (LAGO_Z - zref) * EXAG))
            if 0.05 * img.shape[1] < sx < 0.95 * img.shape[1] and 0.05 * img.shape[0] < sy < 0.95 * img.shape[0]:
                cand.append((abs(sx - img.shape[1] * 0.25) + abs(sy - img.shape[0] * 0.75), sx, sy))
        if cand:
            pt_lago = min(cand)[1:]
    for t in tumbas:
        x, y, zz = t["p"]
        sx, sy = a_pantalla((x, y, zz + 250))
        d_real = float(np.linalg.norm(np.array([x, y, zz + 250]) - pos))
        ix, iy = int(round(sx)), int(round(sy))
        en_cuadro = 0 <= ix < img.shape[1] and 0 <= iy < img.shape[0]
        d_buf = float(-prof[iy, ix]) if en_cuadro and not np.isnan(prof[iy, ix]) else float("nan")
        t["pantalla"] = (sx / SS, sy / SS)
        t["visible_en_render"] = bool(en_cuadro and abs(d_buf - d_real) < 140)
    pl.close()

    # --- perspectiva aerea --------------------------------------------------------
    d = -prof
    cielo = np.isnan(d)
    f = 1.0 - np.exp(-np.nan_to_num(d, nan=0.0) / L_BRUMA)
    f = np.clip(f, 0, 0.72)[..., None]
    out = img[..., :3] * (1 - f) + BRUMA * f
    out[cielo] = img[..., :3][cielo]
    # ligera curva de contraste para el aire seco del altiplano
    out = np.clip((out - 0.5) * 1.06 + 0.5, 0, 1)
    final = Image.fromarray((out * 255).astype(np.uint8)).resize((ANCHO_PX, ALTO_PX),
                                                                 Image.LANCZOS)
    # se recorta la franja superior de cielo vacio
    CIELO = 230
    final = final.crop((0, CIELO, ANCHO_PX, ALTO_PX))
    alto = ALTO_PX - CIELO

    # --- composicion: rotulos, leyenda y creditos -----------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib import patheffects as pe

    TORRE_N = json.load(open(os.path.join(RES, "cuenca_torre.json"), encoding="utf-8"))
    nombre = " ".join(TORRE_N["observador"].split())
    alt = "{:,}".format(round(TORRE_N["altitud_m"])).replace(",", " ")
    halo = [pe.withStroke(linewidth=3, foreground="white")]

    fig = plt.figure(figsize=(ANCHO_PX / 300, (alto + 190) / 300), dpi=300)
    ax = fig.add_axes([0, 190 / (alto + 190), 1, alto / (alto + 190)])
    ax.imshow(final)
    ax.set_xlim(0, ANCHO_PX); ax.set_ylim(alto, 0); ax.axis("off")
    tx, ty = pt_torre[0] / SS, pt_torre[1] / SS - CIELO
    ax.annotate("%s\n%s m" % (nombre, alt), xy=(tx, ty), xytext=(tx + 150, ty - 120),
                fontsize=7.5, color="#111827", ha="left", va="bottom", path_effects=halo,
                arrowprops=dict(arrowstyle="-", color="#111827", lw=0.8))
    if pt_lago:
        ax.text(pt_lago[0] / SS, pt_lago[1] / SS - CIELO, "lago Titicaca", fontsize=8, style="italic",
                ha="center", va="center", color="white",
                path_effects=[pe.withStroke(linewidth=2, foreground="#1e3a5f")])

    lax = fig.add_axes([0, 0, 1, 190 / (alto + 190)]); lax.axis("off")
    n_vis = sum(t["visible_desde_torre"] for t in tumbas)
    leg = [Line2D([0], [0], marker="^", color="w", markerfacecolor="#111827", markersize=8,
                  label="Torre observadora"),
           Line2D([0], [0], marker="o", color="w", markerfacecolor="#334155",
                  markeredgecolor="#e5e7eb", markersize=7,
                  label="Sitio funerario a menos de 10 km (%d; visibles desde la torre: %d)"
                        % (len(tumbas), n_vis)),
           Line2D([0], [0], marker="s", color="w", markerfacecolor="#d9837d",
                  markeredgecolor="#cc1212", markersize=8,
                  label="Cuenca visual de la torre (alcance 10 km)")]
    lax.legend(handles=leg, loc="upper left", ncol=2, frameon=False, fontsize=7,
               bbox_to_anchor=(0.01, 1.0), handletextpad=0.4, columnspacing=1.2)
    lax.text(0.99, 0.08, "Exageración vertical ×%.1f · Copernicus DEM GLO-30 · %s"
             % (EXAG, meta_o["atribucion_es"]), ha="right", va="bottom", fontsize=6,
             color="#4a463f", transform=lax.transAxes)
    out_png = os.path.join(FIG, "fig3d_perspectiva.png")
    fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fig)

    json.dump({"exageracion": EXAG, "semilado_m": SEMILADO,
               "camara": {"azimut_deg": math.degrees(cam_az), "distancia_h_m": dist_h,
                          "altura_m": alt_cam, "angulo_vision_deg": 34.0},
               "sol": {"azimut_deg": meta_o["sol_azimut"], "elevacion_deg": meta_o["sol_elevacion"]},
               "bruma_l_m": L_BRUMA, "supermuestreo": SS,
               "tumbas": [{k: v for k, v in t.items() if k != "p"} for t in tumbas]},
              open(os.path.join(RES, "render3d.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    vis_cam = sum(t["visible_en_render"] for t in tumbas)
    print("-> %s | tumbas en escena %d, visibles desde la torre %d, visibles para la camara %d"
          % (out_png, len(tumbas), n_vis, vis_cam))


if __name__ == "__main__":
    main()
