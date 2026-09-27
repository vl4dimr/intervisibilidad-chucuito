# -*- coding: utf-8 -*-
"""
Genera un visor web 3D interactivo del paisaje visual de Chucuito.

Un unico HTML autocontenido, con Three.js: el relieve real como malla drapeada
(tinte hipsometrico + sombreado + la cuenca visual en rojo), los sitios
arqueologicos como marcadores 3D —las torres funerarias resaltadas, la
observadora como piramide—, y navegacion orbital. A diferencia de la figura
estatica de matplotlib, aqui el motor 3D ordena en profundidad y los sitios se
ven sobre el terreno.

Es la pieza de «arqueologia virtual» para el regreso a VAR: interactiva,
reproducible y depositable en Zenodo con DOI. Depende solo de numpy, rasterio
y matplotlib (para cocinar la textura); Three.js se sirve desde cdnjs.

Salida: chucuito_visor3d.html
"""
import base64
import csv
import io
import json
import os

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from rasterio.warp import transform as tcoords

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RES = os.path.join(BASE, "data"), os.path.join(BASE, "results")
UTM = "EPSG:32719"
N = 220   # lado de la malla del visor (submuestreo)


def main():
    with rasterio.open(os.path.join(DATA, "terreno_utm.tif")) as s:
        dem = s.read(1).astype(np.float32)
        tr = s.transform
        H, W = dem.shape
    vs = np.load(os.path.join(RES, "viewshed_nuestro.npy"))
    obs = json.load(open(os.path.join(RES, "observador_3d.json"), encoding="utf-8"))

    # recorte cuadrado centrado en el observador (~14 km)
    xs, ys = tcoords("EPSG:4326", UTM, [obs["x_raster"]], [obs["y_raster"]])
    oc, of = ~tr * (xs[0], ys[0]); oc, of = int(round(oc)), int(round(of))
    r = int(7000 / 30)
    f0, f1 = max(0, of - r), min(H, of + r)
    c0, c1 = max(0, oc - r), min(W, oc + r)

    fy = np.linspace(f0, f1 - 1, N).astype(int)
    fx = np.linspace(c0, c1 - 1, N).astype(int)
    z = dem[np.ix_(fy, fx)]
    vcrop = vs[np.ix_(fy, fx)]

    # --- textura: hipsometrico + sombreado + cuenca ------------------------
    hips = LinearSegmentedColormap.from_list("h",
        ["#eef2ea", "#d9dfc9", "#c3b795", "#a8875f", "#8a6a4a", "#7d6a63"])
    ls = LightSource(azdeg=315, altdeg=45)
    rgb = ls.shade(z, cmap=hips, blend_mode="soft", vert_exag=5,
                   dx=30, dy=30)[:, :, :3]
    agua = np.abs(z - 3808.5) < 0.05
    rgb[agua] = (0.788, 0.847, 0.906)
    vis = vcrop == 1
    rgb[vis, 0] = 0.72 + 0.28 * rgb[vis, 0]
    rgb[vis, 1] = 0.12 + 0.30 * rgb[vis, 1]
    rgb[vis, 2] = 0.12 + 0.30 * rgb[vis, 2]

    buf = io.BytesIO()
    plt.imsave(buf, np.flipud(rgb), format="png")
    tex_b64 = base64.b64encode(buf.getvalue()).decode()

    # --- alturas normalizadas para Three.js --------------------------------
    z0 = float(z.min())
    alturas = (z - z0).astype(float)              # metros sobre el minimo
    lado_m = (c1 - c0) * 30.0                      # extension real, metros

    # --- sitios: a coordenadas de la malla ---------------------------------
    sitios = []
    rows = list(csv.DictReader(open(os.path.join(DATA, "sitios_chucuito.csv"),
                                    encoding="utf-8-sig")))
    for row in rows:
        ux, uy = tcoords("EPSG:4326", UTM, [float(row["lon"])], [float(row["lat"])])
        cc, ff = ~tr * (ux[0], uy[0]); cc, ff = int(round(cc)), int(round(ff))
        if not (f0 <= ff < f1 and c0 <= cc < c1):
            continue
        # a coordenadas [0,1] de la malla
        u = (cc - c0) / (c1 - c0)
        v = (ff - f0) / (f1 - f0)
        alt = float(dem[ff, cc] - z0)
        es_fun = row["funerario"] == "True"
        es_obs = int(row["id"]) == int(obs["id"])
        visible = bool(vs[ff, cc] == 1)
        sitios.append({"u": u, "v": v, "alt": alt, "fun": es_fun,
                       "obs": es_obs, "vis": visible,
                       "nom": row["nombre"].strip()})

    n_fun = sum(1 for s in sitios if s["fun"] and not s["obs"])
    n_fun_vis = sum(1 for s in sitios if s["fun"] and not s["obs"] and s["vis"])

    datos = {
        "N": N, "lado_m": lado_m, "alturas": alturas.ravel().tolist(),
        "z_min": z0, "z_rango": float(z.max() - z.min()),
        "sitios": sitios, "n_fun": n_fun, "n_fun_vis": n_fun_vis,
        "obs_nom": obs["nombre"].strip(), "obs_alt": obs["altitud"],
    }

    html = PLANTILLA.replace("__TEX__", tex_b64).replace(
        "__DATOS__", json.dumps(datos))
    out = os.path.join(BASE, "chucuito_visor3d.html")
    open(out, "w", encoding="utf-8").write(html)
    kb = os.path.getsize(out) / 1024
    print("-> %s (%.0f KB) | %d sitios, %d torres funerarias (%d visibles)"
          % (out, kb, len(sitios), n_fun, n_fun_vis))


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chucuito 3D — paisaje visual desde una torre funeraria</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden;background:#0f1420;
    font-family:Arial,Helvetica,sans-serif;color:#e5e7eb}
  #c{position:fixed;inset:0}
  #panel{position:fixed;top:14px;left:14px;background:rgba(17,24,39,.82);
    padding:14px 16px;border-radius:10px;max-width:330px;line-height:1.5;
    backdrop-filter:blur(4px)}
  #panel h1{margin:0 0 6px;font-size:15px}
  #panel p{margin:4px 0;font-size:12px;color:#cbd5e1}
  .k{display:inline-block;width:12px;height:12px;border-radius:50%;
    margin-right:6px;vertical-align:middle;border:1px solid #fff}
  #hint{position:fixed;bottom:14px;left:14px;font-size:11px;color:#94a3b8}
  b.r{color:#f87171}
</style></head><body>
<div id="c"></div>
<div id="panel">
  <h1>Chucuito: el paisaje visual de una tumba</h1>
  <p>Cuenca visual desde la torre funeraria más alta del corpus
     (<span id="onom"></span>, <span id="oalt"></span> m), en rojo sobre el
     relieve real.</p>
  <p><span class="k" style="background:#111827"></span>Torre observadora</p>
  <p><span class="k" style="background:#b91c1c"></span>Otra torre funeraria
     (<b class="r"><span id="nfv"></span> de <span id="nf"></span></b> visible)</p>
  <p><span class="k" style="background:#3b4252"></span>Sitio no funerario</p>
  <p style="color:#94a3b8;font-size:11px;margin-top:8px">Exageración
     vertical ×2.5. Copernicus DEM GLO-30.</p>
</div>
<div id="hint">Arrastra para orbitar · rueda para acercar · clic derecho para desplazar</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/controls/OrbitControls.js"></script>
<script>
const D = __DATOS__;
document.getElementById('onom').textContent = D.obs_nom;
document.getElementById('oalt').textContent = Math.round(D.obs_alt);
document.getElementById('nf').textContent = D.n_fun;
document.getElementById('nfv').textContent = D.n_fun_vis;

const N = D.N, LADO = 100, EXAG = 2.5;
const escZ = (LADO / D.lado_m) * EXAG;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f1420);
scene.fog = new THREE.Fog(0x0f1420, 180, 340);
const cam = new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 0.1, 2000);
cam.position.set(0, 90, 120);
const rnd = new THREE.WebGLRenderer({antialias:true});
rnd.setSize(innerWidth, innerHeight);
rnd.setPixelRatio(Math.min(devicePixelRatio, 2));
document.getElementById('c').appendChild(rnd.domElement);
const ctr = new THREE.OrbitControls(cam, rnd.domElement);
ctr.enableDamping = true; ctr.maxPolarAngle = Math.PI*0.49;

// --- terreno: malla desplazada por el DEM ---
const geo = new THREE.PlaneGeometry(LADO, LADO, N-1, N-1);
const pos = geo.attributes.position;
for (let i=0;i<pos.count;i++){
  pos.setZ(i, D.alturas[i]*escZ);
}
geo.computeVertexNormals();
const tex = new THREE.TextureLoader().load('data:image/png;base64,__TEX__');
tex.minFilter = THREE.LinearFilter;
const mat = new THREE.MeshStandardMaterial({map:tex, roughness:.95, metalness:0});
const terreno = new THREE.Mesh(geo, mat);
terreno.rotation.x = -Math.PI/2;   // de plano XY a horizontal, altura en Y
scene.add(terreno);

// --- luces ---
scene.add(new THREE.AmbientLight(0xffffff, .55));
const sol = new THREE.DirectionalLight(0xffffff, .9);
sol.position.set(-1, 1.4, .6); scene.add(sol);

// --- sitios ---
function aMundo(u, v, alt){
  return new THREE.Vector3((u-0.5)*LADO, alt*escZ, -(0.5-v)*LADO);
}
D.sitios.forEach(s=>{
  const p = aMundo(s.u, s.v, s.alt);
  let m;
  if (s.obs){
    m = new THREE.Mesh(new THREE.ConeGeometry(1.6, 4, 4),
        new THREE.MeshStandardMaterial({color:0x111827}));
    m.position.set(p.x, p.y+2, p.z);
  } else {
    const col = s.fun ? 0xb91c1c : 0x3b4252;
    const rad = s.fun ? 1.1 : 0.8;
    m = new THREE.Mesh(new THREE.SphereGeometry(rad, 16, 12),
        new THREE.MeshStandardMaterial({color:col,
          emissive: s.vis ? 0x661111 : 0x000000}));
    m.position.set(p.x, p.y+rad, p.z);
  }
  scene.add(m);
});

// centrar la orbita sobre la torre observadora
const o = D.sitios.find(s=>s.obs);
if(o){ const p=aMundo(o.u,o.v,o.alt); ctr.target.set(p.x,p.y,p.z); }

addEventListener('resize', ()=>{
  cam.aspect = innerWidth/innerHeight; cam.updateProjectionMatrix();
  rnd.setSize(innerWidth, innerHeight);
});
(function loop(){ requestAnimationFrame(loop); ctr.update(); rnd.render(scene, cam); })();
</script></body></html>"""


if __name__ == "__main__":
    main()
