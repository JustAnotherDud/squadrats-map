"""One-off: reconstrói data/events.json a partir do histórico da branch `data`.

Critério de "dia": o último snapshot de cada dia UTC. Compara dias
consecutivos e corre eventos.detectar. O resultado é versionado; a partir daí
append_events.py mantém-no com um append incremental (só os dias ainda não
cobertos).

Os snapshots vêm de recon_snapshots.snapshots_estendidos: club_regioes.json
real de 15 ago em diante, reconstruído do club.json (Classifier + cache)
para 26 jul -> 14 ago. A comparação de fronteira 14->15 ago recupera eventos
que a versão antiga (só club_regioes.json) perdia por não ter baseline.

Uso: py backfill_events.py [--branch origin/data] [pasta_saida]
"""
import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone

import eventos
import recon_snapshots

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")


def main(out_dir, branch):
    por_dia = recon_snapshots.snapshots_estendidos(REPO, branch)
    dias = sorted(por_dia)
    print(f"{len(dias)} dias com snapshot, {dias[0]} -> {dias[-1]}")

    # marcos de totais: snapshots do squadrats.json (só existe de facto na
    # branch `data`, sem reconstrução: antes disso não há marco de totais).
    sq_por_dia = {}
    try:
        sq_por_dia, _ = eventos.snapshots_por_dia(REPO, branch, path="data/squadrats.json")
        print(f"squadrats.json: {len(sq_por_dia)} dias para marcos de totais")
    except Exception as e:
        print(f"squadrats.json indisponível, sem marcos de totais ({e})")

    todos, vistos = [], set()
    for ontem, hoje in zip(dias, dias[1:]):
        for ev in eventos.detectar(por_dia[ontem], por_dia[hoje], hoje):
            k = eventos.chave(ev)
            if k not in vistos:
                vistos.add(k)
                todos.append(ev)
        if ontem in sq_por_dia and hoje in sq_por_dia:
            for ev in eventos.detectar_totais(
                    eventos.totais_sqi(sq_por_dia[ontem]), eventos.totais_sqi(sq_por_dia[hoje]),
                    eventos.uniao_clube(por_dia[ontem]), eventos.uniao_clube(por_dia[hoje]), hoje):
                k = eventos.chave(ev)
                if k not in vistos:
                    vistos.add(k)
                    todos.append(ev)
    todos = eventos.ordenar_feed(eventos.colapsar_marcos(todos))

    resultado = {
        "gerado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "desde": eventos.DESDE,
        "eventos": todos,
    }
    caminho = os.path.join(out_dir, "events.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, separators=(",", ":"))

    c = Counter((e["nivel"], e["tipo"]) for e in todos)
    print(f"\n{len(todos)} eventos -> {caminho}")
    for (nivel, tipo), n in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f"  {nivel:<10} {tipo:<20} {n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", default="origin/data")
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir, args.branch)
