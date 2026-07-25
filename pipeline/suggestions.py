"""Sugestões de progresso (o que falta para o próximo übersquadrat) + o guard
que garante que sabemos reproduzir as regras da Squadrats antes de as usar
para sugerir seja o que for.

Validado em pipeline/spikes/reproduzir_regras.py contra o `size` real do
servidor (yard/übersquadrat batem exatamente, para squadrats e squadratinhos).
"""
from collections import deque

VIZINHOS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def clusters_fechados(visitados):
    """Squares fechados (visitados com os 4 vizinhos cardinais também
    visitados), agrupados em componentes 4-conexas."""
    fechados = {
        s for s in visitados
        if all((s[0] + dx, s[1] + dy) in visitados for dx, dy in VIZINHOS4)
    }
    porver, clusters = set(fechados), []
    while porver:
        raiz = porver.pop()
        comp, fila = {raiz}, deque([raiz])
        while fila:
            x, y = fila.popleft()
            for dx, dy in VIZINHOS4:
                v = (x + dx, y + dy)
                if v in porver:
                    porver.remove(v)
                    comp.add(v)
                    fila.append(v)
        clusters.append(comp)
    return clusters


def maior_uber(visitados):
    """DP clássico do "maior quadrado cheio": dp[x,y] = lado do maior
    quadrado com canto inferior-direito em (x,y)."""
    dp, melhor, canto = {}, 0, None
    for (x, y) in sorted(visitados):
        v = 1 + min(dp.get((x - 1, y), 0), dp.get((x, y - 1), 0), dp.get((x - 1, y - 1), 0))
        dp[(x, y)] = v
        if v > melhor:
            melhor, canto = v, (x, y)
    return melhor, canto


def verify_rules(visitados, esperado_yard, esperado_uber, label):
    """O guard: se isto falhar, não sabemos reproduzir as regras da Squadrats
    — não publicar sugestões inventadas com ar de rigor. Falhar alto."""
    clusters = clusters_fechados(visitados)
    maior_yard = max((len(c) for c in clusters), default=0)
    uber, _ = maior_uber(visitados)
    if maior_yard != esperado_yard or uber != esperado_uber:
        raise RuntimeError(
            f"suggestions.py: não reproduzimos as regras da Squadrats para '{label}' — "
            f"yard calculado={maior_yard} (servidor diz {esperado_yard}), "
            f"übersquadrat calculado={uber} (servidor diz {esperado_uber}). "
            f"A abortar sem publicar sugestões (seriam inventadas)."
        )


def proximo_ubersquadrat(visitados, n_atual, margem=2):
    """Para o alvo N = n_atual+1, encontra a janela NxN com menos squares em
    falta. Prefix-sum sobre a bbox dos visitados (+ margem) para não ter de
    testar janela a janela em O(N²)."""
    n = n_atual + 1
    xs = [x for x, y in visitados]
    ys = [y for x, y in visitados]
    x0, x1 = min(xs) - margem, max(xs) + margem
    y0, y1 = min(ys) - margem, max(ys) + margem
    w, h = x1 - x0 + 2, y1 - y0 + 2  # +1 p/ prefix sum, +1 p/ folga

    grid = [[0] * w for _ in range(h)]
    for x, y in visitados:
        if x0 <= x <= x1 and y0 <= y <= y1:
            grid[y - y0 + 1][x - x0 + 1] = 1

    prefix = [[0] * w for _ in range(h)]
    for yy in range(1, h):
        for xx in range(1, w):
            prefix[yy][xx] = (grid[yy][xx] + prefix[yy - 1][xx]
                               + prefix[yy][xx - 1] - prefix[yy - 1][xx - 1])

    def soma(x_ini, y_ini, tam):
        x_fim, y_fim = x_ini + tam, y_ini + tam
        if x_fim >= w or y_fim >= h:
            return -1  # fora da grelha (prefix não cobre) — ignorar
        return (prefix[y_fim][x_fim] - prefix[y_ini][x_fim]
                - prefix[y_fim][x_ini] + prefix[y_ini][x_ini])

    melhor_falta, melhor_janela = n * n + 1, None
    for yy in range(0, h - n):
        for xx in range(0, w - n):
            capturados = soma(xx, yy, n)
            if capturados < 0:
                continue
            falta = n * n - capturados
            if 0 < falta < melhor_falta:
                melhor_falta = falta
                melhor_janela = (xx, yy)

    if melhor_janela is None:
        return None

    xx, yy = melhor_janela
    x_ini, y_ini = xx + x0, yy + y0
    faltam = [
        (x_ini + dx, y_ini + dy)
        for dx in range(n) for dy in range(n)
        if (x_ini + dx, y_ini + dy) not in visitados
    ]
    return {"n_alvo": n, "faltam": melhor_falta, "squares_em_falta": faltam,
            "canto": (x_ini, y_ini)}
