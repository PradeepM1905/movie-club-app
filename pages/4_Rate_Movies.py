import streamlit as st
from utils.sheets import load_sheet, get_sprint_display_info, get_current_sprint, get_previous_sprint, has_user_rated_sprint_movies, get_current_datetime, load_testing_config

def show():
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
                from utils.sheets import get_sheet_connection
                ws = get_sheet_connection().worksheet("Ratings")
                current_timestamp = get_current_datetime()
                
                for movie_name, rating, dnw in ratings_data:
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
