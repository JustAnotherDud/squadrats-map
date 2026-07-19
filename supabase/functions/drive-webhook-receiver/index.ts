// Recetor do webhook do Google Drive (changes.watch) -> filtra mudanças
// relevantes (KML novo na pasta squadrats-exports) -> dispara repository_dispatch.
//
// Notas importantes:
// - As notificações do Drive não trazem corpo JSON — vêm só como cabeçalhos
//   HTTP (X-Goog-Channel-Id, X-Goog-Resource-State, X-Goog-Channel-Token, etc.).
//   O webhook só diz "algo mudou", não o quê — daí o changes.list() a seguir.
// - `verify_jwt=false` (config.toml) porque a Google não sabe autenticar-se com
//   o Supabase. A ÚNICA defesa do endpoint é o X-Goog-Channel-Token.
// - changes.list() pode devolver qualquer mudança visível pela service account
//   (renomeações, mudanças de permissão, etc.) — filtramos para só reagir a
//   ficheiros .kml, dentro da pasta squadrats-exports, não removidos. Tudo o
//   resto: atualiza o pageToken e sai sem disparar dispatch.

import "@supabase/functions-js/edge-runtime.d.ts";
import { getDriveAccessToken } from "./google_auth.ts";
import { getPageToken, updatePageToken } from "./sync_state.ts";

const GITHUB_OWNER = "JustAnotherDud";
const GITHUB_REPO = "squadrats-map";
const DISPATCH_EVENT_TYPE = "kml-updated";
const SQUADRATS_FOLDER_ID = "1015cvEBGXiMFdgsCh_xvKR-Lp2nu7f1V";
const DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly";

const CHANNEL_TOKEN = Deno.env.get("CHANNEL_TOKEN");
const GH_PAT = Deno.env.get("GH_PAT");

interface DriveChange {
  fileId: string;
  removed?: boolean;
  file?: { name?: string; parents?: string[]; mimeType?: string };
}

async function listRelevantChanges(): Promise<{ relevant: DriveChange[]; newPageToken: string }> {
  const accessToken = await getDriveAccessToken(DRIVE_SCOPE);
  let pageToken = await getPageToken();
  const relevant: DriveChange[] = [];
  let newPageToken = pageToken;

  while (true) {
    const url = new URL("https://www.googleapis.com/drive/v3/changes");
    url.searchParams.set("pageToken", pageToken);
    url.searchParams.set(
      "fields",
      "nextPageToken,newStartPageToken,changes(fileId,removed,file(name,parents,mimeType))",
    );

    const resp = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!resp.ok) throw new Error(`changes.list falhou: ${resp.status} ${await resp.text()}`);
    const data = await resp.json();

    for (const change of (data.changes ?? []) as DriveChange[]) {
      if (change.removed) continue;
      const name = change.file?.name ?? "";
      const parents = change.file?.parents ?? [];
      if (name.toLowerCase().endsWith(".kml") && parents.includes(SQUADRATS_FOLDER_ID)) {
        relevant.push(change);
      }
    }

    if (data.nextPageToken) {
      pageToken = data.nextPageToken;
      continue;
    }
    newPageToken = data.newStartPageToken ?? pageToken;
    break;
  }

  return { relevant, newPageToken };
}

async function dispatchGithub(change: DriveChange): Promise<void> {
  if (!GH_PAT) throw new Error("GH_PAT em falta, não consigo disparar o dispatch.");

  const resp = await fetch(
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
        client_payload: { fileId: change.fileId, fileName: change.file?.name },
      }),
    },
  );

  if (!resp.ok) {
    throw new Error(`repository_dispatch falhou: ${resp.status} ${await resp.text()}`);
  }
}

Deno.serve(async (req: Request) => {
  const channelToken = req.headers.get("x-goog-channel-token");
  const resourceState = req.headers.get("x-goog-resource-state");
  const channelId = req.headers.get("x-goog-channel-id");

  if (!CHANNEL_TOKEN || channelToken !== CHANNEL_TOKEN) {
    console.warn("drive-webhook-receiver: channel token inválido ou em falta, a ignorar pedido.");
    return new Response("forbidden", { status: 403 });
  }

  console.log("drive-webhook-receiver: notificação válida", JSON.stringify({ channelId, resourceState }));

  if (resourceState === "sync") {
    console.log("drive-webhook-receiver: ping de sincronização inicial, sem ação.");
    return new Response("ok", { status: 200 });
  }

  try {
    const { relevant, newPageToken } = await listRelevantChanges();
    console.log(`drive-webhook-receiver: ${relevant.length} mudança(s) relevante(s) de KML.`);

    for (const change of relevant) {
      console.log("drive-webhook-receiver: a disparar dispatch para", change.file?.name, change.fileId);
      await dispatchGithub(change);
    }

    await updatePageToken(newPageToken);

    return new Response("ok", { status: 200 });
  } catch (err) {
    console.error("drive-webhook-receiver: erro a processar mudanças", err);
    return new Response("internal error", { status: 500 });
  }
});
