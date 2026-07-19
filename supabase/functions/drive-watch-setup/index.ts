// Cria/renova o canal changes.watch() do Drive. Chamada pelo GitHub Actions
// (cron a cada 12h), NUNCA pela Google — por isso é mais fechada que a
// drive-webhook-receiver: exige X-Setup-Token válido, sem isso qualquer pessoa
// com o URL conseguiria recriar/parar os canais à vontade (DoS do pipeline).
//
// Ordem das operações, de propósito: cria o canal novo primeiro, confirma
// sucesso, só DEPOIS pára o antigo. Falhar para o lado de "canal a mais"
// (inofensivo — dispatches duplicados são absorvidos pela idempotência do T6)
// em vez de "canal a menos" (ficar sem canal nenhum até ao próximo cron —
// janela surda de até 12h).

import "@supabase/functions-js/edge-runtime.d.ts";
import { getDriveAccessToken } from "../_shared/google_auth.ts";
import { getSyncState, updateChannel } from "../_shared/sync_state.ts";

const SETUP_TOKEN = Deno.env.get("SETUP_TOKEN");
const CHANNEL_TOKEN = Deno.env.get("CHANNEL_TOKEN");
const WEBHOOK_URL = Deno.env.get("SUPABASE_URL")
  ? `${Deno.env.get("SUPABASE_URL")}/functions/v1/drive-webhook-receiver`
  : undefined;
const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly";
const CHANNEL_LIFETIME_MS = 24 * 3600 * 1000;

async function createChannel(accessToken: string, pageToken: string) {
  const channelId = crypto.randomUUID();
  const expiration = Date.now() + CHANNEL_LIFETIME_MS;

  const resp = await fetch(
    `https://www.googleapis.com/drive/v3/changes/watch?pageToken=${encodeURIComponent(pageToken)}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: channelId,
        type: "web_hook",
        address: WEBHOOK_URL,
        token: CHANNEL_TOKEN,
        expiration: String(expiration),
      }),
    },
  );

  if (!resp.ok) {
    throw new Error(`changes.watch falhou: ${resp.status} ${await resp.text()}`);
  }
  return await resp.json() as { id: string; resourceId: string; expiration: string };
}

async function stopChannel(accessToken: string, id: string, resourceId: string) {
  const resp = await fetch("https://www.googleapis.com/drive/v3/channels/stop", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ id, resourceId }),
  });
  if (!resp.ok) {
    // não relançar — um stop falhado deixa um canal órfão inofensivo (ver nota
    // no topo do ficheiro), não deve fazer o pedido inteiro falhar.
    console.warn(`channels.stop falhou (canal antigo pode continuar ativo): ${resp.status} ${await resp.text()}`);
    return false;
  }
  return true;
}

Deno.serve(async (req: Request) => {
  const setupToken = req.headers.get("x-setup-token");
  if (!SETUP_TOKEN || setupToken !== SETUP_TOKEN) {
    console.warn("drive-watch-setup: X-Setup-Token inválido ou em falta, a recusar.");
    return new Response("forbidden", { status: 403 });
  }

  if (!WEBHOOK_URL || !CHANNEL_TOKEN) {
    return new Response("server misconfigured (WEBHOOK_URL/CHANNEL_TOKEN em falta)", { status: 500 });
  }

  try {
    const state = await getSyncState();
    const accessToken = await getDriveAccessToken(DRIVE_SCOPE);

    const newChannel = await createChannel(accessToken, state.page_token);
    console.log("drive-watch-setup: canal novo criado", newChannel.id, "expira em", newChannel.expiration);

    await updateChannel({
      channel_id: newChannel.id,
      channel_resource_id: newChannel.resourceId,
      channel_expiration: new Date(Number(newChannel.expiration)).toISOString(),
    });

    let oldStopped: boolean | "skipped" = "skipped";
    if (
      state.channel_id && state.channel_resource_id &&
      state.channel_id !== newChannel.id
    ) {
      oldStopped = await stopChannel(accessToken, state.channel_id, state.channel_resource_id);
    }

    return Response.json({
      ok: true,
      newChannelId: newChannel.id,
      expiration: new Date(Number(newChannel.expiration)).toISOString(),
      oldChannelStopped: oldStopped,
    });
  } catch (err) {
    console.error("drive-watch-setup: erro", err);
    return new Response(`internal error: ${err}`, { status: 500 });
  }
});
