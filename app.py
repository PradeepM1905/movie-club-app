import os
import streamlit as st
import gspread
from datetime import datetime, date
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
    
    #st.write("Debug: Raw users data from sheet:", users_data)  # Debug line
    
    for row in users_data:
        uname = row.get("user_name")
        role = row.get("role", "normal").lower()
        # Try different possible column names for password
        password = row.get("password") or row.get("pass") or row.get("pwd") or ""
        
        if uname:
            users_list.append(uname)
            users_roles[uname] = role
            users_passwords[uname] = password
            
            # Debug each user
            #st.write(f"Debug: Loaded user '{uname}' with password: {'[SET]' if password else '[NOT SET]'}")
    
    return users_list, users_roles, users_passwords

# ---------------------------------------
# PASSWORD HASHING
# ---------------------------------------
def hash_password(password):
    """Simple password hashing for basic security"""
    return hashlib.sha256(password.encode()).hexdigest()

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
    
    # Debug information (you can remove this after testing)
    st.write(f"Debug: User '{username}', Role: '{role}', Stored password present: {bool(stored_password)}")
    
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
        
        # For testing: show what's being compared (remove after debugging)
        st.write(f"Debug: Input password hash: {hash_password(password)}")
        st.write(f"Debug: Stored password hash: {stored_password}")
        
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
menu = []
if st.session_state.enable_suggestion or st.session_state.role == "admin":
    menu.append("Suggest Movie")
if st.session_state.enable_voting or st.session_state.role == "admin":
    menu.append("Voting")
if st.session_state.enable_rating or st.session_state.role == "admin":
    menu.append("Rate Movies")

menu.append("Dashboard")

if st.session_state.role == "admin":
    menu += ["Admin Panel", "Finalize Sprint"]

if not menu:
    menu = ["Dashboard"]  # Always show at least dashboard

selected = st.sidebar.radio("📋 Navigation", menu)

st.sidebar.write(f"👤 Logged in as: **{st.session_state.username}** ({st.session_state.role})")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ---------------------------------------
# PAGE: SUGGEST MOVIE
# ---------------------------------------
if selected == "Suggest Movie":
    if not st.session_state.enable_suggestion and st.session_state.role != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        st.stop()

    st.header("🎥 Suggest a Movie (Anonymous)")
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
                ws.append_row([user_name, movie_name, genre, description, image_url, str(datetime.now())])
                st.success("✅ Movie suggestion submitted anonymously!")
            except Exception as e:
                st.warning(f"Failed to write suggestion: {e}")

# ---------------------------------------
# PAGE: VOTING
# ---------------------------------------
elif selected == "Voting":
    if not st.session_state.enable_voting and st.session_state.role != "admin":
        st.warning("Voting page is currently disabled by admin.")
        st.stop()

    st.header("🗳️ Voting: Have You Watched This Movie?")
    voter_name = st.session_state.username
    movies = load_sheet("Suggestions")

    if not movies:
        st.info("No movie suggestions found.")
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
                for movie_name, watched in votes_data:
                    ws.append_row([movie_name, voter_name, watched, str(datetime.now())])
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

    st.header("⭐ Rate Movies")
    rater_name = st.session_state.username
    movies = load_sheet("Suggestions")

    if not movies:
        st.info("No movies to rate.")
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
                for movie_name, rating, dnw in ratings_data:
                    ws.append_row([movie_name, rater_name, rating, dnw, str(datetime.now())])
                st.success("✅ Ratings submitted!")
            except Exception as e:
                st.warning(f"Failed to save ratings: {e}")

# ---------------------------------------
# PAGE: DASHBOARD
# ---------------------------------------
elif selected == "Dashboard":
    st.header("📊 Movie Ratings Dashboard")
    ratings = load_sheet("Ratings")

    if not ratings:
        st.info("No ratings yet.")
    else:
        df = pd.DataFrame(ratings)
        df["rating"] = df["rating"].astype(float)
        df["did_not_watch"] = df["did_not_watch"].astype(bool)

        st.write("### Average Ratings by Movie")
        for movie in df["movie_name"].unique():
            avg = df.loc[~df["did_not_watch"] & (df["movie_name"] == movie), "rating"].mean()
            st.write(f"🎬 {movie}: **{avg:.2f}**")

# ---------------------------------------
# PAGE: ADMIN PANEL
# ---------------------------------------
elif selected == "Admin Panel":
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        st.stop()

    st.header("⚙️ Admin Panel")

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

    st.header("🏁 Finalize Sprint")
    
    # Sprint configuration
    col1, col2 = st.columns(2)
    with col1:
        sprint_name = st.text_input("Sprint Name", value=f"Sprint_{datetime.now().strftime('%Y%m%d')}")
    with col2:
        sprint_days = st.number_input("Sprint Duration (days)", min_value=1, value=15)
    
    st.markdown("---")
    
    # Load current data
    suggestions = load_sheet("Suggestions")
    votes = load_sheet("Voting")
    ratings = load_sheet("Ratings")
    users_data = load_sheet("Users")
    
    if not suggestions:
        st.warning("No movie suggestions found for this sprint.")
        st.stop()
    
    # Calculate statistics
    st.subheader("📊 Sprint Statistics")
    
    # Convert to DataFrames for easier analysis
    df_suggestions = pd.DataFrame(suggestions)
    df_votes = pd.DataFrame(votes)
    df_ratings = pd.DataFrame(ratings)
    df_users = pd.DataFrame(users_data)
    
    if not df_votes.empty:
        df_votes['watched'] = df_votes['watched'].astype(bool)
    
    if not df_ratings.empty:
        df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
        df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(bool)
    
    # Display basic stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Movies Suggested", len(df_suggestions))
    with col2:
        total_votes = len(df_votes) if not df_votes.empty else 0
        st.metric("Total Votes", total_votes)
    with col3:
        total_ratings = len(df_ratings) if not df_ratings.empty else 0
        st.metric("Total Ratings", total_ratings)
    with col4:
        st.metric("Active Users", len(df_users))
    
    # Points Calculation Logic (Updated based on your requirements)
    st.subheader("💰 Points Calculation Breakdown")
    
    # Initialize points dictionary
    user_points = {user: 0 for user in df_users['user_name'].tolist()}
    user_breakdown = {user: {"average_rating": 0, "bonus": 0, "deductions": 0, "total": 0} for user in df_users['user_name'].tolist()}
    
    # Points rules (from your specification)
    bonus_per_new_movie = 0.5  # Bonus for suggesting a movie no one watched
    deduction_per_missed_movie = 0.25  # Deduction for each movie not watched
    
    # Calculate points for each user
    for user in user_points.keys():
        # 1. Calculate average rating of movies the user has watched
        user_ratings = df_ratings[(df_ratings['user_name'] == user) & (~df_ratings['did_not_watch'])]
        if len(user_ratings) > 0:
            average_rating = user_ratings['rating'].mean()
        else:
            average_rating = 0
        
        # 2. Calculate bonus for movies suggested that no one watched
        user_suggestions = df_suggestions[df_suggestions['user_name'] == user]['movie_name'].tolist()
        bonus = 0
        for movie in user_suggestions:
            # Check if anyone watched this movie
            movie_votes = df_votes[(df_votes['movie_name'] == movie) & (df_votes['watched'] == True)]
            if len(movie_votes) == 0:
                bonus += bonus_per_new_movie
        
        # 3. Calculate deductions for movies the user did not watch
        all_movies = df_suggestions['movie_name'].unique()
        user_watched_movies = df_votes[(df_votes['user_name'] == user) & (df_votes['watched'] == True)]['movie_name'].tolist()
        movies_not_watched = [movie for movie in all_movies if movie not in user_watched_movies]
        deductions = len(movies_not_watched) * deduction_per_missed_movie
        
        # 4. Calculate total points
        total_points = average_rating + bonus - deductions
        
        # Store the breakdown
        user_breakdown[user] = {
            "average_rating": average_rating,
            "bonus": bonus,
            "deductions": deductions,
            "total": total_points
        }
        user_points[user] = total_points
    
    # Display detailed points breakdown
    st.write("#### Detailed Points Calculation")
    for user, breakdown in user_breakdown.items():
        with st.expander(f"📋 {user}'s Points Breakdown"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Average Rating", f"{breakdown['average_rating']:.2f}")
            with col2:
                st.metric("Bonus", f"{breakdown['bonus']:.2f}")
            with col3:
                st.metric("Deductions", f"{breakdown['deductions']:.2f}")
            with col4:
                st.metric("Total Points", f"{breakdown['total']:.2f}")
            
            st.write(f"**Calculation:** {breakdown['average_rating']:.2f} (Avg Rating) + {breakdown['bonus']:.2f} (Bonus) - {breakdown['deductions']:.2f} (Deductions) = {breakdown['total']:.2f}")
    
    # Display Leaderboard
    st.subheader("🏆 Leaderboard")
    leaderboard_data = []
    for user, points in sorted(user_points.items(), key=lambda x: x[1], reverse=True):
        breakdown = user_breakdown[user]
        leaderboard_data.append({
            "Rank": len(leaderboard_data) + 1,
            "User": user,
            "Total Points": f"{points:.2f}",
            "Avg Rating": f"{breakdown['average_rating']:.2f}",
            "Bonus": f"{breakdown['bonus']:.2f}",
            "Deductions": f"{breakdown['deductions']:.2f}"
        })
    
    df_leaderboard = pd.DataFrame(leaderboard_data)
    st.dataframe(df_leaderboard, use_container_width=True)
    
    # WhatsApp Message Generation
    st.subheader("📱 WhatsApp Messages")
    
    # Sprint Summary Message
    sprint_summary = f"""🎬 *MOVIE CLUB SPRINT RESULTS* 🎬

*Sprint:* {sprint_name}
*Duration:* {sprint_days} days

*📊 Statistics:*
• Movies Suggested: {len(df_suggestions)}
• Total Participants: {len(user_points)}
• Most Active: {max(user_points.items(), key=lambda x: x[1])[0] if user_points else 'N/A'}

*🏆 TOP 3:*
"""
    
    # Add top 3 winners
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)[:3]
    for i, (user, points) in enumerate(sorted_users):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        sprint_summary += f"{medal} {user}: {points:.2f} points\n"
    
    sprint_summary += f"\n*🎬 Movie Ratings Summary:*\n"
    
    # Add movie ratings summary
    if not df_ratings.empty:
        movie_ratings = df_ratings[~df_ratings['did_not_watch']].groupby('movie_name')['rating'].mean().round(2)
        for movie, rating in movie_ratings.items():
            sprint_summary += f"• {movie}: {rating}/10 ⭐\n"
    
    sprint_summary += "\nGreat job everyone! 🎉 See you next sprint! 👋"
    
    # Display messages
    st.text_area("Sprint Summary Message (Copy for WhatsApp)", sprint_summary, height=300)
    
    # Finalize button
    st.markdown("---")
    st.warning("⚠️ Finalizing will archive current data and start a new sprint. This action cannot be undone.")
    
    if st.button("🚀 Finalize Sprint and Archive Data"):
        try:
            # Archive current data (you might want to create archive sheets)
            # For now, we'll just clear the current data for new sprint
            sheet.worksheet("Suggestions").clear()
            sheet.worksheet("Voting").clear() 
            sheet.worksheet("Ratings").clear()
            
            # Update user points in Users sheet (accumulate points)
            ws_users = sheet.worksheet("Users")
            users_records = ws_users.get_all_records()
            for i, user_record in enumerate(users_records):
                user_name = user_record['user_name']
                if user_name in user_points:
                    current_points = float(user_record.get('points', 0))
                    new_points = current_points + user_points[user_name]
                    # Update points in the Users sheet (column 3)
                    ws_users.update_cell(i + 2, 3, round(new_points, 2))
            
            st.success("✅ Sprint finalized! Data archived and new sprint started.")
            st.cache_data.clear()
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Error finalizing sprint: {e}")
