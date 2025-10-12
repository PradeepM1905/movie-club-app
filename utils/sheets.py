import streamlit as st
import gspread
from datetime import datetime, date, timedelta
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import os

# Global sheet connection
_sheet = None

def get_sheet_connection():
    """Get or create Google Sheets connection"""
    global _sheet
    if _sheet is None:
        try:
            GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))
            
            if "type" in st.secrets:
                credentials_dict = {k: st.secrets[k] for k in [
                    "type", "project_id", "private_key_id", "private_key",
                    "client_email", "client_id", "auth_uri", "token_uri",
                    "auth_provider_x509_cert_url", "client_x509_cert_url"
                ]}
                gc = gspread.service_account_from_dict(credentials_dict)
            else:
                gc = gspread.service_account(filename="credentials.json")

            _sheet = gc.open_by_url(GOOGLE_SHEET_URL)
        except Exception as e:
            st.error(f"Google Sheets connection error: {e}")
            st.stop()
    return _sheet

@st.cache_data(ttl=120)
def load_sheet(sheet_name, return_dict=False):
    """Load sheet data with caching"""
    try:
        sheet_data = get_sheet_connection().worksheet(sheet_name).get_all_records()
        if return_dict and sheet_data:
            # Convert to dictionary format for config
            config_dict = {}
            for row in sheet_data:
                config_dict[row['key']] = row['value'].lower() == 'true'
            return config_dict
        return sheet_data
    except Exception as e:
        st.warning(f"Failed to load {sheet_name}: {e}")
        return [] if not return_dict else {}

def reload_users():
    """Reload users data"""
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

@st.cache_data(ttl=60)
def load_testing_config():
    """Load testing configuration from Google Sheets"""
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
                    st.warning(f"⚠️ Invalid date format in Testing sheet: {test_date_str}. Use YYYY-MM-DD or DD/MM/YYYY")
                    return False, date.today()
        return False, date.today()
    except Exception as e:
        return False, date.today()

def get_current_date():
    """Get current date - either real or from testing configuration"""
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return test_date
    else:
        return date.today()

def get_current_datetime():
    """Get current datetime - either real or from testing configuration"""
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return datetime.combine(test_date, datetime.min.time())
    else:
        return datetime.now()

@st.cache_data(ttl=120)
def get_current_sprint():
    """Get the current active sprint based on date"""
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

def get_previous_sprint():
    """Get the previous sprint for rating purposes"""
    try:
        sprints_data = load_sheet("Sprints")
        current_date = get_current_date()
        
        sorted_sprints = sorted(sprints_data, 
                              key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'), 
                              reverse=True)
        
        for sprint in sorted_sprints:
            end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()
            if end_date < current_date:
                return sprint
        
        return None
    except Exception as e:
        st.warning(f"Error loading previous sprint: {e}")
        return None

def get_sprint_display_info():
    """Get sprint information for display"""
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
    """Check if user has already suggested a movie in the current sprint"""
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

def has_user_voted_in_sprint(user_name, sprint_id):
    """Check if user has already voted in the current sprint"""
    try:
        votes = load_sheet("Voting")
        suggestions = load_sheet("Suggestions")
        sprint_movies = [s['movie_name'] for s in suggestions 
                        if (s.get('sprint') == sprint_id 
                        and s.get('user_name') != user_name)]
        
        user_votes = [v for v in votes if v.get('user_name') == user_name and v.get('movie_name') in sprint_movies]
        return len(user_votes) > 0
    except Exception as e:
        st.warning(f"Error checking user votes: {e}")
        return False

def has_user_rated_sprint_movies(user_name, sprint_id):
    """Check if user has already rated movies from a specific sprint"""
    try:
        ratings = load_sheet("Ratings")
        for rating in ratings:
            if (rating.get('user_name') == user_name and 
                rating.get('sprint') == sprint_id):
                return True
        return False
    except Exception as e:
        st.warning(f"Error checking user ratings: {e}")
        return False
