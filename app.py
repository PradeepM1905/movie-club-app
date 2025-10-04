import os
import streamlit as st
import gspread
from datetime import datetime
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials

# -------------------
# PAGE CONFIG
# -------------------
st.set_page_config(page_title="Movie Club", page_icon="🎬", layout="wide")

# -------------------
# LOGIN SYSTEM
# -------------------
# Example st.secrets:
# {
#   "users": {
#       "admin": {"password": "admin_pass", "role": "admin"},
#       "user1": {"password": "user1_pass", "role": "normal"}
#   }
# }

users_secrets = st.secrets.get("users", {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

def login(username, password):
    user = users_secrets.get(username)
    if user and user["password"] == password:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.role = user["role"]
        st.success(f"Logged in as {username} ({user['role']})")
        return True
    else:
        st.error("Invalid username or password")
        return False

if not st.session_state.logged_in:
    st.title("🎬 Movie Club Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login(username, password)
    st.stop()  # Stop app until login

# -------------------
# CONNECT TO GOOGLE SHEETS
# -------------------
if st.session_state.logged_in:
    try:
        if "type" in st.secrets:
            credentials_dict = {
                "type": st.secrets["type"],
                "project_id": st.secrets["project_id"],
                "private_key_id": st.secrets["private_key_id"],
                "private_key": st.secrets["private_key"],
                "client_email": st.secrets["client_email"],
                "client_id": st.secrets["client_id"],
                "auth_uri": st.secrets["auth_uri"],
                "token_uri": st.secrets["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["client_x509_cert_url"]
            }
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
            gc = gspread.service_account(filename="credentials.json")

        sheet = gc.open_by_url(st.secrets.get("GOOGLE_SHEET_URL"))
        suggestions_ws = sheet.worksheet("Suggestions")
        ratings_ws = sheet.worksheet("Ratings")
        voting_ws = sheet.worksheet("Voting")
        users_ws = sheet.worksheet("Users")
        sprints_ws = sheet.worksheet("Sprints")
        points_ws = sheet.worksheet("Points")
    except Exception as e:
        st.warning(f"Google Sheets connection error: {e}")
        suggestions_ws = ratings_ws = voting_ws = users_ws = sprints_ws = points_ws = None

# -------------------
# CACHED SHEET READS
# -------------------
@st.cache_data(ttl=60)
def load_users():
    if users_ws:
        return [u["user_name"] for u in users_ws.get_all_records() if u.get("user_name")]
    return []

@st.cache_data(ttl=60)
def load_suggestions():
    if suggestions_ws:
        return suggestions_ws.get_all_records()
    return []

@st.cache_data(ttl=60)
def load_ratings():
    if ratings_ws:
        return ratings_ws.get_all_records()
    return []

@st.cache_data(ttl=60)
def load_voting():
    if voting_ws:
        return voting_ws.get_all_records()
    return []

@st.cache_data(ttl=60)
def load_sprints():
    if sprints_ws:
        return sprints_ws.get_all_records()
    return []

@st.cache_data(ttl=60)
def load_points():
    if points_ws:
        return points_ws.get_all_records()
    return []

users_list = load_users()
suggestions_list = load_suggestions()
ratings_list = load_ratings()
voting_list = load_voting()
sprints_list = load_sprints()
points_list = load_points()

# -------------------
# CLOUDINARY CONFIG
# -------------------
try:
    cloudinary.config(
        cloud_name=st.secrets.get("CLOUD_NAME"),
        api_key=st.secrets.get("API_KEY"),
        api_secret=st.secrets.get("API_SECRET")
    )
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

# -------------------
# TESTING MODE
# -------------------
testing_mode = st.sidebar.checkbox("Enable Testing Mode", value=False)
if testing_mode:
    today = st.sidebar.date_input("Select current date (for testing)", value=datetime.today())
else:
    today = datetime.today().date()

st.sidebar.write(f"Logged in as: **{st.session_state.username} ({st.session_state.role})**")
st.write(f"📅 Effective Date: {today.strftime('%Y-%m-%d')}")

# -------------------
# UTILITY: Current Sprint
# -------------------
def get_current_sprint(sprints_list, current_date):
    for sprint in sprints_list:
        start_date = datetime.strptime(sprint["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d").date()
        if start_date <= current_date <= end_date:
            return sprint["sprint_id"], sprint.get("description", "")
    return None, ""

current_sprint_id, current_sprint_desc = get_current_sprint(sprints_list, today)
st.write(f"📌 Current Sprint: {current_sprint_id} {current_sprint_desc}")

# -------------------
# PAGE ACCESS CONTROL
# -------------------
# Admin control switches
if st.session_state.role == "admin":
    st.sidebar.header("Admin Controls")
    enable_suggestion = st.sidebar.checkbox("Enable Suggestion Page", value=True)
    enable_voting = st.sidebar.checkbox("Enable Voting Page", value=True)
    enable_rating = st.sidebar.checkbox("Enable Rating Page", value=True)
else:
    enable_suggestion = enable_voting = enable_rating = True

menu_items = ["Dashboard", "Finalize Sprint"]
if enable_suggestion:
    menu_items.insert(0, "Suggest Movie")
if enable_voting:
    menu_items.insert(1 if enable_suggestion else 0, "Voting")
if enable_rating:
    menu_items.insert(2 if enable_suggestion and enable_voting else 1, "Rate Movies")

menu = st.sidebar.radio("Navigation", menu_items)

# -------------------
# PAGE LOGIC
# -------------------
# --- Suggest Movie ---
if menu == "Suggest Movie":
    st.header("Suggest a Movie")
    if users_list:
        user_name = st.selectbox("Your Name", users_list)
    else:
        user_name = st.text_input("Your Name")
    movie_name = st.text_input("Movie Name")
    genre = st.text_input("Genre")
    description = st.text_area("Where to watch it?")
    image = st.file_uploader("Upload Poster (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Submit Suggestion"):
        if not movie_name or not user_name:
            st.error("Please provide your name and movie name!")
        else:
            image_url = ""
            if image:
                try:
                    result = cloudinary.uploader.upload(image)
                    image_url = result.get('secure_url', '')
                except Exception as e:
                    st.warning(f"Cloudinary upload failed: {e}")

            if suggestions_ws:
                try:
                    suggestions_ws.append_row([current_sprint_id, user_name, movie_name, genre, description, image_url, str(datetime.now())])
                    st.success("✅ Your movie suggestion has been submitted!")
                except Exception as e:
                    st.warning(f"Failed to write to Google Sheets: {e}")
            else:
                st.warning("Google Sheets not connected. Suggestion not saved.")

# --- Voting ---
elif menu == "Voting":
    st.header("Vote if you have watched the movie")
    if users_list:
        voter_name = st.selectbox("Your Name for Voting", users_list)
    else:
        voter_name = st.text_input("Your Name for Voting")

    movies = [m for m in suggestions_list if m.get("sprint") == current_sprint_id] if suggestions_list else []
    votes_data = []
    if movies:
        for movie in movies:
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get('image_url'):
                st.image(movie['image_url'], width=200)
            watched = st.checkbox("Have you watched this?", key=f"vote_{movie.get('movie_name','')}")
            st.markdown("---")
            votes_data.append((movie.get('movie_name',''), watched))

        if st.button("Submit Votes"):
            if not voter_name:
                st.error("Please enter your name to vote!")
            elif voting_ws:
                try:
                    for movie_name, watched in votes_data:
                        voting_ws.append_row([current_sprint_id, movie_name, voter_name, watched, str(datetime.now())])
                    st.success("✅ Votes submitted!")
                except Exception as e:
                    st.warning(f"Failed to submit votes: {e}")
            else:
                st.warning("Google Sheets not connected. Votes not saved.")

# --- Rate Movies ---
elif menu == "Rate Movies":
    st.header("Rate Suggested Movies")
    if users_list:
        rater_name = st.selectbox("Enter your name or nickname", users_list)
    else:
        rater_name = st.text_input("Enter your name or nickname")

    # Previous sprint movies
    prev_sprint_id = None
    if sprints_list:
        sprint_index = next((i for i, s in enumerate(sprints_list) if s["sprint_id"] == current_sprint_id), None)
        prev_sprint_id = sprints_list[sprint_index-1]["sprint_id"] if sprint_index and sprint_index > 0 else None

    movies = [m for m in suggestions_list if m.get("sprint") == prev_sprint_id] if suggestions_list else []

    if not movies:
        st.info("No movies to rate for previous sprint.")
    else:
        ratings_data = []
        for movie in movies:
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get('image_url'):
                st.image(movie['image_url'], width=200)
            rating = st.slider(
                f"Rate {movie.get('movie_name','')}",
                min_value=5.0,
                max_value=10.0,
                value=5.0,
                step=0.5,
                key=f"rating_{movie.get('movie_name','')}"
            )
            did_not_watch = st.checkbox(f"Did not watch {movie.get('movie_name','')}", key=f"dnw_{movie.get('movie_name','')}")
            st.markdown("---")
            ratings_data.append((movie.get('movie_name',''), rating, did_not_watch))

        if st.button("Submit All Ratings"):
            if not rater_name:
                st.error("Please enter your name before submitting ratings!")
            elif ratings_ws:
                try:
                    for movie_name, rating, did_not_watch in ratings_data:
                        ratings_ws.append_row([prev_sprint_id, movie_name, rater_name, rating, did_not_watch, str(datetime.now())])
                    st.success("✅ All ratings submitted successfully!")
                except Exception as e:
                    st.warning(f"Failed to write ratings: {e}")
            else:
                st.warning("Google Sheets not connected. Ratings not saved.")

# --- Dashboard ---
elif menu == "Dashboard":
    st.header("Movie Ratings Dashboard")
    st.write("Dashboard UI goes here (ratings, points, leaderboard)")

# --- Finalize Sprint ---
elif menu == "Finalize Sprint":
    if st.session_state.role != "admin":
        st.warning("Only admin can finalize sprint")
    else:
        st.header("Finalize Sprint")
        st.write("Finalize Sprint UI goes here")
