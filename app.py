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
    points_ws = sheet.worksheet("Points")
    users_ws = sheet.worksheet("Users")
    sprints_ws = sheet.worksheet("Sprints")
except Exception as e:
    st.warning(f"Google Sheets connection error: {e}")
    suggestions_ws = ratings_ws = voting_ws = points_ws = users_ws = sprints_ws = None

# -------------------
# FETCH USERS AND SPRINTS
# -------------------
try:
    users_list = [u["user_name"] for u in users_ws.get_all_records() if u.get("user_name")]
except Exception as e:
    st.warning(f"Failed to load users: {e}")
    users_list = []

try:
    sprints_list = sprints_ws.get_all_records() if sprints_ws else []
except Exception as e:
    st.warning(f"Failed to load sprints: {e}")
    sprints_list = []

def get_current_sprint(sprints_list):
    #today = datetime.today().date()

    #for Testing----------------------
    test_date = st.sidebar.date_input(
        "Select current date (for testing)",
        value=datetime.today()
    )
    today = test_date
    #----------------------------------
    
    for sprint in sprints_list:
        start_date = datetime.strptime(sprint["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d").date()
        if start_date <= today <= end_date:
            return sprint["sprint_id"], sprint.get("description", "")
    return None, ""

current_sprint_id, current_sprint_desc = get_current_sprint(sprints_list)

# -------------------
# STREAMLIT UI
# -------------------
st.title("🎬 Movie Club")
st.write(f"📅 Current Sprint: {current_sprint_id} {current_sprint_desc}")
st.write(f"📅 Effective Date: {today.strftime('%Y-%m-%d')}")

menu = st.sidebar.radio("Navigation", ["Suggest Movie", "Voting", "Rate Movies", "Dashboard", "Finalize Sprint"])

# -------------------
# PAGE 1: Suggest Movie
# -------------------
if menu == "Suggest Movie":
    st.header("Suggest a Movie")

    user_name = st.selectbox("Your Name", users_list)
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
                    suggestions_ws.append_row([
                        current_sprint_id,
                        user_name,
                        movie_name,
                        genre,
                        description,
                        image_url,
                        str(datetime.now())
                    ])
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
    voter_name = st.selectbox("Your Name for Voting", users_list)

    movies = []
    if suggestions_ws:
        try:
            # Fetch only current sprint suggestions
            all_movies = suggestions_ws.get_all_records()
            movies = [m for m in all_movies if m["sprint"] == current_sprint_id]
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    votes_data = []
    if movies:
        for idx, movie in enumerate(movies):
            st.subheader(movie.get('movie_name', 'Unknown'))
            st.write(f"Genre: {movie.get('genre','')}")
            st.write(f"Where to watch: {movie.get('description','')}")
            if movie.get('image_url'):
                st.image(movie['image_url'], width=200)
            watched = st.checkbox("Have you watched this?", key=f"vote_{idx}")
            st.markdown("---")
            votes_data.append((movie.get('movie_name',''), watched))

        if st.button("Submit Votes"):
            if not voter_name:
                st.error("Please enter your name to vote!")
            elif voting_ws:
                try:
                    for movie_name, watched in votes_data:
                        voting_ws.append_row([
                            current_sprint_id,
                            movie_name,
                            voter_name,
                            watched,
                            str(datetime.now())
                        ])
                    st.success("✅ Votes submitted!")
                except Exception as e:
                    st.warning(f"Failed to submit votes: {e}")
            else:
                st.warning("Google Sheets not connected. Votes not saved.")
    else:
        st.info("No movie suggestions for this sprint yet.")

# -------------------
# PAGE 3: Rate Movies
# -------------------
elif menu == "Rate Movies":
    st.header("Rate Suggested Movies")

    rater_name = st.selectbox("Select your name", users_list)

    movies = []
    if suggestions_ws:
        try:
            # Fetch previous sprint suggestions only
            all_movies = suggestions_ws.get_all_records()
            # Determine previous sprint
            sprint_index = next((i for i, s in enumerate(sprints_list) if s["sprint_id"] == current_sprint_id), None)
            prev_sprint_id = sprints_list[sprint_index-1]["sprint_id"] if sprint_index and sprint_index > 0 else None
            movies = [m for m in all_movies if m["sprint"] == prev_sprint_id]
        except Exception as e:
            st.warning(f"Failed to fetch suggestions: {e}")

    if not movies:
        st.info("No movies to rate yet.")
    else:
        ratings_data = []
        for idx, movie in enumerate(movies):
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
                key=f"rating_{idx}"
            )
            did_not_watch = st.checkbox(f"Did not watch {movie.get('movie_name','')}", key=f"dnw_{idx}")
            st.markdown("---")
            ratings_data.append((movie.get('user_name',''), movie.get('movie_name',''), rating, did_not_watch))

        if st.button("Submit All Ratings"):
            if not rater_name:
                st.error("Please select your name before submitting ratings!")
            elif ratings_ws:
                try:
                    for suggestor, movie_name, rating, did_not_watch in ratings_data:
                        ratings_ws.append_row([
                            prev_sprint_id,
                            movie_name,
                            rater_name,
                            rating,
                            did_not_watch,
                            str(datetime.now())
                        ])
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
    points_data = []
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
    if points_ws:
        try:
            points_data = points_ws.get_all_records()
        except Exception as e:
            st.warning(f"Failed to fetch points: {e}")

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

# -------------------
# PAGE 5: Finalize Sprint (Admin)
# -------------------
elif menu == "Finalize Sprint":
    st.header("Finalize Sprint & Update Points")

    if st.button("Calculate Points & Generate WhatsApp Message"):
        try:
            # 1. Determine previous sprint
            sprint_index = next((i for i, s in enumerate(sprints_list) if s["sprint_id"] == current_sprint_id), None)
            prev_sprint_id = sprints_list[sprint_index-1]["sprint_id"] if sprint_index and sprint_index > 0 else None

            # 1.5. Fetch relevant suggestions and ratings from Sheets
            suggestions = []
            ratings = []
            points_data = []

            if suggestions_ws:
                suggestions = suggestions_ws.get_all_records()
            if ratings_ws:
                ratings = ratings_ws.get_all_records()
            if points_ws:
                points_data = points_ws.get_all_records()
                
            # 2. Fetch relevant suggestions and ratings
            suggestions_prev = [m for m in suggestions if m["sprint"] == prev_sprint_id]
            ratings_prev = [r for r in ratings if r["sprint"] == prev_sprint_id]

            # 3. Build avg rating per movie
            movie_points = {}
            for movie in suggestions_prev:
                movie_name = movie["movie_name"]
                suggestor = movie["user_name"]
                ratings_movie = [r for r in ratings_prev if r["movie_name"] == movie_name and not r["did_not_watch"]]
                if ratings_movie:
                    avg_rating = sum([r["rating"] for r in ratings_movie])/len(ratings_movie)
                else:
                    avg_rating = 0
                bonus = 0.5 if len(ratings_movie)==0 else 0
                movie_points[movie_name] = {"suggestor": suggestor, "avg_rating": avg_rating, "bonus": bonus}

            # 4. Update points for users
            total_points = {u["user_name"]: u.get("total_points",0) for u in points_data}
            for movie_name, val in movie_points.items():
                user = val["suggestor"]
                add_points = val["avg_rating"] + val["bonus"]
                total_points[user] = total_points.get(user, 0) + add_points

            # Deduct 0.25 for users who did not watch movies
            for r in ratings_prev:
                if r["did_not_watch"]:
                    user = r["rater_name"]
                    total_points[user] = total_points.get(user,0) - 0.25

            # 5. Save updated points back to Google Sheet
            if points_ws:
                # Clear existing points sheet
                points_ws.clear()
                points_ws.append_row(["user_name","total_points"])
                for user, pts in total_points.items():
                    points_ws.append_row([user, round(pts,3)])

            # 6. Generate WhatsApp messages
            rating_msg = f"🎥 {prev_sprint_id} Rating 🎥\n" + "━━━━━━━━━━━━━━\n"
            for movie_name, val in movie_points.items():
                rating_msg += f"🍿 {val['suggestor']}: {movie_name} - {val['avg_rating']:.3f}\n"
            rating_msg += "━━━━━━━━━━━━━━"

            leaderboard_msg = f"🏆 *Points after {prev_sprint_id} Sprint* 🏆\n" + "━━━━━━━━━━━━━━\n"
            sorted_points = sorted(total_points.items(), key=lambda x: x[1], reverse=True)
            for user, pts in sorted_points:
                leaderboard_msg += f"👤 {user} : {pts:.3f}\n"
            leaderboard_msg += "━━━━━━━━━━━━━━"

            st.subheader("Sprint Rating Message")
            st.text_area("Copy this message for WhatsApp", rating_msg, height=300)

            st.subheader("Leaderboard Message")
            st.text_area("Copy this message for WhatsApp", leaderboard_msg, height=300)

            st.success("✅ Points calculated and messages generated!")

        except Exception as e:
            st.warning(f"Failed to finalize sprint: {e}")




def get_current_sprint(sprints_list, current_date):
    for sprint in sprints_list:
        start_date = datetime.strptime(sprint["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(sprint["end_date"], "%Y-%m-%d").date()
        if start_date <= current_date <= end_date:
            return sprint["sprint_id"], sprint.get("description", "")
    return None, ""
