// Leitura/escrita da linha singleton drive_sync_state via PostgREST, usando a
// service role key (auto-injetada pelo runtime — SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY
// são nomes reservados, não precisam de ser definidos como secret nosso).

const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

function restHeaders() {
  if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
    throw new Error("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY em falta no ambiente da function");
  }
  return {
    apikey: SERVICE_ROLE_KEY,
    Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
    "Content-Type": "application/json",
  };
}

export interface SyncState {
  page_token: string;
  channel_id: string | null;
  channel_resource_id: string | null;
  channel_expiration: string | null;
}

export async function getSyncState(): Promise<SyncState> {
  const resp = await fetch(
    `${SUPABASE_URL}/rest/v1/drive_sync_state?id=eq.1&select=page_token,channel_id,channel_resource_id,channel_expiration`,
    { headers: restHeaders() },
  );
  if (!resp.ok) throw new Error(`falha a ler drive_sync_state: ${resp.status} ${await resp.text()}`);
  const rows = await resp.json();
  if (!rows.length) throw new Error("drive_sync_state não tem a linha singleton — corre o seed (T5 spike)");
  return rows[0];
}

export async function getPageToken(): Promise<string> {
  return (await getSyncState()).page_token;
}

export async function updatePageToken(pageToken: string): Promise<void> {
  await patchState({ page_token: pageToken });
}

export async function updateChannel(fields: {
  channel_id: string;
  channel_resource_id: string;
  channel_expiration: string;
}): Promise<void> {
  await patchState(fields);
}

async function patchState(fields: Record<string, unknown>): Promise<void> {
  const resp = await fetch(`${SUPABASE_URL}/rest/v1/drive_sync_state?id=eq.1`, {
    method: "PATCH",
    headers: restHeaders(),
    body: JSON.stringify({ ...fields, updated_at: new Date().toISOString() }),
  });
  if (!resp.ok) throw new Error(`falha a atualizar drive_sync_state: ${resp.status} ${await resp.text()}`);
}
