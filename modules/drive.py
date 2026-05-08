"""
Google Drive connector.
Fetches .docx script files using Adset Code (e.g. GAI647) as the filename key.
Files are downloaded temporarily, text extracted, then deleted immediately.
"""

import os
import tempfile
from docx import Document


def get_drive_service(credentials_dict):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(credentials_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds)


def list_scripts_in_folder(service, folder_id):
    results = service.files().list(q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' and trashed=false", fields="files(id, name)", pageSize=200).execute()
    return {f["name"].replace(".docx", "").strip(): f["id"] for f in results.get("files", [])}


def extract_text_from_drive_file(service, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    import io
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    buffer.seek(0)
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(buffer.read()); tmp_path = tmp.name
    try:
        doc = Document(tmp_path)
        text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    finally: os.unlink(tmp_path)
    return text
