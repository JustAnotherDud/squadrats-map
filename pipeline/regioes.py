"""Lógica partilhada das páginas por região (concelho/distrito, PT).

Consumido por:
  - backfill_regioes.py  (varre todo o histórico da branch `data`, uma vez)
  - append_regioes.py    (passo do run_all.py — só os dias novos)
  - gen_regiao_stubs.py  (escreve regioes/<key>.html a partir de data/regioes/)

Cada região com actividade (algum atleta com >=1 square lá) tem um ficheiro
data/regioes/<key>.json, onde key = "c-<slug>" (concelho) ou "d-<slug>"
(distrito) — o prefixo desambigua os 18 nomes que são concelho E distrito
(Santarém, Coimbra, ...). O slug é o mesmo do pipeline.slugs.slugify, para o
historico.html poder reconstruir o URL com um slugify igual em JS.
"""
import json
import os

from slugs import slugify

DESDE = "2026-08-15"  # club_regioes.json só existe a partir daqui
NIVEIS = ("concelho", "distrito")
CHAVE_BUCKET = {"concelho": "by_concelho", "distrito": "by_distrito"}
CHAVE_ADJ = {"concelho": "concelhos", "distrito": "distritos"}
CHAVE_STATS = {"concelho": "by_concelho", "distrito": "by_distrito"}

ATLETAS_ORDEM = ["Zé", "Xeira", "Carolina", "Inês S.", "Pedro"]


def key_de(nivel, nome):
    return ("c-" if nivel == "concelho" else "d-") + slugify(nome)


def regioes_ativas(club_regioes):
    """{nivel: set(nomes)} das regiões PT com pelo menos um atleta a >0."""
    fora = {n: set() for n in NIVEIS}
    for info in club_regioes.get("atletas", {}).values():
        for nivel in NIVEIS:
            for nome, n in (info.get(CHAVE_BUCKET[nivel]) or {}).items():
                if n > 0:
                    fora[nivel].add(nome)
    return fora


def ranking_de(club_regioes, nivel, nome):
    """[(atleta, captured), ...] ordenado desc; empate pela ordem canónica.
    Só atletas com captured > 0."""
    b = CHAVE_BUCKET[nivel]
    pares = []
    for atleta, info in club_regioes.get("atletas", {}).items():
        n = (info.get(b) or {}).get(nome, 0)
        if n > 0:
            pares.append((atleta, n))
    pares.sort(key=lambda t: (-t[1],
               ATLETAS_ORDEM.index(t[0]) if t[0] in ATLETAS_ORDEM else 99))
    return pares


def comprimir_timeline(tl):
    """[(data, ranking), ...] -> só as entradas em que o ranking mudou face à
    anterior (a primeira fica sempre). O frontend arrasta a última conhecida
    até `gerado`. Sem isto, uma região parada acumulava uma linha por dia."""
    fora = []
    for data, r in sorted(tl, key=lambda t: t[0]):
        rr = [list(x) for x in r]
        if not fora or fora[-1][1] != rr:
            fora.append((data, rr))
    return fora


def timelines(snaps_por_dia, alvo=None):
    """{(nivel, nome): [(data, [(atleta, n), ...]), ...]} — o ranking de cada
    região em cada dia UTC em que já tinha actividade. `alvo` opcional:
    {nivel: set(nomes)} para limitar a essas regiões (as activas hoje)."""
    fora = {}
    for dia in sorted(snaps_por_dia):
        snap = snaps_por_dia[dia]
        for nivel in NIVEIS:
            nomes = set()
            for info in snap.get("atletas", {}).values():
                nomes |= set(n for n, v in (info.get(CHAVE_BUCKET[nivel]) or {}).items() if v > 0)
            if alvo is not None:
                nomes &= alvo[nivel]
            for nome in nomes:
                r = ranking_de(snap, nivel, nome)
                if r:
                    fora.setdefault((nivel, nome), []).append((dia, r))
    return fora


def _distrito_pai(concelhos_geojson_path, nome):
    """distrito (property `parent`) de um concelho — para o cabeçalho."""
    try:
        with open(concelhos_geojson_path, encoding="utf-8") as f:
            geo = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    for feat in geo.get("features", []):
        if feat["properties"].get("NAME_2") == nome:
            return feat["properties"].get("parent")
    return None


def construir(nivel, nome, snapshot_atual, timeline, stats, adjacency,
              ativas, concelhos_geojson_path):
    """Dict final de uma região. `timeline` = [(data, [(atleta, n), ...]), ...]
    já acumulado; `ativas` = regioes_ativas(snapshot_atual) para saber que
    vizinhos têm página."""
    total = (stats.get(CHAVE_STATS[nivel], {}).get(nome) or {})
    z14 = (total.get("z14") or {}).get("total")
    z17 = (total.get("z17") or {}).get("total")

    rank = ranking_de(snapshot_atual, nivel, nome)
    ranking = [
        {"nome": a, "captured": n, "pct": round(100 * n / z17, 2) if z17 else None}
        for a, n in rank
    ]

    viz = []
    for vn in (adjacency.get(CHAVE_ADJ[nivel], {}).get(nome, {}) or {}).get("neighbors", []):
        viz.append({"nome": vn, "key": key_de(nivel, vn),
                    "tem_pagina": vn in ativas[nivel]})

    pai = _distrito_pai(concelhos_geojson_path, nome) if nivel == "concelho" else None

    return {
        "nivel": nivel,
        "regiao": nome,
        "cc": "PT",
        "key": key_de(nivel, nome),
        "slug": slugify(nome),
        "distrito_pai": pai,
        "distrito_pai_key": key_de("distrito", pai) if pai else None,
        "totais": {"z14": z14, "z17": z17},
        "ranking": ranking,
        "vizinhos": viz,
        "timeline": [
            {"data": d, "ranking": [[a, n] for a, n in r]}
            for d, r in comprimir_timeline(timeline)
        ],
        "desde": DESDE,
    }


def escrever(out_dir, regiao_dict, gerado):
    d = dict(regiao_dict, gerado=gerado)
    os.makedirs(os.path.join(out_dir, "regioes"), exist_ok=True)
    caminho = os.path.join(out_dir, "regioes", regiao_dict["key"] + ".json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return caminho
