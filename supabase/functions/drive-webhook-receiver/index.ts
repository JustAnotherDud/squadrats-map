// Recetor mínimo do webhook do Google Drive (changes.watch).
//
// Notas importantes (spike T2):
// - As notificações do Drive não trazem corpo JSON — vêm só como cabeçalhos
//   HTTP (X-Goog-Channel-Id, X-Goog-Resource-State, X-Goog-Resource-Id, etc.).
//   Por isso este handler regista os headers, não faz `req.json()`.
// - A Google exige resposta 200 rápida. Este handler não deve processar nada
//   de pesado inline — só confirma a receção. O disparo do repository_dispatch
//   (T3/T4) entra aqui depois, ainda de forma síncrona mas leve (só um POST).
// - Esta function corre sem verificação de JWT (ver supabase/config.toml,
//   [functions.drive-webhook-receiver] verify_jwt = false) porque a Google
//   não sabe autenticar-se com o Supabase.

import "@supabase/functions-js/edge-runtime.d.ts";

const GOOG_HEADERS = [
  "x-goog-channel-id",
  "x-goog-channel-expiration",
  "x-goog-resource-id",
  "x-goog-resource-state",
  "x-goog-resource-uri",
  "x-goog-message-number",
];

Deno.serve(async (req: Request) => {
  const headers: Record<string, string> = {};
  for (const key of GOOG_HEADERS) {
    const value = req.headers.get(key);
    if (value) headers[key] = value;
  }

  console.log("drive-webhook-receiver: notificação recebida", JSON.stringify(headers));

  // "sync" é o primeiro ping que a Google manda ao criar o canal — confirma
  // que o endpoint está vivo, não representa uma mudança real.
  if (headers["x-goog-resource-state"] === "sync") {
    console.log("drive-webhook-receiver: ping de sincronização inicial, sem ação.");
  }

  return new Response("ok", { status: 200 });
});
