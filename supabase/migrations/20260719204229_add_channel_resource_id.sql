-- channels.stop() exige id + resourceId; só guardávamos channel_id (T5).
-- Sem isto não dá para parar o canal antigo ao renovar (T7).
alter table drive_sync_state add column channel_resource_id text;
