"""Passo do run_all.py: recalcula data/atividades.json do zero a cada
corrida (cruzamento de squadrats.json com o feed de actividades do
folha-do-clube, ver atividades.py).

Recompute total, não incremental: ao contrário do append_events.py, aqui não
há estado a proteger de duplicação (nada como uma chave por dia) -- o
histórico de squadrats.json na branch `data` mais o activities.json
publicado já são a fonte de verdade completa, por isso recalcular tudo a
cada corrida dá sempre o mesmo resultado correcto. Mais simples e sem risco
de desalinhamento entre um estado incremental e o histórico real. Custo: um
`git show` por commit de squadrats.json, limitado pelo `--depth=500` do
workflow (poucos segundos, mesma ordem de grandeza do append_events.py).

Uso: py append_atividades.py [pasta_saida]
"""
import argparse
import json
import os
from datetime import datetime, timezone

import requests

import atividades

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")

ACTIVITIES_URL = "https://raw.githubusercontent.com/JustAnotherDud/folha-do-clube/main/activities.json"


def _buscar_atividades():
    """Linhas de activities.json (folha-do-clube). Degrada para [] com
    aviso se a busca falhar, em vez de abortar o passo -- as janelas de
    ganho continuam a escrever-se, só ficam todas "sem correspondência" até
    à corrida seguinte."""
    try:
        r = requests.get(ACTIVITIES_URL, timeout=30)
        r.raise_for_status()
        return r.json().get("linhas", [])
    except Exception as e:
        print(f"append_atividades: activities.json indisponível ({e}), a continuar sem correspondências")
        return []


def main(out_dir):
    novo_path = os.path.join(out_dir, "squadrats.json")
    if not os.path.exists(novo_path):
        print("append_atividades: sem squadrats.json novo, nada a fazer")
        return
    with open(novo_path, encoding="utf-8") as f:
        hoje = json.load(f)

    # histórico publicado + o snapshot desta corrida (ainda não commitado),
    # mesmo princípio do "hoje" no append_events.py
    snaps = atividades.snapshots_todos(REPO, "origin/data")
    hoje_ts = datetime.fromisoformat(hoje["atualizado"].replace("Z", "+00:00"))
    snaps.append((hoje_ts, hoje))
    snaps.sort(key=lambda p: p[0])

    janelas = atividades.deltas_squadratinhos(snaps)
    linhas = _buscar_atividades()
    resultado = atividades.cruzar(janelas, linhas)

    out = {
        "gerado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "janelas": resultado,
    }
    caminho = os.path.join(out_dir, "atividades.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    n_repartidas = sum(1 for j in resultado if j["repartido"])
    n_sem = sum(1 for j in resultado if not j["atividades"])
    print(f"append_atividades: {len(resultado)} janela(s) de ganho, "
          f"{n_repartidas} repartida(s), {n_sem} sem correspondência -> atividades.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir)
