from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# File to upload
FILE_NAME = "warrensoutputfile.json"
MIME_TYPE = "application/json"

# ID of your shared Google Drive folder
FOLDER_ID = "1BUGp74aYgCIVBSWHQRtBCb4Gf4uiGkjw"

# Load credentials from service account
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = "service_account.json"

def upload_file_to_drive():
    # Authenticate with service account
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    # Build the Drive service
    service = build('drive', 'v3', credentials=creds)

    # Prepare file metadata
    file_metadata = {
        'name': FILE_NAME,
        'parents': [FOLDER_ID]
    }

    # Prepare file for upload
    media = MediaFileUpload(FILE_NAME, mimetype=MIME_TYPE)

    # Upload the file
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"✅ File uploaded to Google Drive. File ID: {uploaded_file.get('id')}")

if __name__ == '__main__':
    upload_file_to_drive()
