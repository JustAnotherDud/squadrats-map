"""Passo do run_all.py: acrescenta a data/events.json os eventos dos dias
ainda não cobertos, sem reprocessar o histórico todo (isso é o
backfill_events.py).

Trabalha por DIA UTC, tal como o backfill, assim os dois concordam sempre,
mesmo quando o pipeline esteve parado vários dias e um run recupera o
atraso (cada dia em falta fica com os seus eventos, não colapsa tudo no dia
da recuperação). Num run normal (6×/dia) isto lê 1-2 commits, não 118.

O snapshot "de hoje" é o club_regioes.json acabado de gerar (ainda não
commitado); os dias anteriores vêm do histórico de `origin/data`.

Append idempotente: a chave de cada evento é por dia (eventos.chave), por
isso os 6 runs do mesmo dia não duplicam nada.

Uso: py append_events.py [pasta_saida]
"""
import argparse
import json
import os
from datetime import datetime, timezone

import eventos

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO, "data")


def main(out_dir):
    novo_path = os.path.join(out_dir, "club_regioes.json")
    if not os.path.exists(novo_path):
        print("append_events: sem club_regioes.json novo, nada a fazer")
        return
    with open(novo_path, encoding="utf-8") as f:
        novo = json.load(f)
    hoje = datetime.fromisoformat(
        novo["atualizado"].replace("Z", "+00:00")
    ).date().isoformat()

    events_path = os.path.join(out_dir, "events.json")
    try:
        with open(events_path, encoding="utf-8") as f:
            atual = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        atual = {"gerado": None, "desde": eventos.DESDE, "eventos": []}
    atual.setdefault("eventos", [])
    atual.setdefault("desde", eventos.DESDE)

    ultimo = max((e["data"] for e in atual["eventos"]), default=eventos.DESDE)

    # caminho preferido: walk dia-a-dia sobre o histórico de origin/data (precisa
    # de profundidade, o workflow faz `git fetch origin data --depth=...`).
    try:
        por_dia = eventos.snapshots_por_dia(REPO, "origin/data", desde=ultimo)
    except Exception as e:
        print(f"append_events: git log de origin/data indisponível ({e})")
        por_dia = {}
    por_dia[hoje] = novo  # o run actual manda no seu próprio dia
    dias = [d for d in sorted(por_dia) if d <= hoje]

    # fallback (checkout shallow sem histórico): compara só o topo de
    # origin/data com o novo, tudo atribuído ao dia de hoje. Menos preciso num
    # gap de vários dias, mas nunca perde eventos num run normal.
    if len(dias) < 2:
        try:
            raw = __import__("subprocess").run(
                ["git", "-C", REPO, "show", "origin/data:data/club_regioes.json"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            ).stdout
            por_dia = {"_prev": json.loads(raw), hoje: novo}
            dias = ["_prev", hoje]
            print("append_events: sem histórico, a comparar só topo de origin/data vs novo")
        except Exception:
            print("append_events: sem snapshot anterior, só actualiza 'gerado'")

    novos = []
    if len(dias) >= 2:
        ja = {eventos.chave(e) for e in atual["eventos"]}
        for ontem, dia in zip(dias, dias[1:]):
            for ev in eventos.detectar(por_dia[ontem], por_dia[dia], dia if dia != "_prev" else hoje):
                k = eventos.chave(ev)
                if k not in ja:
                    ja.add(k)
                    novos.append(ev)

    if novos:
        atual["eventos"].extend(novos)
        # colapsa marcos redundantes (25 quando já há 50 no mesmo dia/região/
        # atleta, de um sync grande ou de runs sucessivos) e reordena p/ o feed
        atual["eventos"] = eventos.ordenar_feed(eventos.colapsar_marcos(atual["eventos"]))
        print(f"append_events: +{len(novos)} evento(s)")
        for ev in novos:
            print(f"  {ev['data']} {ev['nivel']} {ev['regiao']}: {ev['tipo']} "
                  f"{ev['quem']}" + (f" > {ev['sobre']}" if ev["sobre"] else ""))
    else:
        print("append_events: sem eventos novos")

    atual["gerado"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir)
