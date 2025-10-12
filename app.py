import os
import streamlit as st
import gspread
from datetime import datetime, date, timedelta
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials
import hashlib

# ---------------------------------------
# PAGE CONFIG
# ---------------------------------------
st.set_page_config(page_title="🎬 Movie Club", page_icon="🎥", layout="wide")

# ---------------------------------------
# LOAD SECRETS
# ---------------------------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

CLOUD_NAME = st.secrets.get("CLOUD_NAME", os.getenv("CLOUD_NAME"))
API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
API_SECRET = st.secrets.get("API_SECRET", os.getenv("API_SECRET"))
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))
ADMIN_PASS = st.secrets.get("adminPass", os.getenv("adminPass"))

# ---------------------------------------
# CLOUDINARY CONFIG
# ---------------------------------------
try:
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

# ---------------------------------------
# CONNECT GOOGLE SHEETS
# ---------------------------------------
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

# ---------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------
@st.cache_data(ttl=120)
def load_sheet(sheet_name):
    try:
        return sheet.worksheet(sheet_name).get_all_records()
    except Exception as e:
        st.warning(f"Failed to load {sheet_name}: {e}")
        return []

def reload_users():
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

def hash_password(password):
    """Simple password hashing for basic security"""
    return hashlib.sha256(password.encode()).hexdigest()

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

def login(username, password):
    users_list, users_roles, users_passwords = reload_users()
    
    if username not in users_roles:
        st.error("Invalid username")
        return False
    
    role = users_roles[username]
    stored_password = users_passwords.get(username, "")
    
    if role == "admin":
        # Admin uses the secret password
        if password != ADMIN_PASS:
            st.error("Incorrect admin password")
            return False
    else:
        # Normal user uses password from Google Sheets
        if not stored_password or stored_password == "":
            st.error("No password set for this user. Please contact admin.")
            return False
        
        if hash_password(password) != stored_password:
            st.error("Incorrect password")
            return False
    
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.role = role
    st.success(f"✅ Logged in as {username} ({role})")
    return True

# ---------------------------------------
# INITIALIZE SESSION STATE
# ---------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = "normal"
if "enable_suggestion" not in st.session_state:
    st.session_state.enable_suggestion = True
if "enable_voting" not in st.session_state:
    st.session_state.enable_voting = True
if "enable_rating" not in st.session_state:
    st.session_state.enable_rating = True

# ---------------------------------------
# LOGIN SYSTEM
# ---------------------------------------
if not st.session_state.logged_in:
    users_list, users_roles, users_passwords = reload_users()
    
    st.title("🎬 Movie Club Login")
    username = st.selectbox("Select Username", users_list)
    
    # Always show password field for all users
    password = st.text_input("Password", type="password")
    
    # Show password hint based on user type
    if username and users_roles.get(username) == "admin":
        st.info("🔐 Admin login - enter admin password")
    elif username:
        st.info("🔐 User login - enter your personal password")

    if st.button("Login"):
        if not password:
            st.error("Please enter your password")
        else:
            if login(username, password):
                st.rerun()
    st.stop()

# ---------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------
# Load page config
@st.cache_data(ttl=120)
def load_page_config():
    try:
        config_data = sheet.worksheet("Config").get_all_records()
        config_dict = {}
        for row in config_data:
            config_dict[row['key']] = row['value'].lower() == 'true'
        return config_dict
    except:
        return {}

# Get page config
page_config = load_page_config()

# Update session state with persisted config
st.session_state.enable_suggestion = page_config.get('enable_suggestion', True)
st.session_state.enable_voting = page_config.get('enable_voting', True)
st.session_state.enable_rating = page_config.get('enable_rating', True)

# Build menu based on user role and enabled pages
menu_pages = {
    "Dashboard": "🎯 Dashboard",
    "Suggest Movie": "🎥 Suggest Movie", 
    "Voting": "🗳️ Voting",
    "Rate Movies": "⭐ Rate Movies",
    "Admin Panel": "⚙️ Admin Panel",
    "Finalize Sprint": "🏁 Finalize Sprint"
}

# Filter menu based on permissions
available_pages = ["Dashboard"]  # Always show dashboard

if st.session_state.enable_suggestion or st.session_state.role == "admin":
    available_pages.append("Suggest Movie")
if st.session_state.enable_voting or st.session_state.role == "admin":
    available_pages.append("Voting") 
if st.session_state.enable_rating or st.session_state.role == "admin":
    available_pages.append("Rate Movies")

if st.session_state.role == "admin":
    available_pages += ["Admin Panel", "Finalize Sprint"]

# Display menu with icons
menu_options = [menu_pages[page] for page in available_pages]
selected_menu = st.sidebar.radio("📋 Navigation", menu_options)

# Map back to page names
selected_page = None
for page, menu_text in menu_pages.items():
    if menu_text == selected_menu:
        selected_page = page
        break

# ---------------------------------------
# SIDEBAR CONTENT
# ---------------------------------------
# Testing mode status (Visible to all users)
testing_enabled, test_date = load_testing_config()
current_date = get_current_date()
sprint_info = get_sprint_display_info()

st.sidebar.markdown("---")

if testing_enabled:
    st.sidebar.warning(f"🧪 **TESTING MODE**")
    st.sidebar.write(f"📅 Simulated Date: **{test_date}**")
    st.sidebar.info("All dates and sprints use the simulated date above")
else:
    st.sidebar.write(f"📅 **Current Date:** {current_date}")

# Display sprint information
if sprint_info:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏃‍♂️ Current Sprint")
    st.sidebar.write(f"**{sprint_info['sprint_id']}** - {sprint_info['description']}")
    st.sidebar.write(f"📅 {sprint_info['start_date']} to {sprint_info['end_date']}")
    st.sidebar.write(f"⏳ **{sprint_info['days_remaining']} days remaining**")
    
    # Sprint progress
    progress = 100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100)
    st.sidebar.progress(min(100, max(0, progress)) / 100)

st.sidebar.write(f"👤 Logged in as: **{st.session_state.username}** ({st.session_state.role})")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ---------------------------------------
# SHOW DASHBOARD CONTENT IN MAIN APP
# ---------------------------------------
# Display sprint information in header
sprint_info = get_sprint_display_info()
if sprint_info:
    st.header(f"🎬 Movie Club Dashboard - {sprint_info['sprint_id']}")
    st.write(f"**{sprint_info['description']}** | {sprint_info['start_date']} to {sprint_info['end_date']} | {sprint_info['days_remaining']} days remaining")
else:
    st.header("🎬 Movie Club Dashboard")
    st.warning("No active sprint found. Please check Sprints configuration.")

# Show testing mode indicator
testing_enabled, test_date = load_testing_config()
if testing_enabled:
    st.info(f"🧪 Testing Mode Active - Using simulated date: {test_date}")

# Load all data
users_data = load_sheet("Users")
suggestions = load_sheet("Suggestions")
ratings = load_sheet("Ratings")

# Convert to DataFrames
df_users = pd.DataFrame(users_data)
df_suggestions = pd.DataFrame(suggestions) if suggestions else pd.DataFrame()
df_ratings = pd.DataFrame(ratings) if ratings else pd.DataFrame()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Members", len(df_users))
with col2:
    st.metric("Movies Suggested", len(df_suggestions) if not df_suggestions.empty else 0)
with col3:
    if sprint_info:
        st.metric("Days Remaining", sprint_info['days_remaining'])
    else:
        st.metric("Sprint Status", "No Active Sprint")

st.markdown("---")

# Leaderboard Section
st.subheader("🏆 Leaderboard")

if not df_users.empty:
    leaderboard_data = []
    for _, user in df_users.iterrows():
        points = user.get('points', 0)
        try:
            points_float = float(points) if points != '' and points is not None else 0.0
        except (ValueError, TypeError):
            points_float = 0.0
        
        leaderboard_data.append({
            "Rank": len(leaderboard_data) + 1,
            "User": user['user_name'],
            "Total Points": points_float,
            "Role": user['role']
        })
    
    leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)
    
    for i, item in enumerate(leaderboard_data):
        item['Rank'] = i + 1
    
    df_leaderboard = pd.DataFrame(leaderboard_data)
    st.dataframe(df_leaderboard, use_container_width=True)
else:
    st.info("No user data available.")

st.markdown("---")

# Current Sprint Movies Section
st.subheader("🎬 Current Sprint Movies & Ratings")

if not df_suggestions.empty and not df_ratings.empty:
    try:
        df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
        
        if 'did_not_watch' in df_ratings.columns:
            df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(str).str.lower().isin(['true', 'yes', '1', 'y', 't'])
            df_valid_ratings = df_ratings[~df_ratings['did_not_watch']]
        else:
            df_valid_ratings = df_ratings
        
        if not df_valid_ratings.empty:
            movie_ratings = df_valid_ratings.groupby('movie_name')['rating'].agg(['mean', 'count']).round(2)
            movie_ratings = movie_ratings.rename(columns={'mean': 'Average Rating', 'count': 'Number of Ratings'})
            movie_ratings = movie_ratings.sort_values('Average Rating', ascending=False)
            
            for movie, ratings in movie_ratings.iterrows():
                avg_rating = ratings['Average Rating']
                num_ratings = int(ratings['Number of Ratings'])
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{movie}**")
                with col2:
                    st.write(f"⭐ {avg_rating}/10 ({num_ratings} ratings)")
                
                progress_value = float(avg_rating) / 10.0
                st.progress(min(1.0, max(0.0, progress_value)))
        else:
            st.info("No valid ratings available for current movies.")
            
    except Exception as e:
        st.error(f"Error processing ratings: {e}")
        st.info("Showing suggested movies without ratings:")
        for _, movie in df_suggestions.iterrows():
            st.write(f"• **{movie['movie_name']}** - {movie.get('genre', '')}")
            
elif not df_suggestions.empty:
    st.info("Movies suggested but no ratings yet.")
    for _, movie in df_suggestions.iterrows():
        st.write(f"• **{movie['movie_name']}** - {movie.get('genre', '')}")
else:
    st.info("No movies suggested for current sprint.")

st.markdown("---")

# Sprint Countdown Section
st.subheader("⏰ Sprint Progress")

if sprint_info:
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Days until sprint end", sprint_info['days_remaining'])
    with col2:
        if sprint_info['days_remaining'] > 0:
            st.write(f"Sprint ends in **{sprint_info['days_remaining']} days**")
        else:
            st.success("🎉 Sprint completed! Ready for finalization!")
    
    progress = 100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100)
    st.progress(min(100, max(0, progress)) / 100)
    st.caption(f"Current sprint progress: {progress:.1f}% ({sprint_info['total_days'] - sprint_info['days_remaining']} of {sprint_info['total_days']} days)")
else:
    st.info("No active sprint found. Please check Sprints configuration.")
