"""One-off: escreve data/regioes/<key>.json para cada concelho/distrito PT
com actividade, a partir de todo o histórico da branch `data`.

- ranking/totais/vizinhos: do snapshot mais recente
- timeline: o ranking de cada dia UTC (eventos.snapshots_por_dia)

A partir daqui, append_regioes.py (passo do run_all.py) mantém-nos — só
acrescenta os dias novos à timeline, não revarre os 120 commits.

Uso: py backfill_regioes.py [--branch origin/data] [pasta_saida]
"""
import argparse
import json
import os
from datetime import datetime, timezone

import eventos
import regioes

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")
CONCELHOS_GEO = os.path.join(REPO, "data", "concelhos_pt.geojson")


def _carrega(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(out_dir, branch):
    snaps = eventos.snapshots_por_dia(REPO, branch)
    dias = sorted(snaps)
    atual = snaps[dias[-1]]
    print(f"{len(dias)} dias, {dias[0]} -> {dias[-1]}")

    ativas = regioes.regioes_ativas(atual)
    print(f"regiões activas: {len(ativas['concelho'])} concelhos, {len(ativas['distrito'])} distritos")

    tls = regioes.timelines(snaps, alvo=ativas)
    stats = _carrega(os.path.join(out_dir, "stats.json"))
    adjacency = _carrega(os.path.join(REPO, "data", "adjacency.json"))
    gerado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    n = 0
    for nivel in regioes.NIVEIS:
        for nome in sorted(ativas[nivel]):
            tl = tls.get((nivel, nome), [])
            d = regioes.construir(nivel, nome, atual, tl, stats, adjacency,
                                  ativas, CONCELHOS_GEO)
            regioes.escrever(out_dir, d, gerado)
            n += 1
    print(f"{n} ficheiros -> {os.path.join(out_dir, 'regioes')}/")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--branch", default="origin/data")
    p.add_argument("out_dir", nargs="?", default=DATA_DIR)
    a = p.parse_args()
    os.makedirs(os.path.join(a.out_dir, "regioes"), exist_ok=True)
    main(a.out_dir, a.branch)
