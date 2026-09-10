"""Gera os ficheiros de município estrangeiro que o classify.py carrega
(refdata/foreign_muni/<CC>.geojson), recortando a fonte completa para só a
zona que o clube já visitou + 10 km, e poda o grid_totals.json a condizer.

Porquê: guardar os ~11 mil municípios da Alemanha para os 3 que alguém tocou
seria 20 MB carregados em cada corrida do pipeline. Guardar só os municípios
a menos de 10 km de onde um membro REALMENTE andou é preparação real (uma ida
de volta à mesma zona já está coberta) por ~50 KB. A divisão fina de um país
só se materializa quando alguém lá vai a sério.

  fonte    -> refdata/foreign_muni/<CC>.full.geojson.gz: GADM 4.1 nível de
              município, reformatado para {properties: country, region,
              parent}, truncado a 6 casas e gzipado. Vive no `main` (dados
              GADM congelados, ~6,5 MB no total), NUNCA é carregado em
              runtime, só aqui. Para um país novo: ir ao GADM, preparar o
              .full.geojson.gz à mão, e correr isto.
  seed     -> os squares do club.json (data/, união de todos os atletas).
              `git checkout origin/data -- data/club.json` se faltar.
  buffer   -> 10 km REAIS à volta de cada square (projecção equirectangular
              local, ver clip_pais: sem isso o dwithin em graus dava ~6 km
              este-oeste a 53°N).
  saída    -> refdata/foreign_muni/<CC>.geojson (commitado, ~50 KB): é um
              ARTEFACTO, gerado por este script, nunca editado à mão. Correr
              o clip outra vez reconstrói-o de forma determinista a partir
              da fonte + do club.json.

Degradação, se um membro sair fora do buffer numa visita seguinte: os squares
novos ficam a nível de região (Land/província) até se voltar a correr isto.
É VISÍVEL: build_analise.py e classify_club.py contam esses squares e imprimem
`AVISO: <CC>: N square(s) ... fora do recorte de 10 km` no fim do run, e o
número fica em stats.foreign.*.muni_clip_misses. É o sinal de "correr o clip
outra vez" (que, ao contrário de antes, volta a incluir o que for preciso da
fonte completa: o recorte já não é irreversível).

Uso:
  py clip.py            reconstrói todos os foreign_muni/<CC>.geojson
  py clip.py DE ES      só estes
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys

from shapely import STRtree, points
from shapely.affinity import scale
from shapely.geometry import shape
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FOREIGN_MUNI = os.path.join(HERE, "foreign_muni")
GRID_TOTALS = os.path.join(HERE, "grid_totals.json")
CLUB_JSON = os.path.join(REPO, "data", "club.json")

BUFFER_KM = 10
KM_POR_GRAU_LAT = 111.0  # 1° de latitude, constante; a longitude corrige-se com cos(lat)
ZOOM = 17  # club.json é z17


def _clean(g):
    return g if g.is_valid else make_valid(g)


def _pontos_capturados():
    """(lon, lat) no centro de cada square do club.json. Seed do clip:
    mantêm-se os municípios a <10 km DESTES pontos (não os municípios já
    classificados: isso era circular, um square sem match de município não
    entrava no seed e ficava de fora do recorte para sempre).

    Devolve os pares crus (não um array de Point): o clip_pais reprojecta-os
    por país antes de os usar (ver lá)."""
    if not os.path.isfile(CLUB_JSON):
        sys.exit(
            f"clip.py: {CLUB_JSON} não existe. É um ficheiro da branch `data`: "
            "`git checkout origin/data -- data/club.json`."
        )
    with open(CLUB_JSON, encoding="utf-8") as f:
        club = json.load(f)
    n = 2 ** ZOOM
    xy = []
    for x, y, _mask in club["squares"]:
        lon = (x + 0.5) / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / n))))
        xy.append((lon, lat))
    return xy


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


def clip_pais(cc, xy):
    fonte = os.path.join(FOREIGN_MUNI, f"{cc}.full.geojson.gz")
    saida = os.path.join(FOREIGN_MUNI, f"{cc}.geojson")
    if not os.path.isfile(fonte):
        print(f"  {cc}: sem {os.path.basename(fonte)}, ignorado (país novo? "
              f"preparar a fonte completa do GADM primeiro, ver docstring)")
        return
    with gzip.open(fonte, "rt", encoding="utf-8") as f:
        fc = json.load(f)
    feats = fc["features"]
    names = [ft["properties"]["region"] for ft in feats]
    geoms = [_clean(shape(ft["geometry"])) for ft in feats]

    # dwithin mede em graus como se o plano fosse quadrado, mas 1° de longitude
    # vale 111·cos(lat) km, não 111. Sem corrigir, o buffer de 10 km encolhe
    # para ~6 km este-oeste a 53°N e pior mais a norte (foi o que quase deixou
    # cair Quickborn/DE). Projecta-se país + pontos para um equirectangular
    # local (x·cos(lat0)), onde 1° ≈ 111 km nos dois eixos, e aí o dwithin já
    # é um círculo real. lat0 = latitude média dos municípios do país.
    ys = [g.centroid.y for g in geoms]
    k = math.cos(math.radians((min(ys) + max(ys)) / 2))
    geoms_proj = [scale(g, xfact=k, yfact=1.0, origin=(0, 0)) for g in geoms]
    pts_proj = points([(lon * k, lat) for lon, lat in xy])

    # municípios a <= BUFFER_KM de algum square capturado. STRtree.query com
    # predicate="dwithin" faz isto vectorizado (não um buffer de 10 mil pontos).
    tree = STRtree(geoms_proj)
    _pt_idx, muni_idx = tree.query(pts_proj, predicate="dwithin",
                                   distance=BUFFER_KM / KM_POR_GRAU_LAT)
    keep = sorted(set(int(i) for i in muni_idx))
    if not keep:
        print(f"  {cc}: 0 municípios dentro do buffer, {os.path.basename(saida)} "
              f"não reescrito (o clube não tem squares perto de {cc})")
        return
    mantidos = {names[i] for i in keep}

    sub = {"type": "FeatureCollection", "features": [feats[i] for i in keep]}
    body = json.dumps(sub, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    antes_kb = os.path.getsize(saida) / 1024 if os.path.isfile(saida) else 0
    with open(saida, "wb") as f:
        f.write(body)
    print(f"  {cc}: {len(feats)} -> {len(keep)} municípios (a {BUFFER_KM} km reais "
          f"de um square)  {antes_kb:.0f} KB -> {len(body)/1024:.0f} KB")
    _poda_grid_totals(cc, mantidos)


def main(paises):
    if not paises:
        paises = sorted(
            os.path.basename(p)[:-len(".full.geojson.gz")]
            for p in glob.glob(os.path.join(FOREIGN_MUNI, "*.full.geojson.gz"))
        )
    print(f"clip: {BUFFER_KM} km à volta dos squares de "
          f"{os.path.relpath(CLUB_JSON, REPO)}")
    xy = _pontos_capturados()
    for cc in paises:
        clip_pais(cc.upper(), xy)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paises", nargs="*", help="códigos de país (default: todos)")
    a = ap.parse_args()
    main(a.paises)
