"""One-off: reconstrói data/events.json a partir de todo o histórico de
commits de data/club_regioes.json na branch `data`.

Critério de "dia": o último snapshot de cada dia UTC (eventos.snapshots_por_dia,
mesma lógica do backfill_daily_gains.py). Compara dias consecutivos e corre
eventos.detectar. O resultado é versionado; a partir daí append_events.py
mantém-no com um append incremental (só os dias ainda não cobertos).

O histórico de club_regioes.json começa em 2026-08-15 — os eventos não vão
mais para trás do que isso.

Uso: py backfill_events.py [--branch origin/data] [pasta_saida]
"""
import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone

import eventos

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")


def main(out_dir, branch):
    por_dia = eventos.snapshots_por_dia(REPO, branch)
    dias = sorted(por_dia)
    print(f"{len(dias)} dias com snapshot, {dias[0]} -> {dias[-1]}")

    todos, vistos = [], set()
    for ontem, hoje in zip(dias, dias[1:]):
        for ev in eventos.detectar(por_dia[ontem], por_dia[hoje], hoje):
            k = eventos.chave(ev)
            if k not in vistos:
                vistos.add(k)
                todos.append(ev)
    todos.sort(key=lambda e: (e["data"], e["nivel"], e["regiao"], e["tipo"]))

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
