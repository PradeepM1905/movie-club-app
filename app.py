import os
import streamlit as st

# Must be first Streamlit command
st.set_page_config(page_title="Movie Club", page_icon="🎬", layout="wide")

import gspread
from datetime import datetime
import pandas as pd
import altair as alt
import cloudinary
import cloudinary.uploader
from oauth2client.service_account import ServiceAccountCredentials
import json

# -------------------
# LOAD SECRETS
# -------------------
# Local development: load from .env
if "CLOUD_NAME" not in st.secrets:
    from dotenv import load_dotenv
    load_dotenv()  # reads variables from .env

# Cloudinary credentials
CLOUD_NAME = st.secrets["CLOUD_NAME"] if "CLOUD_NAME" in st.secrets else os.getenv("CLOUD_NAME")
API_KEY = st.secrets["API_KEY"] if "API_KEY" in st.secrets else os.getenv("API_KEY")
API_SECRET = st.secrets["API_SECRET"] if "API_SECRET" in st.secrets else os.getenv("API_SECRET")

# Google Sheets URL
GOOGLE_SHEET_URL = st.secrets["GOOGLE_SHEET_URL"] if "GOOGLE_SHEET_URL" in st.secrets else os.getenv("GOOGLE_SHEET_URL")

# -------------------
# CONFIGURE CLOUDINARY
# -------------------
try:
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET
    )
except Exception as e:
    st.warning(f"Cloudinary config error: {e}")

# -------------------
# CONNECT TO GOOGLE SHEETS
# -------------------
try:
    if "type" in st.secrets:  # Streamlit Cloud
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
    else:  # Local
        gc = gspread.service_account(filename="credentials.json")

    sheet = gc.open_by_url(GOOGLE_SHEET_URL)
    suggestions_ws = sheet.worksheet("Suggestions")
    ratings_ws = sheet.worksheet("Ratings")
except Exception as e:
    st.warning(f"Google Sheets connection error: {e}")
    suggestions_ws = None
    ratings_ws = None

# -------------------
# STREAMLIT UI
# -------------------
st.title("🎬 Movie Club App (Robust Version)")

menu = st.sidebar.radio("Navigation", ["Suggest Movie", "Rate Movies", "Dashboard"])

# -------------------
# PAGE 1: Suggest Movie
# -------------------
if menu == "Suggest Movie":
    st.header("Suggest a Movie")
    movie_name = st.text_input("Movie Name")
    description = st.text_area("Why should we watch it?")
    image = st.file_uploader("Upload Poster (optional)", type=["png", "jpg", "jpeg"])

    if st.button("Submit Suggestion"):
        if not movie_name:
            st.error("Movie name is required!")
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
                    suggestions_ws.append_row([movie_name, description, image_url, str(datetime.now())])
                    st.success("✅ Your movie suggestion has been submitted anonymously!")
                except Exception as e:
                    st.warning(f"Failed to write to Google Sheets: {e}")
            else:
                st.warning("Google Sheets not connected. Suggestion not saved.")

# -------------------
# PAGE 2: Rate Movies
# -------------------
elif menu == "Rate Movies":
    st.header("Rate Suggested Movies")
    user_name = st.text_input("Enter your name or nickname")

    movies = []
    if suggestions_ws:
        try:
            movies = suggestions_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    if not movies:
        st.info("No movies suggested yet.")
    else:
        for movie in movies:
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(movie.get('description', ''))
            if movie.get('image_url'):
                st.image(movie['image_url'], width=200)
            rating = st.slider(f"Rate {movie.get('movie_name', '')}", 1, 10, 5, key=movie.get('movie_name', ''))

            if st.button(f"Submit Rating for {movie.get('movie_name', '')}", key=f"rate_{movie.get('movie_name', '')}"):
                if not user_name:
                    st.error("Please enter your name before rating!")
                elif ratings_ws:
                    try:
                        ratings_ws.append_row([movie.get('movie_name', ''), user_name, rating, str(datetime.now())])
                        st.success(f"✅ Rating for {movie.get('movie_name', '')} submitted!")
                    except Exception as e:
                        st.warning(f"Failed to write rating to Google Sheets: {e}")
                else:
                    st.warning("Google Sheets not connected. Rating not saved.")

# -------------------
# PAGE 3: Dashboard
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
        avg_ratings = df_ratings.groupby("movie_name")["rating"].mean().reset_index()
        avg_ratings = avg_ratings.sort_values("rating", ascending=False)

        st.write("### Average Ratings")
        st.table(avg_ratings)

        chart = alt.Chart(avg_ratings).mark_bar().encode(
            x="movie_name",
            y="rating",
            tooltip=["movie_name", "rating"]
        )
        st.altair_chart(chart, use_container_width=True)

        st.write("### All Ratings")
        st.dataframe(df_ratings)

        st.write("### Movie Posters")
        for movie in suggestions:
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(movie.get('description', ''))
            if movie.get('image_url'):
                st.image(movie['image_url'], width=200)

