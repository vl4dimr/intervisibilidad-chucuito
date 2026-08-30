# -*- coding: utf-8 -*-
"""
Potencia de los contrastes: ¿que efecto habriamos podido detectar?

Un resultado no significativo admite dos lecturas opuestas —no hay efecto, o no
habia forma de verlo— y distinguirlas exige mirar la dispersion del modelo nulo,
no solo el valor p. Si la desviacion tipica nula es enorme, el contraste solo
detectaria efectos descomunales y su silencio no informa de nada.

Aqui se calcula, para cada nulo y cada alcance, el efecto minimo detectable: la
densidad que el conjunto observado tendria que haber alcanzado para superar el
percentil 95 de la distribucion nula. Comparado con lo observado, dice si el
contraste estaba en condiciones de responder.

Salida: results/potencia.json
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(BASE, "results")


def cargar(nombre):
    p = os.path.join(RES, nombre)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    nul = cargar("nulos.json")
    rig = cargar("nulo_rigido.json")
    fun = cargar("funerarios.json")

    filas = []

    if nul:
        for nombre, bloque in nul["nulos"].items():
            for k, d in bloque.items():
                filas.append({
                    "contraste": nombre, "alcance_m": float(k),
                    "observado": d["densidad_obs"],
                    "nulo_media": d["densidad_nula_media"],
                    "nulo_sd": d["densidad_nula_sd"],
                    "umbral_p95": d["densidad_nula_p95"],
                    "p": d["p_unilateral"], "z": d["z"],
                })
    if rig:
        for k, d in rig["por_alcance"].items():
            filas.append({
                "contraste": "rigido", "alcance_m": float(k),
                "observado": d["densidad_obs"],
                "nulo_media": d["nula_media"], "nulo_sd": d["nula_sd"],
                "umbral_p95": d["nula_p95"], "p": d["p_unilateral"], "z": d["z"],
            })
    if fun:
        for k, d in fun["por_alcance"].items():
            filas.append({
                "contraste": "subred_funeraria", "alcance_m": float(k),
                "observado": d["densidad_funeraria"],
                "nulo_media": d["densidad_aleatoria_media"],
                "nulo_sd": d["densidad_aleatoria_sd"],
                "umbral_p95": d["densidad_aleatoria_media"] + 1.645 * d["densidad_aleatoria_sd"],
                "p": d["p_unilateral"], "z": d["z"],
            })

    for f in filas:
        # cuanto tendria que haber subido la densidad observada para ser significativa
        f["falta_para_p95"] = f["umbral_p95"] - f["observado"]
        f["efecto_min_detectable_rel"] = (
            (f["umbral_p95"] - f["nulo_media"]) / f["nulo_media"] if f["nulo_media"] else None)
        f["cv_nulo"] = f["nulo_sd"] / f["nulo_media"] if f["nulo_media"] else None

    print("POTENCIA DE LOS CONTRASTES\n")
    print("  %-22s %7s  %8s %8s %8s   %8s  %7s" %
          ("contraste", "alcance", "observ.", "nulo", "umbral", "ef.mín.", "p"))
    for f in sorted(filas, key=lambda x: (x["contraste"], x["alcance_m"])):
        emd = f["efecto_min_detectable_rel"]
        print("  %-22s %6.0fm  %8.4f %8.4f %8.4f   %+7.0f%%  %7.4f" %
              (f["contraste"], f["alcance_m"], f["observado"], f["nulo_media"],
               f["umbral_p95"], 100 * emd if emd is not None else float("nan"), f["p"]))

    with open(os.path.join(RES, "potencia.json"), "w", encoding="utf-8") as fh:
        json.dump({"filas": filas,
                   "nota": ("El efecto minimo detectable es el aumento relativo sobre la media "
                            "nula que la densidad observada habria necesitado para superar el "
                            "percentil 95. Valores altos indican un contraste de baja potencia, "
                            "en el que un resultado no significativo no permite concluir ausencia "
                            "de efecto.")},
                  fh, ensure_ascii=False, indent=2)
    print("\n  ->", os.path.join(RES, "potencia.json"))


if __name__ == "__main__":
    main()
