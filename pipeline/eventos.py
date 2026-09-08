"""Detecção de eventos do clube a partir de snapshots de club_regioes.json.

Um "evento" é uma mudança digna de nota no ranking por região (concelho ou
distrito, só PT — ver squadrats-historico-plano abaixo). Consumido por:
  - backfill_events.py (varre todo o histórico da branch `data`, uma vez)
  - append_events.py (passo do run_all.py, compara só anterior vs actual)

Ambos produzem exactamente os mesmos eventos para o mesmo par de snapshots,
e a CHAVE de cada evento (`chave`) é por DIA, não por timestamp — os 6 runs/
dia re-detectam o mesmo flip e o append é idempotente (ver README).

Níveis: só `concelho` e `distrito`, só PT. Região/município estrangeiros e
país: zero eventos em toda a história (2026-08-15+), ficam de fora do v1.

Tipos:
  - ultrapassagem      X passou Y (X agora acima de Y; antes Y acima, ou X ausente)
  - novo_lider         mudou o 1º da região (e havia 1º antes) — absorve o par
                       (novo_lider, ex_lider), esse não sai também como ultrapassagem
  - primeira_presenca  X capturou o 1º squadratinho numa região que JÁ tinha
                       outro atleta (juntou-se a um board existente)
  - marco              X cruzou um patamar de squadratinhos (só para cima)
"""

# patamares por nível — escolhidos contra o histórico real (ver plano):
# concelho arranca em 25 (~1 km² coberto, "andou lá a sério"), distrito mais
# alto porque acumula naturalmente mais. Só cruzados para cima.
# Backfill (26 jul+): ~28 marcos. Projecção futura ~3-6/semana no total.
MARCOS = {
    "concelho": [25, 50, 100, 250, 500, 1000],
    "distrito": [50, 100, 250, 500, 1000, 2500],
}

ATLETAS_ORDEM = ["Zé", "Xeira", "Carolina", "Inês S.", "Pedro"]

DESDE = "2026-07-26"  # 1.º dia com club.json (o histórico < 15 ago é
                      # reconstruído do club.json — ver recon_snapshots.py)


def snapshots_por_dia(repo, branch="origin/data", desde=None):
    """{data_utc: club_regioes_dict} — o ÚLTIMO snapshot commitado de cada dia
    UTC na branch dada. Mesma regra que o backfill_daily_gains.py.

    `desde` (YYYY-MM-DD) limita a leitura aos commits desse dia em diante — o
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

    por_dia, ts_por_dia = {}, {}
    for sha in shas:
        try:
            raw = subprocess.run(
                ["git", "-C", repo, "show", f"{sha}:data/club_regioes.json"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            ).stdout
            d = __import__("json").loads(raw)
        except Exception:
            continue
        ts = datetime.fromisoformat(d["atualizado"].replace("Z", "+00:00"))
        dia = ts.date().isoformat()
        if dia not in ts_por_dia or ts > ts_por_dia[dia]:
            por_dia[dia] = d
            ts_por_dia[dia] = ts
    return por_dia


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


def _marcos_cruzados(nivel, antes, agora):
    return [T for T in MARCOS.get(nivel, []) if antes < T <= agora]


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
    # snapshot em que aparece — senão "passava" toda a gente em todas as
    # regiões onde tem squares, num dia só. Mesmo critério do daily_gains.py.
    # (Aconteceu no backfill quando o Pedro entrou a 1 ago: 54 eventos falsos.)
    estreantes = (set((atual or {}).get("atletas", {}))
                  - set((anterior or {}).get("atletas", {})))

    for chave, cb in nb.items():
        nivel, reg = chave
        ca = na.get(chave, {})
        ra = ranking(ca)
        rb = ranking(cb)

        # --- marcos (independentes do ranking) ---
        for atl, agora in cb.items():
            for T in _marcos_cruzados(nivel, ca.get(atl, 0), agora):
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
    # região e dia, já assumiu a liderança ou passou alguém — tira-se para o
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
    """Identidade por DIA — o que torna o append idempotente entre os 6 runs
    do mesmo dia. Um marco inclui o patamar; os outros o par de atletas."""
    extra = ev["valores"][0] if ev["tipo"] == "marco" else (ev.get("sobre") or "")
    return (ev["data"], ev["nivel"], ev["regiao"], ev["tipo"], ev["quem"], str(extra))
