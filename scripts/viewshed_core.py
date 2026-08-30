# -*- coding: utf-8 -*-
"""
Nucleo de calculo de linea de vision sobre un modelo digital de elevacion.

Una linea de vision entre dos puntos no es una recta sobre el terreno: la
superficie terrestre se curva y la atmosfera refracta la luz. A las distancias
de este estudio —hasta 26 km— ignorarlo no es aceptable. En el punto medio de un
trayecto de 26 km la curvatura hunde el terreno unos 11,5 m respecto a la cuerda
recta, suficiente para que dos sitios que el calculo plano declara intervisibles
no lo sean, o al reves.

La correccion habitual combina ambos efectos en un radio terrestre efectivo
R/(1-k), con k = 0,13 para condiciones atmosfericas medias. El descenso aparente
del terreno a distancia d de un trayecto de longitud D es d(D-d)/2R_ef.

Las alturas de observador y objetivo importan tanto como el relieve. Una chullpa
no es un punto en el suelo: son torres de entre tres y doce metros, y esa altura
decide buena parte de los casos limite. Aqui se parametrizan en vez de fijarse.
"""
import numpy as np

R_EARTH = 6371000.0
K_REFRACTION = 0.13
R_EFF = R_EARTH / (1.0 - K_REFRACTION)


def curvature_rise(d, D):
    """Elevacion aparente del terreno intermedio respecto a la cuerda, en metros.

    El signo es contraintuitivo y es facil equivocarlo. Trabajando en el plano
    tangente al observador, el terreno desciende d^2/2R con la distancia y el
    objetivo desciende D^2/2R. Al reescribir la condicion de bloqueo respecto a
    la recta que une observador y objetivo sin corregir, esos dos descensos se
    combinan en un termino d(D-d)/2R que se SUMA al terreno intermedio: visto
    desde la cuerda, la Tierra abulta entre los dos extremos y se anula en ellos.

    Restarlo, como parece natural al hablar de «descenso por curvatura», vuelve
    la Tierra concava y hace que ningun relieve bloquee jamas a larga distancia.
    """
    return d * (D - d) / (2.0 * R_EFF)


def line_of_sight(dem, res_x, res_y, c0, r0, c1, r1,
                  h_obs=1.7, h_tgt=3.0, n_samples=None, return_profile=False):
    """Comprueba si hay vision directa entre dos celdas del DEM.

    dem          matriz de elevaciones
    res_x, res_y tamano de celda en metros
    c0, r0       columna y fila del observador
    c1, r1       columna y fila del objetivo
    h_obs, h_tgt alturas sobre el terreno, en metros

    Devuelve True si la vista esta despejada. El muestreo usa un punto por celda
    a lo largo del trayecto, que es la densidad natural del dato: muestrear mas
    fino solo interpolaria informacion que el DEM no tiene.
    """
    dx = (c1 - c0) * res_x
    dy = (r1 - r0) * res_y
    D = float(np.hypot(dx, dy))
    if D < 1e-6:
        return (True, None) if return_profile else True

    if n_samples is None:
        n_samples = int(max(abs(c1 - c0), abs(r1 - r0))) + 1
    n_samples = max(n_samples, 3)

    t = np.linspace(0.0, 1.0, n_samples)
    cc = np.rint(c0 + (c1 - c0) * t).astype(np.int32)
    rr = np.rint(r0 + (r1 - r0) * t).astype(np.int32)
    np.clip(cc, 0, dem.shape[1] - 1, out=cc)
    np.clip(rr, 0, dem.shape[0] - 1, out=rr)

    z = dem[rr, cc].astype(np.float64)
    d = t * D

    z_corr = z + curvature_rise(d, D)

    z_start = z[0] + h_obs
    z_end = z[-1] + h_tgt
    sight = z_start + (z_end - z_start) * t

    # Los extremos no se evaluan: el propio punto de observacion no se bloquea.
    interior = slice(1, -1)
    clear = bool(np.all(z_corr[interior] <= sight[interior]))

    if return_profile:
        return clear, {"d": d, "z": z, "z_corr": z_corr, "sight": sight, "D": D}
    return clear


def pairwise_intervisibility(dem, res_x, res_y, cols, rows, h_obs=1.7, h_tgt=3.0,
                             max_dist_m=None, progress=None):
    """Matriz booleana de intervisibilidad entre todos los pares de puntos.

    La relacion se trata como simetrica. Estrictamente no lo es cuando las
    alturas de observador y objetivo diferen, pero la asimetria resultante es
    de centimetros frente a decenas de metros de relieve, y una red dirigida
    complicaria la interpretacion sin cambiar el resultado.
    """
    n = len(cols)
    vis = np.zeros((n, n), dtype=bool)
    dist = np.zeros((n, n), dtype=np.float32)
    total = n * (n - 1) // 2
    done = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = (cols[j] - cols[i]) * res_x
            dy = (rows[j] - rows[i]) * res_y
            D = float(np.hypot(dx, dy))
            dist[i, j] = dist[j, i] = D
            if max_dist_m is not None and D > max_dist_m:
                done += 1
                continue
            v = line_of_sight(dem, res_x, res_y, cols[i], rows[i], cols[j], rows[j],
                              h_obs=h_obs, h_tgt=h_tgt)
            vis[i, j] = vis[j, i] = v
            done += 1
            if progress and done % progress == 0:
                print("    %d/%d pares" % (done, total), flush=True)
    return vis, dist


def network_stats(vis, dist=None, max_dist_m=None):
    """Descriptores de la red de intervisibilidad."""
    n = vis.shape[0]
    if max_dist_m is not None and dist is not None:
        eligible = (dist <= max_dist_m) & ~np.eye(n, dtype=bool)
    else:
        eligible = ~np.eye(n, dtype=bool)
    n_elig = int(eligible.sum() // 2)
    edges = int((vis & eligible).sum() // 2)
    deg = (vis & eligible).sum(axis=1)

    # Componentes conexas por recorrido en anchura
    seen = np.zeros(n, dtype=bool)
    comps = []
    for s in range(n):
        if seen[s]:
            continue
        stack, comp = [s], []
        seen[s] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in np.nonzero(vis[u] & eligible[u] & ~seen)[0]:
                seen[v] = True
                stack.append(v)
        comps.append(len(comp))

    return {
        "n_sitios": n,
        "pares_elegibles": n_elig,
        "aristas": edges,
        "densidad": edges / n_elig if n_elig else 0.0,
        "grado_medio": float(deg.mean()),
        "grado_max": int(deg.max()),
        "aislados": int((deg == 0).sum()),
        "componentes": len(comps),
        "componente_mayor": max(comps) if comps else 0,
    }
