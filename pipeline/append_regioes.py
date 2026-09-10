"""Passo do run_all.py: reescreve data/regioes/<key>.json.

Recomputa ranking/totais/união/vizinhos de cada região activa a partir do
club_regioes.json novo. Idempotente: escreve o estado actual, sem histórico
acumulado. O workflow faz mirror da pasta, portanto uma região que deixou de
ter actividade desaparece sozinha.

Uso: py append_regioes.py [pasta_saida]
"""
import argparse
import json
import os
from datetime import datetime, timezone

import regioes

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")
# só se usa para o lookup concelho -> distrito (properties.parent), geometria
# nenhuma; lê da fonte de precisão (refdata), não da cópia simplificada de
# data/ que agora só serve para o analise.html desenhar.
CONCELHOS_GEO = os.path.join(HERE, "refdata", "concelhos_pt.geojson")
FOREIGN_MUNI_DIR = os.path.join(HERE, "refdata", "foreign_muni")


def _carrega(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main(out_dir):
    novo = _carrega(os.path.join(out_dir, "club_regioes.json"))
    if not novo:
        print("append_regioes: sem club_regioes.json novo, nada a fazer")
        return

    ativas = regioes.regioes_ativas(novo)
    stats = _carrega(os.path.join(out_dir, "stats.json")) or {}
    adjacency = _carrega(os.path.join(REPO, "data", "adjacency.json")) or {}
    gerado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # "disputada" no índice = evento de troca real (ultrapassagem / novo
    # líder), igual ao historico.html e ao regiao.js. O events.json já está
    # escrito neste ponto, o append_events corre antes deste passo.
    disputadas = regioes.disputadas_de(
        (_carrega(os.path.join(out_dir, "events.json")) or {}).get("eventos", []))

    n = 0
    indice = []
    for nivel in regioes.NIVEIS:
        for nome in sorted(ativas[nivel]):
            reg = regioes.construir(nivel, nome, novo, stats, adjacency,
                                    ativas, CONCELHOS_GEO)
            regioes.escrever(out_dir, reg, gerado)
            indice.append(regioes.linha_indice(reg, disputadas))
            n += 1

    regioes.escrever_indice(out_dir, indice, gerado)
    print(f"append_regioes: {n} regiões, {len(disputadas)} disputadas "
          f"-> regioes_index.json")

    # --- estrangeiro (Fase 2): escreve data/regioes/<ccl>-r-*.json e
    # <ccl>-z-*.json com dados reais, MAS fora do regioes_index.json e sem
    # stub HTML (o gen_regiao_stubs.py ignora estas keys por agora). O
    # renderer, a ligação a partir do índice e as páginas de país são da
    # Fase 3; isto só deixa os dados prontos na branch `data` para inspecção.
    ativas_estr = regioes.ativas_estrangeiro(novo)
    ne = 0
    for ccl, niveis in sorted(ativas_estr.items()):
        pmap = regioes.parent_map_estrangeiro(
            os.path.join(FOREIGN_MUNI_DIR, f"{ccl.upper()}.geojson"))
        for nivel in ("regiao", "zona"):
            for nome in sorted(niveis[nivel]):
                reg = regioes.construir_estrangeiro(
                    ccl, nivel, nome, novo, stats, adjacency, ativas_estr,
                    pmap.get(nome))
                regioes.escrever(out_dir, reg, gerado)
                ne += 1
    if ne:
        print(f"append_regioes: +{ne} ficheiros de região/zona estrangeira "
              f"(fora do índice e sem stub, Fase 2)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out_dir", nargs="?", default=DATA_DIR)
    a = p.parse_args()
    os.makedirs(os.path.join(a.out_dir, "regioes"), exist_ok=True)
    main(a.out_dir)
