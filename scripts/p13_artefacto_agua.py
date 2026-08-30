# -*- coding: utf-8 -*-
"""
Reproduce el artefacto del lago, para que la cifra tenga respaldo.

El articulo afirma que sin enmascarar el agua el contraste rigido cae de z=+2.6
a z=+0.2. Esa cifra procedia de una ejecucion descartada y solo constaba en un
registro de consola: una afirmacion central sin fichero que la sostenga. Aqui se
recalcula el nulo rigido SIN mascara de agua y se guarda, de modo que la
comparacion sea verificable como cualquier otro resultado.

Salida: results/nulo_rigido_sin_mascara.json
"""
import csv, json, math, os, sys, time
import numpy as np, rasterio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viewshed_core import network_stats, pairwise_intervisibility

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
H_OBS, H_TGT = 1.7, 3.0
N_NULL, MARGEN, SEED = 300, 5, 20260831
ALCANCES = [5000.0, 10000.0, 15000.0, 26000.0]

def main():
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig")))
    cols = np.array([int(r["col"]) for r in rows], float)
    fils = np.array([int(r["fila"]) for r in rows], float)
    with rasterio.open(os.path.join(DATA, "terreno_chucuito.tif")) as s:
        dem = s.read(1).astype(np.float32)
    log = json.load(open(os.path.join(DATA, "terreno_log.json"), encoding="utf-8"))
    rx, ry = log["dem_resolucion_m_aprox"]
    H, W = dem.shape
    cx, cy = cols.mean(), fils.mean()
    dc, df = cols - cx, fils - cy

    v0, d0 = pairwise_intervisibility(dem, rx, ry, cols.astype(int), fils.astype(int),
                                      h_obs=H_OBS, h_tgt=H_TGT, max_dist_m=max(ALCANCES))
    obs = {("%.0f" % a): network_stats(v0, d0, a)["densidad"] for a in ALCANCES}

    rng = np.random.default_rng(SEED)
    acum = {("%.0f" % a): [] for a in ALCANCES}
    acc = 0
    t0 = time.time()
    print("Nulo rígido SIN máscara de agua (%d colocaciones)" % N_NULL, flush=True)
    while acc < N_NULL:
        th = rng.uniform(0, 2 * math.pi); ct, st = math.cos(th), math.sin(th)
        rc, rf = dc * ct - df * st, dc * st + df * ct
        lo_c, hi_c = MARGEN - rc.min(), W - MARGEN - rc.max()
        lo_f, hi_f = MARGEN - rf.min(), H - MARGEN - rf.max()
        if lo_c >= hi_c or lo_f >= hi_f:
            continue
        nc = np.rint(rc + rng.uniform(lo_c, hi_c)).astype(int)
        nf = np.rint(rf + rng.uniform(lo_f, hi_f)).astype(int)
        # sin filtro de agua: es justamente lo que se quiere reproducir
        v, d = pairwise_intervisibility(dem, rx, ry, nc, nf, h_obs=H_OBS, h_tgt=H_TGT,
                                        max_dist_m=max(ALCANCES))
        for a in ALCANCES:
            acum["%.0f" % a].append(network_stats(v, d, a)["densidad"])
        acc += 1
        if acc % 50 == 0:
            print("  %d/%d (%.0f s)" % (acc, N_NULL, time.time() - t0), flush=True)

    salida = {"n_null": N_NULL, "mascara_agua": False, "alcances_m": ALCANCES,
              "semilla": SEED, "por_alcance": {},
              "nota": ("Ejecucion deliberadamente sin mascara de agua, para documentar el efecto "
                       "del artefacto. No es un resultado del analisis sino su contraejemplo.")}
    print("\nSIN MÁSCARA DE AGUA")
    for a in ALCANCES:
        k = "%.0f" % a
        arr = np.array(acum[k]); o = obs[k]
        p = (np.sum(arr >= o) + 1) / (len(arr) + 1)
        z = (o - arr.mean()) / arr.std() if arr.std() > 0 else float("nan")
        salida["por_alcance"][k] = {"densidad_obs": o, "nula_media": float(arr.mean()),
                                    "nula_sd": float(arr.std()), "p_unilateral": float(p),
                                    "z": float(z)}
        print("  %5.0f m: obs %.4f | nulo %.4f ± %.4f | z=%+.2f | p=%.4f"
              % (a, o, arr.mean(), arr.std(), z, p), flush=True)
    json.dump(salida, open(os.path.join(RES, "nulo_rigido_sin_mascara.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "nulo_rigido_sin_mascara.json"))

if __name__ == "__main__":
    main()
