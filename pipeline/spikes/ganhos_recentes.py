"""One-off: que squadratinhos é que um atleta capturou entre dois commits do
club.json, e em que concelho/região caem.

Faz o diff dos bitmasks (nada de rede) e classifica só os tiles novos com o
Classifier de sempre (pipeline/classify.py). Não corre o pipeline.

Uso:
    py pipeline/spikes/ganhos_recentes.py <sha_base> <sha_novo> [nome_atleta]
    py pipeline/spikes/ganhos_recentes.py f94b251 404c846 Zé
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
REPO = os.path.dirname(PIPELINE)
REFDATA = os.path.join(PIPELINE, "refdata")
sys.path.insert(0, PIPELINE)

from classify import Classifier            # noqa: E402
from kml_parse import tile_bounds          # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def club_em(sha):
    raw = subprocess.run(
        ["git", "show", f"{sha}:data/club.json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return json.loads(raw)


def squares_do_atleta(club, nome):
    idx = next((i for i, a in enumerate(club["atletas"]) if a["nome"] == nome), None)
    if idx is None:
        sys.exit(f"atleta '{nome}' não está no club.json (tem: "
                 f"{[a['nome'] for a in club['atletas']]})")
    bit = 1 << idx
    return {(x, y) for x, y, m in club["squares"] if m & bit}, idx


def main(sha_base, sha_novo, nome):
    base = club_em(sha_base)
    novo = club_em(sha_novo)
    if base["zoom"] != 17 or novo["zoom"] != 17:
        sys.exit("club.json não está a zoom 17 — inesperado")

    sq_base, i_base = squares_do_atleta(base, nome)
    sq_novo, i_novo = squares_do_atleta(novo, nome)
    novos = sq_novo - sq_base
    perdidos = sq_base - sq_novo

    print(f"{nome}: bit {i_base} (base) / {i_novo} (novo)")
    print(f"base  {sha_base}  {base['atualizado']}  — {len(sq_base)} squadratinhos")
    print(f"novo  {sha_novo}  {novo['atualizado']}  — {len(sq_novo)} squadratinhos")
    print(f"\nnovos: {len(novos)}   perdidos: {len(perdidos)}")
    if perdidos:
        print("  AVISO: há tiles que desapareceram — o diff deixa de ser só ganhos")
    if not novos:
        return

    clf = Classifier(
        os.path.join(REFDATA, "distritos_pt.geojson"),
        os.path.join(REFDATA, "concelhos_pt.geojson"),
        foreign_dir=os.path.join(REFDATA, "foreign"),
        foreign_muni_dir=os.path.join(REFDATA, "foreign_muni"),
    )

    por_concelho, por_distrito = {}, {}
    por_regiao_estr, por_municipio_estr = {}, {}
    por_pais = {}
    sem_classificacao = 0
    # extremos: guardar (lat, lon) de cada tile pelo centro do box
    pontos = []

    for x, y in novos:
        poly = tile_bounds(x, y, 17)
        lon_min, lat_min, lon_max, lat_max = poly.bounds
        clat, clon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
        pontos.append((clat, clon, x, y))

        info = clf.classify(poly)
        pais = info["country"]
        if pais:
            por_pais[pais] = por_pais.get(pais, 0) + 1
        if info["in_portugal"]:
            if info["district"]:
                por_distrito[info["district"]] = por_distrito.get(info["district"], 0) + 1
            if info["concelho"]:
                por_concelho[info["concelho"]] = por_concelho.get(info["concelho"], 0) + 1
            if not info["concelho"] and not info["district"]:
                sem_classificacao += 1
        elif pais:
            if info["region"]:
                por_regiao_estr[(pais, info["region"])] = por_regiao_estr.get((pais, info["region"]), 0) + 1
            if info["municipio"]:
                por_municipio_estr[(pais, info["municipio"])] = por_municipio_estr.get((pais, info["municipio"]), 0) + 1
        else:
            sem_classificacao += 1

    def tabela(titulo, d, fmt=lambda k: k):
        print(f"\n{titulo}")
        if not d:
            print("  (nenhum)")
            return
        for k, n in sorted(d.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print(f"  {n:>4}  {fmt(k)}")

    print("\n" + "=" * 60)
    tabela("Por país", por_pais)
    tabela("Por concelho (PT)", por_concelho)
    tabela("Por distrito (PT)", por_distrito)
    tabela("Por região (estrangeiro)", por_regiao_estr, fmt=lambda k: f"{k[1]} ({k[0]})")
    tabela("Por município (estrangeiro)", por_municipio_estr, fmt=lambda k: f"{k[1]} ({k[0]})")
    if sem_classificacao:
        print(f"\nsem classificação: {sem_classificacao}")

    # --- extremos geográficos ---
    norte = max(pontos, key=lambda p: p[0])
    sul = min(pontos, key=lambda p: p[0])
    este = max(pontos, key=lambda p: p[1])
    oeste = min(pontos, key=lambda p: p[1])
    print("\nExtremos dos tiles novos (centro do square):")
    for rot, p in (("mais a norte", norte), ("mais a sul", sul),
                   ("mais a este ", este), ("mais a oeste", oeste)):
        lat, lon, x, y = p
        info = clf.classify(tile_bounds(x, y, 17))
        onde = info["concelho"] or info["region"] or info["country"] or "?"
        print(f"  {rot}: {lat:.4f}, {lon:.4f}  ({onde})  "
              f"https://www.google.com/maps?q={lat:.5f},{lon:.5f}")
    span_ns_km = (norte[0] - sul[0]) * 111.0
    span_ew_km = (este[1] - oeste[1]) * 111.0 * 0.77  # ~cos(39.4°)
    print(f"  amplitude ~{span_ns_km:.0f} km N-S, ~{span_ew_km:.0f} km E-O")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Zé")
