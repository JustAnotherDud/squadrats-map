"""Semeia a linha singleton de drive_sync_state com o startPageToken atual.
Corre uma vez, manualmente — a partir daqui é a Edge Function que mantém o token atualizado.
"""
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY = r"D:\squadrats-map\.secrets\squadrats-drive-sa.json"

creds = service_account.Credentials.from_service_account_file(
    SA_KEY, scopes=["https://www.googleapis.com/auth/drive.readonly"]
)
service = build("drive", "v3", credentials=creds)

start_token = service.changes().getStartPageToken().execute()["startPageToken"]
print("startPageToken atual:", start_token)
print()
print("SQL para inserir (correr via mcp supabase execute_sql):")
print(f"insert into drive_sync_state (id, page_token) values (1, '{start_token}') "
      f"on conflict (id) do update set page_token = excluded.page_token, updated_at = now();")
