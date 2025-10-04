# app.py
import os
import streamlit as st
import gspread
from datetime import datetime
import pandas as pd
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------
# STREAMLIT CONFIG
# -----------------------
st.set_page_config(page_title="Movie Club", layout="wide")

st.write("Secrets loaded:", st.secrets.keys())
# -----------------------
# SECRETS / CONFIG
# -----------------------
ADMIN_PASS = st.secrets.get("adminPass")  # admin password
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL")
GCP_SA = st.secrets.get("gcp_service_account")  # service account dict
CLOUD_NAME = st.secrets.get("CLOUD_NAME")
API_KEY = st.secrets.get("API_KEY")
API_SECRET = st.secrets.get("API_SECRET")

# -----------------------
# CLOUDINARY CONFIG
# -----------------------
try:
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET,
        secure=True
    )
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

# -----------------------
# GOOGLE SHEETS CONNECTION
# -----------------------
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GCP_SA, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(GOOGLE_SHEET_URL)
except Exception as e:
    st.error(f"Google Sheets connection error: {e}")
    st.stop()

# -----------------------
# CACHED LOADERS (accept sheet name strings)
# -----------------------
@st.cache_data(ttl=60)
def load_sheet(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        return ws.get_all_records()
    except Exception as e:
        st.warning(f"Failed to load {sheet_name}: {e}")
        return []

@st.cache_data(ttl=60)
def load_config():
    try:
        ws = sheet.worksheet("Config")
        recs = ws.get_all_records()
        config = {r["key"]: str(r["value"]).lower() == "true" for r in recs}
        return config
    except Exception as e:
        st.warning(f"Failed to load Config: {e}")
        # sensible defaults
        return {"enable_suggestion": True, "enable_voting": True, "enable_rating": True}

def save_config(config_dict):
    try:
        ws = sheet.worksheet("Config")
        for k, v in config_dict.items():
            cell = None
            try:
                cell = ws.find(k)
            except Exception:
                cell = None
            if cell:
                ws.update_cell(cell.row, 2, str(v))
            else:
                ws.append_row([k, str(v)])
        st.cache_data.clear()
        st.success("✅ Config updated")
    except Exception as e:
        st.error(f"Failed to save config: {e}")

# -----------------------
# LOAD USERS (no caching here since it's simple)
# -----------------------
try:
    users_ws = sheet.worksheet("Users")
    users_records = users_ws.get_all_records()
    users_list = [r["user_name"] for r in users_records if r.get("user_name")]
    users_roles = {r["user_name"]: r.get("role", "normal").lower() for r in users_records if r.get("user_name")}
except Exception as e:
    st.warning(f"Failed to load Users sheet: {e}")
    users_list, users_roles = [], {}

# -----------------------
# SESSION STATE
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

# -----------------------
# LOGIN UI & Logic
# -----------------------
def login(username, password=None):
    role = users_roles.get(username, "normal")
    if role == "admin":
        if password != ADMIN_PASS:
            st.error("Incorrect admin password")
            return False
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.role = role
    st.success(f"Logged in as {username} ({role})")
    return True

if not st.session_state.logged_in:
    st.title("🎬 Movie Club — Login")
    username = st.selectbox("Select username", users_list)
    password = None
    if users_roles.get(username) == "admin":
        password = st.text_input("Admin password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.rerun()
    st.stop()

# -----------------------
# Sidebar / common
# -----------------------
st.sidebar.write(f"👤 {st.session_state.username} ({st.session_state.role})")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

config = load_config()

# Build navigation based on config and role
menu = []
if config.get("enable_suggestion", True) or st.session_state.role == "admin":
    menu.append("Suggest Movie")
if config.get("enable_voting", True) or st.session_state.role == "admin":
    menu.append("Voting")
if config.get("enable_rating", True) or st.session_state.role == "admin":
    menu.append("Rate Movies")
menu.append("Dashboard")
if st.session_state.role == "admin":
    menu += ["Admin Panel", "Finalize Sprint"]

selected = st.sidebar.radio("Navigation", menu)

# -----------------------
# Suggest Movie (with Cloudinary upload)
# -----------------------
if selected == "Suggest Movie":
    if not config.get("enable_suggestion", True) and st.session_state.role != "admin":
        st.warning("Suggestion page is disabled by admin.")
        st.stop()

    st.header("🎥 Suggest a Movie (anonymous in UI)")
    movie_name = st.text_input("Movie name")
    genre = st.text_input("Genre")
    platform = st.text_input("Where to watch (platform/link)")
    image = st.file_uploader("Poster (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Submit Suggestion"):
        if not movie_name:
            st.error("Please enter movie name.")
        else:
            image_url = ""
            if image is not None:
                try:
                    # Cloudinary accepts file-like objects; streamlit UploadedFile works
                    # If issues occur, use image.read(), but uploader can accept file object
                    res = cloudinary.uploader.upload(image)
                    image_url = res.get("secure_url", "")
                except Exception as e:
                    st.warning(f"Cloudinary upload failed: {e}")
                    image_url = ""
            try:
                ws = sheet.worksheet("Suggestions")
                ws.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    st.session_state.username,  # stored but UI remains anonymous
                    movie_name,
                    genre,
                    platform,
                    image_url,
                    datetime.now().isoformat()
                ])
                st.cache_data.clear()
                st.success("✅ Suggestion submitted (stored anonymously in UI).")
            except Exception as e:
                st.error(f"Failed to save suggestion: {e}")

# -----------------------
# Voting Page
# -----------------------
elif selected == "Voting":
    if not config.get("enable_voting", True) and st.session_state.role != "admin":
        st.warning("Voting page is disabled by admin.")
        st.stop()

    st.header("🗳️ Voting — Have you watched it?")
    suggestions = load_sheet("Suggestions")
    if not suggestions:
        st.info("No suggestions yet.")
    else:
        voter = st.session_state.username
        votes = []
        for row in suggestions:
            st.subheader(row.get("movie_name", "Unknown"))
            st.write(f"Genre: {row.get('genre','')}")
            st.write(f"Where: {row.get('platform','')}")
            if row.get("image_url"):
                st.image(row.get("image_url"), width=200)
            watched = st.checkbox("Have you watched this?", key=f"vote_{row.get('movie_name')}")
            votes.append((row.get("movie_name"), watched))
            st.markdown("---")

        if st.button("Submit Votes"):
            try:
                ws = sheet.worksheet("Voting")
                for movie_name, watched in votes:
                    ws.append_row([movie_name, voter, bool(watched), datetime.now().isoformat()])
                st.cache_data.clear()
                st.success("✅ Votes submitted")
            except Exception as e:
                st.error(f"Failed to save votes: {e}")

# -----------------------
# Rate Movies Page
# -----------------------
elif selected == "Rate Movies":
    if not config.get("enable_rating", True) and st.session_state.role != "admin":
        st.warning("Rating page is disabled by admin.")
        st.stop()

    st.header("⭐ Rate Movies")
    suggestions = load_sheet("Suggestions")
    if not suggestions:
        st.info("No movies to rate yet.")
    else:
        rater = st.session_state.username
        ratings_to_submit = []
        for row in suggestions:
            movie = row.get("movie_name")
            st.subheader(movie)
            if row.get("image_url"):
                st.image(row.get("image_url"), width=200)
            rating = st.slider(f"Rate {movie}", 5.0, 10.0, 7.5, 0.5, key=f"rating_{movie}")
            did_not_watch = st.checkbox(f"Did not watch {movie}", key=f"dnw_{movie}")
            ratings_to_submit.append((movie, rating, bool(did_not_watch)))
            st.markdown("---")

        if st.button("Submit Ratings"):
            try:
                ws = sheet.worksheet("Ratings")
                for movie, rating, dnw in ratings_to_submit:
                    ws.append_row([movie, rater, rating, dnw, datetime.now().isoformat()])
                st.cache_data.clear()
                st.success("✅ Ratings submitted")
            except Exception as e:
                st.error(f"Failed to save ratings: {e}")

# -----------------------
# Dashboard
# -----------------------
elif selected == "Dashboard":
    st.header("📊 Dashboard")
    ratings = load_sheet("Ratings")
    if not ratings:
        st.info("No ratings yet.")
    else:
        df = pd.DataFrame(ratings)
        # defensive column mapping
        if "rater_name" not in df.columns and "rater" in df.columns:
            df.rename(columns={"rater": "rater_name"}, inplace=True)
        if "rating" in df.columns:
            df["rating"] = df["rating"].astype(float)
        if "did_not_watch" in df.columns:
            df["did_not_watch"] = df["did_not_watch"].astype(bool)

        st.write("### Latest suggestions (preview)")
        sugg = load_sheet("Suggestions")
        if sugg:
            st.table(pd.DataFrame(sugg).tail(10))

        st.write("### Ratings summary (by movie)")
        if "movie_name" in df.columns:
            for movie in df["movie_name"].unique():
                movie_df = df[df["movie_name"] == movie]
                avg = movie_df.loc[~movie_df["did_not_watch"], "rating"].mean()
                st.write(f"🎬 {movie} — Average: {avg:.2f}")

# -----------------------
# Admin Panel (persist config in Config sheet)
# -----------------------
elif selected == "Admin Panel":
    if st.session_state.role != "admin":
        st.warning("Admin only.")
        st.stop()

    st.header("⚙️ Admin Panel")
    cfg = load_config()
    st.subheader("Page controls (persisted)")
    en_suggest = st.checkbox("Enable Suggestion", value=cfg.get("enable_suggestion", True))
    en_vote = st.checkbox("Enable Voting", value=cfg.get("enable_voting", True))
    en_rate = st.checkbox("Enable Rating", value=cfg.get("enable_rating", True))

    if st.button("Save Page Controls"):
        newcfg = {"enable_suggestion": en_suggest, "enable_voting": en_vote, "enable_rating": en_rate}
        save_config(newcfg)
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("Add user")
    new_user = st.text_input("New user's name")
    new_role = st.selectbox("Role", ["normal", "admin"])
    if st.button("Add User"):
        try:
            ws = sheet.worksheet("Users")
            ws.append_row([new_user, new_role])
            st.cache_data.clear()
            st.success(f"Added {new_user} as {new_role}")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add user: {e}")

# -----------------------
# Finalize Sprint (placeholder)
# -----------------------
elif selected == "Finalize Sprint":
    if st.session_state.role != "admin":
        st.warning("Admin only.")
        st.stop()

    st.header("🏁 Finalize Sprint")
    st.info("Finalize sprint logic (points calc & WhatsApp message) can be implemented here.")
