"""Pipeline: squares do squadrats.com (KML ou vector tiles) -> JSON classificado
por concelho/distrito.

Uso:
  py pipeline.py --kml <caminho.kml> [pasta_saida]      (fallback, ver tiles_fetch.py)
  py pipeline.py --uid <firebase_uid> [pasta_saida]      (fonte principal)

ATENÇÃO (2026-08-15): correr este ficheiro directamente só actualiza o mapa
pessoal do José (tile_info_*.json, stats.json, trophies.json). Não toca em
squadrats.json/club.json/daily_gains.json — os ficheiros que o folha-do-clube
e o club.html lêem. Para actualizar tudo de uma vez (o que se quer quase
sempre), usar `run_all.py`, não este ficheiro directamente. Fora de emergência
local, preferir mesmo `gh workflow run fetch-map-data.yml` — corre run_all.py
já dentro do fluxo normal de publicação na branch `data`, sem montagem manual
de git worktree.
"""
import argparse
import json
import os
import sys

from kml_parse import parse_kml_geometries, reconstruct_squares, tile_bounds, ZOOM_BY_TYPE
from classify import Classifier

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
REFDATA_DIR = os.path.join(HERE, "refdata")  # fronteiras não-simplificadas, só para classificação


def run(kml_path, out_dir):
    """Fallback: export manual de KML (ver README — mantido caso o endpoint
    de vector tiles mude ou fique indisponível sem aviso)."""
    geoms = parse_kml_geometries(kml_path)

    # falhar alto e cedo: um KML sem a camada "squadrats" é quase certamente um
    # export incompleto/de teste, não um export real — nunca deve gerar JSON
    # vazio/parcial que silenciosamente apague os dados reais do site.
    if "squadrats" not in geoms:
        raise RuntimeError(
            f"KML '{kml_path}' não tem a camada 'squadrats' — export incompleto ou "
            f"ficheiro errado. Placemarks encontrados: {list(geoms.keys()) or '(nenhum)'}. "
            f"A abortar sem tocar em ficheiros de saída."
        )
    return run_from_geoms(geoms, out_dir, strict_validation=False)


def run_from_tiles(uid, out_dir, bbox=None):
    """Fonte principal: fetch directo aos vector tiles da Squadrats (ver
    tiles_fetch.py). Substitui o export manual de KML."""
    from athletes import known_squadratinhos
    from tiles_fetch import scan_athlete

    kwargs = {"bbox": bbox} if bbox else {}
    known = known_squadratinhos(out_dir).get(uid)
    resultado = scan_athlete(uid, with_trophy_geometry=True, known_squadratinhos=known, **kwargs)
    if resultado is None:
        # probe confirmou "sem alterações" (ver tiles_fetch.py) — os
        # ficheiros que este UID publica (tile_info_*.json, stats.json,
        # trophies.json, suggestions.json, classification_fallbacks.json) já
        # estão no out_dir, carregados da branch 'data' antes de correr — não
        # tocar neles é o comportamento certo, não é um "esquecimento".
        print(f"UID '{uid}': sem alterações desde a última publicação — a manter ficheiros existentes")
        return {}
    geoms, counts, trophies = resultado

    if "squadrats" not in geoms:
        raise RuntimeError(
            f"UID '{uid}': nenhum square 'squadrats' encontrado na área varrida — "
            f"varrimento incompleto ou atleta sem dados. A abortar sem tocar em ficheiros de saída."
        )
    write_trophies(trophies, counts, out_dir)
    return run_from_geoms(geoms, out_dir, strict_validation=True, counts=counts)


# grelha a que cada troféu pertence — o mapa mostra os do zoom activo
TROPHY_GRID = {
    "squadrats": ["yard", "backyards", "ubersquadrat"],
    "squadratinhos": ["yardinho", "backyardinhos", "ubersquadratinho"],
}


def write_trophies(trophies, counts, out_dir):
    """data/trophies.json — geometria das formas de troféu, para o mapa as
    poder desenhar como camadas opcionais.

    Nota sobre `backyards`: a geometria que a Squadrats manda INCLUI o yard
    principal (confirmado em spikes/backyards_probe.py). Aqui subtrai-se o
    yard, para as duas camadas poderem ser desenhadas ao mesmo tempo sem se
    taparem — o `size` publicado continua a ser o do servidor (nº de
    clusters, yard incluído), só a geometria é que é a dos secundários.
    """
    from shapely.geometry import MultiPolygon, mapping

    def simplificar(geom):
        # mesma razão do sort dos tile_info: a ordem dos polígonos dentro de um
        # MultiPolygon não é estável entre plataformas
        if isinstance(geom, MultiPolygon):
            geom = MultiPolygon(sorted(geom.geoms, key=lambda p: p.bounds))
        # a grelha é ortogonal: simplificar tira vértices redundantes das
        # bordas clipadas sem mexer no desenho
        g = geom.simplify(1e-6, preserve_topology=True)
        geo = mapping(g)

        def arred(o):
            if isinstance(o[0], (int, float)):
                return [round(c, 6) for c in o]
            return [arred(c) for c in o]

        return {**geo, "coordinates": arred(geo["coordinates"])}

    out = {}
    for grelha, camadas in TROPHY_GRID.items():
        bloco = {}
        yard_name = camadas[0]
        for nome in camadas:
            if nome not in trophies:
                continue
            geom = trophies[nome]
            if nome.startswith("backyard") and yard_name in trophies:
                geom = geom.difference(trophies[yard_name])
                if geom.is_empty:
                    continue
            bloco[nome] = {"size": counts.get(nome), "geometry": simplificar(geom)}
        if bloco:
            out[grelha] = bloco

    path = os.path.join(out_dir, "trophies.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"trophies -> {path}")


def write_suggestions(visitados_por_grelha, counts, out_dir):
    """data/suggestions.json — o que falta para o próximo übersquadrat.

    Antes de sugerir seja o que for, `verify_rules` confirma que as nossas
    regras reproduzem o yard e o übersquadrat que o servidor reporta. Se
    divergirem, aborta: uma sugestão calculada com regras erradas parece
    rigorosa e não é.
    """
    from suggestions import verify_rules, proximo_ubersquadrat, melhor_ligacao, corredores

    out = {}
    for grelha, (visitados, zoom) in visitados_por_grelha.items():
        yard_name, _, uber_name = TROPHY_GRID[grelha]
        esperado_yard, esperado_uber = counts.get(yard_name), counts.get(uber_name)
        if esperado_yard is None or esperado_uber is None:
            continue
        verify_rules(visitados, esperado_yard, esperado_uber, grelha)

        bloco = {
            "zoom": zoom,
            "ligacao": melhor_ligacao(visitados),
            # "ligacao_backyard" (melhor_ligacao_backyard, suggestions.py) foi
            # removido daqui a pedido (2026-08-16, "não uso") — a função fica
            # no suggestions.py, só deixou de ser chamada/publicada.
            "corredores": corredores(visitados),
        }

        s = proximo_ubersquadrat(visitados, esperado_uber)
        if s is not None:
            cx, cy = s["canto"]
            bloco["uber"] = {
                "atual": esperado_uber,
                "alvo": s["n_alvo"],
                "faltam": s["faltam"],
                "canto": {"x": cx, "y": cy},
                "squares": [{"x": x, "y": y} for x, y in s["squares_em_falta"]],
            }
        out[grelha] = bloco

    path = os.path.join(out_dir, "suggestions.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"suggestions -> {path}")


def run_from_geoms(geoms, out_dir, strict_validation, counts=None):
    classifier = Classifier(
        os.path.join(REFDATA_DIR, "distritos_pt.geojson"),
        os.path.join(REFDATA_DIR, "concelhos_pt.geojson"),
        foreign_dir=os.path.join(REFDATA_DIR, "foreign"),
        foreign_muni_dir=os.path.join(REFDATA_DIR, "foreign_muni"),
    )

    with open(os.path.join(REFDATA_DIR, "grid_totals.json"), encoding="utf-8") as f:
        grid_totals = json.load(f)

    zkey_by_type = {"squadrats": "z14", "squadratinhos": "z17"}

    summary = {}
    visitados_por_grelha = {}
    # países estrangeiros com total conhecido (grid_totals já tem country_XX/
    # by_region_XX — ver compute_grid_totals.py) — descoberto a partir das
    # chaves do próprio grid_totals, não de uma lista fixa: um país novo lá
    # aparece aqui sozinho, sem tocar neste ficheiro.
    paises_com_total = sorted({
        k[len("country_"):].upper() for k in grid_totals if k.startswith("country_") and k != "country_pt"
    })
    # mesmo princípio, para o nível concelho/município equivalente — hoje só
    # ES (grid_totals["by_municipio_es"]), descoberto pelas chaves, não por
    # uma lista fixa.
    paises_com_municipio = sorted({
        k[len("by_municipio_"):].upper() for k in grid_totals if k.startswith("by_municipio_")
    })
    stats = {"by_concelho": {}, "by_distrito": {}, "country_pt": {}, "foreign": {}}
    for cc in paises_com_total:
        stats[f"country_{cc.lower()}"] = {}
        stats[f"by_region_{cc.lower()}"] = {}
    for cc in paises_com_municipio:
        stats[f"by_municipio_{cc.lower()}"] = {}
    total_squares = 0
    not_on_land = 0
    fallback_events = []  # squares resolvidos por proximidade (país e/ou concelho), não por área

    for type_name, zoom in ZOOM_BY_TYPE.items():
        if type_name not in geoms:
            print(f"aviso: camada '{type_name}' não encontrada", file=sys.stderr)
            continue

        declared_size, geom = geoms[type_name]
        squares = reconstruct_squares(geom, zoom)

        if declared_size is not None and len(squares) != declared_size:
            msg = (
                f"{type_name} — reconstruídos {len(squares)}, declarados {declared_size} "
                f"(diferença indica varrimento incompleto ou bug de geometria)"
            )
            if strict_validation:
                # vector tiles: a auto-validação É a rede de segurança do
                # pipeline (ver tiles_fetch.py) — nunca publicar dados que não
                # batam com o total que o próprio servidor da Squadrats reporta.
                raise RuntimeError(msg)
            print(f"aviso: {msg}", file=sys.stderr)

        out = []
        by_concelho_captured, by_distrito_captured = {}, {}
        by_foreign_captured = {}  # {country: {region: count}}
        by_foreign_municipio_captured = {}  # {country: {municipio: count}}
        unclassified_foreign = 0
        pt_captured = foreign_captured = 0
        for x, y, lon, lat in squares:
            info = classifier.classify(tile_bounds(x, y, zoom))
            out.append({
                "x": x, "y": y, "zoom": zoom,
                "lon": round(lon, 6), "lat": round(lat, 6),
                "in_portugal": info["in_portugal"],
                "district": info["district"],
                "concelho": info["concelho"],
                "country": info["country"],
                "region": info["region"],
                "municipio": info["municipio"],
            })
            total_squares += 1
            if not info["on_land"]:
                not_on_land += 1

            for level, deg in (
                ("country", info["country_fallback_deg"]),
                ("concelho", info["concelho_fallback_deg"]),
            ):
                if deg is not None:
                    fallback_events.append({
                        "x": x, "y": y, "zoom": zoom,
                        "lon": round(lon, 6), "lat": round(lat, 6),
                        "level": level,
                        "resolved_to": info["concelho"] if level == "concelho"
                                       else (info["district"] if info["in_portugal"] else f"{info['country']}/{info['region']}"),
                        "distance_deg": round(deg, 6),
                        "distance_m_approx": round(deg * 111_000),  # aproximado, sem correcção de latitude
                    })

            if info["in_portugal"]:
                pt_captured += 1
                by_concelho_captured[info["concelho"]] = by_concelho_captured.get(info["concelho"], 0) + 1
                by_distrito_captured[info["district"]] = by_distrito_captured.get(info["district"], 0) + 1
            else:
                foreign_captured += 1
                if info["country"] and info["region"]:
                    by_foreign_captured.setdefault(info["country"], {})
                    by_foreign_captured[info["country"]][info["region"]] = (
                        by_foreign_captured[info["country"]].get(info["region"], 0) + 1
                    )
                    if info["municipio"]:
                        by_foreign_municipio_captured.setdefault(info["country"], {})
                        by_foreign_municipio_captured[info["country"]][info["municipio"]] = (
                            by_foreign_municipio_captured[info["country"]].get(info["municipio"], 0) + 1
                        )
                else:
                    # sem geometria disponível para este país — fallback genérico
                    # (mesmo comportamento de antes desta iteração)
                    unclassified_foreign += 1

        visitados_por_grelha[type_name] = ({(s["x"], s["y"]) for s in out}, zoom)

        # ordem estável: a de `reconstruct_squares` varia com a plataforma/versão
        # do shapely, e sem isto o `git diff --quiet` do workflow via sempre
        # diferença e comitava todos os dias mesmo sem squares novos
        out.sort(key=lambda s: (s["x"], s["y"]))

        out_path = os.path.join(out_dir, f"tile_info_{type_name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

        summary[type_name] = {
            "total": len(out),
            "in_portugal": pt_captured,
        }
        print(f"{type_name}: {len(out)} squares -> {out_path}")

        zkey = zkey_by_type[type_name]

        def pct(captured, total):
            return round(100.0 * captured / total, 2) if total else 0.0

        for name, total_info in grid_totals["by_concelho"].items():
            total = total_info.get(zkey, 0)
            captured = by_concelho_captured.get(name, 0)
            stats["by_concelho"].setdefault(name, {})[zkey] = {
                "captured": captured, "total": total, "pct": pct(captured, total),
            }
        for name, total_info in grid_totals["by_distrito"].items():
            total = total_info.get(zkey, 0)
            captured = by_distrito_captured.get(name, 0)
            stats["by_distrito"].setdefault(name, {})[zkey] = {
                "captured": captured, "total": total, "pct": pct(captured, total),
            }

        pt_total = grid_totals["country_pt"].get(zkey, 0)
        stats["country_pt"][zkey] = {
            "captured": pt_captured, "total": pt_total, "pct": pct(pt_captured, pt_total),
        }

        for cc in paises_com_total:
            captured_by_region = by_foreign_captured.get(cc, {})
            for name, total_info in grid_totals.get(f"by_region_{cc.lower()}", {}).items():
                total = total_info.get(zkey, 0)
                captured = captured_by_region.get(name, 0)
                stats[f"by_region_{cc.lower()}"].setdefault(name, {})[zkey] = {
                    "captured": captured, "total": total, "pct": pct(captured, total),
                }
            total_pais = grid_totals.get(f"country_{cc.lower()}", {}).get(zkey, 0)
            captured_pais = sum(captured_by_region.values())
            stats[f"country_{cc.lower()}"][zkey] = {
                "captured": captured_pais, "total": total_pais or None,
                "pct": pct(captured_pais, total_pais) if total_pais else None,
            }

        for cc in paises_com_municipio:
            captured_by_municipio = by_foreign_municipio_captured.get(cc, {})
            for name, total_info in grid_totals.get(f"by_municipio_{cc.lower()}", {}).items():
                total = total_info.get(zkey, 0)
                captured = captured_by_municipio.get(name, 0)
                stats[f"by_municipio_{cc.lower()}"].setdefault(name, {})[zkey] = {
                    "captured": captured, "total": total, "pct": pct(captured, total),
                }
        stats["foreign"][zkey] = {**by_foreign_captured, "unclassified": unclassified_foreign}

    if counts:
        write_suggestions(visitados_por_grelha, counts, out_dir)

    stats_path = os.path.join(out_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, separators=(",", ":"))
    print(f"stats -> {stats_path}")

    # ficheiro à parte (não no stats.json): quantos squares não estão em
    # terra nenhuma, e a lista de quem foi resolvido por proximidade em vez
    # de área — país e/ou concelho. distance_m_approx separa fenda de dados
    # (metros) de água genuína (centenas de metros/km), sem impor um corte.
    fallbacks_path = os.path.join(out_dir, "classification_fallbacks.json")
    with open(fallbacks_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_squares": total_squares,
            "not_on_land": not_on_land,
            "fallback_events": len(fallback_events),
            "events": fallback_events,
        }, f, ensure_ascii=False, indent=2)
    print(f"classificação: {not_on_land}/{total_squares} squares não estão em terra "
          f"nenhuma (resolvidos por proximidade ou sem classificação); "
          f"{len(fallback_events)} campos (país/concelho) resolvidos por proximidade -> {fallbacks_path}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--kml", dest="kml_path", help="fallback: caminho para um KML exportado manualmente")
    source.add_argument("--uid", dest="uid", help="fonte principal: Firebase UID do atleta")
    parser.add_argument("out_dir", nargs="?", default=DATA_DIR)
    args = parser.parse_args()

    print(
        "AVISO: a correr pipeline.py directamente — só actualiza o mapa pessoal "
        "(tile_info_*.json/stats.json/trophies.json). squadrats.json/club.json/"
        "daily_gains.json (folha-do-clube, club.html) ficam por actualizar. "
        "Para tudo: `py run_all.py` ou `gh workflow run fetch-map-data.yml`.",
        file=sys.stderr,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    if args.uid:
        result = run_from_tiles(args.uid, args.out_dir)
    else:
        result = run(args.kml_path, args.out_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
