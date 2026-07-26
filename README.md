# squadrats-map

Mapa de squares (squadrats/squadratinhos) capturados, com % por concelho/distrito de Portugal, servido via GitHub Pages.

O ciclo é automático: `fetch-map-data.yml` corre diariamente, busca os dados **diretamente aos
vector tiles da Squadrats** (sem export manual de KML) e comita se houver diferença real. Também
publica `data/squadrats.json` — totais simples (sem breakdown geográfico) para os 3 atletas do
clube, consumido pelo `club-koms` como o `prs.json`.

## Estrutura

- `index.html` — o mapa detalhado do José (GitHub Pages serve isto na raiz)
- `club.html` — página do club: squadratinhos dos três atletas com conta Squadrats,
  cor por combinação de quem partilha cada square. Sem classificação por concelho nem troféus —
  é outro assunto e outro ficheiro de dados (`data/club.json`). Squares desenhados em canvas
  (~9000; em SVG o mapa engasgava a arrastar).
- `data/` — ficheiros consumidos pelo `index.html` (geometria simplificada, classificação dos squares) + `squadrats.json` (totais do clube) + `trophies.json` (formas de yard/backyards/übersquadrat, para as camadas opcionais do mapa)
- `pipeline/` — busca os squares do José e produz os ficheiros em `data/`
  - `tiles_fetch.py` — **fonte principal**: fetch directo aos vector tiles da Squadrats
    (`tiles1.squadrats.com/{uid}/trophies/{ts}/{z}/{x}/{y}.pbf`, endpoint não documentado, ver
    "Regras de uso" abaixo). Descoberta em cascata (z4→z7→z10, cada nível só explora filhos dos
    tiles com cobertura do nível anterior) — robusto a um atleta ter capturas em qualquer parte
    do mundo, sem bbox fixo a adivinhar. Auto-validação obrigatória: a contagem reconstruída de
    `squadrats`/`squadratinhos` tem de bater exatamente com o `size` que o próprio servidor
    reporta — se não bater, `pipeline.py`/`fetch_club_koms.py` rebentam em vez de publicar dados
    errados.
  - `pipeline.py` — orquestrador. `py pipeline.py --uid <firebase_uid> <out_dir>` (fonte principal)
    ou `py pipeline.py --kml <caminho.kml> <out_dir>` (fallback, ver abaixo)
  - `fetch_club_koms.py` — totais simples (todas as 8 camadas) para Zé/Xeira/Carolina → `data/squadrats.json`
  - `fetch_club_squares.py` — squadratinhos dos mesmos três, com bitmask de quem tem cada square →
    `data/club.json` (o `fetch_club_koms.py` só traz totais; este traz as coordenadas).
    A ordem da lista `ATLETAS` fixa a atribuição dos bits: não reordenar
    sem regenerar o ficheiro.
  - `kml_parse.py` — **fallback**: parse de KML exportado manualmente + reconstrução dos squares
    individuais (x, y, zoom) por varrimento da grelha XYZ. `reconstruct_squares()` é partilhado
    com `tiles_fetch.py` — o resto do pipeline (classificação, stats) não sabe nem quer saber se
    os squares vieram de um KML ou de um tile
  - `classify.py` — classifica cada square em concelho/distrito (point-in-polygon com STRtree)
  - `download_kml.py` — descarrega um ficheiro do Drive pelo `fileId` (só usado pelo fallback `process-kml.yml`)
  - `compute_grid_totals.py` — **one-off**, corre manualmente, nunca pelo pipeline: calcula quantos tiles (zoom14/17) existem no total em cada concelho/distrito/país, usando o mesmo critério do `classify.py` (centro do tile). Output commitado em `refdata/grid_totals.json` — recalcular sempre que as fronteiras OU a regra de classificação (`classify.py`) mudarem, para os totais nunca divergirem do critério usado nos capturados.
  - `compute_adjacency.py` — **one-off**: adjacência entre concelhos/distritos/províncias ES (`geom.buffer(eps).intersects()`) + greedy coloring sobre a paleta categórica do `index.html`, para vizinhos nunca partilharem cor no modo "Cores: região". Output commitado em `data/adjacency.json`. Recalcular só se as fronteiras mudarem.
  - `refdata/` — fronteiras de concelho/distrito **não simplificadas** (só para classificação — mais precisas que as de `data/`, que estão simplificadas para pesarem menos no browser) + `grid_totals.json`
  - `refdata/foreign/` — geometria de precisão de regiões estrangeiras, um ficheiro por país (`ES.geojson`). Adicionar um país novo (ex: França) = só adicionar `FR.geojson` com o mesmo formato (`properties.country` + `properties.region` por feature), zero alterações de código em `classify.py`/`pipeline.py`.
  - `spikes/` — scripts de teste/validação usados durante o desenvolvimento — não fazem parte do pipeline em produção
- `supabase/functions/` — Edge Functions do caminho **fallback** por KML (ver arquitetura abaixo)
- `.github/workflows/`
  - `fetch-map-data.yml` — **principal**, cron diário (06:00 UTC), sem dependência do Drive
  - `process-kml.yml` + `renew-drive-watch.yml` — **fallback**, ver secção própria abaixo

## O que significa cada camada (`size`)

Confirmado empiricamente (`pipeline/spikes/backyards_probe.py`, 25 jul 2026) — o `size` **não
significa a mesma coisa em todas as camadas**:

| Camada | `size` é… | Verificado (Zé) |
|---|---|---|
| `squadrats` / `squadratinhos` | nº de **squares** visitados | 392 squares / 5050 squares |
| `yard` / `yardinho` | nº de **squares** do maior cluster fechado | 90 squares em 1 cluster / 480 em 1 |
| `ubersquadrat` / `ubersquadratinho` | o **N** do maior quadrado cheio NxN | 6 → 6x6 |
| `backyards` / `backyardinhos` | nº de **clusters** fechados, **incluindo o principal** | 10 clusters (101 squares) / 144 clusters (1264 squares) |

"Cluster fechado" = conjunto contíguo de squares visitados em que cada um tem os 4 vizinhos
(N/E/S/O) também visitados.

**A pegadinha do `backyards`:** conta clusters, não squares — e a sua geometria **contém** a do
`yard` (verificado: `backyards.contains(yard) == True`, área da interseção idêntica à do yard).
Logo `yard + backyards` **não** é somável: dos 10 backyards do Zé, 1 é o yard principal (90
squares) e os outros 9 somam 11 squares entre todos — quase todos um único square fechado
isolado, invisíveis no mapa e não renderizados pela app. Isto fecha a questão que estava em
aberto no brief de investigação (§10.1).

**No mapa:** estas formas estão em `data/trophies.json` e podem ser ligadas nos chips do topo
(desligadas por defeito), seguindo a grelha activa — em Squadrats mostram yard/backyards/über, em
Squadratinhos as versões "-inho". A geometria de `backyards` publicada aí é a dos clusters
**secundários** (subtrai-se o yard, para as duas camadas poderem estar ligadas ao mesmo tempo sem
se taparem); o `size` continua a ser o do servidor, com o yard incluído.

## Regras de uso do endpoint de vector tiles

`tiles1.squadrats.com` não é uma API pública nem documentada — são dados que os atletas tornaram
públicos e cujos links partilharam voluntariamente (o URL do mapa em `squadrats.com/map/{uid}/17`
já expõe o UID). Para não abusar:

- Correr no máximo uma vez por dia (o `fetch-map-data.yml` está em cron diário). Era semanal;
  passou a diário para o mapa não andar uma semana atrás das corridas. Um varrimento completo
  são ~1200 pedidos pelos três atletas — pouco, mas não subir a frequência sem motivo
- `User-Agent` identificável (`squadrats-map-sync/1.0 (+github.com/...)`, ver `tiles_fetch.py`)
- Concorrência baixa (`MAX_CONCURRENCY = 4` em `tiles_fetch.py`, não subir sem motivo)
- Nunca publicar os tiles em bruto — só os agregados derivados (`tile_info_*.json`, `stats.json`, `squadrats.json`)
- O `{TS}` no URL tem de ser fresco (`int(time.time()*1000)`) a cada pedido — o servidor ignora o
  valor mas a resposta vem com `cache-control: max-age=31536000` e o URL é a chave de cache; um
  timestamp fixo devolve dados congelados sem erro nenhum (falha silenciosa)

### Nota sobre nomes de concelho duplicados

Dois pares de concelhos têm o mesmo nome em Portugal: **Calheta** (Açores/Madeira) e **Lagoa**
(Açores/Algarve). Os ficheiros de fronteiras (`concelhos_pt.geojson`, refdata e display) já vêm
com isso desambiguado — `Calheta (Açores)`, `Calheta (Madeira)`, `Lagoa (Açores)`, `Lagoa (Faro)` —
gerado a partir do `NAME_1` (distrito/região) do GADM. Sem isto, os dois concelhos colidiam na
mesma chave e um dos dois perdia todas as capturas/totais na agregação.

### Regiões estrangeiras (Espanha e futuras)

Squares fora de Portugal são classificados por província espanhola quando há geometria
disponível (`refdata/foreign/ES.geojson`, 52 províncias/GADM ESP nível 2, nomes corrigidos —
`Asturias`, `Cantabria`, `Madrid`, `León`, etc., sem os espaços em falta do GADM). Sem geometria
para o país em causa (ex: um square em França, hoje), o square fica genérico — `country`/`region`
a `null` no `tile_info_*.json`, contado em `stats.foreign[zkey].unclassified`, sem quebrar nada.

Só a **contagem** de capturados por província é calculada (`stats.json` → `foreign`) — não há
"total da grelha" nem `%` para regiões estrangeiras (seria trabalho especulativo sem volume de
dados; ver `grid_totals.json`, que já tem o schema preparado mas não calcula nada para ES).

## Rodar o pipeline manualmente

```
py -m pip install -r requirements.txt
py pipeline/pipeline.py --uid PjHY1RpxbmgMrQG3ITdTeDa7t6M2 data   # José, via vector tiles
py pipeline/fetch_club_koms.py data                                # totais dos 3 atletas
```

Produz `data/tile_info_squadrats.json`, `data/tile_info_squadratinhos.json`, `data/stats.json` e `data/squadrats.json`.

Fallback por KML (ver secção própria): `py pipeline/pipeline.py --kml data/sample-export.kml data`.

## Arquitetura

### Caminho principal — vector tiles (`fetch-map-data.yml`, cron semanal)

```
[fetch-map-data.yml, cron semanal ou workflow_dispatch]
                    |
                    v
[tiles_fetch.py] --fetch--> tiles1.squadrats.com/{uid}/trophies/{ts}/{z}/{x}/{y}.pbf
   descoberta em cascata z4->z7->z10, depois busca os filhos z12 com cobertura
   auto-validação: contagem reconstruída == `size` do servidor, senão rebenta
                    |
      +-------------+-------------+
      |                           |
      v                           v
[pipeline.py --uid]      [fetch_club_koms.py]
  José -> classify.py       Zé/Xeira/Carolina -> totais simples (8 camadas)
  -> tile_info_*.json,      -> data/squadrats.json
     data/stats.json
      |                           |
      +-------------+-------------+
                    |
                    v
          commit condicional (só se houver diff real)
                    |
                    v
          [GitHub Pages: redeploy automático]
```

### Caminho fallback — export manual de KML (`process-kml.yml` + Drive/Supabase)

Mantido caso o endpoint de vector tiles mude ou fique bloqueado sem aviso (não documentado, sem
API pública — ver "Regras de uso" acima). Desativado na prática assim que ninguém largar KMLs na
pasta do Drive, mas pronto a usar sem reconstruir nada.

```
[App squadrats.com] --export manual do KML--> [Google Drive: pasta squadrats-exports]
                                                          |
                                             Drive changes.watch() (push)
                                                          |
                                                          v
                              [Supabase Edge Function: drive-webhook-receiver]
                            valida X-Goog-Channel-Token, chama changes.list(),
                            filtra por .kml + pasta certa + não-trashed/removed
                                                          |
                                             repository_dispatch (GitHub API)
                                                          |
                                                          v
                              [GitHub Actions: process-kml.yml]
                    download do KML pelo fileId -> pipeline.py -> commit condicional
                                                          |
                                             (só se houver diff real)
                                                          v
                                        [GitHub Pages: redeploy automático]

[GitHub Actions: renew-drive-watch.yml, cron 12h] --> [Supabase Edge Function: drive-watch-setup]
                    cria canal novo (expiration +24h) -> confirma -> pára o canal antigo
```

### Porquê duas Edge Functions

- **`drive-webhook-receiver`** — recebe as notificações da Google. Tem de aceitar pedidos
  não-autenticados (a Google não sabe autenticar-se com o Supabase), por isso a única defesa é o
  header `X-Goog-Channel-Token` batendo certo com o secret `CHANNEL_TOKEN`.
- **`drive-watch-setup`** — só é chamada pelo GitHub Actions (nunca pela Google), por isso pode ser
  mais fechada: exige `X-Setup-Token` próprio. Sem isto, qualquer pessoa com o URL conseguiria
  recriar/parar os canais à vontade.

Ambas partilham código em `supabase/functions/_shared/` (`google_auth.ts` assina o JWT da service
account com Web Crypto, sem dependências externas; `sync_state.ts` lê/escreve a tabela
`drive_sync_state`).

### Porquê a tabela `drive_sync_state`

O webhook da Google só diz "algo mudou" — não diz o quê. É preciso `changes.list()` com o
`pageToken` guardado para descobrir. A tabela é um singleton (`id=1 check`) com RLS ativo e sem
policies — só a service role key (usada pelas Edge Functions) lhe acede; a `anon` key exposta no
browser da app de nutrição do mesmo projeto Supabase não consegue tocar-lhe.

### Secrets (nunca em ficheiro versionado)

| Secret | Onde | Para quê |
|---|---|---|
| `GOOGLE_SA_KEY` | Supabase secrets **e** GitHub Actions secrets (duplicado, arquitetura obriga) | autenticar como a service account do Drive (`squadrats-drive-sa@garmin-calendar-sync-488923`, permissão **Viewer** na pasta) |
| `GH_PAT` | Supabase secrets | `drive-webhook-receiver` dispara o `repository_dispatch` — fine-grained, só `squadrats-map`, Contents R/W |
| `CHANNEL_TOKEN` | Supabase secrets | única defesa do `drive-webhook-receiver` (`verify_jwt=false`) |
| `SETUP_TOKEN` | Supabase secrets **e** GitHub Actions secrets | única defesa do `drive-watch-setup` |

## Debugar: "o mapa parou de atualizar"

1. **`fetch-map-data.yml` corre mas falha.** A causa mais provável é a auto-validação a apanhar um
   varrimento incompleto — ver logs do run, a mensagem diz qual camada/UID não bateu com o `size`
   do servidor. Se for um atleta com capturas nalgum sítio muito remoto que os níveis de cascata
   (`DISCOVERY_LEVELS = (4, 7, 10)` em `tiles_fetch.py`) não apanharam, ajustar os níveis ou correr
   manualmente com um `bbox=` mais específico primeiro para confirmar onde está a cobertura em falta.
2. **UID devolve 500.** `SquadratsHttpError` — o UID mudou ou ficou inválido. Confirmar em
   `squadrats.com/map/{uid}/17` que o mapa do atleta ainda abre.
3. **O endpoint de vector tiles mudou ou está bloqueado.** Não é documentado, pode mudar sem aviso
   (ver "Regras de uso" acima). Ativa o fallback por KML: exporta manualmente da app, larga na
   pasta `squadrats-exports` do Drive (o watch ainda está ativo, ver `renew-drive-watch.yml`) —
   `process-kml.yml` retoma sozinho. Ou corre à mão:
   ```
   py pipeline/pipeline.py --kml <kml_descarregado_à_mão> data
   git add data/tile_info_*.json data/stats.json && git commit -m "chore(data): update manual" && git push
   ```
4. **O canal do Drive expirou (só importa se estiveres a usar o fallback).** Confirma em
   `drive_sync_state.channel_expiration` (tabela Supabase) se já passou. Se sim, corre
   `workflow_dispatch` em [renew-drive-watch](../../actions/workflows/renew-drive-watch.yml)
   manualmente para recuperar já.
5. **O schedule do GitHub foi desativado por inatividade (60 dias sem commits).** Corre
   `workflow_dispatch` em qualquer um dos workflows uma vez — reativa o schedule.

## Ver também

`squadrats-pipeline-plano.md` — plano original com o histórico de decisões e resultados de cada
spike (T1-T9).
