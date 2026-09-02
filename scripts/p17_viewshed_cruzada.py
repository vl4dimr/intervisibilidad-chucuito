# -*- coding: utf-8 -*-
"""
Validacion cruzada de la cuenca visual: nuestro motor contra GDAL.

Fisher (1993) mostro que implementaciones independientes del mismo viewshed
discrepan sin que ninguna parezca rota. Aqui se mide esa discrepancia para
nuestro caso: la cuenca visual desde el sitio funerario mas alto del corpus
(Gentilmoko Yacari, 4 144 m, Juli) calculada dos veces sobre el mismo raster
proyectado —una con gdal_viewshed (via qgis_process de QGIS) y otra con
nuestro motor de linea de vision— con parametros identicos: observador a
1.7 m, objetivo a 3.0 m, alcance 10 km, y el mismo coeficiente de curvatura
(cc = 1 - k = 0.87, que es exactamente nuestra formulacion R/(1-k)).

El DEM original esta en grados (EPSG:4326); la curvatura en unidades de grado
no significa nada, asi que primero se reproyecta a UTM 19S (EPSG:32719) a
30 m, y ambos motores corren sobre ese raster.

Salidas:
  data/terreno_utm.tif                  el raster proyectado (una vez)
  results/viewshed_gdal.tif             cuenca segun GDAL
  results/viewshed_nuestro.npy          cuenca segun nuestro motor
  results/viewshed_cruzada.json         acuerdo, desacuerdos y donde caen
"""
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import line_of_sight

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
QPROC = r"C:\Program Files\QGIS 3.44.13\bin\qgis_process-qgis-ltr.bat"

H_OBS, H_TGT = 1.7, 3.0
ALCANCE = 10000.0
CC = 0.87            # 1 - k, con k = 0.13: la misma correccion que el motor
UTM = "EPSG:32719"


def reproyectar():
    dst = os.path.join(DATA, "terreno_utm.tif")
    if os.path.exists(dst):
        return dst
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        tr, w, h = calculate_default_transform(src.crs, UTM, src.width, src.height,
                                               *src.bounds, resolution=30.0)
        kw = src.meta.copy()
        kw.update(crs=UTM, transform=tr, width=w, height=h)
        with rasterio.open(dst, "w", **kw) as out:
            reproject(source=rasterio.band(src, 1), destination=rasterio.band(out, 1),
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=tr, dst_crs=UTM, resampling=Resampling.bilinear)
    print("reproyectado ->", dst, flush=True)
    return dst


def main():
    utm = reproyectar()
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))

    with rasterio.open(utm) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
        # el observador, del CRS geografico al UTM
        from rasterio.warp import transform as tcoords
        xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
        ox, oy = xs[0], ys[0]
        oc, of = ~tr * (ox, oy)
        oc, of = int(round(oc)), int(round(of))
    print("observador UTM: %.0f,%.0f -> col %d fila %d | dem %.0f m"
          % (ox, oy, oc, of, dem[of, oc]), flush=True)

    # ---- GDAL, via qgis_process --------------------------------------------
    salida_gdal = os.path.join(RES, "viewshed_gdal.tif")
    if os.path.exists(salida_gdal):
        os.remove(salida_gdal)
    cmd = [QPROC, "run", "gdal:viewshed", "--",
           "INPUT=%s" % utm, "BAND=1",
           "OBSERVER=%.1f,%.1f [%s]" % (ox, oy, UTM),
           "OBSERVER_HEIGHT=%s" % H_OBS, "TARGET_HEIGHT=%s" % H_TGT,
           "MAX_DISTANCE=%s" % ALCANCE, "EXTRA=-cc %s" % CC,
           "OUTPUT=%s" % salida_gdal]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if not os.path.exists(salida_gdal):
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        sys.exit("gdal:viewshed no produjo salida")
    print("gdal:viewshed en %.0f s" % (time.time() - t0), flush=True)

    # gdal_viewshed recorta al alcance: su ventana se encaja en la malla
    # completa usando su propio transform
    with rasterio.open(salida_gdal) as sg:
        ventana = sg.read(1)
        trg = sg.transform

    h, w = dem.shape
    vs_gdal = np.zeros((h, w), dtype=ventana.dtype)
    dc = int(round((trg.c - tr.c) / 30.0))
    df = int(round((tr.f - trg.f) / 30.0))
    vh, vw = ventana.shape
    vs_gdal[df:df + vh, dc:dc + vw] = ventana

    # ---- nuestro motor, mismas condiciones ---------------------------------
    rad = int(ALCANCE / 30.0) + 1
    f0, f1 = max(0, of - rad), min(h, of + rad + 1)
    c0, c1 = max(0, oc - rad), min(w, oc + rad + 1)
    ruta_nuestro = os.path.join(RES, "viewshed_nuestro.npy")
    if os.path.exists(ruta_nuestro):
        nuestro = np.load(ruta_nuestro)
        print("nuestro motor: reutilizado de", ruta_nuestro, flush=True)
    else:
        nuestro = None
    t0 = time.time()
    n_eval = 0
    if nuestro is None:
      nuestro = np.zeros(dem.shape, dtype=np.uint8)
      for f in range(f0, f1):
        for c in range(c0, c1):
            d = math.hypot(c - oc, f - of) * 30.0
            if d > ALCANCE:
                continue
            n_eval += 1
            if line_of_sight(dem, 30.0, 30.0, oc, of, c, f,
                             h_obs=H_OBS, h_tgt=H_TGT):
                nuestro[f, c] = 1
        if (f - f0) % 120 == 0:
            print("  fila %d/%d (%.0f s)" % (f - f0, f1 - f0, time.time() - t0),
                  flush=True)
      print("nuestro motor: %d celdas en %.0f s" % (n_eval, time.time() - t0), flush=True)
      np.save(ruta_nuestro, nuestro)

    # ---- comparacion --------------------------------------------------------
    # gdal_viewshed: 255 = visible, 0 = oculto (y nodata fuera del alcance)
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.hypot((xx - oc) * 30.0, (yy - of) * 30.0)
    dentro = dist <= ALCANCE
    g = (vs_gdal == 255)
    n = (nuestro == 1)
    acuerdo = (g == n) & dentro
    solo_gdal = g & ~n & dentro
    solo_nos = n & ~g & dentro
    tot = int(dentro.sum())
    res = {
        "observador": {"nombre": obs["nombre"], "col_utm": oc, "fila_utm": of,
                       "altitud_dem": float(dem[of, oc])},
        "parametros": {"h_obs": H_OBS, "h_tgt": H_TGT, "alcance_m": ALCANCE,
                       "cc": CC, "crs": UTM, "res_m": 30.0},
        "celdas_evaluadas": tot,
        "visibles_gdal": int((g & dentro).sum()),
        "visibles_nuestro": int((n & dentro).sum()),
        "acuerdo": float(acuerdo.sum() / tot),
        "solo_gdal": int(solo_gdal.sum()),
        "solo_nuestro": int(solo_nos.sum()),
        # ¿los desacuerdos se concentran lejos, cerca del horizonte de cada
        # relieve, como cabe esperar de diferencias de interpolacion?
        "dist_media_desacuerdo_m": float(dist[solo_gdal | solo_nos].mean())
        if (solo_gdal | solo_nos).any() else None,
        "dist_media_total_m": float(dist[dentro].mean()),
    }
    json.dump(res, open(os.path.join(RES, "viewshed_cruzada.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res, indent=2, ensure_ascii=False)[:900])


if __name__ == "__main__":
    main()
