import os
import streamlit as st
import gspread
from datetime import datetime, date
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials

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
    for row in users_data:
        uname = row.get("user_name")
        role = row.get("role", "normal").lower()
        if uname:
            users_list.append(uname)
            users_roles[uname] = role
    return users_list, users_roles

# ---------------------------------------
# LOGIN SYSTEM
# ---------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = "normal"

users_list, users_roles = reload_users()

def login(username, password):
    if username not in users_roles:
        st.error("Invalid username")
        return False
    role = users_roles[username]
    if role == "admin":
        if password != ADMIN_PASS:
            st.error("Incorrect admin password")
            return False
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.role = role
    st.success(f"✅ Logged in as {username} ({role})")
    return True

if not st.session_state.logged_in:
    st.title("🎬 Movie Club Login")
    username = st.selectbox("Select Username", users_list)
    password = None
    if users_roles.get(username) == "admin":
        password = st.text_input("Admin Password", type="password")

    if st.button("Login"):
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
menu = ["Suggest Movie", "Voting", "Rate Movies", "Dashboard"]
if st.session_state.role == "admin":
    menu += ["Admin Panel", "Finalize Sprint"]
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
    st.checkbox("Enable Suggestion Page", key="enable_suggestion")
    st.checkbox("Enable Voting Page", key="enable_voting")
    st.checkbox("Enable Rating Page", key="enable_rating")

    st.subheader("Add New User")
    new_user = st.text_input("New User Name")
    role = st.selectbox("Role", ["normal", "admin"])
    if st.button("Add User"):
        try:
            ws = sheet.worksheet("Users")
            ws.append_row([new_user, role])
            st.success(f"✅ Added {new_user} as {role}")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.warning(f"Failed to add user: {e}")

# ---------------------------------------
# PAGE: FINALIZE SPRINT
# ---------------------------------------
elif selected == "Finalize Sprint":
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        st.stop()

    st.header("🏁 Finalize Sprint")
    st.info("This section will finalize sprint, calculate points and generate WhatsApp messages.")
