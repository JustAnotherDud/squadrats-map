"""Recorta os ficheiros de município estrangeiro (refdata/foreign_muni/*.geojson)
para só a zona que o clube já visitou + 10 km, e poda o grid_totals.json a
condizer.

Porquê: guardar os ~11 mil municípios da Alemanha para os 3 que alguém tocou
é 20 MB de "e se". Guardar só os municípios a menos de 10 km de onde um
membro REALMENTE andou é preparação real (uma ida de volta à mesma zona está
coberta) por ~150 KB. A divisão fina de um país só se constrói quando alguém
lá vai a sério.

  origem   -> GADM 4.1 level 4 (Gemeinde/municipio), reformatado à mão uma vez
              para {properties: country, region, parent}. NÃO se vai buscar
              aqui — parte-se do ficheiro completo que já está no repo (ou,
              para um país novo, do ficheiro completo posto à mão em
              refdata/foreign_muni/<CC>.geojson antes de correr isto).
  seed     -> os municípios em que o clube tem squares (data/club_regioes.json,
              união dos atletas). Precisa do club_regioes.json presente:
              `git checkout origin/data -- data/club_regioes.json` se faltar.
  buffer   -> 10 km à volta da geometria desses municípios.

Degradação, se um membro sair fora do buffer numa visita seguinte: os squares
novos ficam a nível de região (Land/província) até se voltar a correr isto.
É VISÍVEL: build_mapa.py e classify_club.py contam esses squares e imprimem
`AVISO: <CC>: N square(s) ... fora do recorte de 10 km` no fim do run, e o
número fica em stats.foreign.*.muni_clip_misses. É o sinal de "correr o clip
outra vez".

Uso:
  py clip.py            recorta todos os foreign_muni/*.geojson
  py clip.py DE ES      só estes
"""
import argparse
import json
import os
import sys

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FOREIGN_MUNI = os.path.join(HERE, "foreign_muni")
GRID_TOTALS = os.path.join(HERE, "grid_totals.json")
CLUB_REGIOES = os.path.join(REPO, "data", "club_regioes.json")

BUFFER_KM = 10
DEG_PER_KM = 1.0 / 111.0


def _clean(g):
    return g if g.is_valid else make_valid(g)


def _municipios_capturados(cc):
    """Nomes de município em `cc` (minúsculo) onde algum atleta do clube tem
    squares, unindo os by_municipio de todos os atletas."""
    if not os.path.isfile(CLUB_REGIOES):
        sys.exit(
            f"clip.py: {CLUB_REGIOES} não existe. É um ficheiro da branch "
            "`data`: `git checkout origin/data -- data/club_regioes.json`."
        )
    with open(CLUB_REGIOES, encoding="utf-8") as f:
        cr = json.load(f)
    nomes = set()
    for info in cr.get("atletas", {}).values():
        nomes |= set((info.get("by_municipio") or {}).get(cc.lower(), {}))
    return nomes


def _poda_grid_totals(cc, mantidos):
    if not os.path.isfile(GRID_TOTALS):
        return
    with open(GRID_TOTALS, encoding="utf-8") as f:
        gt = json.load(f)
    chave = f"by_municipio_{cc.lower()}"
    bloco = gt.get(chave)
    if not bloco:
        return
    antes = len(bloco)
    gt[chave] = {k: v for k, v in bloco.items() if k in mantidos}
    with open(GRID_TOTALS, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  grid_totals.json[{chave}]: {antes} -> {len(gt[chave])} municípios")


def clip_pais(cc):
    path = os.path.join(FOREIGN_MUNI, f"{cc}.geojson")
    if not os.path.isfile(path):
        print(f"  {cc}: sem {path}, ignorado")
        return
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    feats = fc["features"]
    names = [ft["properties"]["region"] for ft in feats]
    geoms = [_clean(shape(ft["geometry"])) for ft in feats]

    capturados = _municipios_capturados(cc)
    seed_idx = [i for i, n in enumerate(names) if n in capturados]
    falta = capturados - {names[i] for i in seed_idx}
    if falta:
        print(f"  {cc}: {len(falta)} nome(s) capturado(s) sem match no geojson: {sorted(falta)}")
    if not seed_idx:
        print(f"  {cc}: 0 municípios capturados, NÃO recortado (ficaria vazio)")
        return

    hull = unary_union([geoms[i] for i in seed_idx]).buffer(BUFFER_KM * DEG_PER_KM)
    keep = [i for i, g in enumerate(geoms) if g.intersects(hull)]
    mantidos = {names[i] for i in keep}

    sub = {"type": "FeatureCollection", "features": [feats[i] for i in keep]}
    body = json.dumps(sub, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    antes_kb = os.path.getsize(path) / 1024
    with open(path, "wb") as f:
        f.write(body)
    print(f"  {cc}: {len(feats)} -> {len(keep)} municípios "
          f"({len(seed_idx)} visitados + vizinhos a {BUFFER_KM} km)  "
          f"{antes_kb:.0f} KB -> {len(body)/1024:.0f} KB")
    _poda_grid_totals(cc, mantidos)


def main(paises):
    if not paises:
        paises = sorted(
            os.path.splitext(f)[0] for f in os.listdir(FOREIGN_MUNI)
            if f.endswith(".geojson")
        )
    print(f"clip: buffer {BUFFER_KM} km, seeds de {os.path.relpath(CLUB_REGIOES, REPO)}")
    for cc in paises:
        clip_pais(cc.upper())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paises", nargs="*", help="códigos de país (default: todos)")
    a = ap.parse_args()
    main(a.paises)
