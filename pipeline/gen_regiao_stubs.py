"""Gera os stubs HTML das páginas de região: regioes/<key>.html, um por
ficheiro em data/regioes/. Cada stub é só casca, carrega ../nav.js,
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
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)

# regiões/zonas estrangeiras (<ccl>-r-*, <ccl>-z-*): o append_regioes já
# escreve os .json na branch `data`, mas o stub e o renderer só na Fase 3.
# Ignora-as aqui (nem gera nem apaga) para o cron não commitar páginas
# meio-feitas.
ADIAR_FASE3 = re.compile(r"^[a-z]{2}-[rz]-")

STUB = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<link rel="manifest" href="../manifest.json">
<link rel="icon" href="../favicon.ico" sizes="32x32">
<link rel="icon" href="../icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<meta name="theme-color" content="#14131b">
<title>{nome} · Squadrats Club</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preload" as="font" type="font/woff2" crossorigin href="../fonts/bricolage-grotesque.woff2">
<link rel="preload" as="font" type="font/woff2" crossorigin href="../fonts/ibm-plex-sans-400.woff2">
<link rel="stylesheet" href="../site.css">
<link rel="stylesheet" href="regiao.css">
</head>
<body>
<main id="regiao" data-key="{key}" data-nivel="{nivel}" data-nome="{nome}">
  <p class="reg-estado">A carregar {nome}…</p>
</main>
<script src="../nav.js"></script>
<script src="../shared.js"></script>
<script src="comum.js"></script>
<script src="regiao.js"></script>
</body>
</html>
"""


def main(repo_dir, dados_dir):
    destino = os.path.join(repo_dir, "regioes")
    os.makedirs(destino, exist_ok=True)

    # index.html (índice) e pais-*.html (páginas por país) são à mão, não
    # geradas a partir de data/regioes/, nunca as apagar
    escritos = {"index.html", "pais-pt.html", "pais-es.html"}
    for p in sorted(glob.glob(os.path.join(dados_dir, "regioes", "*.json"))):
        key = os.path.splitext(os.path.basename(p))[0]  # <key>.json -> <key>
        if ADIAR_FASE3.match(key):
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        with open(os.path.join(destino, key + ".html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(STUB.format(nome=d["regiao"], key=key, nivel=d["nivel"]))
        escritos.add(key + ".html")
        print(f"stub: regioes/{key}.html")

    for ficheiro in os.listdir(destino):
        if not ficheiro.endswith(".html") or ficheiro in escritos:
            continue
        if ADIAR_FASE3.match(os.path.splitext(ficheiro)[0]):
            continue  # não mexer nas keys adiadas para a Fase 3
        os.remove(os.path.join(destino, ficheiro))
        print(f"removido (regiao sem actividade): regioes/{ficheiro}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("repo_dir", nargs="?", default=REPO_DIR)
    p.add_argument("dados_dir", nargs="?", default=os.path.join(REPO_DIR, "data"))
    a = p.parse_args()
    main(a.repo_dir, a.dados_dir)
