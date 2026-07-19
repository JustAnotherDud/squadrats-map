# Squadrats — Pipeline em tempo real: plano de execução

**Papel:** este documento é o plano. A Claude Code (Sonnet 5) executa em modo agente, passo a passo, secção a secção. Onde há incerteza técnica, está marcado — testar essa peça isoladamente antes de construir o resto à volta dela.

**Confirmado antes de começar:** o Squadrats não tem API pública (só recebe de Strava/Garmin/Komoot, não expõe dados para fora). O export manual do KML pela app fica — não há como automatizar essa parte. Tudo o resto, sim.

---

## 1. Arquitetura alvo

```
[App Squadrats] --export manual--> [Google Drive: pasta /squadrats-exports]
                                              |
                                   Drive changes.watch() (push, ~segundos)
                                              |
                                              v
                          [Supabase Edge Function: drive-webhook-receiver]
                                              |
                              valida channel token, identifica ficheiro novo
                                              |
                                    repository_dispatch (GitHub API)
                                              |
                                              v
                              [GitHub Actions: process-kml.yml]
                          download KML -> pipeline Python -> gera JSON
                                              |
                                    commit + push para o repo
                                              |
                                              v
                                    [GitHub Pages: redeploy automático]
```

Peça adicional (não no caminho crítico, mas necessária): **renovação do canal**. Os canais do `changes.watch()` expiram (a Google recomenda não confiar em expirações longas — testar o valor real devolvido, ver secção 3). Precisa de um cron semanal (pode ser a própria GitHub Action, `schedule:` semanal) que chama outra Edge Function para recriar o watch.

---

## 2. Componentes e responsabilidades

| Componente | Onde vive | Responsabilidade |
|---|---|---|
| Pasta Drive `squadrats-exports` | Google Drive do Dud | Recebe o KML exportado manualmente |
| `drive-watch-setup` | Supabase Edge Function | Cria/renova o canal `changes.watch()` |
| `drive-webhook-receiver` | Supabase Edge Function | Recebe POST da Google, valida, dispara GitHub |
| `process-kml.yml` | GitHub Actions (`.github/workflows/`) | Descarrega KML, corre pipeline, commita |
| `pipeline.py` | Repo (script Python) | Parse KML → classifica PT/distrito/concelho → JSON (já existe, testado nas conversas anteriores) |
| `squadrats-mapa.html` | Repo, servido por GitHub Pages | Visualização (já existe) |
| `state.json` | Repo | Último `fileId` processado, evita reprocessar |

---

## 3. Incertezas a validar antes de construir em cima (spike list)

Ordenar por esta lista — cada uma é um teste isolado, descartável se falhar, antes de integrar no pipeline real.

### 3.1 Expiração real do canal `changes.watch()`
**Porquê importa:** define a frequência do cron de renovação.
**Como testar:** criar um canal de teste (`changes.watch()`) contra uma pasta de teste, sem campo `expiration` explícito, e ler o valor de `expiration` que a Google devolve na resposta. Comparar com a doc (que é vaga nisto para `changes.watch` vs `files.watch`).
**Quem testa:** Claude Code, com credenciais OAuth/service account do Dud (precisa de acesso à Drive API — ver checklist de secrets, secção 5).

### 3.2 Supabase Edge Function como recetor HTTPS válido
**Porquê importa:** é a peça nova do stack (Dud já usa Supabase, mas não Edge Functions para isto).
**Como testar:** deploy de uma Edge Function mínima que só faz `console.log` do body recebido + devolve 200. Apontar o `address` do `watch()` para ela. Confirmar que a notificação chega (ver logs da function).
**Risco conhecido:** a Google exige resposta 200 rápida (não processar de forma síncrona lenta) — a function deve só validar e disparar o `repository_dispatch`, não correr o pipeline inline.

### 3.3 `repository_dispatch` a partir da Edge Function
**Porquê importa:** é o elo entre Supabase e GitHub.
**Como testar:** chamar manualmente a API (`POST /repos/{owner}/{repo}/dispatches` com `event_type` custom) via curl/Postman primeiro, confirmar que a Action arranca. Só depois ligar isso à Edge Function.
**Precisa de:** um GitHub PAT com scope `repo`, guardado como secret na Edge Function (Supabase secrets, não no código).

### 3.4 Identificar qual ficheiro mudou (o webhook da Drive não diz *o quê* mudou)
**Porquê importa:** `changes.watch()` só notifica "algo mudou" — não vem com o `fileId`. É preciso chamar `changes.list()` com o `pageToken` guardado para saber o que foi.
**Como testar:** dentro do teste 3.1/3.2, adicionar a chamada a `changes.list()` após receber a notificação, confirmar que devolve o ficheiro novo e um `newStartPageToken` para a próxima vez.
**Nota:** o `state.json` no repo (ou uma tabela Supabase, mais simples de já ter) precisa de guardar esse `pageToken`, não só o último `fileId`.

---

## 4. Tarefas para a Claude Code (ordem de execução)

Cada tarefa só avança para a seguinte depois de confirmada — não construir tudo de uma vez.

- [x] **T1** — Validar 3.1 (expiração do canal) isoladamente, reportar o valor real
      **Resultado (2026-07-19):**
      - Teste 1 (`t1_watch_expiration.py`), sem pedir `expiration`: canal expira ao fim de
        **1 hora** — isto é só o *default*, não o máximo.
      - Teste 2 (`t1b_watch_expiration_24h.py`), pedindo `expiration = agora + 24h`
        explicitamente no body do `watch()`: a Google **honrou o pedido** e devolveu
        expiração a ~24h exatas (23:59:59, arredondamento normal).
      - Conclusão: `drive-watch-setup` (T7) deve sempre pedir `expiration` explícito de
        +24h. Cron de renovação pode ser **diário com margem** (ex. a cada 12h), não
        horário — bem mais simples.
- [x] **T2** — Deploy da Edge Function mínima (3.2), confirmar receção do webhook
      **Resultado (2026-07-19):** `drive-webhook-receiver` deployada no projeto `Baseline`
      (`yvsjchzvoikqlpbqsphs`) com `verify_jwt=false` (a Google não autentica-se com o
      Supabase). Testada com POST simulando os headers `X-Goog-*` — 200 OK, headers
      registados corretamente nos logs, boot em 18ms. Nota: as notificações do Drive
      **não trazem corpo JSON**, só headers — o handler não faz `req.json()`.
- [x] **T3** — Testar `repository_dispatch` manual via curl (3.3)
      **Resultado (2026-07-19):** PAT fine-grained (só `squadrats-map`, Contents: R/W,
      expira 2026-10-17) + workflow `.github/workflows/process-kml.yml`
      (`on: repository_dispatch, types: [kml-updated]`). 204 do curl, run verde em 10s.
- [x] **T4** — Ligar 3.2 + 3.3: Edge Function recebe webhook → dispara `repository_dispatch`
      **Resultado (2026-07-19):** `drive-webhook-receiver` reescrita — valida
      `X-Goog-Channel-Token` contra secret `CHANNEL_TOKEN` (403 se errado/em falta,
      única defesa do endpoint dado `verify_jwt=false`), ignora `resource-state=sync`
      sem ação, dispara `repository_dispatch` via `GH_PAT` (secret) nos restantes casos.
      Testado: sem token → 403; com token + `state=change` → 200 e run `kml-updated`
      confirmado nos Actions. Secrets `GH_PAT` e `CHANNEL_TOKEN` só existem nos
      Supabase secrets — `CHANNEL_TOKEN` também guardado local em `.secrets/channel_token.txt`
      (git-ignored) para reutilizar no `watch()` real em T7.
- [ ] **T5** — Implementar `changes.list()` + tracking de `pageToken` (3.4), guardar em tabela Supabase `drive_sync_state`
- [ ] **T6** — Escrever `process-kml.yml`: recebe `repository_dispatch`, descarrega o ficheiro certo do Drive (via `fileId` devolvido por T5), corre `pipeline.py`, commita
- [ ] **T7** — Escrever `drive-watch-setup` como function separada (pedindo sempre `expiration = +24h` explícito) + GitHub Action **a cada 12h** que a chama (renovação do canal, com margem folgada antes das 24h)
- [ ] **T8** — Teste end-to-end: exportar um KML real, confirmar que o site atualiza sozinho em minutos
- [ ] **T9** — Documentar no README do repo: como funciona, como debugar se parar de atualizar (ex: canal expirado sem renovar)

---

## 5. Checklist de credenciais/secrets necessários

| Secret | Onde | Para quê |
|---|---|---|
| Service account JSON (Drive API, scope `drive.readonly` no mínimo) | Supabase secrets | `changes.watch()`, `changes.list()`, download do ficheiro |
| GitHub PAT (scope `repo`) | Supabase secrets | `repository_dispatch` |
| Channel token (string arbitrária, gerada por nós) | Supabase secrets + comparada no payload recebido | Confirmar que o webhook não é spoofed |

Nenhum destes deve aparecer em código commitado — tudo via secrets do Supabase / GitHub Actions.

---

## 6. Fora de âmbito por agora

- Automatizar o export do KML em si (impossível sem API do Squadrats)
- % do concelho de Rio Maior noutros tipos de estatística além dos já feitos (squadrats/squadratinhos) — revisitar se surgir necessidade
- Notificações (ex: Telegram/email quando o site atualiza) — fácil de adicionar depois, não bloqueia o resto
