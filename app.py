import os
import streamlit as st
import gspread
from datetime import datetime
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="🎬 Movie Club", layout="wide")

# -----------------------------
# LOAD SECRETS / ENV
# -----------------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

CLOUD_NAME = st.secrets.get("CLOUD_NAME", os.getenv("CLOUD_NAME"))
API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
API_SECRET = st.secrets.get("API_SECRET", os.getenv("API_SECRET"))
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))
ADMIN_PASS = st.secrets.get("adminPass", os.getenv("adminPass"))

# -----------------------------
# CLOUDINARY CONFIG
# -----------------------------
try:
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
except Exception as e:
    st.warning(f"⚠️ Cloudinary config error: {e}")

# -----------------------------
# GOOGLE SHEETS CONNECTION
# -----------------------------
sheet = None
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
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

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_url(GOOGLE_SHEET_URL)
    st.sidebar.success("✅ Connected to Google Sheet")

except Exception as e:
    st.sidebar.error(f"Google Sheets connection error: {e}")

# -----------------------------
# LOAD WORKSHEETS
# -----------------------------
def load_ws(name):
    try:
        return sheet.worksheet(name) if sheet else None
    except:
        st.warning(f"Worksheet '{name}' not found.")
        return None

users_ws = load_ws("Users")
suggestions_ws = load_ws("Suggestions")
ratings_ws = load_ws("Ratings")
voting_ws = load_ws("Voting")
config_ws = load_ws("Config")

# -----------------------------
# LOAD USERS AND ROLES
# -----------------------------
users_list, users_roles = [], {}
if users_ws:
    try:
        data = users_ws.get_all_records()
        users_list = [u["user_name"] for u in data if u.get("user_name")]
        users_roles = {u["user_name"]: u.get("role", "user") for u in data}
    except Exception as e:
        st.warning(f"Failed to load users: {e}")

# -----------------------------
# LOGIN SYSTEM
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

def login(username, password):
    if username not in users_roles:
        st.error("Unknown user")
        return False
    role = users_roles[username]
    if role == "admin":
        if password == ADMIN_PASS:
            st.session_state.logged_in = True
            st.session_state.current_user = username
            st.session_state.is_admin = True
            return True
        else:
            st.error("Incorrect admin password")
            return False
    else:
        st.session_state.logged_in = True
        st.session_state.current_user = username
        st.session_state.is_admin = False
        return True

# LOGIN PAGE
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

# -----------------------------
# CONFIG PAGE ACCESS (Admin Only)
# -----------------------------
if "page_config" not in st.session_state:
    st.session_state.page_config = {
        "Suggest Movie": True,
        "Voting": True,
        "Rate Movies": True
    }

if st.session_state.is_admin and config_ws:
    st.sidebar.subheader("⚙️ Admin Controls")
    with st.sidebar.expander("Enable/Disable Pages"):
        for page in st.session_state.page_config:
            enabled = st.checkbox(f"{page}", value=st.session_state.page_config[page])
            st.session_state.page_config[page] = enabled
        st.info("These toggles control what normal users can access.")

# -----------------------------
# SIDEBAR MENU
# -----------------------------
menu_options = []
if st.session_state.page_config.get("Suggest Movie"): menu_options.append("Suggest Movie")
if st.session_state.page_config.get("Voting"): menu_options.append("Voting")
if st.session_state.page_config.get("Rate Movies"): menu_options.append("Rate Movies")
menu_options.append("Dashboard")
if st.session_state.is_admin: menu_options.append("Admin")

menu = st.sidebar.radio("Navigation", menu_options)

# -----------------------------
# PAGE 1: Suggest Movie
# -----------------------------
if menu == "Suggest Movie":
    st.header("🎬 Suggest a Movie")
    user_name = st.session_state.current_user
    movie_name = st.text_input("Movie Name")
    genre = st.text_input("Genre")
    description = st.text_area("Where to watch it?")
    image = st.file_uploader("Upload Poster (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Submit Suggestion"):
        if not movie_name:
            st.error("Please provide the movie name!")
        else:
            image_url = ""
            if image:
                try:
                    result = cloudinary.uploader.upload(image)
                    image_url = result.get("secure_url", "")
                except Exception as e:
                    st.warning(f"Cloudinary upload failed: {e}")

            if suggestions_ws:
                try:
                    suggestions_ws.append_row([user_name, movie_name, genre, description, image_url, str(datetime.now())])
                    st.success("✅ Your movie suggestion has been submitted!")
                except Exception as e:
                    st.warning(f"Failed to write to Google Sheets: {e}")

# -----------------------------
# PAGE 2: Voting
# -----------------------------
elif menu == "Voting":
    st.header("🎥 Vote for Movies")
    voter_name = st.session_state.current_user

    movies = []
    if suggestions_ws:
        try:
            movies = suggestions_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    votes_data = []
    if movies:
        for movie in movies:
            st.subheader(movie.get("movie_name", "Unknown"))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get("image_url"):
                st.image(movie["image_url"], width=200)
            watched = st.checkbox("Have you watched this?", key=f"vote_{movie.get('movie_name','')}")
            st.markdown("---")
            votes_data.append((movie.get("movie_name",""), watched))

        if st.button("Submit Votes"):
            if voting_ws:
                try:
                    for movie_name, watched in votes_data:
                        voting_ws.append_row([movie_name, voter_name, watched, str(datetime.now())])
                    st.success("✅ Votes submitted!")
                except Exception as e:
                    st.warning(f"Failed to submit votes: {e}")

# -----------------------------
# PAGE 3: Rate Movies
# -----------------------------
elif menu == "Rate Movies":
    st.header("⭐ Rate Movies")
    rater_name = st.session_state.current_user

    movies = []
    if suggestions_ws:
        try:
            movies = suggestions_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    if not movies:
        st.info("No movies suggested yet.")
    else:
        ratings_data = []
        for movie in movies:
            st.subheader(movie.get("movie_name", "Unknown"))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get("image_url"):
                st.image(movie["image_url"], width=200)
            rating = st.slider(
                f"Rate {movie.get('movie_name','')}",
                min_value=5.0,
                max_value=10.0,
                value=7.0,
                step=0.5,
                key=f"rating_{movie.get('movie_name','')}"
            )
            did_not_watch = st.checkbox(f"Did not watch {movie.get('movie_name','')}", key=f"dnw_{movie.get('movie_name','')}")
            st.markdown("---")
            ratings_data.append((movie.get('movie_name',''), rating, did_not_watch))

        if st.button("Submit All Ratings"):
            if ratings_ws:
                try:
                    for movie_name, rating, did_not_watch in ratings_data:
                        ratings_ws.append_row([movie_name, rater_name, rating, did_not_watch, str(datetime.now())])
                    st.success("✅ All ratings submitted successfully!")
                except Exception as e:
                    st.warning(f"Failed to write ratings: {e}")

# -----------------------------
# PAGE 4: Dashboard
# -----------------------------
elif menu == "Dashboard":
    st.header("📊 Dashboard")

    ratings = []
    suggestions = []
    if ratings_ws:
        try:
            ratings = ratings_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch ratings: {e}")
    if suggestions_ws:
        try:
            suggestions = suggestions_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    if not ratings:
        st.info("No ratings yet.")
    else:
        df_ratings = pd.DataFrame(ratings)
        df_ratings["rating"] = df_ratings["rating"].astype(float)
        df_ratings["did_not_watch"] = df_ratings["did_not_watch"].astype(bool)

        st.write("### Ratings by Movie")
        for movie in df_ratings["movie_name"].unique():
            movie_df = df_ratings[df_ratings["movie_name"] == movie]
            avg_rating = movie_df.loc[~movie_df["did_not_watch"], "rating"].mean()
            st.write(f"**{movie}** - Average Rating: {avg_rating:.2f}")
            st.table(movie_df[["rater_name", "rating", "did_not_watch"]])

# -----------------------------
# PAGE 5: Admin
# -----------------------------
elif menu == "Admin" and st.session_state.is_admin:
    st.header("🧑‍💼 Admin Panel")
    st.write("Use sidebar controls to enable/disable pages.")
    st.info("Additional admin functionalities (add users, finalize sprint, etc.) can be added here.")
