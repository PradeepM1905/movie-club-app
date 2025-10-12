import os
import streamlit as st
import gspread
from datetime import datetime, date, timedelta
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials
import hashlib

st.set_page_config(page_title="Suggest Movie", page_icon="🎥")

# ---------------------------------------
# REPEAT ALL NECESSARY CONFIG AND FUNCTIONS
# ---------------------------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

CLOUD_NAME = st.secrets.get("CLOUD_NAME", os.getenv("CLOUD_NAME"))
API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
API_SECRET = st.secrets.get("API_SECRET", os.getenv("API_SECRET"))
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))

try:
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

try:
    if "type" in st.secrets:
        credentials_dict = {k: st.secrets[k] for k in [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri",
            "auth_provider_x509_cert_url", "client_x509_cert_url"
        ]}
        gc = gspread.service_account_from_dict(credentials_dict)
    else:
        gc = gspread.service_account(filename="credentials.json")

    sheet = gc.open_by_url(GOOGLE_SHEET_URL)
except Exception as e:
    st.error(f"Google Sheets connection error: {e}")
    st.stop()

@st.cache_data(ttl=120)
def load_sheet(sheet_name):
    try:
        return sheet.worksheet(sheet_name).get_all_records()
    except Exception as e:
        st.warning(f"Failed to load {sheet_name}: {e}")
        return []

@st.cache_data(ttl=60)
def load_testing_config():
    try:
        testing_data = load_sheet("Testing")
        if not testing_data or len(testing_data) == 0:
            return False, date.today()
            
        if testing_data and len(testing_data) > 0:
            test_config = testing_data[0]
            if not test_config:
                return False, date.today()
                
            test_date_str = test_config.get('date', '').strip()
            
            if not test_date_str:
                return False, date.today()
            
            try:
                test_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
                return True, test_date
            except ValueError:
                try:
                    test_date = datetime.strptime(test_date_str, '%d/%m/%Y').date()
                    return True, test_date
                except ValueError:
                    return False, date.today()
        return False, date.today()
    except Exception as e:
        return False, date.today()

def get_current_date():
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return test_date
    else:
        return date.today()

def get_current_datetime():
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return datetime.combine(test_date, datetime.min.time())
    else:
        return datetime.now()

@st.cache_data(ttl=120)
def get_current_sprint():
    try:
        sprints_data = load_sheet("Sprints")
        current_date = get_current_date()
        
        for sprint in sprints_data:
            start_date = datetime.strptime(sprint['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()
            
            if start_date <= current_date <= end_date:
                return sprint
        
        if sprints_data:
            sorted_sprints = sorted(sprints_data, 
                                  key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'), 
                                  reverse=True)
            return sorted_sprints[0]
        
        return None
    except Exception as e:
        st.warning(f"Error loading sprints: {e}")
        return None

def get_sprint_display_info():
    current_sprint = get_current_sprint()
    if current_sprint:
        current_date = get_current_date()
        sprint_end = datetime.strptime(current_sprint['end_date'], '%Y-%m-%d').date()
        days_remaining = (sprint_end - current_date).days
        
        return {
            'sprint_id': current_sprint['sprint_id'],
            'description': current_sprint.get('description', ''),
            'start_date': current_sprint['start_date'],
            'end_date': current_sprint['end_date'],
            'days_remaining': max(0, days_remaining),
            'total_days': (sprint_end - datetime.strptime(current_sprint['start_date'], '%Y-%m-%d').date()).days + 1
        }
    return None

def has_user_suggested_in_sprint(user_name, sprint_id):
    try:
        suggestions = load_sheet("Suggestions")
        for suggestion in suggestions:
            if (suggestion.get('user_name') == user_name and 
                suggestion.get('sprint') == sprint_id):
                return True
        return False
    except Exception as e:
        st.warning(f"Error checking user suggestions: {e}")
        return False

def main():
    if not st.session_state.get('enable_suggestion', True) and st.session_state.get('role') != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        return

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()
    
    if sprint_info and current_sprint:
        st.header(f"🎥 Suggest a Movie - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | {sprint_info['days_remaining']} days remaining")
    else:
        st.header("🎥 Suggest a Movie")
        st.warning("No active sprint found. Movie suggestions will not be associated with any sprint.")
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    user_name = st.session_state.username
    
    # Check if user has already suggested in this sprint
    if current_sprint and has_user_suggested_in_sprint(user_name, current_sprint['sprint_id']):
        st.success("✅ You have already suggested a movie for this sprint!")
        st.info("You can only suggest one movie per sprint.")
        return
    
    movie_name = st.text_input("Movie Name")
    genre = st.text_input("Genre")
    description = st.text_area("Where to watch it?")
    image = st.file_uploader("Upload Poster (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Submit Suggestion"):
        if not movie_name:
            st.error("Please provide a movie name!")
        else:
            image_url = ""
            if image:
                try:
                    result = cloudinary.uploader.upload(image)
                    image_url = result.get('secure_url', '')
                except Exception as e:
                    st.warning(f"Cloudinary upload failed: {e}")

            try:
                ws = sheet.worksheet("Suggestions")
                current_timestamp = get_current_datetime()
                sprint_id = current_sprint['sprint_id'] if current_sprint else ""
                
                ws.append_row([
                    sprint_id,
                    user_name,
                    movie_name,
                    genre,
                    description,
                    image_url,
                    str(current_timestamp)
                ])
                st.success("✅ Movie suggestion submitted!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.warning(f"Failed to write suggestion: {e}")

if __name__ == "__main__":
    main()
