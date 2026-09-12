"""Cruza o feed de actividades do Strava (folha-do-clube/activities.json)
com os ganhos de squadratinhos entre snapshots consecutivos de
squadrats.json, resolução por CORRIDA do pipeline, não por dia (ao
contrário de eventos.snapshots_por_dia, que fica só com o último snapshot
de cada dia UTC: aqui a resolução fina é o ponto todo, ver a investigação
"Actividades do clube").

Consumido por append_atividades.py (passo do run_all.py).

Uma "janela de ganho" é [inicio, fim] = os "atualizado" de dois snapshots
consecutivos de squadrats.json, para um atleta com ganho > 0 de
squadratinhos nesse intervalo. Cruza contra actividades cujo intervalo
[startDate, startDate + duracao_s] se sobrepõe à janela:
  - 0 actividades: ganho sem correspondência (bicicleta sem Strava, crédito
    retroactivo do Squadrats, como o caso do Pedro em Grândola).
  - 1 actividade: fica com o ganho todo, sem partilha.
  - 2+ actividades: reparte o ganho na proporção do tempo de SOBREPOSIÇÃO de
    cada uma com a janela (não a duração inteira da actividade), marcado
    "repartido": True -- a UI tem de mostrar isto, nunca apresentar um
    número repartido como exacto.
"""
import json
import subprocess
from datetime import datetime, timedelta


def _iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshots_todos(repo, branch="origin/data", path="data/squadrats.json"):
    """[(datetime, dict), ...] em ordem cronológica, UM POR COMMIT (ao
    contrário de eventos.snapshots_por_dia, que só guarda o último de cada
    dia) -- cada commit é uma corrida do pipeline, com o seu próprio
    "atualizado". Mesmo tratamento de commits ilegíveis que
    snapshots_por_dia: salta e avisa, só levanta RuntimeError se a branch
    tiver commits do ficheiro e NENHUM for legível (histórico presente mas
    inacessível, quase sempre um `git fetch --depth` curto demais)."""
    args = ["git", "-C", repo, "log", branch, "--format=%H", "--reverse", "--", path]
    shas = subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.split()

    snaps, saltados = [], []
    for sha in shas:
        r = subprocess.run(["git", "-C", repo, "show", f"{sha}:{path}"],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            saltados.append((sha, "blob em falta (checkout shallow?)"))
            continue
        try:
            d = json.loads(r.stdout)
            ts = _iso(d["atualizado"])
        except Exception as e:
            saltados.append((sha, f"squadrats.json inesperado: {type(e).__name__}: {e}"))
            continue
        snaps.append((ts, d))

    if saltados:
        from collections import Counter
        resumo = Counter(m for _, m in saltados)
        print(f"snapshots_todos: {len(saltados)}/{len(shas)} commit(s) saltado(s), "
              + "; ".join(f"{n}x {m}" for m, n in resumo.most_common()))
    if shas and not snaps:
        raise RuntimeError(
            f"snapshots_todos: {len(shas)} commit(s) de {path} em {branch}, "
            "nenhum legível. Clone shallow demais? "
            "(o workflow faz `git fetch origin data --depth=500`)."
        )
    snaps.sort(key=lambda p: p[0])
    return snaps


def deltas_squadratinhos(snaps):
    """[{"atleta", "inicio", "fim", "ganho"}, ...] -- ganho de squadratinhos
    por atleta entre cada par de snapshots consecutivos, só onde ganho > 0.
    A maioria dos pares dá ganho 0 (6 corridas/dia, poucas com sincronização
    nova) e fica de fora, por construção."""
    janelas = []
    for (t0, d0), (t1, d1) in zip(snaps, snaps[1:]):
        antes, depois = d0.get("atletas", {}), d1.get("atletas", {})
        for nome, info in depois.items():
            total_novo = info.get("squadratinhos", 0)
            total_velho = (antes.get(nome) or {}).get("squadratinhos", 0)
            ganho = total_novo - total_velho
            if ganho > 0:
                janelas.append({"atleta": nome, "inicio": t0, "fim": t1, "ganho": ganho})
    return janelas


def _intervalo_atividade(a):
    inicio = _iso(a["inicio"])
    return inicio, inicio + timedelta(seconds=a.get("duracao_s") or 0)


def _sobreposicao_s(a_inicio, a_fim, j_inicio, j_fim):
    inicio, fim = max(a_inicio, j_inicio), min(a_fim, j_fim)
    return max(0.0, (fim - inicio).total_seconds())


def cruzar(janelas, atividades):
    """Cada janela ganha "atividades" (lista, 0+) e "repartido" (bool). Ver
    docstring do módulo para a regra. `atividades` = linhas de
    activities.json (id/atleta/tipo/inicio/duracao_s/dist_km/ritmo)."""
    por_atleta = {}
    for a in atividades:
        por_atleta.setdefault(a["atleta"], []).append(a)

    resultado = []
    for j in janelas:
        candidatas = []
        for a in por_atleta.get(j["atleta"], []):
            a_inicio, a_fim = _intervalo_atividade(a)
            sobre = _sobreposicao_s(a_inicio, a_fim, j["inicio"], j["fim"])
            if sobre > 0:
                candidatas.append((a, sobre))

        repartido = len(candidatas) > 1
        lista = []
        if len(candidatas) == 1:
            a, _ = candidatas[0]
            lista.append({"id": a["id"], "tipo": a.get("tipo", ""),
                          "dist_km": a.get("dist_km"), "ganho": j["ganho"]})
        elif candidatas:
            soma = sum(s for _, s in candidatas) or 1.0
            restante = j["ganho"]
            for i, (a, s) in enumerate(candidatas):
                # a última fica com o resto, para a soma bater certo com
                # j["ganho"] apesar do arredondamento das anteriores
                fatia = round(j["ganho"] * s / soma) if i < len(candidatas) - 1 else restante
                restante -= fatia
                lista.append({"id": a["id"], "tipo": a.get("tipo", ""),
                              "dist_km": a.get("dist_km"), "ganho": fatia})

        resultado.append({
            "atleta": j["atleta"], "inicio": _fmt(j["inicio"]), "fim": _fmt(j["fim"]),
            "ganho": j["ganho"], "repartido": repartido, "atividades": lista,
        })
    return resultado
