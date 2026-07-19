import json
import time
import uuid
import datetime
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
requested_expiration_ms = int((time.time() + 24 * 3600) * 1000)
print("expiration pedida (ms):", requested_expiration_ms,
      "=", datetime.datetime.fromtimestamp(requested_expiration_ms / 1000, datetime.timezone.utc))

body = {
    "id": channel_id,
    "type": "web_hook",
    "address": "https://example.com/squadrats-webhook-placeholder",
    "expiration": str(requested_expiration_ms),
}

try:
    resp = service.changes().watch(
        pageToken=start_token["startPageToken"],
        body=body,
    ).execute()
    print("resposta watch():", json.dumps(resp, indent=2))
    if "expiration" in resp:
        exp_ms = int(resp["expiration"])
        exp_dt = datetime.datetime.fromtimestamp(exp_ms / 1000, datetime.timezone.utc)
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        print("expiration devolvida (UTC):", exp_dt)
        print("duração real do canal:", exp_dt - now_dt)

    # limpar o canal de teste já a seguir
    service.channels().stop(body={"id": resp["id"], "resourceId": resp["resourceId"]}).execute()
    print("canal de teste parado.")
except HttpError as e:
    print("HttpError:", e.resp.status, e.reason)
    print(e.content.decode() if hasattr(e.content, "decode") else e.content)
