create table drive_sync_state (
  id int primary key default 1 check (id = 1),  -- singleton, força 1 linha só
  page_token text not null,
  channel_id text,                  -- id do canal watch ativo (T7 precisa para parar o antigo ao renovar)
  channel_expiration timestamptz,   -- quando expira, para debug ("porque parou de sincronizar?")
  updated_at timestamptz default now()
);

alter table drive_sync_state enable row level security;
-- sem policies: só a service role key (usada pela Edge Function) acede, ignorando RLS.
-- a anon key exposta no browser da app de nutrição não consegue ler nem escrever aqui.
