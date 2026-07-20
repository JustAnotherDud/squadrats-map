# squadrats-map

Mapa de squares (squadrats/squadratinhos) capturados, com % por concelho/distrito de Portugal, servido via GitHub Pages.

O ciclo é automático: exportas o KML da app squadrats.com para uma pasta do Google Drive, e uns
minutos depois o mapa no GitHub Pages já reflete os dados novos, sem mais nenhuma ação manual.

## Estrutura

- `index.html` — o mapa (GitHub Pages serve isto na raiz)
- `data/` — ficheiros consumidos pelo `index.html` (geometria simplificada, classificação dos squares)
- `pipeline/` — converte o KML exportado do squadrats.com nos ficheiros em `data/`
  - `pipeline.py` — orquestrador (`py pipeline.py <kml> <out_dir>`)
  - `kml_parse.py` — parse do KML + reconstrução dos squares individuais (x, y, zoom) por varrimento da grelha XYZ
  - `classify.py` — classifica cada square em concelho/distrito (point-in-polygon com STRtree)
  - `download_kml.py` — descarrega um ficheiro do Drive pelo `fileId` (usado pelo workflow em CI)
  - `compute_grid_totals.py` — **one-off**, corre manualmente, nunca pelo pipeline: calcula quantos tiles (zoom14/17) existem no total em cada concelho/distrito/país, usando o mesmo critério do `classify.py` (centro do tile). Output commitado em `refdata/grid_totals.json` — recalcular sempre que as fronteiras OU a regra de classificação (`classify.py`) mudarem, para os totais nunca divergirem do critério usado nos capturados.
  - `compute_adjacency.py` — **one-off**: adjacência entre concelhos/distritos/províncias ES (`geom.buffer(eps).intersects()`) + greedy coloring sobre a paleta categórica do `index.html`, para vizinhos nunca partilharem cor no modo "Cores: região". Output commitado em `data/adjacency.json`. Recalcular só se as fronteiras mudarem.
  - `refdata/` — fronteiras de concelho/distrito **não simplificadas** (só para classificação — mais precisas que as de `data/`, que estão simplificadas para pesarem menos no browser) + `grid_totals.json`
  - `refdata/foreign/` — geometria de precisão de regiões estrangeiras, um ficheiro por país (`ES.geojson`). Adicionar um país novo (ex: França) = só adicionar `FR.geojson` com o mesmo formato (`properties.country` + `properties.region` por feature), zero alterações de código em `classify.py`/`pipeline.py`.
  - `spikes/` — scripts de teste/validação usados durante o desenvolvimento (T1, T5) — não fazem parte do pipeline em produção
- `supabase/functions/` — as duas Edge Functions do pipeline automático (ver arquitetura abaixo)
- `.github/workflows/` — `process-kml.yml` (processa KMLs novos) e `renew-drive-watch.yml` (renova o canal do Drive)

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
py pipeline/pipeline.py data/sample-export.kml data
```

Produz `data/tile_info_squadrats.json` e `data/tile_info_squadratinhos.json`.

## Arquitetura da automação

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

1. **O canal expirou sem renovar.** Confirma em `drive_sync_state.channel_expiration` (tabela
   Supabase) se já passou. Se sim, o `renew-drive-watch.yml` parou de correr — verifica em
   [Actions → renew-drive-watch](../../actions/workflows/renew-drive-watch.yml) se os runs recentes
   existem e passaram. Corre `workflow_dispatch` manualmente para recuperar já.
2. **O schedule do GitHub foi desativado por inatividade (60 dias sem commits).** O heartbeat
   mensal (`heartbeat.txt`) devia prevenir isto — se mesmo assim aconteceu, vai a
   `Settings → Actions → General` e reativa o workflow, ou corre `workflow_dispatch` uma vez (isso
   também já reativa o schedule).
3. **O `repository_dispatch` não chega.** Testa a Edge Function diretamente:
   ```
   curl -i -X POST https://yvsjchzvoikqlpbqsphs.supabase.co/functions/v1/drive-webhook-receiver \
     -H "X-Goog-Channel-Id: debug" \
     -H "X-Goog-Channel-Token: <CHANNEL_TOKEN>" \
     -H "X-Goog-Resource-State: change"
   ```
   200 sem novo run em Actions → o `changes.list()` não encontrou nada relevante (normal se não
   houver KML novo) ou o filtro `.kml`/pasta/`trashed` está a excluir por engano — ver logs da
   function no dashboard do Supabase.
4. **O workflow `process-kml` corre mas falha.** Provavelmente o KML não tem a camada `squadrats`
   (export incompleto) — `pipeline.py` falha alto de propósito nesse caso, exit 1, sem tocar em
   `data/`. Confirma nos logs do run qual foi o erro exato.
5. **Nada disto e continua parado.** Fallback manual, sempre disponível:
   ```
   py pipeline/pipeline.py <kml_descarregado_à_mão> data
   git add data/tile_info_*.json && git commit -m "chore(data): update manual" && git push
   ```

## Ver também

`squadrats-pipeline-plano.md` — plano original com o histórico de decisões e resultados de cada
spike (T1-T9).
