# -*- coding: utf-8 -*-
"""
Tercer modelo nulo: la misma configuracion, movida sobre el terreno.

Los dos nulos anteriores sortean puntos independientes, de modo que el conjunto
nulo queda mucho mas disperso que el observado, que se apina en la ribera del
lago. Comparar una configuracion agrupada contra otra dispersa mezcla dos cosas:
donde estan los sitios y como estan dispuestos entre si.

Este nulo separa ambas. Toma la nube de sitios tal cual —conservando todas las
distancias mutuas y por tanto la forma exacta del conjunto— y la traslada y rota
rigidamente a otra posicion del area de estudio. La pregunta que responde es
precisa: dada esta configuracion, ¿esta colocada donde se ve mas de lo que se
veria en otro sitio cualquiera?

Es el nulo mas exigente de los tres. Si la intervisibilidad observada tambien lo
supera, no se explica ni por la altitud ni por el agrupamiento, sino por el
emplazamiento concreto.

Salida: results/nulo_rigido.json
"""
import csv
import json
import math
import os
import sys
import time

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import network_stats, pairwise_intervisibility

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
RES = os.path.join(BASE, "results")

# El lago Titicaca ocupa el 30,6 % del area como superficie plana constante.
# Una colocacion que deje sitios dentro del agua no es un emplazamiento posible,
# y ademas veria sin obstaculos, asi que se rechaza.
COTA_AGUA = 3808.5
TOL_AGUA = 0.05

H_OBS, H_TGT = 1.7, 3.0
N_NULL = 500
ALCANCES = [5000.0, 10000.0, 15000.0, 26000.0]
SEED = 20260831
MARGEN = 5  # celdas de guarda respecto al borde del DEM


def main():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = np.array([int(r["col"]) for r in rows], dtype=float)
    fils = np.array([int(r["fila"]) for r in rows], dtype=float)
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        dem = src.read(1).astype(np.float32)
    with open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8") as f:
        log = json.load(f)
    res_x, res_y = log["dem_resolucion_m_aprox"]
    H, W = dem.shape
    agua = np.abs(dem - COTA_AGUA) < TOL_AGUA
    print("Agua: %.1f %% del area" % (100 * agua.mean()), flush=True)

    # centrar la nube en su propio centroide
    cx, cy = cols.mean(), fils.mean()
    dc, df = cols - cx, fils - cy
    radio = float(np.hypot(dc, df).max())
    print("Sitios: %d | radio de la nube: %.0f celdas (%.1f km)"
          % (len(rows), radio, radio * res_x / 1000), flush=True)

    if radio + MARGEN >= min(H, W) / 2:
        print("AVISO: la nube casi llena el area; las rotaciones disponibles son limitadas.",
              flush=True)

    obs = {}
    v0, d0 = pairwise_intervisibility(dem, res_x, res_y,
                                      cols.astype(int), fils.astype(int),
                                      h_obs=H_OBS, h_tgt=H_TGT, max_dist_m=max(ALCANCES))
    for a in ALCANCES:
        obs["%.0f" % a] = network_stats(v0, d0, a)["densidad"]

    rng = np.random.default_rng(SEED)
    acum = {("%.0f" % a): [] for a in ALCANCES}
    intentos, aceptadas = 0, 0
    t0 = time.time()
    while aceptadas < N_NULL:
        intentos += 1
        th = rng.uniform(0, 2 * math.pi)
        ct, st = math.cos(th), math.sin(th)
        rc = dc * ct - df * st
        rf = dc * st + df * ct
        # centro admisible para que toda la nube quepa dentro del DEM
        lo_c, hi_c = MARGEN - rc.min(), W - MARGEN - rc.max()
        lo_f, hi_f = MARGEN - rf.min(), H - MARGEN - rf.max()
        if lo_c >= hi_c or lo_f >= hi_f:
            continue
        nc = np.rint(rc + rng.uniform(lo_c, hi_c)).astype(int)
        nf = np.rint(rf + rng.uniform(lo_f, hi_f)).astype(int)
        if agua[nf, nc].any():
            continue
        v, d = pairwise_intervisibility(dem, res_x, res_y, nc, nf,
                                        h_obs=H_OBS, h_tgt=H_TGT, max_dist_m=max(ALCANCES))
        for a in ALCANCES:
            acum["%.0f" % a].append(network_stats(v, d, a)["densidad"])
        aceptadas += 1
        if aceptadas % 25 == 0:
            el = time.time() - t0
            print("  %d/%d  (%.0f s, quedan ~%.0f s)"
                  % (aceptadas, N_NULL, el, el / aceptadas * (N_NULL - aceptadas)), flush=True)

    salida = {"n_null": N_NULL, "intentos": intentos,
              "tasa_aceptacion": N_NULL / intentos,
              "cota_agua": COTA_AGUA, "fraccion_agua": float(agua.mean()), "alcances_m": ALCANCES,
              "h_obs": H_OBS, "h_tgt": H_TGT, "semilla": SEED, "por_alcance": {}}
    print("\nCONTRASTE: configuracion observada frente a la misma nube desplazada y rotada")
    for a in ALCANCES:
        k = "%.0f" % a
        arr = np.array(acum[k])
        o = obs[k]
        p = (np.sum(arr >= o) + 1) / (len(arr) + 1)
        z = (o - arr.mean()) / arr.std() if arr.std() > 0 else float("nan")
        salida["por_alcance"][k] = {
            "densidad_obs": o, "nula_media": float(arr.mean()), "nula_sd": float(arr.std()),
            "nula_p05": float(np.percentile(arr, 5)), "nula_p95": float(np.percentile(arr, 95)),
            "p_unilateral": float(p), "z": float(z),
        }
        print("  %5.0f m: obs %.4f | nulo %.4f ± %.4f | z=%+.2f | p=%.4f"
              % (a, o, arr.mean(), arr.std(), z, p), flush=True)

    with open(os.path.join(RES, "nulo_rigido.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "nulo_rigido.json"))


if __name__ == "__main__":
    main()
