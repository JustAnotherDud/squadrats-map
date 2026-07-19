"""Descarrega um ficheiro do Drive pelo fileId, usando a service account
(credenciais em GOOGLE_SA_KEY — JSON em string, a mesma usada pela Edge Function).

Uso: py download_kml.py <file_id> <output_path>
"""
import argparse
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_id")
    parser.add_argument("output_path")
    args = parser.parse_args()

    raw_key = os.environ.get("GOOGLE_SA_KEY")
    if not raw_key:
        raise SystemExit("GOOGLE_SA_KEY em falta no ambiente")

    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw_key), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)

    meta = service.files().get(fileId=args.file_id, fields="id,name,size").execute()
    print(f"a descarregar {meta['name']} ({meta.get('size', '?')} bytes)")

    request = service.files().get_media(fileId=args.file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    os.makedirs(os.path.dirname(args.output_path) or ".", exist_ok=True)
    with open(args.output_path, "wb") as f:
        f.write(buf.getvalue())

    print(f"gravado em {args.output_path}")


if __name__ == "__main__":
    main()
