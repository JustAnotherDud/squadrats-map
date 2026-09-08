"""One-off: reconstrói data/gains_regioes.json de 26 jul a ontem.

O club_regioes.json só existe a partir de 15 ago; antes disso reconstrói-se
o breakdown por região de cada dia a partir do histórico de data/club.json
(que vai até 26 jul), classificando cada square com o Classifier de sempre.
Cache (x,y) -> (concelho, distrito): cada square único é classificado uma
vez só, mesmo aparecendo em 44 snapshots (~15 k squares, ~8 s).

A partir daqui, append_gains_regioes.py (passo do run_all.py) mantém o
ficheiro — só faz o diff de dois snapshots de club_regioes.json, sem
classificar nada.

Uso: py backfill_gains_regioes.py [--branch origin/data] [pasta_saida]
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone

import gains_regioes
from classify import Classifier
from kml_parse import tile_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")
REFDATA = os.path.join(HERE, "refdata")
ZOOM = 17


def _git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def snapshots_club_por_dia(branch):
    """{data_utc: club_dict} — o último club.json commitado de cada dia UTC,
    pela data do campo `atualizado` (mesma regra do backfill_daily_gains.py)."""
    shas = _git("log", branch, "--format=%H", "--", "data/club.json").split()
    por_dia, ts_por_dia = {}, {}
    for sha in shas:
        try:
            d = json.loads(_git("show", f"{sha}:data/club.json"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        raw = d.get("atualizado")
        if not raw:
            continue
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dia = ts.date().isoformat()
        if dia not in ts_por_dia or ts > ts_por_dia[dia]:
            por_dia[dia], ts_por_dia[dia] = d, ts
    return por_dia


def reconstruir(club, classifier, cache):
    """club.json -> formato club_regioes ({"atletas": {nome: {by_concelho,
    by_distrito, by_pais}}}), classificando cada square (com cache).
    `by_pais` só o estrangeiro — para dar nome ao resíduo do drill-down."""
    atletas = club["atletas"]
    out = {a["nome"]: {"by_concelho": {}, "by_distrito": {}, "by_pais": {}}
           for a in atletas}
    for x, y, mask in club["squares"]:
        cd = cache.get((x, y))
        if cd is None:
            info = classifier.classify(tile_bounds(x, y, ZOOM))
            cd = ((info["concelho"], info["district"], None) if info["in_portugal"]
                  else (None, None, info["country"]))
            cache[(x, y)] = cd
        conc, dist, pais = cd
        if not conc and not dist and not pais:
            continue
        for i, a in enumerate(atletas):
            if mask & (1 << i):
                reg = out[a["nome"]]
                if conc:
                    reg["by_concelho"][conc] = reg["by_concelho"].get(conc, 0) + 1
                if dist:
                    reg["by_distrito"][dist] = reg["by_distrito"].get(dist, 0) + 1
                if pais and pais != "PT":
                    reg["by_pais"][pais] = reg["by_pais"].get(pais, 0) + 1
    return {"atletas": out}


def main(out_dir, branch):
    snaps = snapshots_club_por_dia(branch)
    dias = sorted(d for d in snaps if d >= gains_regioes.DESDE)
    if not dias:
        print("sem snapshots de club.json — nada a fazer")
        return
    print(f"{len(dias)} dias de club.json: {dias[0]} -> {dias[-1]}")

    classifier = Classifier(
        os.path.join(REFDATA, "distritos_pt.geojson"),
        os.path.join(REFDATA, "concelhos_pt.geojson"),
        foreign_dir=os.path.join(REFDATA, "foreign"),
        foreign_muni_dir=os.path.join(REFDATA, "foreign_muni"),
    )
    cache = {}
    recon = {}
    for i, dia in enumerate(dias, 1):
        recon[dia] = reconstruir(snaps[dia], classifier, cache)
        print(f"  [{i}/{len(dias)}] {dia}  (cache {len(cache)})")

    saida, prev = [], None
    for dia in dias:
        if prev is not None:
            g = gains_regioes.diff_snapshots(recon[prev], recon[dia])
            if g:
                saida.append({"data": dia, "atletas": g})
        prev = dia

    gerado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = gains_regioes.escrever(out_dir, saida, gerado)
    tot = sum(len(x["atletas"]) for x in saida)
    print(f"{len(saida)} dias com ganhos por região ({tot} entradas atleta-dia) -> {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--branch", default="origin/data")
    p.add_argument("out_dir", nargs="?", default=DATA_DIR)
    a = p.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    main(a.out_dir, a.branch)
