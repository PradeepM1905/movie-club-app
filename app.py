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
# LOAD SECRETS
# -------------------
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()

CLOUD_NAME = st.secrets.get("CLOUD_NAME", os.getenv("CLOUD_NAME"))
API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
API_SECRET = st.secrets.get("API_SECRET", os.getenv("API_SECRET"))
GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", os.getenv("GOOGLE_SHEET_URL"))

# -------------------
# CONFIGURE CLOUDINARY
# -------------------
try:
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

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

    sheet = gc.open_by_url(GOOGLE_SHEET_URL)
    suggestions_ws = sheet.worksheet("Suggestions")
    ratings_ws = sheet.worksheet("Ratings")
    voting_ws = sheet.worksheet("Voting")
except Exception as e:
    st.warning(f"Google Sheets connection error: {e}")
    suggestions_ws = ratings_ws = voting_ws = None

try:
    users_ws = sheet.worksheet("Users")
    users_list = [u["user_name"] for u in users_ws.get_all_records() if u.get("user_name")]
except Exception as e:
    st.warning(f"Failed to load users: {e}")
    users_ws = None
    users_list = []
    
# -------------------
# STREAMLIT UI
# -------------------
st.title("🎬 Movie Club")

menu = st.sidebar.radio("Navigation", ["Suggest Movie", "Voting", "Rate Movies", "Dashboard"])

# -------------------
# PAGE 1: Suggest Movie
# -------------------
if menu == "Suggest Movie":
    st.header("Suggest a Movie")
    user_name = st.selectbox("Your Name", users_list if users_list else ["Select user"])
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
                    suggestions_ws.append_row([user_name, movie_name, genre, description, image_url, str(datetime.now())])
                    st.success("✅ Your movie suggestion has been submitted!")
                except Exception as e:
                    st.warning(f"Failed to write to Google Sheets: {e}")
            else:
                st.warning("Google Sheets not connected. Suggestion not saved.")

# -------------------
# PAGE 2: Voting
# -------------------
elif menu == "Voting":
    st.header("Vote if you have watched the movie")
    voter_name = st.selectbox("Your Name for Voting", users_list if users_list else ["Select user"])

    movies = []
    if suggestions_ws:
        try:
            movies = suggestions_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    votes_data = []
    if movies:
        for movie in movies:
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(f"Suggested by: {movie.get('user_name','')}")
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
                        voting_ws.append_row([movie_name, voter_name, watched, str(datetime.now())])
                    st.success("✅ Votes submitted!")
                except Exception as e:
                    st.warning(f"Failed to submit votes: {e}")
            else:
                st.warning("Google Sheets not connected. Votes not saved.")

# -------------------
# PAGE 3: Rate Movies
# -------------------
elif menu == "Rate Movies":
    st.header("Rate Suggested Movies")
    rater_name = st.selectbox("Select your name", users_list if users_list else ["Select user"])

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
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(f"Suggested by: {movie.get('user_name','')}")
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
                        ratings_ws.append_row([movie_name, rater_name, rating, did_not_watch, str(datetime.now())])
                    st.success("✅ All ratings submitted successfully!")
                except Exception as e:
                    st.warning(f"Failed to write ratings: {e}")
            else:
                st.warning("Google Sheets not connected. Ratings not saved.")

# -------------------
# PAGE 4: Dashboard
# -------------------
elif menu == "Dashboard":
    st.header("Movie Ratings Dashboard")

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
            st.table(movie_df[["user_name", "rating", "did_not_watch"]])

        st.write("### Points by User")
        points_list = []
        for user in df_ratings["user_name"].unique():
            user_df = df_ratings[df_ratings["user_name"] == user]
            avg_point = user_df.loc[~user_df["did_not_watch"], "rating"].mean()
            bonus = 0.5 if user_df["did_not_watch"].sum() == 0 else 0
            deduction = 0.25 * user_df["did_not_watch"].sum()
            total_points = avg_point + bonus - deduction
            points_list.append({
                "user_name": user,
                "avg_rating": avg_point,
                "bonus": bonus,
                "did_not_watch_deduction": deduction,
                "total_points": total_points
            })
        st.table(pd.DataFrame(points_list))
