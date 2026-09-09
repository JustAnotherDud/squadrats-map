"""Detecção de eventos do clube a partir de snapshots de club_regioes.json.

Um "evento" é uma mudança digna de nota no ranking por região (concelho ou
distrito, só PT, ver squadrats-historico-plano abaixo). Consumido por:
  - backfill_events.py (varre todo o histórico da branch `data`, uma vez)
  - append_events.py (passo do run_all.py, compara só anterior vs actual)

Ambos produzem exactamente os mesmos eventos para o mesmo par de snapshots,
e a CHAVE de cada evento (`chave`) é por DIA, não por timestamp, os 6 runs/
dia re-detectam o mesmo flip e o append é idempotente (ver README).

Níveis: só `concelho` e `distrito`, só PT. Região/município estrangeiros e
país: zero eventos em toda a história (2026-08-15+), ficam de fora do v1.

Tipos:
  - ultrapassagem      X passou Y (X agora acima de Y; antes Y acima, ou X ausente)
  - novo_lider         mudou o 1º da região (e havia 1º antes), absorve o par
                       (novo_lider, ex_lider), esse não sai também como ultrapassagem
  - primeira_presenca  X capturou o 1º squadratinho numa região que JÁ tinha
                       outro atleta (juntou-se a um board existente)
  - marco              X cruzou um patamar de squadratinhos (só para cima)
"""

# patamares por nível, escolhidos contra o histórico real (ver plano):
# concelho arranca em 25 (~1 km² coberto, "andou lá a sério"), distrito mais
# alto porque acumula naturalmente mais. Só cruzados para cima.
# Backfill (26 jul+): ~28 marcos. Projecção futura ~3-6/semana no total.
MARCOS = {
    "concelho": [25, 50, 100, 250, 500, 1000],
    "distrito": [50, 100, 250, 500, 1000, 2500],
}

ATLETAS_ORDEM = ["Zé", "Xeira", "Carolina", "Inês S.", "Pedro"]

DESDE = "2026-07-26"  # 1.º dia com club.json (o histórico < 15 ago é
                      # reconstruído do club.json, ver recon_snapshots.py)


def snapshots_por_dia(repo, branch="origin/data", desde=None):
    """(por_dia, saltados).

    `por_dia` = {data_utc: club_regioes_dict}, o ÚLTIMO snapshot commitado de
    cada dia UTC na branch dada. Mesma regra que o backfill_daily_gains.py.

    `saltados` = [(sha, motivo), ...] dos commits que o `git log` listou mas
    que não deu para ler (blob em falta num checkout shallow, ou JSON/formato
    inesperado). Vazio no caminho feliz. Quem chama decide o que fazer com
    ele; um commit saltado no meio do histórico faz um dia colapsar no
    anterior, por isso não deve passar despercebido.

    Levanta RuntimeError se o `git log` listou commits e NENHUM deu para ler
    (histórico presente na branch mas inacessível no clone — quase sempre um
    `git fetch --depth` curto demais). Um clone sem qualquer commit do
    ficheiro devolve ({}, []) sem erro: é o primeiro run, não uma anomalia.

    `desde` (YYYY-MM-DD) limita a leitura aos commits desse dia em diante, o
    passo incremental passa aqui o último dia já coberto para não ler o
    histórico todo a cada run.
    """
    import subprocess
    from datetime import datetime

    args = ["git", "-C", repo, "log", branch, "--format=%H"]
    if desde:
        args += [f"--since={desde}T00:00:00Z"]
    args += ["--", "data/club_regioes.json"]
    shas = subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.split()

    por_dia, ts_por_dia, saltados = {}, {}, []
    for sha in shas:
        r = subprocess.run(
            ["git", "-C", repo, "show", f"{sha}:data/club_regioes.json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode != 0:
            err = " ".join((r.stderr or "").split())[:120]
            hint = "blob em falta (checkout shallow?)" if not err else f"git show falhou: {err}"
            saltados.append((sha, hint))
            continue
        try:
            d = __import__("json").loads(r.stdout)
            ts = datetime.fromisoformat(d["atualizado"].replace("Z", "+00:00"))
        except Exception as e:
            saltados.append((sha, f"club_regioes.json inesperado: {type(e).__name__}: {e}"))
            continue
        dia = ts.date().isoformat()
        if dia not in ts_por_dia or ts > ts_por_dia[dia]:
            por_dia[dia] = d
            ts_por_dia[dia] = ts

    if saltados:
        from collections import Counter
        resumo = Counter(m for _, m in saltados)
        print(f"snapshots_por_dia: {len(saltados)}/{len(shas)} commit(s) saltado(s) — "
              + "; ".join(f"{n}x {m}" for m, n in resumo.most_common()))

    if shas and not por_dia:
        raise RuntimeError(
            f"snapshots_por_dia: {len(shas)} commit(s) de data/club_regioes.json em "
            f"{branch}, nenhum legível. Clone shallow demais? "
            "(o workflow faz `git fetch origin data --depth=500`)."
        )
    return por_dia, saltados


def _idx(nome):
    return ATLETAS_ORDEM.index(nome) if nome in ATLETAS_ORDEM else 99


def niveis_de(club_regioes):
    """{(nivel, regiao): {atleta: captured}} para concelho e distrito (PT)."""
    out = {}
    for nome, info in club_regioes.get("atletas", {}).items():
        for reg, n in (info.get("by_concelho") or {}).items():
            out.setdefault(("concelho", reg), {})[nome] = n
        for reg, n in (info.get("by_distrito") or {}).items():
            out.setdefault(("distrito", reg), {})[nome] = n
    return out


def ranking(counts):
    """Lista de atletas com captured > 0, do maior para o menor.
    Empate desempata pela ordem canónica (mesma do bitmask/cores)."""
    presentes = [(n, c) for n, c in counts.items() if c > 0]
    presentes.sort(key=lambda t: (-t[1], _idx(t[0])))
    return [n for n, _ in presentes]


def _marco_cruzado(nivel, antes, agora):
    """O patamar MAIS ALTO cruzado entre `antes` e `agora` (None se nenhum).
    Num sync grande (20 -> 55) cruzam-se 25 e 50 de uma vez, mas o 50 já
    implica o 25, o evento pequeno é redundante no feed."""
    cruzados = [T for T in MARCOS.get(nivel, []) if antes < T <= agora]
    return max(cruzados) if cruzados else None


def detectar(anterior, atual, data):
    """Eventos ao passar de `anterior` -> `atual` (dois club_regioes.json).
    `data` é a data (YYYY-MM-DD, UTC) a que o evento fica atribuído.

    Devolve lista de dicts: {data, nivel, cc, regiao, tipo, quem, sobre, valores}.
    `sobre` = quem foi passado / ex-líder (None quando não se aplica).
    `valores` = [quem, sobre] na ultrapassagem; [patamar, contagem] no marco;
                [contagem] nos restantes.
    """
    eventos = []
    na, nb = niveis_de(anterior), niveis_de(atual)

    # Atleta que entra no roster (ATHLETES_JSON) não gera eventos no 1.º
    # snapshot em que aparece, senão "passava" toda a gente em todas as
    # regiões onde tem squares, num dia só. Mesmo critério do daily_gains.py.
    # (Aconteceu no backfill quando o Pedro entrou a 1 ago: 54 eventos falsos.)
    estreantes = (set((atual or {}).get("atletas", {}))
                  - set((anterior or {}).get("atletas", {})))

    for chave, cb in nb.items():
        nivel, reg = chave
        ca = na.get(chave, {})
        ra = ranking(ca)
        rb = ranking(cb)

        # --- marcos (independentes do ranking), só o patamar mais alto/dia ---
        for atl, agora in cb.items():
            T = _marco_cruzado(nivel, ca.get(atl, 0), agora)
            if T is not None:
                eventos.append(_ev(data, nivel, reg, "marco", atl, None, [T, agora]))

        if ra == rb:
            continue

        pos_a = {n: i for i, n in enumerate(ra)}
        pos_b = {n: i for i, n in enumerate(rb)}

        # --- novo líder (havia líder antes e mudou) ---
        par_lideranca = None
        if ra and rb and ra[0] != rb[0]:
            novo, ex = rb[0], ra[0]
            par_lideranca = (novo, ex)
            eventos.append(_ev(data, nivel, reg, "novo_lider", novo, ex,
                               [cb.get(novo, 0), cb.get(ex, 0)]))

        # --- ultrapassagens (pares que trocaram), menos o par da liderança ---
        for x in rb:
            for y in rb:
                if pos_b[x] >= pos_b[y]:
                    continue
                if par_lideranca == (x, y):
                    continue  # já saiu como novo_lider
                era_abaixo = (x not in pos_a) or (y in pos_a and pos_a[x] > pos_a[y])
                if era_abaixo:
                    eventos.append(_ev(data, nivel, reg, "ultrapassagem", x, y,
                                       [cb.get(x, 0), cb.get(y, 0)]))

        # --- primeira presença (região que já tinha outro atleta) ---
        for n in rb:
            if ca.get(n, 0) == 0 and len(ra) >= 1:
                eventos.append(_ev(data, nivel, reg, "primeira_presenca", n, None,
                                   [cb.get(n, 0)]))

    # "capturou o 1º square" é implícito quando o mesmo atleta, na mesma
    # região e dia, já assumiu a liderança ou passou alguém, tira-se para o
    # feed não repetir o mesmo movimento com duas frases.
    fortes = {
        (e["quem"], e["nivel"], e["regiao"])
        for e in eventos if e["tipo"] in ("novo_lider", "ultrapassagem")
    }
    return [
        e for e in eventos
        if e["quem"] not in estreantes
        and not (e["tipo"] == "primeira_presenca"
                 and (e["quem"], e["nivel"], e["regiao"]) in fortes)
    ]


def _ev(data, nivel, reg, tipo, quem, sobre, valores):
    return {
        "data": data,
        "nivel": nivel,
        "cc": "PT",
        "regiao": reg,
        "tipo": tipo,
        "quem": quem,
        "sobre": sobre,
        "valores": valores,
    }


def chave(ev):
    """Identidade por DIA, o que torna o append idempotente entre os 6 runs
    do mesmo dia. Um marco inclui o patamar; os outros o par de atletas."""
    extra = ev["valores"][0] if ev["tipo"] == "marco" else (ev.get("sobre") or "")
    return (ev["data"], ev["nivel"], ev["regiao"], ev["tipo"], ev["quem"], str(extra))


# ordem de leitura dentro de um dia: primeiro os movimentos de ranking, depois
# a estreia, e o marco no fim (é o "e ainda"). O feed é mais-recente-primeiro
# por dia; dentro do dia segue esta ordem, agrupado por região.
ORDEM_TIPO = {"novo_lider": 0, "ultrapassagem": 1, "primeira_presenca": 2, "marco": 3}


def ordenar_feed(evs):
    """Ordena para o feed: dia desc, depois nivel, região, tipo (ver ORDEM_TIPO)."""
    return sorted(evs, key=lambda e: (
        e["data"], e["nivel"], e["regiao"], ORDEM_TIPO.get(e["tipo"], 9),
        str(e.get("sobre") or ""),
    ))


def colapsar_marcos(evs):
    """Por (data, nivel, regiao, quem) mantém só o marco de patamar mais alto.
    Um sync grande pode gerar 25 e 50 de uma vez, ou runs sucessivos do mesmo
    dia tê-los acrescentado em separado, o 50 já implica o 25."""
    melhor = {}
    for i, e in enumerate(evs):
        if e["tipo"] != "marco":
            continue
        k = (e["data"], e["nivel"], e["regiao"], e["quem"])
        if k not in melhor or e["valores"][0] > evs[melhor[k]]["valores"][0]:
            melhor[k] = i
    manter = set(melhor.values())
    return [e for i, e in enumerate(evs) if e["tipo"] != "marco" or i in manter]
