# -*- coding: utf-8 -*-
"""
Analisis separado por distrito.

El conjunto de Chucuito no es una nube: son dos grupos espacialmente disjuntos,
Juli con 168 sitios y Pomata con 12, separados por unos 25 km de relieve. El
mapa lo muestra con claridad y obliga a revisar el diseno anterior, que los
trataba como un solo conjunto.

Agregarlos tiene dos consecuencias indeseables. En los alcances largos entran al
computo pares Juli-Pomata que no describen ninguna relacion de vecindad y que
casi siempre estan bloqueados, lo que rebaja artificialmente la densidad
observada. Y el nulo rigido rota una configuracion que en realidad son dos, de
modo que reproduce una separacion que quiza no tenga significado.

Aqui se repite el contraste rigido sobre Juli solo, que es el unico grupo con
tamano suficiente, y se compara con el resultado agregado. Pomata se describe
pero no se contrasta: con 12 sitios, cualquier valor p seria ilustrativo y no
informativo.

Salida: results/por_distrito.json
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
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")

COTA_AGUA, TOL_AGUA = 3808.5, 0.05
H_OBS, H_TGT = 1.7, 3.0
N_NULL, MARGEN, SEED = 500, 5, 20260902
ALCANCES = [5000.0, 10000.0, 15000.0]
MIN_SITIOS = 30  # por debajo de esto no se contrasta, solo se describe


def nulo_rigido(dem, agua, rx, ry, cols, fils, n_null, rng):
    H, W = dem.shape
    cx, cy = cols.mean(), fils.mean()
    dc, df = cols - cx, fils - cy
    acum = {("%.0f" % a): [] for a in ALCANCES}
    acc, intentos = 0, 0
    while acc < n_null:
        intentos += 1
        if intentos > n_null * 400:
            break
        th = rng.uniform(0, 2 * math.pi)
        ct, st = math.cos(th), math.sin(th)
        rc, rf = dc * ct - df * st, dc * st + df * ct
        lo_c, hi_c = MARGEN - rc.min(), W - MARGEN - rc.max()
        lo_f, hi_f = MARGEN - rf.min(), H - MARGEN - rf.max()
        if lo_c >= hi_c or lo_f >= hi_f:
            continue
        nc = np.rint(rc + rng.uniform(lo_c, hi_c)).astype(int)
        nf = np.rint(rf + rng.uniform(lo_f, hi_f)).astype(int)
        if agua[nf, nc].any():
            continue
        v, d = pairwise_intervisibility(dem, rx, ry, nc, nf, h_obs=H_OBS, h_tgt=H_TGT,
                                        max_dist_m=max(ALCANCES))
        for a in ALCANCES:
            acum["%.0f" % a].append(network_stats(v, d, a)["densidad"])
        acc += 1
    return acum, acc, intentos


def main():
    with open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as src:
        dem = src.read(1).astype(np.float32)
    with open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8") as f:
        log = json.load(f)
    rx, ry = log["dem_resolucion_m_aprox"]
    agua = np.abs(dem - COTA_AGUA) < TOL_AGUA

    distritos = sorted({r["distrito"].strip().lower() for r in rows})
    salida = {"n_null": N_NULL, "alcances_m": ALCANCES, "min_sitios": MIN_SITIOS,
              "distritos": {}}

    # separacion entre los dos grupos, para justificar el desglose
    grupos = {}
    for d in distritos:
        sel = [r for r in rows if r["distrito"].strip().lower() == d]
        grupos[d] = (np.array([float(r["x_m"]) for r in sel]),
                     np.array([float(r["y_m"]) for r in sel]))
    if len(distritos) == 2:
        a, b = distritos
        sep = math.hypot(grupos[a][0].mean() - grupos[b][0].mean(),
                         grupos[a][1].mean() - grupos[b][1].mean())
        salida["separacion_centroides_km"] = sep / 1000
        print("Separación entre centroides de %s y %s: %.1f km" % (a, b, sep / 1000), flush=True)

    for d in distritos:
        sel = [r for r in rows if r["distrito"].strip().lower() == d]
        cols = np.array([int(r["col"]) for r in sel], float)
        fils = np.array([int(r["fila"]) for r in sel], float)
        fun = np.array([r["funerario"] == "True" for r in sel])
        n = len(sel)
        print("\n%s: %d sitios (%d con topónimo funerario)" % (d.upper(), n, int(fun.sum())), flush=True)

        v0, d0 = pairwise_intervisibility(dem, rx, ry, cols.astype(int), fils.astype(int),
                                          h_obs=H_OBS, h_tgt=H_TGT, max_dist_m=max(ALCANCES))
        obs = {("%.0f" % a): network_stats(v0, d0, a) for a in ALCANCES}
        for a in ALCANCES:
            st = obs["%.0f" % a]
            print("   %5.0f m: %4d aristas / %5d pares  densidad %.4f  grado %.2f"
                  % (a, st["aristas"], st["pares_elegibles"], st["densidad"],
                     st["grado_medio"]), flush=True)

        bloque = {"n_sitios": n, "n_funerarios": int(fun.sum()),
                  "observado": {k: v for k, v in obs.items()}}

        if n < MIN_SITIOS:
            bloque["contraste"] = None
            bloque["nota"] = ("Grupo demasiado pequeno para contrastar: con %d sitios el modelo nulo "
                              "no tiene potencia y cualquier valor p seria ilustrativo." % n)
            print("   sin contraste: %d sitios, por debajo del umbral de %d" % (n, MIN_SITIOS), flush=True)
        else:
            rng = np.random.default_rng(SEED)
            t0 = time.time()
            acum, acc, intentos = nulo_rigido(dem, agua, rx, ry, cols, fils, N_NULL, rng)
            bloque["contraste"] = {}
            print("   nulo rígido: %d colocaciones de %d intentos (%.0f s)"
                  % (acc, intentos, time.time() - t0), flush=True)
            for a in ALCANCES:
                k = "%.0f" % a
                arr = np.array(acum[k])
                o = obs[k]["densidad"]
                p = (np.sum(arr >= o) + 1) / (len(arr) + 1)
                z = (o - arr.mean()) / arr.std() if arr.std() > 0 else float("nan")
                bloque["contraste"][k] = {"densidad_obs": o, "nula_media": float(arr.mean()),
                                          "nula_sd": float(arr.std()), "p_unilateral": float(p),
                                          "z": float(z), "n_colocaciones": int(acc)}
                print("   %5.0f m: obs %.4f | nulo %.4f ± %.4f | z=%+.2f | p=%.4f"
                      % (a, o, arr.mean(), arr.std(), z, p), flush=True)
        salida["distritos"][d] = bloque

    with open(os.path.join(RES, "por_distrito.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "por_distrito.json"))


if __name__ == "__main__":
    main()
