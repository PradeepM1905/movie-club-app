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

# Initialize page control flags
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
# PAGE ROUTING - Show Dashboard by default
# ---------------------------------------
# Since we're using Streamlit's native multi-page, we'll just show dashboard here
# Other pages will be automatically handled by Streamlit

if selected_page == "Dashboard" or selected_page is None:
    # Import and show dashboard content directly
    import pandas as pd
    
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

else:
    # For other pages, Streamlit will automatically route to the pages/ directory
    # We just need to make sure the user has permission
    st.info(f"Navigate to {selected_menu} using the sidebar menu.")
