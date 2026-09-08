"""Gera os stubs HTML das páginas de região: regioes/<key>.html, um por
ficheiro em data/regioes/. Cada stub é só casca — carrega ../nav.js,
../shared.js (MESES/fmtData/regiaoHref) e ../regiao.js, que lê
data/regioes/<key>.json da branch `data`.

Corre no fetch-map-data.yml a seguir ao append_regioes; commita para o `main`
só se a lista de regiões tiver mudado (padrão do gen_profile_stubs.py).
Apaga stubs de regiões que já não têm ficheiro de dados.

Uso: py gen_regiao_stubs.py [pasta_repo] [pasta_dados]
"""
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)

STUB = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>{nome} — Squadrats Club</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="regiao.css">
</head>
<body>
<main id="regiao" data-key="{key}" data-nivel="{nivel}" data-nome="{nome}">
  <p class="reg-estado">A carregar {nome}…</p>
</main>
<script src="../nav.js"></script>
<script src="../shared.js"></script>
<script src="regiao.js"></script>
</body>
</html>
"""


def main(repo_dir, dados_dir):
    destino = os.path.join(repo_dir, "regioes")
    os.makedirs(destino, exist_ok=True)

    escritos = set()
    for p in sorted(glob.glob(os.path.join(dados_dir, "regioes", "*.json"))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        key = d["key"]
        with open(os.path.join(destino, key + ".html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(STUB.format(nome=d["regiao"], key=key, nivel=d["nivel"]))
        escritos.add(key + ".html")
        print(f"stub: regioes/{key}.html")

    for ficheiro in os.listdir(destino):
        if ficheiro.endswith(".html") and ficheiro not in escritos:
            os.remove(os.path.join(destino, ficheiro))
            print(f"removido (região sem actividade): regioes/{ficheiro}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("repo_dir", nargs="?", default=REPO_DIR)
    p.add_argument("dados_dir", nargs="?", default=os.path.join(REPO_DIR, "data"))
    a = p.parse_args()
    main(a.repo_dir, a.dados_dir)
