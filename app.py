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
# SESSION STATE INIT
# -------------------
for key in ["logged_in", "username", "role"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "logged_in" else False

# -------------------
# CONNECT TO GOOGLE SHEETS
# -------------------
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
# LOAD USERS FROM SHEET
# -------------------
users_list = []
users_roles = {}
try:
    if users_ws:
        for row in users_ws.get_all_records():
            uname = row.get("user_name")
            role = row.get("role", "normal")
            if uname:
                users_list.append(uname)
                users_roles[uname] = role
except Exception as e:
    st.warning(f"Failed to load users: {e}")
    users_list = []
    users_roles = {}

# -------------------
# LOGIN PAGE
# -------------------
def login(username, password=None):
    if username not in users_roles:
        st.error("Invalid username")
        return False
    role = users_roles[username]
    if role == "admin":
        admin_pass = st.secrets.get("adminPass")
        if password != admin_pass:
            st.error("Incorrect admin password")
            return False
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.role = role
    st.success(f"Logged in as {username} ({role})")
    return True

if not st.session_state.logged_in:
    st.title("🎬 Movie Club Login")
    username = st.selectbox("Select Username", users_list)
    if users_roles.get(username) == "admin":
        password = st.text_input("Admin Password", type="password")
    else:
        password = None
    if st.button("Login"):
        login(username, password)
    st.stop()

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
    today = st.sidebar.date_input("Select current date", value=datetime.today())
else:
    today = datetime.today().date()

st.sidebar.write(f"Logged in as: **{st.session_state.username} ({st.session_state.role})**")
st.write(f"📅 Effective Date: {today.strftime('%Y-%m-%d')}")

# -------------------
# UTILITY FUNCTIONS
# -------------------
@st.cache_data(ttl=60)
def load_sheet(ws):
    if ws:
        return ws.get_all_records()
    return []

def get_current_sprint(sprints_list, current_date):
    for sprint in sprints_list:
        start_date = datetime.strptime(sprint["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d").date()
        if start_date <= current_date <= end_date:
            return sprint["sprint_id"], sprint.get("description", "")
    return None, ""

# -------------------
# LOAD SHEET DATA
# -------------------
suggestions_list = load_sheet(suggestions_ws)
ratings_list = load_sheet(ratings_ws)
voting_list = load_sheet(voting_ws)
sprints_list = load_sheet(sprints_ws)
points_list = load_sheet(points_ws)

current_sprint_id, current_sprint_desc = get_current_sprint(sprints_list, today)
st.write(f"📌 Current Sprint: {current_sprint_id} {current_sprint_desc}")

# -------------------
# PAGE ACCESS CONTROL
# -------------------
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
# PAGES LOGIC
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
    st.header("Voting Page")
    voter_name = st.selectbox("Your Name", users_list)
    movies = [m for m in suggestions_list if m.get("sprint") == current_sprint_id] if suggestions_list else []
    votes_data = []
    if movies:
        for movie in movies:
            st.subheader(movie.get("movie_name", "Unknown"))
            st.write(f"Genre: {movie.get('genre', '')}")
            st.write(f"Where to watch: {movie.get('description', '')}")
            if movie.get("image_url"):
                st.image(movie["image_url"], width=200)
            watched = st.checkbox("Have you watched this?", key=f"vote_{movie.get('movie_name')}")
            votes_data.append((movie.get("movie_name"), watched))
            st.markdown("---")

        if st.button("Submit Votes"):
            if voting_ws:
                try:
                    for movie_name, watched in votes_data:
                        voting_ws.append_row([current_sprint_id, movie_name, voter_name, watched, str(datetime.now())])
                    st.success("✅ Votes submitted!")
                except Exception as e:
                    st.warning(f"Failed to submit votes: {e}")

# --- Rate Movies ---
elif menu == "Rate Movies":
    st.header("Rate Movies Page")
    rater_name = st.selectbox("Your Name", users_list)
    # Previous sprint
    prev_sprint_id = None
    if sprints_list:
        idx = next((i for i, s in enumerate(sprints_list) if s["sprint_id"] == current_sprint_id), None)
        prev_sprint_id = sprints_list[idx-1]["sprint_id"] if idx and idx > 0 else None
    movies = [m for m in suggestions_list if m.get("sprint") == prev_sprint_id] if suggestions_list else []

    ratings_data = []
    for movie in movies:
        st.subheader(movie.get("movie_name", "Unknown"))
        st.write(f"Genre: {movie.get('genre','')}")
        st.write(f"Where to watch: {movie.get('description','')}")
        if movie.get("image_url"):
            st.image(movie["image_url"], width=200)
        rating = st.slider(f"Rate {movie.get('movie_name')}", 5.0, 10.0, 5.0, 0.5, key=f"rating_{movie.get('movie_name')}")
        did_not_watch = st.checkbox(f"Did not watch {movie.get('movie_name')}", key=f"dnw_{movie.get('movie_name')}")
        ratings_data.append((movie.get("movie_name"), rating, did_not_watch))
        st.markdown("---")

    if st.button("Submit Ratings"):
        if ratings_ws:
            try:
                for movie_name, rating, dnw in ratings_data:
                    ratings_ws.append_row([prev_sprint_id, movie_name, rater_name, rating, dnw, str(datetime.now())])
                st.success("✅ Ratings submitted!")
            except Exception as e:
                st.warning(f"Failed to submit ratings: {e}")

# --- Dashboard ---
elif menu == "Dashboard":
    st.header("Dashboard Page")
    st.write("Display ratings, points, leaderboard here.")

# --- Finalize Sprint ---
elif menu == "Finalize Sprint":
    if st.session_state.role != "admin":
        st.warning("Only admin can finalize sprint")
    else:
        st.header("Finalize Sprint")
        st.write("Admin can finalize sprint, update points, and generate WhatsApp messages here.")
