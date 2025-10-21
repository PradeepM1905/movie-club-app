import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# ---------------------------------------
# CONNECT GOOGLE SHEETS
# ---------------------------------------
def connect_google_sheets():
    """Connect to Google Sheets and return the sheet object"""
    try:
        print("🔍 [GOOGLE SHEETS API CALL] Connecting to Google Sheets...")
        if "type" in st.secrets:
            credentials_dict = {k: st.secrets[k] for k in [
                "type", "project_id", "private_key_id", "private_key",
                "client_email", "client_id", "auth_uri", "token_uri",
                "auth_provider_x509_cert_url", "client_x509_cert_url"
            ]}
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
            gc = gspread.service_account(filename="credentials.json")

        GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))
        sheet = gc.open_by_url(GOOGLE_SHEET_URL)
        return sheet
    except Exception as e:
        st.error(f"Google Sheets connection error: {e}")
        st.stop()

# ---------------------------------------
# LOAD SHEETS SAFELY WITH CACHING
# ---------------------------------------
@st.cache_data(ttl=120)
def load_sheet(sheet_name):  # Remove sheet parameter
    try:
        print(f"🔍 [GOOGLE SHEETS API CALL] Loading sheet: {sheet_name}")
        sheet = connect_google_sheets()  # Create sheet inside function
        return sheet.worksheet(sheet_name).get_all_records()
    except Exception as e:
        st.warning(f"Failed to load {sheet_name}: {e}")
        return []

def reload_users():  # Remove sheet parameter
    users_data = load_sheet("Users")
    users_roles = {}
    users_list = []
    users_passwords = {}

    for row in users_data:
        uname = row.get("user_name")
        role = row.get("role", "normal").lower()
        password = row.get("password") or row.get("pass") or row.get("pwd") or ""

        if uname:
            users_list.append(uname)
            users_roles[uname] = role
            users_passwords[uname] = password

    return users_list, users_roles, users_passwords
