# sheets_utils_gh.py - Streamlit-free version for GitHub Actions
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def connect_google_sheets():
    """Connect to Google Sheets without Streamlit dependencies"""
    try:
        credentials_dict = {
            "type": "service_account",
            "project_id": os.getenv('GCP_PROJECT_ID'),
            "private_key_id": os.getenv('GCP_PRIVATE_KEY_ID'),
            "private_key": os.getenv('GCP_PRIVATE_KEY').replace('\\n', '\n'),
            "client_email": os.getenv('GCP_CLIENT_EMAIL'),
            "client_id": os.getenv('GCP_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token", 
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv('GCP_CLIENT_X509_CERT_URL')
        }
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(creds)
        
        sheet_url = os.getenv('GOOGLE_SHEET_URL')
        sheet = gc.open_by_url(sheet_url)
        return sheet
    except Exception as e:
        print(f"Google Sheets connection error: {e}")
        return None

def load_sheet(sheet_name):
    """Load sheet data without Streamlit caching"""
    try:
        sheet = connect_google_sheets()
        return sheet.worksheet(sheet_name).get_all_records()
    except Exception as e:
        print(f"Failed to load {sheet_name}: {e}")
        return []
