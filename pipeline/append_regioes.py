"""Passo do run_all.py: mantém data/regioes/<key>.json.

Recomputa ranking/totais/vizinhos do snapshot novo e ACRESCENTA à timeline
os dias UTC ainda não cobertos (anda só nesses no histórico de origin/data,
não nos 120 commits). Mesmo padrão do append_events.py: fallback a comparar
só o topo se o checkout for shallow.

Regiões que deixaram de ter actividade não são reescritas — o workflow faz
mirror da pasta, portanto o ficheiro desaparece sozinho.

Uso: py append_regioes.py [pasta_saida]
"""
import argparse
import glob
import json
import os
import subprocess
from datetime import datetime, timezone

import eventos
import regioes

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")
CONCELHOS_GEO = os.path.join(REPO, "data", "concelhos_pt.geojson")


def _carrega(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _tl_existente(out_dir):
    """{(nivel, nome): [(data, [(a,n),...]), ...]} das timelines já publicadas."""
    fora = {}
    for p in glob.glob(os.path.join(out_dir, "regioes", "*.json")):
        d = _carrega(p)
        if not d:
            continue
        chave = (d["nivel"], d["regiao"])
        fora[chave] = [(x["data"], [tuple(t) for t in x["ranking"]]) for x in d.get("timeline", [])]
    return fora


def main(out_dir):
    novo = _carrega(os.path.join(out_dir, "club_regioes.json"))
    if not novo:
        print("append_regioes: sem club_regioes.json novo — nada a fazer")
        return
    hoje = datetime.fromisoformat(novo["atualizado"].replace("Z", "+00:00")).date().isoformat()

    tl_ant = _tl_existente(out_dir)
    coberto = {d for tl in tl_ant.values() for d, _ in tl}
    ultimo = max(coberto, default=regioes.DESDE)

    try:
        snaps = eventos.snapshots_por_dia(REPO, "origin/data", desde=ultimo)
    except Exception as e:
        print(f"append_regioes: git log de origin/data indisponível ({e})")
        snaps = {}
    snaps[hoje] = novo
    dias = [d for d in sorted(snaps) if d <= hoje]

    if len(dias) < 2:
        raw = subprocess.run(
            ["git", "-C", REPO, "show", "origin/data:data/club_regioes.json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if raw.returncode == 0:
            try:
                snaps = {"_prev": json.loads(raw.stdout), hoje: novo}
                dias = ["_prev", hoje]
                print("append_regioes: sem histórico — só topo de origin/data vs novo")
            except json.JSONDecodeError:
                pass

    ativas = regioes.regioes_ativas(novo)
    # timelines dos dias novos (só regiões activas hoje)
    tl_novas = regioes.timelines(
        {d: s for d, s in snaps.items() if d != "_prev"}, alvo=ativas
    )
    if "_prev" in snaps:  # fallback: trata o topo como "ontem"
        for chave, r in regioes.timelines({"_prev": snaps["_prev"]}, alvo=ativas).items():
            tl_novas.setdefault(chave, [])
            tl_novas[chave] = [(hoje, r[0][1])] + tl_novas.get(chave, [])

    stats = _carrega(os.path.join(out_dir, "stats.json")) or {}
    adjacency = _carrega(os.path.join(REPO, "data", "adjacency.json")) or {}
    gerado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    n = novas = 0
    for nivel in regioes.NIVEIS:
        for nome in sorted(ativas[nivel]):
            chave = (nivel, nome)
            tl = list(tl_ant.get(chave, []))
            cobertos = {d for d, _ in tl}
            antes = len(regioes.comprimir_timeline(tl))
            for d, r in tl_novas.get(chave, []):
                if d not in cobertos:
                    tl.append((d, r))
            tl.sort(key=lambda t: t[0])
            reg = regioes.construir(nivel, nome, novo, tl, stats, adjacency,
                                    ativas, CONCELHOS_GEO)
            novas += max(0, len(reg["timeline"]) - antes)
            regioes.escrever(out_dir, reg, gerado)
            n += 1
    print(f"append_regioes: {n} regiões, {novas} entrada(s) de timeline nova(s)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out_dir", nargs="?", default=DATA_DIR)
    a = p.parse_args()
    os.makedirs(os.path.join(a.out_dir, "regioes"), exist_ok=True)
    main(a.out_dir)
