import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY = r"D:\squadrats-map\.secrets\squadrats-drive-sa.json"
FOLDER_ID = "1015cvEBGXiMFdgsCh_xvKR-Lp2nu7f1V"

creds = service_account.Credentials.from_service_account_file(
    SA_KEY, scopes=["https://www.googleapis.com/auth/drive"]
)
service = build("drive", "v3", credentials=creds)

about = service.about().get(fields="user").execute()
print("autenticado como:", about["user"]["emailAddress"])

results = service.files().list(
    q=f"'{FOLDER_ID}' in parents",
    fields="files(id, name)",
).execute()
print("ficheiros na pasta:", results.get("files"))

folder = service.files().get(fileId=FOLDER_ID, fields="id,name,capabilities").execute()
print("acesso à pasta:", json.dumps(folder, indent=2))
