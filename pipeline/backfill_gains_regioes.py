"""One-off: reconstrói data/gains_regioes.json de 26 jul a ontem.

O club_regioes.json só existe a partir de 15 ago; antes disso reconstrói-se
o breakdown por região de cada dia a partir do histórico de data/club.json
(que vai até 26 jul), classificando cada square com o Classifier de sempre.
Cache (x,y) -> (concelho, distrito): cada square único é classificado uma
vez só, mesmo aparecendo em 44 snapshots (~15 k squares, ~8 s). A
reconstrução vive em recon_snapshots.py, partilhada com o backfill_events.

A partir daqui, append_gains_regioes.py (passo do run_all.py) mantém o
ficheiro — só faz o diff de dois snapshots de club_regioes.json, sem
classificar nada.

Uso: py backfill_gains_regioes.py [--branch origin/data] [pasta_saida]
"""
import argparse
import os
from datetime import datetime, timezone

import gains_regioes
import recon_snapshots

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")


def main(out_dir, branch):
    snaps = recon_snapshots.snapshots_club_por_dia(REPO, branch)
    dias = sorted(d for d in snaps if d >= gains_regioes.DESDE)
    if not dias:
        print("sem snapshots de club.json — nada a fazer")
        return
    print(f"{len(dias)} dias de club.json: {dias[0]} -> {dias[-1]}")

    classifier = recon_snapshots.criar_classifier()
    cache = {}
    recon = {}
    for i, dia in enumerate(dias, 1):
        recon[dia] = recon_snapshots.reconstruir(snaps[dia], classifier, cache)
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
