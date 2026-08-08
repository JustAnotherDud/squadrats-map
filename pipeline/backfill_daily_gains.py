"""One-off: reconstrói o histórico de ganhos diários a partir do git log de
data/squadrats.json. Corre uma vez, o resultado (data/daily_gains.json) fica
versionado; a partir daí fetch_club_koms.py mantém-no actualizado a cada
corrida (recalcula só a entrada do dia corrente, idempotente).

Critério de "dia": a data (UTC) do campo `atualizado` DENTRO de cada
snapshot — não a data do commit em si. O bot corre a horas variáveis e às
vezes duas vezes no mesmo dia UTC (ver discussão sobre "ruído de timestamp"),
por isso ficamos com o ÚLTIMO snapshot de cada dia UTC; o ganho desse dia é
a diferença para o último snapshot do dia anterior.

Atleta que aparece pela primeira vez num dia não conta como "ganho" nesse
dia — seria o total dele inteiro a aparecer como um pico gigante só por ter
sido acrescentado ao ATHLETES dict, não por ter corrido isso tudo num dia.

Uso: py backfill_daily_gains.py
"""
import json
import os
import subprocess
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

CAMPOS = ["squadrats", "squadratinhos", "yard", "yardinho",
          "ubersquadrat", "ubersquadratinho", "backyards", "backyardinhos"]


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8",
        cwd=os.path.dirname(HERE), check=True,
    ).stdout


def commits_de(caminho_relativo):
    out = git("log", "--follow", "--format=%H", "--", caminho_relativo)
    return [h for h in out.strip().splitlines() if h]


def snapshot(commit):
    conteudo = git("show", f"{commit}:data/squadrats.json")
    return json.loads(conteudo)


def main():
    commits = commits_de("data/squadrats.json")
    print(f"{len(commits)} commits no histórico de data/squadrats.json")

    por_dia = {}  # "AAAA-MM-DD" -> (datetime atualizado, atletas)
    ignorados = 0
    for h in commits:
        try:
            d = snapshot(h)
        except subprocess.CalledProcessError:
            ignorados += 1
            continue
        atualizado_raw = d.get("atualizado")
        if not atualizado_raw:
            ignorados += 1
            continue
        atualizado = datetime.fromisoformat(atualizado_raw.replace("Z", "+00:00"))
        dia = atualizado.date().isoformat()
        anterior = por_dia.get(dia)
        if anterior is None or atualizado > anterior[0]:
            por_dia[dia] = (atualizado, d["atletas"])
    if ignorados:
        print(f"  {ignorados} commits ignorados (ficheiro em falta ou sem 'atualizado')")

    dias_ordenados = sorted(por_dia.keys())
    print(f"{len(dias_ordenados)} dias distintos, de {dias_ordenados[0]} a {dias_ordenados[-1]}")

    resultado = []
    anterior_atletas = None
    for dia in dias_ordenados:
        _, atletas = por_dia[dia]
        ganhos = {}
        for nome, valores in atletas.items():
            if anterior_atletas is None or nome not in anterior_atletas:
                continue  # 1º dia de sempre, ou atleta a aparecer pela 1ª vez — sem baseline
            antes = anterior_atletas[nome]
            delta = {}
            for c in CAMPOS:
                d_valor = (valores.get(c) or 0) - (antes.get(c) or 0)
                if d_valor:
                    delta[c] = d_valor
            if delta:
                ganhos[nome] = delta
        if ganhos:
            resultado.append({"data": dia, "atletas": ganhos})
        anterior_atletas = atletas

    # ultimo_total: totais absolutos do snapshot mais recente — é a baseline
    # que daily_gains.actualizar() usa daqui para a frente (não vai ao git)
    out = {
        "gerado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ultimo_total": por_dia[dias_ordenados[-1]][1],
        "dias": resultado,
    }
    out_path = os.path.join(DATA_DIR, "daily_gains.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"escrito {out_path} — {len(resultado)} dias com ganhos reais")


if __name__ == "__main__":
    main()
