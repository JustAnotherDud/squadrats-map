# squadrats-map

Mapa de squares (squadrats/squadratinhos) capturados, com % por concelho/distrito de Portugal, servido via GitHub Pages.

## Estrutura

- `index.html` — o mapa (GitHub Pages serve isto na raiz)
- `data/` — ficheiros consumidos pelo `index.html` (geometria simplificada, classificação dos squares)
- `pipeline/` — script que converte o KML exportado do squadrats.com nos ficheiros em `data/`
  - `pipeline.py` — orquestrador (`py pipeline.py <kml> <out_dir>`)
  - `kml_parse.py` — parse do KML + reconstrução dos squares individuais (x, y, zoom) por varrimento da grelha XYZ
  - `classify.py` — classifica cada square em concelho/distrito (point-in-polygon com STRtree)
  - `refdata/` — fronteiras de concelho/distrito **não simplificadas** (só para classificação — mais precisas que as de `data/`, que estão simplificadas para pesarem menos no browser)

## Rodar o pipeline manualmente

```
py -m pip install -r requirements.txt
py pipeline/pipeline.py data/sample-export.kml data
```

Produz `data/tile_info_squadrats.json` e `data/tile_info_squadratinhos.json`.

## Automação (em progresso)

Ver `squadrats-pipeline-plano.md` para o plano completo: export manual do KML para o Google Drive →
webhook → Supabase Edge Function → GitHub Actions → commit automático → redeploy do Pages.
