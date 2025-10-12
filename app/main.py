import os
import streamlit as st
from utils.auth import login_system, hash_password
from utils.sheets import load_sheet, reload_users, get_current_sprint, get_sprint_display_info, load_testing_config, get_current_date
from utils.common import setup_page_config

# ---------------------------------------
# PAGE CONFIG
# ---------------------------------------
setup_page_config()

# ---------------------------------------
# LOAD SECRETS & INITIALIZE
# ---------------------------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

# Load users and initialize session state
users_list, users_roles, users_passwords = reload_users()

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = "normal"

# ---------------------------------------
# LOGIN SYSTEM
# ---------------------------------------
if not st.session_state.logged_in:
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
            if login_system(username, password, users_roles, users_passwords):
                st.rerun()
    st.stop()

# ---------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------
# Load page config from Google Sheets to persist across sessions
page_config = load_sheet("Config", return_dict=True)

# Update session state with persisted config
st.session_state.enable_suggestion = page_config.get('enable_suggestion', True)
st.session_state.enable_voting = page_config.get('enable_voting', True)
st.session_state.enable_rating = page_config.get('enable_rating', True)

# Build menu based on user role and enabled pages
menu = ["Dashboard"]  # Dashboard first as default

if st.session_state.enable_suggestion or st.session_state.role == "admin":
    menu.append("Suggest Movie")
if st.session_state.enable_voting or st.session_state.role == "admin":
    menu.append("Voting")
if st.session_state.enable_rating or st.session_state.role == "admin":
    menu.append("Rate Movies")

if st.session_state.role == "admin":
    menu += ["Admin Panel", "Finalize Sprint"]

if not menu:
    menu = ["Dashboard"]  # Always show at least dashboard

# ---------------------------------------
# SIDEBAR CONTENT
# ---------------------------------------
selected = st.sidebar.radio("📋 Navigation", menu)

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
# PAGE ROUTING
# ---------------------------------------
# Note: Streamlit will automatically handle page routing based on the pages/ directory
# This main file will show the dashboard by default when no specific page is selected

if selected == "Dashboard":
    # Import and show dashboard
    from pages import Dashboard
    Dashboard.show()
elif selected == "Suggest Movie":
    from pages import Suggest_Movie
    Suggest_Movie.show()
elif selected == "Voting":
    from pages import Voting
    Voting.show()
elif selected == "Rate Movies":
    from pages import Rate_Movies
    Rate_Movies.show()
elif selected == "Admin Panel":
    from pages import Admin_Panel
    Admin_Panel.show()
elif selected == "Finalize Sprint":
    from pages import Finalize_Sprint
    Finalize_Sprint.show()
