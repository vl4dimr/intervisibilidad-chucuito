# -*- coding: utf-8 -*-
"""
Contraste de la capa de sitios con el catalogo oficial del Ministerio de Cultura.

La capa de sitios del analisis (INC, redistribuida sin licencia ni fecha) no
tiene procedencia verificable. El Geoportal del Ministerio de Cultura publica,
sin registro, el catalogo de Monumentos Arqueologicos Prehispanicos: un listado
con nombre y coordenadas de cada monumento (servicio dgpa/json_monumentos) y
una ficha por monumento con region, provincia, distrito y clasificacion
(servicio mapa/verInformacionPoligono). Su geoservidor WFS no responde de forma
anonima, de modo que se usan estos dos servicios del propio portal.

El guion:
  1. descarga el catalogo nacional y lo guarda con la fecha de consulta;
  2. pide la ficha de cada monumento de una caja amplia alrededor de la
     provincia y se queda con los de la provincia de Chucuito;
  3. empareja cada monumento oficial de los distritos estudiados con el sitio
     mas cercano de la capa del INC, y da por coincidentes los pares a menos de
     UMBRAL_M que comparten al menos una palabra significativa del nombre;
  4. resume cuantos monumentos oficiales recoge la capa, a que distancia, y
     cuantos sitios de la capa no figuran en el catalogo oficial.

Salidas:
  data/mincul/monumentos_catalogo.json     catalogo nacional (id, nombre, lat, lon)
  data/mincul/fichas_chucuito.json         fichas de los monumentos de la provincia
  results/contraste_mincul.json            resumen que lee el manuscrito
"""
import csv
import datetime
import html
import json
import math
import os
import re
import time
import unicodedata
import urllib.request
import uuid

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
DIR = os.path.join(DATA, "mincul")
PORTAL = "https://geoportal.cultura.gob.pe/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"
UMBRAL_M = 300.0
VACIAS = {"de", "la", "el", "los", "las", "del", "sector", "sitio", "cerro", "1", "2", "3"}


def pedir(url, datos=None, cabeceras=None):
    rq = urllib.request.Request(url, data=datos, headers=dict({"User-Agent": UA}, **(cabeceras or {})))
    for intento in range(4):
        try:
            return urllib.request.urlopen(rq, timeout=60).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(3 * (intento + 1))
    raise RuntimeError("no responde: %s" % url)


def catalogo():
    t = pedir(PORTAL + "dgpa/json_monumentos")
    ops = re.findall(r'<option lat="([^"]*)"\s+lng="([^"]*)" value="(\d+)">([^<]*)</option>', t)
    out = []
    for la, lo, v, n in ops:
        try:
            out.append({"id": int(v), "nombre": html.unescape(n).strip(),
                        "lat": float(la), "lon": float(lo)})
        except ValueError:
            continue
    return out


def ficha(o):
    b = uuid.uuid4().hex
    campos = {"capas": "capa_marp", "latitud": repr(o["lat"]), "longitud": repr(o["lon"]),
              "id": str(o["id"])}
    cuerpo = "".join('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                     % (b, k, v) for k, v in campos.items()) + "--%s--\r\n" % b
    t = pedir(PORTAL + "mapa/verInformacionPoligono", cuerpo.encode(),
              {"Content-Type": "multipart/form-data; boundary=" + b})
    v = [x.strip() for x in html.unescape(re.sub(r"<[^>]+>", "|", t)).split("|") if x.strip()]
    return {v[i][:-1]: v[i + 1] for i in range(len(v) - 1)
            if v[i].endswith(":") and not v[i + 1].endswith(":")}


def palabras(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", s).split() if w not in VACIAS}


def dist_m(la1, lo1, la2, lo2):
    return 6371000.0 * math.hypot(math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2)),
                                  math.radians(la2 - la1))


def main():
    os.makedirs(DIR, exist_ok=True)
    hoy = datetime.date.today().isoformat()
    f_cat, f_fic = os.path.join(DIR, "monumentos_catalogo.json"), os.path.join(DIR, "fichas_chucuito.json")
    if os.path.exists(f_fic) and not os.environ.get("REDESCARGAR"):
        # se reutiliza la consulta guardada: el resultado queda ligado a su fecha
        c = json.load(open(f_cat, encoding="utf-8")); fi = json.load(open(f_fic, encoding="utf-8"))
        cat, fichas, hoy = c["monumentos"], fi["monumentos"], fi["consulta"]
        print("consulta reutilizada del %s (REDESCARGAR=1 para repetirla)" % hoy)
        return resumir(cat, fichas, hoy)
    cat = catalogo()
    json.dump({"fuente": PORTAL + "dgpa/json_monumentos", "consulta": hoy, "monumentos": cat},
              open(os.path.join(DIR, "monumentos_catalogo.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("catalogo nacional: %d monumentos" % len(cat), flush=True)

    caja = [o for o in cat if -17.5 < o["lat"] < -15.9 and -70.1 < o["lon"] < -68.8]
    fichas = []
    for o in caja:
        f = ficha(o)
        if f.get("Provincia") == "Chucuito":
            fichas.append(dict(o, **f))
        time.sleep(0.3)
    json.dump({"fuente": PORTAL + "mapa/verInformacionPoligono", "consulta": hoy,
               "monumentos": fichas},
              open(os.path.join(DIR, "fichas_chucuito.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("provincia de Chucuito: %d monumentos oficiales" % len(fichas), flush=True)
    return resumir(cat, fichas, hoy)


def resumir(cat, fichas, hoy):
    inc = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"), encoding="utf-8-sig")))
    distritos = sorted({r["distrito"].strip().lower() for r in inc})
    ofi = [f for f in fichas if f.get("Distrito", "").strip().lower() in distritos]

    pares, no_recogidos = [], []
    for o in ofi:
        ds = [dist_m(o["lat"], o["lon"], float(r["lat"]), float(r["lon"])) for r in inc]
        j = int(np.argmin(ds))
        comun = palabras(o["nombre"]) & palabras(inc[j]["nombre"])
        reg = {"oficial": o["nombre"], "id_oficial": o["id"], "distrito": o.get("Distrito"),
               "clasificacion": o.get("Clasificación"), "inc_mas_cercano": inc[j]["nombre"].strip(),
               "id_inc": int(inc[j]["id"]), "distancia_m": round(ds[j], 1),
               "palabras_comunes": sorted(comun)}
        if ds[j] <= UMBRAL_M and comun:
            pares.append(reg)
        else:
            no_recogidos.append(reg)
    ids_inc = {p["id_inc"] for p in pares}
    # desglose de los no recogidos: fuera del area que cubre la capa, entradas
    # repetidas del propio catalogo (mismo nombre a menos de 50 m) y el resto
    lejos = [n for n in no_recogidos if n["distancia_m"] > 5000]
    vistos, repetidos = [], []
    for n in no_recogidos:
        o = next(f for f in ofi if f["id"] == n["id_oficial"])
        if any(v["nombre"] == o["nombre"] and dist_m(v["lat"], v["lon"], o["lat"], o["lon"]) < 50
               for v in vistos):
            repetidos.append(n)
        vistos.append(o)
    dentro = [n for n in no_recogidos if n not in lejos and n not in repetidos]
    d = [p["distancia_m"] for p in pares]
    resumen = {
        "consulta": hoy,
        "fuente": "Ministerio de Cultura del Perú, Geoportal, catálogo de Monumentos "
                  "Arqueológicos Prehispánicos (servicios dgpa/json_monumentos y "
                  "mapa/verInformacionPoligono)",
        "monumentos_catalogo_nacional": len(cat),
        "monumentos_provincia": len(fichas),
        "monumentos_por_distrito": {k: sum(1 for f in fichas if f.get("Distrito") == k)
                                    for k in sorted({f.get("Distrito") for f in fichas})},
        "distritos_estudiados": distritos,
        "monumentos_en_distritos_estudiados": len(ofi),
        "recogidos_en_capa_inc": len(pares),
        "no_recogidos_en_capa_inc": len(no_recogidos),
        "sitios_capa_inc": len(inc),
        "sitios_inc_sin_monumento_oficial": len(inc) - len(ids_inc),
        "distancia_mediana_m": round(float(np.median(d)), 1) if d else None,
        "distancia_maxima_m": round(float(np.max(d)), 1) if d else None,
        "umbral_m": UMBRAL_M,
        "no_recogidos_fuera_de_cobertura": len(lejos),
        "no_recogidos_repetidos_en_catalogo": len(repetidos),
        "no_recogidos_dentro_de_cobertura": len(dentro),
        "nombres_no_recogidos_dentro": sorted({n["oficial"] for n in dentro}),
        "pares": pares,
        "no_recogidos": no_recogidos,
    }
    json.dump(resumen, open(os.path.join(RES, "contraste_mincul.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("en %s: %d oficiales, %d en la capa del INC (mediana %.0f m), %d no; "
          "%d de %d sitios de la capa sin monumento oficial"
          % ("/".join(distritos), len(ofi), len(pares), resumen["distancia_mediana_m"] or 0,
             len(no_recogidos), resumen["sitios_inc_sin_monumento_oficial"], len(inc)))


if __name__ == "__main__":
    main()
