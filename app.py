import os
import streamlit as st
import gspread
from datetime import datetime, date, timedelta
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials
import hashlib

# Import the login system
from login_system import initialize_session_state, render_login_page, hash_password

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
# TESTING MODE FROM GOOGLE SHEETS
# ---------------------------------------
@st.cache_data(ttl=60)
def load_testing_config():
    """Load testing configuration from Google Sheets"""
    try:
        testing_data = load_sheet("Testing")
        # Add null check here
        if not testing_data or len(testing_data) == 0:
            return False, date.today()
            
        if testing_data and len(testing_data) > 0:
            # Get the first row which should contain the test date
            test_config = testing_data[0]
            # Add null check for test_config
            if not test_config:
                return False, date.today()
                
            test_date_str = test_config.get('date', '').strip()
            
            # Add check for empty string
            if not test_date_str:
                return False, date.today()
            
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
        # Remove the warning or handle silently
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

def get_previous_sprint():
    """Get the previous sprint for  purposes"""
    try:
        sprints_data = load_sheet("Sprints")
        current_date = get_current_date()
        
        # Sort sprints by end_date descending
        sorted_sprints = sorted(sprints_data, 
                              key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'), 
                              reverse=True)
        
        # Find the sprint that ended just before today
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

# ---------------------------------------
# CHECK USER ACTIVITY STATUS
# ---------------------------------------
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
        # Get movies from current sprint that are NOT user's own movies
        suggestions = load_sheet("Suggestions")
        sprint_movies = [s['movie_name'] for s in suggestions 
                        if (s.get('sprint') == sprint_id 
                        and s.get('user_name') != user_name)]  # Exclude own movies
        
        # Check if user has voted for any movie in this sprint
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
    st.subheader("🎬 Current Sprint Movies")
    
    if not df_suggestions.empty:
        # Filter suggestions for current sprint if available
        if sprint_info:
            current_sprint_suggestions = df_suggestions[df_suggestions['sprint'] == sprint_info['sprint_id']]
        else:
            current_sprint_suggestions = df_suggestions
        
        if not current_sprint_suggestions.empty:
            # Display movies in a grid layout
            cols = st.columns(3)  # 3 columns for the grid
            
            for idx, movie in current_sprint_suggestions.iterrows():
                col_idx = idx % 3
                with cols[col_idx]:
                    # Movie poster/image with smaller size
                    if movie.get('image_url') and pd.notna(movie['image_url']) and movie['image_url'].strip():
                        st.image(movie['image_url'], 
                               width=200,  # Fixed smaller width
                               output_format="PNG")
                    else:
                        # Placeholder with smaller dimensions
                        st.image("https://via.placeholder.com/200x300/333333/FFFFFF?text=No+Poster", 
                               width=200,  # Fixed smaller width
                               output_format="PNG")
                    
                    # Movie title and genre only
                    st.write(f"**{movie.get('movie_name', 'Unknown Movie')}**")
                    st.write(f"*{movie.get('genre', 'Not specified')}*")
                    
                    # Add some spacing between cards
                    st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.info("No movies suggested for current sprint.")
    else:
        st.info("No movies suggested yet.")
    
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
    
    # Check if user has already suggested in this sprint
    if current_sprint and has_user_suggested_in_sprint(user_name, current_sprint['sprint_id']):
        st.success("✅ You have already suggested a movie for this sprint!")
        st.info("You can only suggest one movie per sprint.")
        st.stop()
    
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
                st.cache_data.clear()
                st.rerun()
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
    current_sprint = get_current_sprint()
    
    if sprint_info and current_sprint:
        st.header(f"🗳️ Voting - {sprint_info['sprint_id']}")
        st.write(f"**Have You Watched These Movies?**")
    else:
        st.header("🗳️ Voting")
        st.warning("No active sprint found for voting.")
        st.stop()
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    voter_name = st.session_state.username
    
    # Check if user has already voted in this sprint
    if has_user_voted_in_sprint(voter_name, current_sprint['sprint_id']):
        st.success("✅ You have already voted for this sprint!")
        st.info("You can only vote once per sprint.")
        st.stop()
    
    movies = load_sheet("Suggestions")


    if current_sprint and movies:
        movies = [movie for movie in movies 
                  if (movie.get('sprint') == current_sprint['sprint_id'] 
                  and movie.get('user_name') != voter_name)]  # Exclude user's own movies

    if not movies:
        st.info("No movie suggestions from other members found for current sprint.")
    else:
        st.info(f"Found {len(movies)} movies suggested by other members to vote on")
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
                st.cache_data.clear()
                st.rerun()
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
    previous_sprint = get_previous_sprint()
    
    # Determine which sprint to rate - previous sprint for rating
    rating_sprint = previous_sprint if previous_sprint else current_sprint
    
    if rating_sprint:
        st.header(f"⭐ Rate Movies - {rating_sprint['sprint_id']}")
        if rating_sprint == previous_sprint:
            st.info("📅 Rating movies from the previous sprint")
        else:
            st.write(f"**Rate the movies from current sprint**")
    else:
        st.header("⭐ Rate Movies")
        st.warning("No sprint found for rating.")
        st.stop()
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    rater_name = st.session_state.username
    
    # Check if user has already rated this sprint's movies
    if has_user_rated_sprint_movies(rater_name, rating_sprint['sprint_id']):
        st.success("✅ You have already rated movies for this sprint!")
        st.info("You can only rate once per sprint.")
        st.stop()
    
    movies = load_sheet("Suggestions")

    if rating_sprint and movies:
        movies = [movie for movie in movies 
                  if (movie.get('sprint') == rating_sprint['sprint_id'] 
                  and movie.get('user_name') != rater_name)]  # Exclude user's own movies

    if not movies:
        st.info("No movies from other members found to rate for this sprint.")
    else:
        st.info(f"Found {len(movies)} movies from other members to rate")
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
                
                for movie_name, rating, dnw in ratings_data:
                    # Append row with sprint information
                    ws.append_row([
                        rating_sprint['sprint_id'],  # sprint
                        movie_name,         # movie_name
                        rater_name,         # user_name
                        rating,             # rating
                        dnw,                # did_not_watch
                        str(current_timestamp)  # timestamp
                    ])
                
                st.success("✅ Ratings submitted!")
                st.cache_data.clear()
                st.rerun()
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
    
    # Calculate button
    st.markdown("---")
    st.subheader("💰 Calculate Points")
    
    if st.button("🚀 Calculate & Save Sprint Points", type="primary"):
        # Points Calculation Logic
        user_points = {}
        user_breakdown = {}
        point_info_data = []
        
        # Points rules
        bonus_per_new_movie = 0.5
        deduction_per_missed_movie = 0.25
        
        # Create a mapping from movie name to suggester
        movie_to_suggester = {}
        for _, row in df_suggestions.iterrows():
            movie_to_suggester[row['movie_name']] = row['user_name']
        
        # Calculate points for each user
        for user in df_users['user_name'].tolist():
            # Get movies suggested by this user
            user_suggested_movies = df_suggestions[df_suggestions['user_name'] == user]['movie_name'].tolist()
            
            # Calculate total deductions for this user
            user_not_watched = df_ratings[(df_ratings['user_name'] == user) & (df_ratings['did_not_watch'] == True)]
            total_deductions = len(user_not_watched) * deduction_per_missed_movie
            
            # Calculate bonus for movies suggested that no one watched
            bonus = 0
            unwatched_suggestions = []
            for movie in user_suggested_movies:
                movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
                if len(movie_ratings) == 0:
                    bonus += bonus_per_new_movie
                    unwatched_suggestions.append(movie)
            
            # For each movie suggested by the user, calculate points
            user_total_points = 0
            
            # If user suggested multiple movies, distribute deductions evenly
            deduction_per_movie = total_deductions / len(user_suggested_movies) if user_suggested_movies else 0
            
            for movie in user_suggested_movies:
                # Get all ratings for this movie where people actually watched it
                movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
                
                total_point = 0
                average_point = 0
                
                if not movie_ratings.empty:
                    total_point = movie_ratings['rating'].sum()
                    average_point = movie_ratings['rating'].mean()
                
                # Calculate deduction for this specific movie (distributed evenly)
                movie_deduction = -deduction_per_movie  # Negative because it's a deduction
                
                # Calculate bonus for this specific movie
                movie_bonus = bonus_per_new_movie if movie in unwatched_suggestions else 0
                
                # Final total for this movie
                final_total = average_point + movie_deduction + movie_bonus
                
                # Add to user's total points
                user_total_points += final_total
                
                # Add to point info table
                point_info_data.append({
                    "Movie": movie,
                    "User": user,
                    "Total Point": round(total_point, 3),
                    "Average Point": round(average_point, 3),
                    "Deduction": round(movie_deduction, 3),
                    "Bonus": round(movie_bonus, 3),
                    "Final Total": round(final_total, 3)
                })
            
            # Store user breakdown
            user_breakdown[user] = {
                "total_points": user_total_points,
                "total_deductions": total_deductions,
                "bonus_new_movies": bonus,
                "movies_suggested": len(user_suggested_movies)
            }
            user_points[user] = user_total_points
        
        # Save to Points sheet
        try:
            ws_points = sheet.worksheet("Points")
        except:
            ws_points = sheet.add_worksheet(title="Points", rows="1000", cols="10")
            ws_points.append_row(["sprint", "user_name", "total_points", "deductions", "bonus", "movies_suggested", "finalized_date"])
        
        # Save individual sprint results
        for user, points in user_points.items():
            breakdown = user_breakdown[user]
            ws_points.append_row([
                current_sprint['sprint_id'],
                user,
                round(points, 3),
                round(breakdown['total_deductions'], 3),
                round(breakdown['bonus_new_movies'], 3),
                breakdown['movies_suggested'],
                str(get_current_date())
            ])
        
        # Update Users sheet with accumulated points
        ws_users = sheet.worksheet("Users")
        users_records = ws_users.get_all_records()
        
        # Create a mapping of current points for each user
        current_user_points = {}
        for user_record in users_records:
            user_name = user_record['user_name']
            points_value = user_record.get('points', '0')
            try:
                current_user_points[user_name] = float(points_value) if points_value not in ['', None] else 0.0
            except (ValueError, TypeError):
                current_user_points[user_name] = 0.0
        
        # Update points in Users sheet (column 3)
        for i, user_record in enumerate(users_records):
            user_name = user_record['user_name']
            if user_name in user_points:
                current_points = current_user_points.get(user_name, 0.0)
                new_points = current_points + user_points[user_name]
                ws_users.update_cell(i + 2, 3, round(new_points, 3))
        
        st.success("✅ Sprint points calculated and saved successfully!")
        
        # Display Point Info Table
        st.markdown("---")
        st.subheader("📋 Point Info")
        
        df_point_info = pd.DataFrame(point_info_data)
        st.dataframe(df_point_info, use_container_width=True)
        
        # WhatsApp Messages Section
        st.markdown("---")
        st.subheader("📱 WhatsApp Messages")
        
        # Message 1: Current Sprint Average Points (per user)
        message1 = f"""🎥 {current_sprint['sprint_id']} Rating 🎥
━━━━━━━━━━━━━━
"""
        # Calculate average points per user (sum of Final Total for their movies)
        user_avg_points = {}
        for row in point_info_data:
            user = row['User']
            final_total = row['Final Total']
            if user not in user_avg_points:
                user_avg_points[user] = 0
            user_avg_points[user] += final_total
        
        # Sort users by average points (highest first)
        sorted_by_avg = sorted(user_avg_points.items(), key=lambda x: x[1], reverse=True)
        for user, avg_points in sorted_by_avg:
            if avg_points > 0:  # Only include users with positive points
                message1 += f"🍿 {user}: {avg_points:.3f}\n"
        
        message1 += "━━━━━━━━━━━━━━"
        
        # Message 2: Total Points after this sprint
        message2 = f"🏆 *Points after {current_sprint['sprint_id']} Sprint* 🏆\n━━━━━━━━━━━━━━\n"
        
        # Get updated total points from current_user_points (after adding this sprint's points)
        updated_totals = {}
        for user in current_user_points:
            if user in user_points:
                updated_totals[user] = current_user_points[user] + user_points[user]
            else:
                updated_totals[user] = current_user_points[user]
        
        # Sort by total points (highest first)
        sorted_by_total = sorted(updated_totals.items(), key=lambda x: x[1], reverse=True)
        
        for user, total in sorted_by_total:
            if total > 0:  # Only include users with points
                # Format with consistent spacing
                message2 += f"👤 {user.ljust(12)}:{total:.3f}\n"
        
        message2 += "━━━━━━━━━━━━━━"
        
        # Display messages in two columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Current Sprint Ratings**")
            st.code(message1, language=None)
            if st.button("📋 Copy Rating Message", key="copy_rating"):
                st.session_state.copied_text = message1
                st.success("✅ Rating message copied to clipboard!")
        
        with col2:
            st.write("**Total Points Leaderboard**")
            st.code(message2, language=None)
            if st.button("📋 Copy Points Message", key="copy_points"):
                st.session_state.copied_text = message2
                st.success("✅ Points message copied to clipboard!")
        
        # JavaScript for clipboard copy
        if 'copied_text' in st.session_state:
            st.markdown(f"""
            <script>
            navigator.clipboard.writeText(`{st.session_state.copied_text}`);
            </script>
            """, unsafe_allow_html=True)
            # Clear after use
            del st.session_state.copied_text
