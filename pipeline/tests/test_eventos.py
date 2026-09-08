"""Testes do eventos.detectar — sobretudo a guarda de estreia de atleta.

O append (run_all.py) nunca exercita essa guarda hoje: os 5 atletas já estão
todos no roster. Só o backfill a exercitou (quando o Pedro entrou a 1 ago
gerava 54 eventos falsos). Estes testes garantem que a guarda não apodrece
até alguém acrescentar um atleta ao ATHLETES_JSON.

Correr: py -m pytest
"""
import eventos


def _snap(atletas):
    """atletas: {nome: {concelho: {reg: n}, distrito: {reg: n}}} -> club_regioes-shaped."""
    return {"atletas": {
        nome: {"by_concelho": v.get("concelho", {}), "by_distrito": v.get("distrito", {})}
        for nome, v in atletas.items()
    }}


def _tipos(evs, quem=None):
    return sorted(e["tipo"] for e in evs if quem is None or e["quem"] == quem)


# --- guarda de estreia -------------------------------------------------------

def test_estreante_nao_gera_eventos():
    """Atleta novo aparece com squares em várias regiões: zero eventos para ele."""
    ant = _snap({
        "Zé":    {"concelho": {"Rio Maior": 40}, "distrito": {"Santarém": 40}},
        "Xeira": {"concelho": {"Rio Maior": 10}, "distrito": {"Santarém": 10}},
    })
    novo = _snap({
        "Zé":    {"concelho": {"Rio Maior": 40}, "distrito": {"Santarém": 40}},
        "Xeira": {"concelho": {"Rio Maior": 10}, "distrito": {"Santarém": 10}},
        "Pedro": {"concelho": {"Rio Maior": 99, "Peniche": 30},
                  "distrito": {"Santarém": 99, "Leiria": 30}},
    })
    evs = eventos.detectar(ant, novo, "2026-08-01")
    assert _tipos(evs, "Pedro") == []
    assert all(e["quem"] != "Pedro" and e["sobre"] != "Pedro" for e in evs)


def test_estreante_nao_e_passado_por_estabelecido():
    """Um atleta estabelecido não 'ultrapassa' quem acabou de aparecer abaixo dele."""
    ant = _snap({"Zé": {"concelho": {"Rio Maior": 40}}})
    novo = _snap({
        "Zé":    {"concelho": {"Rio Maior": 41}},
        "Pedro": {"concelho": {"Rio Maior": 5}},
    })
    evs = eventos.detectar(ant, novo, "2026-08-01")
    assert "ultrapassagem" not in _tipos(evs)


def test_marco_de_estabelecido_sobrevive_a_estreia_de_outro():
    """A guarda só apanha o estreante — o marco genuíno de outro atleta fica."""
    ant = _snap({"Zé": {"concelho": {"Rio Maior": 40}, "distrito": {"Santarém": 40}}})
    novo = _snap({
        "Zé":    {"concelho": {"Rio Maior": 55}, "distrito": {"Santarém": 55}},
        "Pedro": {"concelho": {"Rio Maior": 99}, "distrito": {"Santarém": 99}},
    })
    evs = eventos.detectar(ant, novo, "2026-08-01")
    marcos_ze = [e for e in evs if e["tipo"] == "marco" and e["quem"] == "Zé"]
    assert {e["valores"][0] for e in marcos_ze} == {50}  # cruzou 50 (25 já era antes)
    assert _tipos(evs, "Pedro") == []


# --- comportamento base (rede de regressão) --------------------------------

def test_ultrapassagem_entre_estabelecidos():
    ant = _snap({"Zé": {"concelho": {"Óbidos": 8}}, "Carolina": {"concelho": {"Óbidos": 5}}})
    novo = _snap({"Zé": {"concelho": {"Óbidos": 8}}, "Carolina": {"concelho": {"Óbidos": 12}}})
    evs = eventos.detectar(ant, novo, "2026-09-05")
    # Carolina passou o Zé no topo -> conta como novo_lider, não ultrapassagem
    assert _tipos(evs) == ["novo_lider"]
    e = evs[0]
    assert e["quem"] == "Carolina" and e["sobre"] == "Zé"


def test_ultrapassagem_fora_do_topo():
    ant = _snap({
        "Zé":    {"distrito": {"Leiria": 100}},
        "Xeira": {"distrito": {"Leiria": 20}},
        "Pedro": {"distrito": {"Leiria": 15}},
    })
    novo = _snap({
        "Zé":    {"distrito": {"Leiria": 100}},
        "Xeira": {"distrito": {"Leiria": 20}},
        "Pedro": {"distrito": {"Leiria": 25}},
    })
    evs = eventos.detectar(ant, novo, "2026-09-05")
    assert _tipos(evs) == ["ultrapassagem"]
    assert evs[0]["quem"] == "Pedro" and evs[0]["sobre"] == "Xeira"


def test_ordem_igual_nao_gera_ultrapassagem():
    ant = _snap({"Zé": {"concelho": {"Arouca": 10}}, "Pedro": {"concelho": {"Arouca": 5}}})
    novo = _snap({"Zé": {"concelho": {"Arouca": 20}}, "Pedro": {"concelho": {"Arouca": 8}}})
    evs = eventos.detectar(ant, novo, "2026-09-06")
    assert "ultrapassagem" not in _tipos(evs)
    assert "novo_lider" not in _tipos(evs)


def test_primeira_presenca_suprimida_quando_ha_movimento_forte():
    """Quem chega a uma região nova E passa alguém no mesmo dia não sai com
    duas frases — fica só a ultrapassagem/novo_lider. (Zé já está no roster,
    com actividade noutra região — não é estreante.)"""
    ant = _snap({
        "Xeira": {"concelho": {"Espinho": 30}},
        "Zé":    {"concelho": {"Porto": 5}},
    })
    novo = _snap({
        "Xeira": {"concelho": {"Espinho": 30}},
        "Zé":    {"concelho": {"Espinho": 40, "Porto": 5}},
    })
    evs = eventos.detectar(ant, novo, "2026-09-04")
    tipos = _tipos(evs, "Zé")
    assert "novo_lider" in tipos
    assert "primeira_presenca" not in tipos  # não repete o mesmo movimento
