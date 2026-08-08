"""Ganhos diários por atleta — mantém data/daily_gains.json actualizado.

Fonte da verdade para "que dia é este snapshot": o campo `atualizado` (UTC)
DENTRO do próprio squadrats.json de cada commit — não a data do commit git
(o bot corre a horas variáveis, às vezes 2x no mesmo dia UTC; ver
backfill_daily_gains.py, que populou o histórico inicial com o mesmo
critério).

Atleta que aparece pela primeira vez não conta como "ganho" nesse dia — o
total dele inteiro apareceria como um pico gigante só por ter sido
acrescentado ao ATHLETES dict, não por ter corrido isso tudo num dia.
"""
import json
import os
import subprocess
from datetime import datetime, timezone

CAMPOS = ["squadrats", "squadratinhos", "yard", "yardinho",
          "ubersquadrat", "ubersquadratinho", "backyards", "backyardinhos"]


def _git(repo_dir, *args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8",
        cwd=repo_dir, check=True,
    ).stdout


def ultimo_snapshot_antes_de(repo_dir, hoje_iso):
    """{atleta: {...}} do último squadrats.json commitado com `atualizado`
    de um dia anterior a `hoje_iso` (AAAA-MM-DD). None se não houver nenhum
    (primeiro dia de sempre).

    git log devolve do mais recente para o mais antigo — para na primeira
    entrada de um dia anterior a hoje, que é sempre a mais recente desse
    dia. Evita percorrer o histórico todo em cada corrida."""
    commits = _git(repo_dir, "log", "--follow", "--format=%H", "--", "data/squadrats.json").strip().splitlines()
    for h in commits:
        try:
            conteudo = _git(repo_dir, "show", f"{h}:data/squadrats.json")
            d = json.loads(conteudo)
        except subprocess.CalledProcessError:
            continue  # ficheiro não existia ainda nesse commit
        atualizado_raw = d.get("atualizado")
        if not atualizado_raw:
            continue
        atualizado = datetime.fromisoformat(atualizado_raw.replace("Z", "+00:00"))
        if atualizado.date().isoformat() < hoje_iso:
            return d["atletas"]
    return None


def calcular_delta(antes, agora):
    """{atleta: {campo: delta}} — só campos que mudaram, só atletas com
    baseline no dia anterior."""
    ganhos = {}
    for nome, valores in agora.items():
        if antes is None or nome not in antes:
            continue
        base = antes[nome]
        delta = {}
        for c in CAMPOS:
            d_valor = (valores.get(c) or 0) - (base.get(c) or 0)
            if d_valor:
                delta[c] = d_valor
        if delta:
            ganhos[nome] = delta
    return ganhos


def actualizar(data_dir, repo_dir, atletas_hoje, hoje_iso=None):
    """Actualiza data/daily_gains.json com a entrada do dia corrente.

    Idempotente: se já existir uma entrada para hoje (2ª corrida no mesmo
    dia), substitui-a em vez de duplicar — recalculada contra a mesma
    baseline (o último dia ANTERIOR a hoje), por isso dá sempre o mesmo
    resultado para o mesmo par de dias, run a run."""
    hoje_iso = hoje_iso or datetime.now(timezone.utc).date().isoformat()
    path = os.path.join(data_dir, "daily_gains.json")

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            actual = json.load(f)
    else:
        actual = {"gerado": None, "dias": []}

    antes = ultimo_snapshot_antes_de(repo_dir, hoje_iso)
    ganhos_hoje = calcular_delta(antes, atletas_hoje)

    dias = [d for d in actual["dias"] if d["data"] != hoje_iso]
    if ganhos_hoje:
        dias.append({"data": hoje_iso, "atletas": ganhos_hoje})
    dias.sort(key=lambda d: d["data"])

    actual["dias"] = dias
    actual["gerado"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(actual, f, ensure_ascii=False, separators=(",", ":"))
    return ganhos_hoje
