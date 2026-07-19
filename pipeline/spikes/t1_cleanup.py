from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY = r"D:\squadrats-map\.secrets\squadrats-drive-sa.json"
CHANNEL_ID = "ce6a6bca-62aa-4943-8aec-4a32cbdba075"
RESOURCE_ID = "z5aSSpWh_3cBGTQMIl065DJYg2M"

creds = service_account.Credentials.from_service_account_file(
    SA_KEY, scopes=["https://www.googleapis.com/auth/drive"]
)
service = build("drive", "v3", credentials=creds)
service.channels().stop(body={"id": CHANNEL_ID, "resourceId": RESOURCE_ID}).execute()
print("canal de teste parado.")
