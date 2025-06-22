from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

# Scope for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# File and folder info
FILE_NAME = 'warrensoutputfile.json'
FOLDER_ID = '1BUGp74aYgCIVBSWHQRtBCb4Gf4uiGkjw'  # Your Drive folder

def authenticate():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def upload_to_drive():
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': FILE_NAME,
        'parents': [FOLDER_ID]
    }
    media = MediaFileUpload(FILE_NAME, mimetype='application/json')
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f'File uploaded successfully. File ID: {file.get("id")}')

if __name__ == '__main__':
    upload_to_drive()
