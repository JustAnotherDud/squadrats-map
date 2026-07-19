from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SA_KEY = r"D:\squadrats-map\.secrets\squadrats-drive-sa.json"
FOLDER_ID = "1015cvEBGXiMFdgsCh_xvKR-Lp2nu7f1V"
KML_PATH = r"D:\squadrats-map\data\sample-export.kml"

# a SA só tem Viewer na pasta agora — para este teste de upload precisamos
# temporariamente de escrita; se falhar por permissão, é esperado (ver nota no chat).
creds = service_account.Credentials.from_service_account_file(
    SA_KEY, scopes=["https://www.googleapis.com/auth/drive"]
)
service = build("drive", "v3", credentials=creds)

media = MediaFileUpload(KML_PATH, mimetype="application/vnd.google-earth.kml+xml")
try:
    f = service.files().create(
        body={"name": "squadrats-2026-07-19-teste.kml", "parents": [FOLDER_ID]},
        media_body=media,
        fields="id,name",
    ).execute()
    print("upload OK:", f)
except Exception as e:
    print("upload falhou (esperado se SA só tem Viewer):", e)
