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
# LOAD SHEETS SAFELY WITH CACHING
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

# ---------------------------------------
# PASSWORD HASHING
# ---------------------------------------
def hash_password(password):
    """Simple password hashing for basic security"""
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------------------------------
# TESTING MODE FROM GOOGLE SHEETS
# ---------------------------------------
@st.cache_data(ttl=60)
def load_testing_config():
    """Load testing configuration from Google Sheets"""
    try:
        testing_data = load_sheet("Testing")
        if testing_data and len(testing_data) > 0:
            # Get the first row which should contain the test date
            test_config = testing_data[0]
            test_date_str = test_config.get('date', '').strip()
            
            if test_date_str:
                try:
                    # Parse date from string (assuming YYYY-MM-DD format)
                    test_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
                    return True, test_date
                except ValueError:
                    # Try other common date formats
                    try:
                        test_date = datetime.strptime(test_date_str, '%d/%m/%Y').date()
                        return True, test_date
                    except ValueError:
                        st.warning(f"⚠️ Invalid date format in Testing sheet: {test_date_str}. Use YYYY-MM-DD or DD/MM/YYYY")
                        return False, date.today()
        return False, date.today()
    except Exception as e:
        # If Testing sheet doesn't exist or has errors, return normal mode
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

# ---------------------------------------
# SPRINT MANAGEMENT
# ---------------------------------------
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
        
        # If no active sprint found, return the most recent past sprint or None
        if sprints_data:
            # Sort sprints by end_date descending to get the most recent one
            sorted_sprints = sorted(sprints_data, 
                                  key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'), 
                                  reverse=True)
            return sorted_sprints[0]
        
        return None
    except Exception as e:
        st.warning(f"Error loading sprints: {e}")
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

# ---------------------------------------
# LOGIN SYSTEM
# ---------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = "normal"

users_list, users_roles, users_passwords = reload_users()

def login(username, password):
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
            if login(username, password):
                st.rerun()
    st.stop()

# ---------------------------------------
# ADMIN CONTROL FLAGS
# ---------------------------------------
if "enable_suggestion" not in st.session_state:
    st.session_state.enable_suggestion = True
if "enable_voting" not in st.session_state:
    st.session_state.enable_voting = True
if "enable_rating" not in st.session_state:
    st.session_state.enable_rating = True

# ---------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------
# Load page config from Google Sheets to persist across sessions
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

selected = st.sidebar.radio("📋 Navigation", menu)

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
# PAGE: DASHBOARD
# ---------------------------------------
if selected == "Dashboard":
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
        # Create leaderboard from Users sheet points with proper error handling
        leaderboard_data = []
        for _, user in df_users.iterrows():
            # Safely handle points conversion
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
        
        # Sort by points descending with safe comparison
        leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)
        
        # Update ranks after sorting
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
        # Calculate average ratings for each movie with error handling
        try:
            df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
            
            # Filter out "did not watch" ratings - handle different data types
            if 'did_not_watch' in df_ratings.columns:
                # Convert did_not_watch to boolean safely
                df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(str).str.lower().isin(['true', 'yes', '1', 'y', 't'])
                df_valid_ratings = df_ratings[~df_ratings['did_not_watch']]
            else:
                df_valid_ratings = df_ratings
            
            if not df_valid_ratings.empty:
                movie_ratings = df_valid_ratings.groupby('movie_name')['rating'].agg(['mean', 'count']).round(2)
                movie_ratings = movie_ratings.rename(columns={'mean': 'Average Rating', 'count': 'Number of Ratings'})
                movie_ratings = movie_ratings.sort_values('Average Rating', ascending=False)
                
                # Display movies with ratings
                for movie, ratings in movie_ratings.iterrows():
                    avg_rating = ratings['Average Rating']
                    num_ratings = int(ratings['Number of Ratings'])
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{movie}**")
                    with col2:
                        st.write(f"⭐ {avg_rating}/10 ({num_ratings} ratings)")
                    
                    # Safe progress bar
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
        # Show just the suggested movies
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
        
        # Progress bar for current sprint
        progress = 100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100)
        st.progress(min(100, max(0, progress)) / 100)
        st.caption(f"Current sprint progress: {progress:.1f}% ({sprint_info['total_days'] - sprint_info['days_remaining']} of {sprint_info['total_days']} days)")
    else:
        st.info("No active sprint found. Please check Sprints configuration.")

# ---------------------------------------
# PAGE: SUGGEST MOVIE
# ---------------------------------------
elif selected == "Suggest Movie":
    if not st.session_state.enable_suggestion and st.session_state.role != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        st.stop()

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
                # Use current datetime (real or simulated)
                current_timestamp = get_current_datetime()
                # Get current sprint ID or use empty string if no sprint
                sprint_id = current_sprint['sprint_id'] if current_sprint else ""
                
                # Append row with sprint information
                ws.append_row([
                    sprint_id,          # sprint
                    user_name,          # user_name
                    movie_name,         # movie_name
                    genre,              # genre
                    description,        # description
                    image_url,          # image_url
                    str(current_timestamp)  # timestamp
                ])
                st.success("✅ Movie suggestion submitted!")
            except Exception as e:
                st.warning(f"Failed to write suggestion: {e}")

# ---------------------------------------
# PAGE: VOTING
# ---------------------------------------
elif selected == "Voting":
    if not st.session_state.enable_voting and st.session_state.role != "admin":
        st.warning("Voting page is currently disabled by admin.")
        st.stop()

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    if sprint_info:
        st.header(f"🗳️ Voting - {sprint_info['sprint_id']}")
        st.write(f"**Have You Watched These Movies?**")
    else:
        st.header("🗳️ Voting")
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    voter_name = st.session_state.username
    movies = load_sheet("Suggestions")

    # Filter movies for current sprint if available
    current_sprint = get_current_sprint()
    if current_sprint and movies:
        movies = [movie for movie in movies if movie.get('sprint') == current_sprint['sprint_id']]

    if not movies:
        st.info("No movie suggestions found for current sprint.")
    else:
        votes_data = []
        for movie in movies:
            st.subheader(movie.get("movie_name", "Unknown"))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get("image_url"):
                st.image(movie["image_url"], width=200)
            watched = st.checkbox(f"Have you watched this?", key=f"vote_{movie.get('movie_name','')}")
            st.markdown("---")
            votes_data.append((movie.get('movie_name',''), watched))

        if st.button("Submit Votes"):
            try:
                ws = sheet.worksheet("Voting")
                current_timestamp = get_current_datetime()
                for movie_name, watched in votes_data:
                    ws.append_row([movie_name, voter_name, watched, str(current_timestamp)])
                st.success("✅ Votes submitted!")
            except Exception as e:
                st.warning(f"Failed to submit votes: {e}")

# ---------------------------------------
# PAGE: RATE MOVIES
# ---------------------------------------
elif selected == "Rate Movies":
    if not st.session_state.enable_rating and st.session_state.role != "admin":
        st.warning("Rating page is currently disabled by admin.")
        st.stop()

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()
    
    if sprint_info and current_sprint:
        st.header(f"⭐ Rate Movies - {sprint_info['sprint_id']}")
        st.write(f"**Rate the movies from current sprint**")
    else:
        st.header("⭐ Rate Movies")
        st.warning("No active sprint found. Ratings may not be associated with any sprint.")
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    rater_name = st.session_state.username
    movies = load_sheet("Suggestions")

    # Filter movies for current sprint if available
    if current_sprint and movies:
        movies = [movie for movie in movies if movie.get('sprint') == current_sprint['sprint_id']]

    if not movies:
        st.info("No movies to rate for current sprint.")
    else:
        ratings_data = []
        for movie in movies:
            st.subheader(movie.get("movie_name", "Unknown"))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get("image_url"):
                st.image(movie["image_url"], width=200)
            rating = st.slider(f"Rate {movie.get('movie_name','')}", 5.0, 10.0, 7.5, 0.5)
            did_not_watch = st.checkbox(f"Did not watch", key=f"dnw_{movie.get('movie_name','')}")
            st.markdown("---")
            ratings_data.append((movie.get("movie_name",""), rating, did_not_watch))

        if st.button("Submit Ratings"):
            try:
                ws = sheet.worksheet("Ratings")
                current_timestamp = get_current_datetime()
                # Get current sprint ID or use empty string if no sprint
                sprint_id = current_sprint['sprint_id'] if current_sprint else ""
                
                for movie_name, rating, dnw in ratings_data:
                    # Check if rating already exists for this user and movie in current sprint
                    existing_ratings = load_sheet("Ratings")
                    rating_exists = False
                    
                    for existing_rating in existing_ratings:
                        if (existing_rating.get('user_name') == rater_name and 
                            existing_rating.get('movie_name') == movie_name and 
                            existing_rating.get('sprint') == sprint_id):
                            rating_exists = True
                            break
                    
                    if rating_exists:
                        st.warning(f"Rating already submitted for {movie_name}. Skipping...")
                    else:
                        # Append row with sprint information
                        ws.append_row([
                            sprint_id,          # sprint
                            movie_name,         # movie_name
                            rater_name,         # user_name
                            rating,             # rating
                            dnw,                # did_not_watch
                            str(current_timestamp)  # timestamp
                        ])
                
                st.success("✅ Ratings submitted!")
            except Exception as e:
                st.warning(f"Failed to save ratings: {e}")

# ---------------------------------------
# PAGE: ADMIN PANEL
# ---------------------------------------
elif selected == "Admin Panel":
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        st.stop()

    st.header("⚙️ Admin Panel")

    # Show testing mode status
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.warning(f"🧪 **TESTING MODE ACTIVE** - Current simulated date: {test_date}")
    else:
        st.info(f"📅 **PRODUCTION MODE** - Current date: {get_current_date()}")

    # Show current sprint information
    sprint_info = get_sprint_display_info()
    if sprint_info:
        st.subheader("🏃‍♂️ Current Sprint Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sprint ID", sprint_info['sprint_id'])
        with col2:
            st.metric("Days Remaining", sprint_info['days_remaining'])
        with col3:
            st.metric("Progress", f"{100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100):.1f}%")
        
        st.write(f"**Description:** {sprint_info['description']}")
        st.write(f"**Period:** {sprint_info['start_date']} to {sprint_info['end_date']}")

    st.subheader("Testing Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("Configure testing mode using the Testing sheet")
        st.info("""
        **To enable testing mode:**
        1. Create a 'Testing' worksheet in your Google Sheet
        2. Add headers: `date` (first row)
        3. Set your test date in format YYYY-MM-DD or DD/MM/YYYY
        
        **To disable testing mode:**
        - Clear the date cell or delete the Testing worksheet
        """)
    
    with col2:
        # Quick actions for testing
        st.write("**Quick Actions**")
        if testing_enabled:
            if st.button("🔄 Disable Testing Mode"):
                try:
                    ws = sheet.worksheet("Testing")
                    ws.clear()
                    st.success("✅ Testing mode disabled!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to disable testing: {e}")
        else:
            if st.button("🧪 Enable Testing Mode"):
                try:
                    # Create Testing sheet if it doesn't exist
                    try:
                        ws = sheet.worksheet("Testing")
                    except:
                        ws = sheet.add_worksheet(title="Testing", rows="100", cols="2")
                        ws.append_row(["date"])  # Add header
                    
                    # Set today as test date
                    ws.update_cell(2, 1, date.today().strftime('%Y-%m-%d'))
                    st.success("✅ Testing mode enabled with today's date!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to enable testing: {e}")

    # Current testing configuration
    if testing_enabled:
        st.write("**Current Testing Configuration**")
        st.code(f"""
        Testing Sheet Status: ACTIVE
        Simulated Date: {test_date}
        """)
        
        # Quick date updates
        st.write("**Quick Date Updates**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Set to Today"):
                try:
                    ws = sheet.worksheet("Testing")
                    ws.update_cell(2, 1, date.today().strftime('%Y-%m-%d'))
                    st.success("✅ Date set to today!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        with col2:
            if st.button("+1 Day"):
                try:
                    ws = sheet.worksheet("Testing")
                    new_date = test_date + timedelta(days=1)
                    ws.update_cell(2, 1, new_date.strftime('%Y-%m-%d'))
                    st.success(f"✅ Date set to {new_date}!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        with col3:
            if st.button("-1 Day"):
                try:
                    ws = sheet.worksheet("Testing")
                    new_date = test_date - timedelta(days=1)
                    ws.update_cell(2, 1, new_date.strftime('%Y-%m-%d'))
                    st.success(f"✅ Date set to {new_date}!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        # Manual date input
        new_test_date = st.date_input(
            "Set Custom Test Date",
            value=test_date,
            key="test_date_picker"
        )
        
        if new_test_date != test_date:
            try:
                ws = sheet.worksheet("Testing")
                ws.update_cell(2, 1, new_test_date.strftime('%Y-%m-%d'))
                st.success(f"✅ Date set to {new_test_date}!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update date: {e}")

    st.subheader("Page Control")
    # Use callbacks to save changes immediately
    def update_page_config():
        try:
            ws = sheet.worksheet("Config")
            # Clear existing config
            ws.clear()
            # Add headers
            ws.append_row(["key", "value"])
            # Add new config
            config_data = [
                ["enable_suggestion", str(st.session_state.enable_suggestion)],
                ["enable_voting", str(st.session_state.enable_voting)], 
                ["enable_rating", str(st.session_state.enable_rating)]
            ]
            for config in config_data:
                ws.append_row(config)
            st.cache_data.clear()
            st.success("✅ Page settings saved!")
        except Exception as e:
            st.warning(f"Failed to save config: {e}")

    col1, col2, col3 = st.columns(3)
    with col1:
        suggestion_enabled = st.checkbox("Enable Suggestion Page", 
                      value=st.session_state.enable_suggestion,
                      key="admin_suggestion")
    
    with col2:
        voting_enabled = st.checkbox("Enable Voting Page", 
                      value=st.session_state.enable_voting,
                      key="admin_voting")
    
    with col3:
        rating_enabled = st.checkbox("Enable Rating Page",
                      value=st.session_state.enable_rating,
                      key="admin_rating")

    if st.button("Save Page Settings"):
        st.session_state.enable_suggestion = suggestion_enabled
        st.session_state.enable_voting = voting_enabled
        st.session_state.enable_rating = rating_enabled
        update_page_config()

    st.subheader("User Management")
    
    tab1, tab2 = st.tabs(["Add New User", "Reset User Password"])
    
    with tab1:
        st.write("Add a new user to the system")
        new_user = st.text_input("New User Name")
        role = st.selectbox("Role", ["normal", "admin"])
        user_password = st.text_input("Set Password", type="password", key="new_user_password")
        
        if st.button("Add User"):
            if new_user and user_password:
                try:
                    ws = sheet.worksheet("Users")
                    # Hash the password before storing
                    hashed_password = hash_password(user_password)
                    ws.append_row([new_user, role, 0, hashed_password])  # Start with 0 points
                    st.success(f"✅ Added {new_user} as {role}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.warning(f"Failed to add user: {e}")
            else:
                st.error("Please enter both username and password")
    
    with tab2:
        st.write("Reset password for existing user")
        users_data = load_sheet("Users")
        user_names = [user['user_name'] for user in users_data if user['user_name'] != st.session_state.username]
        
        if user_names:
            selected_user = st.selectbox("Select User", user_names)
            new_password = st.text_input("New Password", type="password", key="reset_password")
            
            if st.button("Reset Password"):
                if new_password:
                    try:
                        ws = sheet.worksheet("Users")
                        users_records = ws.get_all_records()
                        
                        # Find the user and update their password
                        for i, user_record in enumerate(users_records):
                            if user_record['user_name'] == selected_user:
                                hashed_password = hash_password(new_password)
                                # Update password in column 4 (D)
                                ws.update_cell(i + 2, 4, hashed_password)
                                st.success(f"✅ Password reset for {selected_user}")
                                st.cache_data.clear()
                                break
                    except Exception as e:
                        st.warning(f"Failed to reset password: {e}")
                else:
                    st.error("Please enter a new password")
        else:
            st.info("No other users found")

# ---------------------------------------
# PAGE: FINALIZE SPRINT
# ---------------------------------------
elif selected == "Finalize Sprint":
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        st.stop()

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()
    
    if sprint_info and current_sprint:
        st.header(f"🏁 Finalize Sprint - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | Ending on {sprint_info['end_date']}")
    else:
        st.header("🏁 Finalize Sprint")
        st.warning("No active sprint found to finalize.")
        st.stop()
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")

    st.markdown("---")
    
    # Load current data - filter for current sprint
    all_suggestions = load_sheet("Suggestions")
    all_ratings = load_sheet("Ratings")
    users_data = load_sheet("Users")
    
    # Filter data for current sprint
    suggestions = [s for s in all_suggestions if s.get('sprint') == current_sprint['sprint_id']]
    ratings = [r for r in all_ratings if r.get('sprint') == current_sprint['sprint_id']]
    
    if not suggestions:
        st.warning("No movie suggestions found for this sprint.")
        st.stop()

    if not ratings:
        st.warning("No ratings found for this sprint.")
        st.stop()
    
    # Calculate statistics
    st.subheader("📊 Sprint Statistics")
    
    # Convert to DataFrames for easier analysis
    df_suggestions = pd.DataFrame(suggestions)
    df_ratings = pd.DataFrame(ratings)
    df_users = pd.DataFrame(users_data)
    
    # Data cleaning
    df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
    df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(str).str.lower().isin(['true', 'yes', '1', 'y', 't'])
    
    # Display basic stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Movies Suggested", len(df_suggestions))
    with col2:
        total_ratings = len(df_ratings)
        st.metric("Total Ratings", total_ratings)
    with col3:
        watched_ratings = len(df_ratings[~df_ratings['did_not_watch']])
        st.metric("Watched Movies Rated", watched_ratings)
    with col4:
        st.metric("Active Users", len(df_users))
    
    # Points Calculation Logic
    st.subheader("💰 Points Calculation Breakdown")
    
    # Initialize points dictionary
    user_points = {}
    user_breakdown = {}
    
    # Points rules
    bonus_per_new_movie = 0.5  # Bonus for suggesting a movie no one watched
    deduction_per_missed_movie = 0.25  # Deduction for each movie not watched
    
    # Create a mapping from movie name to suggester
    movie_to_suggester = {}
    for _, row in df_suggestions.iterrows():
        movie_to_suggester[row['movie_name']] = row['user_name']
    
    # Calculate points for each user
    for user in df_users['user_name'].tolist():
        # 1. Calculate AVERAGE rating for movies suggested by this user (only watched movies)
        user_suggested_movies = df_suggestions[df_suggestions['user_name'] == user]['movie_name'].tolist()
        
        total_rating_sum = 0
        total_rating_count = 0
        
        for movie in user_suggested_movies:
            # Get all ratings for this movie where people actually watched it
            movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
            if not movie_ratings.empty:
                movie_avg_rating = movie_ratings['rating'].mean()
                total_rating_sum += movie_avg_rating
                total_rating_count += 1
        
        # Calculate AVERAGE rating of suggested movies (average of averages)
        avg_rating_points = total_rating_sum / total_rating_count if total_rating_count > 0 else 0
        
        # 2. Calculate deductions for movies this user did not watch
        user_not_watched = df_ratings[(df_ratings['user_name'] == user) & (df_ratings['did_not_watch'] == True)]
        total_deductions = len(user_not_watched) * deduction_per_missed_movie
        
        # 3. Calculate bonus for movies suggested that no one watched
        bonus = 0
        for movie in user_suggested_movies:
            # Check if anyone watched this movie (anyone rated it without "did not watch")
            movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
            if len(movie_ratings) == 0:
                bonus += bonus_per_new_movie
        
        # 4. Calculate total points (avg_rating_points is already an average, so we use it directly)
        total_points = avg_rating_points - total_deductions + bonus
        
        # Store the breakdown
        user_breakdown[user] = {
            "avg_rating_points": avg_rating_points,
            "total_rating_sum": total_rating_sum,
            "rated_movies_count": total_rating_count,
            "movies_suggested": len(user_suggested_movies),
            "movies_not_watched": len(user_not_watched),
            "total_deductions": total_deductions,
            "bonus_new_movies": bonus,
            "total_points": total_points
        }
        user_points[user] = total_points
    
    # Display detailed points breakdown
    st.write("#### Detailed Points Calculation for Each User")
    for user, breakdown in user_breakdown.items():
        with st.expander(f"📋 {user}'s Points Breakdown - Total: {breakdown['total_points']:.2f} points"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Rating Points**")
                st.write(f"Movies Suggested: {breakdown['movies_suggested']}")
                st.write(f"Movies Rated by Others: {breakdown['rated_movies_count']}")
                st.write(f"Total Rating Sum: {breakdown['total_rating_sum']:.2f}")
                st.write(f"**Avg Rating Points: {breakdown['avg_rating_points']:.2f}**")
            
            with col2:
                st.write("**Deductions**")
                st.write(f"Movies Not Watched: {breakdown['movies_not_watched']}")
                st.write(f"**Total Deductions: -{breakdown['total_deductions']:.2f}**")
            
            with col3:
                st.write("**Suggestions & Bonus**")
                st.write(f"New Movie Bonus: +{breakdown['bonus_new_movies']:.2f}")
            
            st.write("---")
            st.write(f"**Final Calculation:** {breakdown['avg_rating_points']:.2f} (Avg Rating) - {breakdown['total_deductions']:.2f} (Deductions) + {breakdown['bonus_new_movies']:.2f} (Bonus) = **{breakdown['total_points']:.2f} points**")
            
            # Show calculation details
            if breakdown['rated_movies_count'] > 0:
                st.write(f"*Calculation: ({breakdown['total_rating_sum']:.2f} / {breakdown['rated_movies_count']}) = {breakdown['avg_rating_points']:.2f}*")
    
    # Display Leaderboard
    st.subheader("🏆 Final Sprint Leaderboard")
    leaderboard_data = []
    for user, points in sorted(user_points.items(), key=lambda x: x[1], reverse=True):
        breakdown = user_breakdown[user]
        leaderboard_data.append({
            "Rank": len(leaderboard_data) + 1,
            "User": user,
            "Total Points": f"{points:.2f}",
            "Avg Rating": f"{breakdown['avg_rating_points']:.2f}",
            "Deductions": f"-{breakdown['total_deductions']:.2f}",
            "Bonus": f"+{breakdown['bonus_new_movies']:.2f}",
            "Movies Suggested": breakdown['movies_suggested'],
            "Not Watched": breakdown['movies_not_watched']
        })
    
    df_leaderboard = pd.DataFrame(leaderboard_data)
    st.dataframe(df_leaderboard, use_container_width=True)
    
    # Movie Statistics
    st.subheader("🎬 Movie Statistics")
    
    # Calculate movie averages and find suggesters
    movie_stats = []
    for movie in df_suggestions['movie_name'].unique():
        movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
        suggester = movie_to_suggester.get(movie, "Unknown")
        
        if not movie_ratings.empty:
            avg_rating = movie_ratings['rating'].mean()
            num_ratings = len(movie_ratings)
            num_not_watched = len(df_ratings[(df_ratings['movie_name'] == movie) & (df_ratings['did_not_watch'] == True)])
            
            movie_stats.append({
                "Movie": movie,
                "Suggested By": suggester,
                "Avg Rating": f"{avg_rating:.2f}",
                "Ratings Count": num_ratings,
                "Not Watched Count": num_not_watched,
                "Status": "Watched" if num_ratings > 0 else "Not Watched"
            })
        else:
            movie_stats.append({
                "Movie": movie,
                "Suggested By": suggester,
                "Avg Rating": "N/A",
                "Ratings Count": 0,
                "Not Watched Count": len(df_ratings[df_ratings['movie_name'] == movie]),
                "Status": "Not Watched"
            })
    
    df_movie_stats = pd.DataFrame(movie_stats)
    st.dataframe(df_movie_stats, use_container_width=True)
    
    # WhatsApp Message Generation
    st.subheader("📱 WhatsApp Messages")
    
    # Find top 3 winners
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_users[:3]
    
    # Find best rated movie
    best_movie = None
    best_rating = 0
    best_movie_suggester = ""
    for movie in df_suggestions['movie_name'].unique():
        movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
        if not movie_ratings.empty:
            avg_rating = movie_ratings['rating'].mean()
            if avg_rating > best_rating:
                best_rating = avg_rating
                best_movie = movie
                best_movie_suggester = movie_to_suggester.get(movie, "Unknown")
    
    # Find movies no one watched
    unwatched_movies = []
    for movie in df_suggestions['movie_name'].unique():
        movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
        if len(movie_ratings) == 0:
            suggester = movie_to_suggester.get(movie, "Unknown")
            unwatched_movies.append((movie, suggester))
    
    # Sprint Summary Message
    sprint_summary = f"""🎬 *MOVIE CLUB SPRINT RESULTS* 🎬

*Sprint:* {current_sprint['sprint_id']} - {current_sprint['description']}
*Period:* {current_sprint['start_date']} to {current_sprint['end_date']}
*Finalized on:* {get_current_date()}

*📊 SPRINT STATISTICS:*
• Total Movies Suggested: {len(df_suggestions)}
• Total Ratings Submitted: {len(df_ratings)}
• Active Participants: {len(user_points)}
• Movies No One Watched: {len(unwatched_movies)}

*🏆 TOP PERFORMERS:*
"""
    
    # Add top 3 winners with emojis
    medals = ["🥇", "🥈", "🥉"]
    for i, (user, points) in enumerate(top_3):
        breakdown = user_breakdown[user]
        sprint_summary += f"{medals[i]} *{user}:* {points:.2f} points\n"
        sprint_summary += f"   - Suggested {breakdown['movies_suggested']} movies\n"
        sprint_summary += f"   - Avg rating: {breakdown['avg_rating_points']:.2f}\n"
        if breakdown['bonus_new_movies'] > 0:
            sprint_summary += f"   - New movie bonus: +{breakdown['bonus_new_movies']:.2f}\n"
        sprint_summary += "\n"
    
    # Add movie ratings summary
    sprint_summary += f"*🎬 MOVIE RATINGS SUMMARY:*\n"
    
    # Add top 3 rated movies
    rated_movies = [m for m in movie_stats if m['Status'] == 'Watched']
    rated_movies.sort(key=lambda x: float(x['Avg Rating']), reverse=True)
    
    for i, movie in enumerate(rated_movies[:3]):  # Top 3 movies
        sprint_summary += f"• *{movie['Movie']}* - ⭐ {movie['Avg Rating']}/10 (by {movie['Suggested By']})\n"
    
    # Add unwatched movies if any
    if unwatched_movies:
        sprint_summary += f"\n*🚫 MOVIES NO ONE WATCHED (Bonus given):*\n"
        for movie, suggester in unwatched_movies:
            sprint_summary += f"• {movie} (suggested by {suggester})\n"
    
    # Add fun facts
    sprint_summary += f"\n*🎉 FUN FACTS:*\n"
    if best_movie:
        sprint_summary += f"• Highest Rated: *{best_movie}* ({best_rating:.2f}/10 ⭐) by {best_movie_suggester}\n"
    
    most_active_suggester = max(user_breakdown.items(), key=lambda x: x[1]['movies_suggested'])
    sprint_summary += f"• Most Active Suggester: *{most_active_suggester[0]}* ({most_active_suggester[1]['movies_suggested']} movies suggested)\n"
    
    sprint_summary += f"\n*📈 PARTICIPATION RATE:* {len([u for u in user_breakdown.values() if u['movies_suggested'] > 0])}/{len(user_points)} users suggested movies\n"
    
    sprint_summary += "\nGreat job everyone! 🎉 See you next sprint! 👋"
    
    # Display messages
    st.text_area("📋 Sprint Summary Message (Copy for WhatsApp)", sprint_summary, height=500)
    
    # Compact version for quick sharing
    compact_summary = f"""🎬 *MOVIE CLUB RESULTS - {current_sprint['sprint_id']}* 🎬

🏆 WINNERS:
{medals[0]} {top_3[0][0]}: {top_3[0][1]:.2f} pts
{medals[1]} {top_3[1][0]}: {top_3[1][1]:.2f} pts  
{medals[2]} {top_3[2][0]}: {top_3[2][1]:.2f} pts

⭐ TOP MOVIES:
"""
    for i, movie in enumerate(rated_movies[:3]):
        compact_summary += f"{i+1}. {movie['Movie']} - {movie['Avg Rating']}/10\n"
    
    compact_summary += f"\n📊 {len(df_suggestions)} movies, {len(user_points)} participants"
    compact_summary += f"\n\nGreat job! 🎉 Next sprint coming soon! 👋"
    
    st.text_area("📱 Compact Message (Quick Share)", compact_summary, height=200)
    
    # Finalize button
    st.markdown("---")
    st.warning("⚠️ This will calculate and save points for this sprint. No data will be purged.")
    
    if st.button("🚀 Calculate & Save Sprint Points"):
        try:
            # Update Points sheet (sprint-wise points)
            try:
                ws_points = sheet.worksheet("Points")
            except:
                ws_points = sheet.add_worksheet(title="Points", rows="1000", cols="10")
                # Add headers
                ws_points.append_row([
                    "sprint", "user_name", "total_points", "avg_rating_points", 
                    "deductions", "bonus", "movies_suggested", "finalized_date"
                ])
            
            # Save individual sprint results to Points sheet
            for user, points in user_points.items():
                breakdown = user_breakdown[user]
                ws_points.append_row([
                    current_sprint['sprint_id'],
                    user,
                    round(points, 2),  # total_points
                    round(breakdown['avg_rating_points'], 2),  # avg_rating_points (different from total_points)
                    round(breakdown['total_deductions'], 2),
                    round(breakdown['bonus_new_movies'], 2),
                    breakdown['movies_suggested'],
                    str(get_current_date())
                ])
            
            # Update Users sheet with total accumulated points
            ws_users = sheet.worksheet("Users")
            users_records = ws_users.get_all_records()
            
            # Create a mapping of current points for each user
            current_user_points = {}
            for user_record in users_records:
                current_user_points[user_record['user_name']] = float(user_record.get('points', 0))
            
            # Update points for each user
            for i, user_record in enumerate(users_records):
                user_name = user_record['user_name']
                if user_name in user_points:
                    current_points = current_user_points[user_name]
                    new_points = current_points + user_points[user_name]
                    # Update points in the Users sheet (column 3)
                    ws_users.update_cell(i + 2, 3, round(new_points, 2))
            
            st.success("✅ Sprint points calculated and saved successfully!")
            st.balloons()
            
            # Show summary of updated points
            st.subheader("📈 Points Summary")
            points_data = []
            for user, sprint_points in sorted(user_points.items(), key=lambda x: x[1], reverse=True):
                old_total = current_user_points.get(user, 0)
                new_total = old_total + sprint_points
                points_data.append({
                    "User": user,
                    "Sprint Points": f"{sprint_points:.2f}",
                    "Previous Total": f"{old_total:.2f}",
                    "New Total": f"{new_total:.2f}"
                })
            
            st.dataframe(pd.DataFrame(points_data), use_container_width=True)
            
            # Show where data was saved
            st.info(f"📊 **Data Saved To:**\n- **Points Sheet:** Individual sprint performance for {current_sprint['sprint_id']}\n- **Users Sheet:** Updated total points for all users")
            
        except Exception as e:
            st.error(f"❌ Error saving sprint points: {e}")
