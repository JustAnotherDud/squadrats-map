import json
import uuid
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA_KEY = r"D:\squadrats-map\.secrets\squadrats-drive-sa.json"

creds = service_account.Credentials.from_service_account_file(
    SA_KEY, scopes=["https://www.googleapis.com/auth/drive"]
)
service = build("drive", "v3", credentials=creds)

start_token = service.changes().getStartPageToken().execute()
print("startPageToken:", start_token)

channel_id = str(uuid.uuid4())
body = {
    "id": channel_id,
    "type": "web_hook",
    # endpoint fictício só para ver o que a Google devolve antes de validar entrega —
    # se isto rejeitar por falta de verificação de domínio, é o que T2 precisa de resolver.
    "address": "https://example.com/squadrats-webhook-placeholder",
}

try:
    resp = service.changes().watch(
        pageToken=start_token["startPageToken"],
        body=body,
    ).execute()
    print("resposta watch():", json.dumps(resp, indent=2))
    if "expiration" in resp:
        import datetime
        exp_ms = int(resp["expiration"])
        print("expiration (ms):", exp_ms)
        print("expiration (UTC):", datetime.datetime.utcfromtimestamp(exp_ms / 1000))
except HttpError as e:
    print("HttpError:", e.resp.status, e.reason)
    print(e.content.decode() if hasattr(e.content, "decode") else e.content)
