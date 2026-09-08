"""Classificação por concelho/distrito/região dos squares de todos os
atletas do clube, data/club_regioes.json, consumido por club.html para a
vista de detalhe geográfico por atleta (2026-08-15).

Reaproveita data/club.json (já produzido por fetch_club_squares.py na mesma
corrida de run_all.py, sempre corrido antes deste passo) em vez de voltar a
varrer o Squadrats, os squares (x,y) de cada atleta já lá estão, filtrados
pelo bitmask. Só faltava classificar cada um por concelho/país, que é o que
este script faz. Zero pedidos de rede extra.

Escreve dois blocos: "atletas" (captured por região, por atleta) e "uniao"
(squadratinhos que o clube cobre por região, partilhados contados uma vez;
usado como número e ordenação do regioes/index.html via regioes.py). Os
totais (denominador) são os mesmos para toda a gente, já em stats.json (via
grid_totals.json, ver build_mapa.py): o frontend combina os dois.

Uso: py classify_club.py [pasta_saida]
"""
import argparse
import datetime
import json
import os

from athletes import ATLETAS
from classify import Classifier
from kml_parse import tile_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
REFDATA_DIR = os.path.join(HERE, "refdata")

ZOOM = 17  # club.json só tem squadratinhos (ver fetch_club_squares.py)


def classify_uniao(classifier, squares, atletas):
    """União do clube: cada squadratinho de club.json vale 1, sem repetir os
    partilhados (club.json já traz cada (x,y) uma só vez, com o bitmask de
    quem o tem). Ignora mask 0 por segurança, embora fetch_club_squares nunca
    escreva nenhum. É o número que diz "actividade do clube nesta região", ao
    contrário do total da região (só tamanho) ou do capturado pelo líder (um
    atleta só).

    `exclusivos`: por região, quantos squadratinhos cada atleta tem que mais
    nenhum membro do clube tem (bitmask com um único bit). `atletas` = nomes
    por ordem de bit."""
    by_distrito, by_concelho = {}, {}
    exc_distrito, exc_concelho = {}, {}  # nome_regiao -> {atleta: n}
    for x, y, mask in squares:
        if not mask:
            continue
        info = classifier.classify(tile_bounds(x, y, ZOOM))
        if not info["in_portugal"]:
            continue
        d, c = info["district"], info["concelho"]
        if d:
            by_distrito[d] = by_distrito.get(d, 0) + 1
        if c:
            by_concelho[c] = by_concelho.get(c, 0) + 1
        if mask & (mask - 1) == 0:  # potência de 2 -> um só dono
            i = mask.bit_length() - 1
            if 0 <= i < len(atletas):
                nome = atletas[i]
                if d:
                    md = exc_distrito.setdefault(d, {})
                    md[nome] = md.get(nome, 0) + 1
                if c:
                    mc = exc_concelho.setdefault(c, {})
                    mc[nome] = mc.get(nome, 0) + 1
    return {
        "by_distrito": by_distrito, "by_concelho": by_concelho,
        "exclusivos": {"by_distrito": exc_distrito, "by_concelho": exc_concelho},
    }


def classify_athlete(classifier, squares):
    by_distrito, by_concelho = {}, {}
    by_region, by_municipio = {}, {}  # cc minúsculo -> nome -> contagem
    country_totais = {}

    for x, y in squares:
        poly = tile_bounds(x, y, ZOOM)
        info = classifier.classify(poly)
        country = info["country"]
        if country:
            country_totais[country] = country_totais.get(country, 0) + 1

        if info["in_portugal"]:
            if info["district"]:
                by_distrito[info["district"]] = by_distrito.get(info["district"], 0) + 1
            if info["concelho"]:
                by_concelho[info["concelho"]] = by_concelho.get(info["concelho"], 0) + 1
        elif country:
            cc = country.lower()
            if info["region"]:
                by_region.setdefault(cc, {})
                by_region[cc][info["region"]] = by_region[cc].get(info["region"], 0) + 1
            if info["municipio"]:
                by_municipio.setdefault(cc, {})
                by_municipio[cc][info["municipio"]] = by_municipio[cc].get(info["municipio"], 0) + 1

    return {
        "country": country_totais,
        "by_distrito": by_distrito,
        "by_concelho": by_concelho,
        "by_region": by_region,
        "by_municipio": by_municipio,
    }


def main(out_dir):
    with open(os.path.join(out_dir, "club.json"), encoding="utf-8") as f:
        club = json.load(f)

    classifier = Classifier(
        os.path.join(REFDATA_DIR, "distritos_pt.geojson"),
        os.path.join(REFDATA_DIR, "concelhos_pt.geojson"),
        foreign_dir=os.path.join(REFDATA_DIR, "foreign"),
        foreign_muni_dir=os.path.join(REFDATA_DIR, "foreign_muni"),
    )

    squares_por_atleta = {nome: [] for nome, _uid in ATLETAS}
    for x, y, mask in club["squares"]:
        for i, (nome, _uid) in enumerate(ATLETAS):
            if mask & (1 << i):
                squares_por_atleta[nome].append((x, y))

    atletas_out = {}
    for nome, squares in squares_por_atleta.items():
        atletas_out[nome] = classify_athlete(classifier, squares)
        print(f"{nome}: {len(squares)} squares classificados")

    uniao = classify_uniao(classifier, club["squares"], [nome for nome, _uid in ATLETAS])
    print(f"união: {len(club['squares'])} squares distintos classificados")

    resultado = {
        "atualizado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zoom": club["zoom"],
        "atletas": atletas_out,
        "uniao": uniao,
    }
    out_path = os.path.join(out_dir, "club_regioes.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, separators=(",", ":"))
    print(f"escrito: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.out_dir)
