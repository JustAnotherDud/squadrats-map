"""Testes de atividades.py: deltas entre snapshots e o cruzamento com o
feed de actividades. snapshots_todos (git log/show) fica de fora, é
canalização fina sobre o mesmo padrão já provado em eventos.snapshots_por_dia.

Correr: py -m pytest
"""
from datetime import datetime, timedelta, timezone

from atividades import cruzar, deltas_squadratinhos


def _dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _snap(ts, **atletas):
    return (_dt(ts), {"atualizado": ts, "atletas": {n: {"squadratinhos": v} for n, v in atletas.items()}})


def _atividade(id_, atleta, inicio, duracao_s, tipo="Run", dist_km=10.0):
    return {"id": id_, "atleta": atleta, "tipo": tipo, "inicio": inicio,
            "duracao_s": duracao_s, "dist_km": dist_km, "ritmo": "5:00 /km"}


# --- deltas_squadratinhos ---

def test_ganho_positivo_vira_janela():
    snaps = [_snap("2026-09-10T08:00:00", Ze=100), _snap("2026-09-10T12:00:00", Ze=142)]
    janelas = deltas_squadratinhos(snaps)
    assert len(janelas) == 1
    assert janelas[0] == {"atleta": "Ze", "inicio": _dt("2026-09-10T08:00:00"),
                          "fim": _dt("2026-09-10T12:00:00"), "ganho": 42}


def test_sem_ganho_nao_gera_janela():
    snaps = [_snap("2026-09-10T08:00:00", Ze=100), _snap("2026-09-10T12:00:00", Ze=100)]
    assert deltas_squadratinhos(snaps) == []


def test_atleta_novo_no_snapshot_nao_rebenta():
    # Carolina não existia no snapshot anterior: total_velho = 0, ganho = total novo
    snaps = [_snap("2026-09-10T08:00:00"), _snap("2026-09-10T12:00:00", Carolina=5)]
    janelas = deltas_squadratinhos(snaps)
    assert janelas == [{"atleta": "Carolina", "inicio": _dt("2026-09-10T08:00:00"),
                        "fim": _dt("2026-09-10T12:00:00"), "ganho": 5}]


def test_varios_pares_consecutivos():
    snaps = [_snap("2026-09-10T00:00:00", Ze=100), _snap("2026-09-10T08:00:00", Ze=100),
             _snap("2026-09-10T16:00:00", Ze=130)]
    janelas = deltas_squadratinhos(snaps)
    assert len(janelas) == 1  # o par sem ganho fica de fora
    assert janelas[0]["inicio"] == _dt("2026-09-10T08:00:00")
    assert janelas[0]["ganho"] == 30


# --- cruzar ---

def test_sem_atividade_correspondente():
    janelas = [{"atleta": "Pedro", "inicio": _dt("2026-09-10T08:00:00"),
               "fim": _dt("2026-09-10T12:00:00"), "ganho": 4}]
    r = cruzar(janelas, [])
    assert r[0]["atividades"] == [] and r[0]["repartido"] is False and r[0]["ganho"] == 4


def test_uma_atividade_fica_com_o_ganho_todo():
    janelas = [{"atleta": "Xeira", "inicio": _dt("2026-09-10T08:00:00"),
               "fim": _dt("2026-09-10T12:00:00"), "ganho": 42}]
    ativ = [_atividade("A1", "Xeira", "2026-09-10T09:00:00Z", 3600)]  # 09:00-10:00, dentro da janela
    r = cruzar(janelas, ativ)
    assert r[0]["repartido"] is False
    assert r[0]["atividades"] == [{"id": "A1", "tipo": "Run", "dist_km": 10.0, "ganho": 42}]


def test_duas_atividades_repartem_proporcional_a_sobreposicao():
    # janela 08:00-12:00 (4h = 14400s). A1 cobre 08:00-10:00 (2h dentro),
    # A2 cobre 11:00-13:00 (1h dentro) -> repartição 2:1
    janelas = [{"atleta": "Zé", "inicio": _dt("2026-09-10T08:00:00"),
               "fim": _dt("2026-09-10T12:00:00"), "ganho": 30}]
    ativ = [
        _atividade("A1", "Zé", "2026-09-10T08:00:00Z", 7200),
        _atividade("A2", "Zé", "2026-09-10T11:00:00Z", 7200),
    ]
    r = cruzar(janelas, ativ)
    assert r[0]["repartido"] is True
    ganhos = {a["id"]: a["ganho"] for a in r[0]["atividades"]}
    assert ganhos == {"A1": 20, "A2": 10}
    assert sum(ganhos.values()) == 30  # a soma bate sempre, sem perdas de arredondamento


def test_atividade_de_outro_atleta_nao_conta():
    janelas = [{"atleta": "Inês S.", "inicio": _dt("2026-09-10T08:00:00"),
               "fim": _dt("2026-09-10T12:00:00"), "ganho": 4}]
    ativ = [_atividade("A1", "Pedro", "2026-09-10T09:00:00Z", 3600)]
    r = cruzar(janelas, ativ)
    assert r[0]["atividades"] == []


def test_atividade_fora_da_janela_nao_conta():
    janelas = [{"atleta": "Pedro", "inicio": _dt("2026-09-10T08:00:00"),
               "fim": _dt("2026-09-10T12:00:00"), "ganho": 4}]
    ativ = [_atividade("A1", "Pedro", "2026-09-10T20:00:00Z", 1800)]  # às 20h, fora
    r = cruzar(janelas, ativ)
    assert r[0]["atividades"] == []
