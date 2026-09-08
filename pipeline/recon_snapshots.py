"""Snapshots de club_regioes.json estendidos para trás de 2026-08-15.

O club_regioes.json só passou a ser gerado a 15 ago. Antes disso, o breakdown
por concelho/distrito de cada dia reconstrói-se do histórico de club.json
(que vai até 26 jul) + o Classifier de sempre, com uma cache (x,y)->(concelho,
distrito) para não reclassificar o mesmo square em 44 snapshots.

Consumido pelos one-offs `backfill_events.py` e `backfill_regioes.py` — em vez
de `eventos.snapshots_por_dia` sozinho — para que eventos e timelines das
regiões arranquem em 26 jul, não em 15 ago. O `backfill_gains_regioes.py`
reutiliza daqui `snapshots_club_por_dia`/`reconstruir` (reconstrói tudo, não
mistura com o real).

Os passos incrementais (append_*) NÃO usam isto — só olham para o presente.
"""
import json
import os
import subprocess
from datetime import datetime

import eventos
from classify import Classifier
from kml_parse import tile_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REFDATA = os.path.join(HERE, "refdata")
ZOOM = 17
CORTE = "2026-08-15"  # a partir daqui há club_regioes.json real


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def snapshots_club_por_dia(repo, branch):
    """{data_utc: club_dict} — o último club.json commitado de cada dia UTC,
    pela data do campo `atualizado` (mesma regra do backfill_daily_gains.py)."""
    shas = _git(repo, "log", branch, "--format=%H", "--", "data/club.json").split()
    por_dia, ts_por_dia = {}, {}
    for sha in shas:
        try:
            d = json.loads(_git(repo, "show", f"{sha}:data/club.json"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        raw = d.get("atualizado")
        if not raw:
            continue
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dia = ts.date().isoformat()
        if dia not in ts_por_dia or ts > ts_por_dia[dia]:
            por_dia[dia], ts_por_dia[dia] = d, ts
    return por_dia


def criar_classifier():
    return Classifier(
        os.path.join(REFDATA, "distritos_pt.geojson"),
        os.path.join(REFDATA, "concelhos_pt.geojson"),
        foreign_dir=os.path.join(REFDATA, "foreign"),
        foreign_muni_dir=os.path.join(REFDATA, "foreign_muni"),
    )


def reconstruir(club, classifier, cache):
    """club.json -> formato club_regioes ({"atletas": {nome: {by_concelho,
    by_distrito, by_pais}}}), classificando cada square (com cache).
    `by_pais` só o estrangeiro — usado pelo backfill_gains_regioes para dar
    nome ao resíduo; ignorado por eventos/regioes."""
    atletas = club["atletas"]
    out = {a["nome"]: {"by_concelho": {}, "by_distrito": {}, "by_pais": {}}
           for a in atletas}
    for x, y, mask in club["squares"]:
        cd = cache.get((x, y))
        if cd is None:
            info = classifier.classify(tile_bounds(x, y, ZOOM))
            cd = ((info["concelho"], info["district"], None) if info["in_portugal"]
                  else (None, None, info["country"]))
            cache[(x, y)] = cd
        conc, dist, pais = cd
        if not conc and not dist and not pais:
            continue
        for i, a in enumerate(atletas):
            if mask & (1 << i):
                reg = out[a["nome"]]
                if conc:
                    reg["by_concelho"][conc] = reg["by_concelho"].get(conc, 0) + 1
                if dist:
                    reg["by_distrito"][dist] = reg["by_distrito"].get(dist, 0) + 1
                if pais and pais != "PT":
                    reg["by_pais"][pais] = reg["by_pais"].get(pais, 0) + 1
    return {"atletas": out}


def snapshots_estendidos(repo=REPO, branch="origin/data", desde=None):
    """{data_utc: club_regioes-shaped} de `desde` (default eventos.DESDE) até
    hoje: dias < 15 ago reconstruídos do club.json, dias >= 15 ago do
    club_regioes.json real. A comparação de fronteira (14 ago reconstruído vs
    15 ago real) recupera eventos que o backfill original perdia por não ter
    nada antes de 15 ago."""
    desde = desde or eventos.DESDE
    reais = eventos.snapshots_por_dia(repo, branch, desde=max(desde, CORTE))

    fora = dict(reais)
    if desde < CORTE:
        club_por_dia = snapshots_club_por_dia(repo, branch)
        dias_recon = sorted(d for d in club_por_dia if desde <= d < CORTE)
        if dias_recon:
            classifier, cache = criar_classifier(), {}
            for dia in dias_recon:
                fora[dia] = reconstruir(club_por_dia[dia], classifier, cache)
    return fora
