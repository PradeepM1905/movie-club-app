import os
import streamlit as st
import cloudinary
from datetime import timedelta

# Import the modules
from login_system import initialize_session_state, render_login_page, hash_password
from sheets_utils import connect_google_sheets, reload_users, load_sheet
from sprint_management import get_sprint_display_info, load_testing_config, get_current_date, get_previous_sprint_quiz_data
from page_handlers import render_dashboard, render_suggest_movie, render_voting, render_rate_movies
from admin_panel import render_admin_panel
from finalize_sprint import render_finalize_sprint

# ---------------------------------------
# PAGE CONFIG
# ---------------------------------------
st.set_page_config(page_title="🎬 Movie-Club-", page_icon="🎥", layout="wide")

# ---------------------------------------
# LOAD SECRETS
# ---------------------------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

CLOUD_NAME = st.secrets.get("CLOUD_NAME", os.getenv("CLOUD_NAME"))
API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
API_SECRET = st.secrets.get("API_SECRET", os.getenv("API_SECRET"))
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
sheet = connect_google_sheets()

# ---------------------------------------
# INITIALIZE LOGIN SYSTEM
# ---------------------------------------
initialize_session_state()
users_list, users_roles, users_passwords = reload_users()

# Check if user is logged in
if not st.session_state.logged_in:
    render_login_page(users_list, users_roles, users_passwords, ADMIN_PASS)
    st.stop()

# ---------------------------------------
# ADMIN CONTROL FLAGS
# ---------------------------------------
if "enable_suggestion" not in st.session_state:
    st.session_state.enable_suggestion = True
if "enable_voting" not in st.session_state:
    st.session_state.enable_voting = False  # Start with voting disabled
if "enable_rating" not in st.session_state:
    st.session_state.enable_rating = True

# NEW: Voting phase control
if "voting_phase" not in st.session_state:
    st.session_state.voting_phase = "suggestion"  # suggestion -> voting -> results

# ---------------------------------------
# SIDEBAR NAVIGATION - UPDATE THIS SECTION
# ---------------------------------------
# Update page config loading to include voting phase
@st.cache_data(ttl=120)
def load_page_config():
    try:
        config_data = load_sheet("Config")
        config_dict = {}
        for row in config_data:
            if row['key'] == 'voting_phase':
                st.session_state.voting_phase = row['value']
            else:
                config_dict[row['key']] = row['value'].lower() == 'true'
        return config_dict
    except:
        return {}

# Get page config
page_config = load_page_config()

# Update session state with persisted config
st.session_state.enable_suggestion = page_config.get('enable_suggestion', True)
st.session_state.enable_voting = page_config.get('enable_voting', False)  # Default to False
st.session_state.enable_rating = page_config.get('enable_rating', True)

# Build menu based on user role, enabled pages, and voting phase
menu = ["Dashboard"]

# Show suggestion page based on voting phase
current_phase = st.session_state.get('voting_phase', 'suggestion')

# ADMIN USERS: Show all pages regardless of phase
if st.session_state.role == "admin":
    menu.append("Suggest Movie")
    menu.append("Voting")  # Admin always sees Voting page
    menu.append("Rate Movies")
    menu.append("Admin Panel")
    menu.append("Finalize Sprint")
else:
    # NORMAL USERS: Page access controlled by phase and enabled flags
    if st.session_state.enable_suggestion:
        menu.append("Suggest Movie")
    
    # Show voting page only if enabled AND in voting phase
    if st.session_state.enable_voting and current_phase == "voting":
        menu.append("Voting")
    
    # Show rating page only if allowed for current/previous sprint
    if st.session_state.enable_rating:
        from sprint_management import get_current_sprint, get_previous_sprint, is_rating_allowed_for_sprint
        current_sprint = get_current_sprint()
        previous_sprint = get_previous_sprint()
        rating_sprint = previous_sprint if previous_sprint else current_sprint
        
        if is_rating_allowed_for_sprint(rating_sprint):
            menu.append("Rate Movies")

if not menu:
    menu = ["Dashboard"]

selected = st.sidebar.radio("📋 Navigation", menu)

# Add voting phase indicator in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Current Phase")
st.sidebar.write(f"**{current_phase.upper()} PHASE**")

# ---------------------------------------
# TESTING MODE STATUS (Visible to all users)
# ---------------------------------------
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
# PAGE ROUTING
# ---------------------------------------
if selected == "Dashboard":
    render_dashboard()
elif selected == "Suggest Movie":
    render_suggest_movie()
elif selected == "Voting":
    render_voting()
elif selected == "Rate Movies":
    render_rate_movies()
elif selected == "Admin Panel":
    render_admin_panel(hash_password)
elif selected == "Finalize Sprint":
    render_finalize_sprint(hash_password)
