import streamlit as st
import pandas as pd
import cloudinary.uploader
from sheets_utils import load_sheet, connect_google_sheets
from sprint_management import get_current_sprint, get_previous_sprint, get_sprint_display_info, get_current_datetime
from user_activity import has_user_suggested_in_sprint, has_user_voted_in_sprint, has_user_rated_sprint_movies
# ---------------------------------------
# PAGE: DASHBOARD
# ---------------------------------------
def render_dashboard():
    """Render the dashboard page"""
    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    if sprint_info:
        st.header(f"🎬 Movie Club Dashboard - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | {sprint_info['start_date']} to {sprint_info['end_date']} | {sprint_info['days_remaining']} days remaining")
    else:
        st.header("🎬 Movie Club Dashboard")
        st.warning("No active sprint found. Please check Sprints configuration.")

    # Show testing mode indicator
    from sprint_management import load_testing_config
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

    # Sprint Countdown Section
    st.subheader("⏰ Sprint Progress")

    if sprint_info:
        # Progress bar for current sprint
        progress = 100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100)
        st.progress(min(100, max(0, progress)) / 100)
        st.caption(f"Current sprint progress: {progress:.1f}% ({sprint_info['total_days'] - sprint_info['days_remaining']} of {sprint_info['total_days']} days)")
    else:
        st.info("No active sprint found. Please check Sprints configuration.")


    st.markdown("---")

    # Leaderboard Section
    st.subheader("🏆 Points Table")

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

# ---------------------------------------
# PAGE: SUGGEST MOVIE
# ---------------------------------------
def render_suggest_movie():
    """Render the suggest movie page"""
    if not st.session_state.enable_suggestion and st.session_state.role != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        return

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
    from sprint_management import load_testing_config
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")

    user_name = st.session_state.username

    # Check if user has already suggested in this sprint
    if current_sprint and has_user_suggested_in_sprint(user_name, current_sprint['sprint_id']):
        st.success("✅ You have already suggested a movie for this sprint!")
        st.info("You can only suggest one movie per sprint.")
        return

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
                sheet = connect_google_sheets()
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
def render_voting():
    """Render the voting page"""
    if not st.session_state.enable_voting and st.session_state.role != "admin":
        st.warning("Voting page is currently disabled by admin.")
        return

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()

    if sprint_info and current_sprint:
        st.header(f"🗳️ Voting - {sprint_info['sprint_id']}")
        st.write(f"**Have You Watched These Movies?**")
    else:
        st.header("🗳️ Voting")
        st.warning("No active sprint found for voting.")
        return

    # Show testing mode indicator
    from sprint_management import load_testing_config
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")

    voter_name = st.session_state.username

    # Check if user has already voted in this sprint
    if has_user_voted_in_sprint(voter_name, current_sprint['sprint_id']):
        st.success("✅ You have already voted for this sprint!")
        st.info("You can only vote once per sprint.")
        return

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
            watched = st.radio(
                f"Have you watched {movie.get('movie_name', 'this movie')}?",
                options=["Yes", "No"],
                key=f"vote_{movie.get('movie_name','')}"
            )
            watched = watched == "Yes"
            st.markdown("---")
            votes_data.append((movie.get('movie_name',''), watched))

        if st.button("Submit Votes"):
            # Validate that all movies have been voted on
            if len(votes_data) != len(movies):
                st.error("❌ Please vote Yes or No for all movies before submitting!")
                return

            try:
                sheet = connect_google_sheets()
                ws = sheet.worksheet("Voting")
                current_timestamp = get_current_datetime()
                for movie_name, watched in votes_data:
                    ws.append_row([movie_name, voter_name, watched, str(current_timestamp)])
                st.success("✅ Votes submitted!")
                st.cache_data.clear()
                # Set flag and show success immediately
                st.session_state.votes_submitted = True
                # Show success page right here
                st.success("✅ You have successfully voted for this sprint!")
                st.info("Thank you for participating in the voting!")
                st.balloons()
                return  # Stop further execution
            except Exception as e:
                st.warning(f"Failed to submit votes: {e}")


# ---------------------------------------
# PAGE: RATE MOVIES
# ---------------------------------------
def render_rate_movies():
    """Render the rate movies page"""
    if not st.session_state.enable_rating and st.session_state.role != "admin":
        st.warning("Rating page is currently disabled by admin.")
        return

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
        return

    # Show testing mode indicator
    from sprint_management import load_testing_config
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")

    rater_name = st.session_state.username

    # Check if user has already rated this sprint's movies
    if has_user_rated_sprint_movies(rater_name, rating_sprint['sprint_id']):
        st.success("✅ You have already rated movies for this sprint!")
        st.info("You can only rate once per sprint.")
        return

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
                sheet = connect_google_sheets()
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