// Recetor do webhook do Google Drive (changes.watch) -> dispara repository_dispatch no GitHub.
//
// Notas importantes:
// - As notificações do Drive não trazem corpo JSON — vêm só como cabeçalhos
//   HTTP (X-Goog-Channel-Id, X-Goog-Resource-State, X-Goog-Channel-Token, etc.).
// - `verify_jwt=false` (config.toml) porque a Google não sabe autenticar-se com
//   o Supabase. A ÚNICA defesa do endpoint é o X-Goog-Channel-Token, que tem de
//   bater certo com o secret CHANNEL_TOKEN gerado por nós — sem isso, qualquer
//   pessoa que descubra o URL da function dispara builds no repo à vontade.
// - A Google exige resposta 200 rápida — o disparo do repository_dispatch é um
//   único POST leve, não faz nenhum processamento pesado aqui.

import "@supabase/functions-js/edge-runtime.d.ts";

const GITHUB_OWNER = "JustAnotherDud";
const GITHUB_REPO = "squadrats-map";
const DISPATCH_EVENT_TYPE = "kml-updated";

const CHANNEL_TOKEN = Deno.env.get("CHANNEL_TOKEN");
const GH_PAT = Deno.env.get("GH_PAT");

Deno.serve(async (req: Request) => {
  const channelToken = req.headers.get("x-goog-channel-token");
  const resourceState = req.headers.get("x-goog-resource-state");
  const channelId = req.headers.get("x-goog-channel-id");

  if (!CHANNEL_TOKEN || channelToken !== CHANNEL_TOKEN) {
    console.warn("drive-webhook-receiver: channel token inválido ou em falta, a ignorar pedido.");
    return new Response("forbidden", { status: 403 });
  }

  console.log(
    "drive-webhook-receiver: notificação válida",
    JSON.stringify({ channelId, resourceState }),
  );

  // "sync" é o primeiro ping ao criar o canal — não representa uma mudança real.
  if (resourceState === "sync") {
    console.log("drive-webhook-receiver: ping de sincronização inicial, sem ação.");
    return new Response("ok", { status: 200 });
  }

  if (!GH_PAT) {
    console.error("drive-webhook-receiver: GH_PAT em falta, não consigo disparar o dispatch.");
    return new Response("server misconfigured", { status: 500 });
  }

  const dispatchResp = await fetch(
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${GH_PAT}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        event_type: DISPATCH_EVENT_TYPE,
        client_payload: { resourceState, channelId },
      }),
    },
  );

  if (!dispatchResp.ok) {
    const body = await dispatchResp.text();
    console.error("drive-webhook-receiver: falha no repository_dispatch", dispatchResp.status, body);
    return new Response("dispatch failed", { status: 502 });
  }

  console.log("drive-webhook-receiver: repository_dispatch disparado com sucesso.");
  return new Response("ok", { status: 200 });
});
