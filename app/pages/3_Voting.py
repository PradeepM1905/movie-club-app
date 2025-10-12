import streamlit as st
from utils.sheets import load_sheet, get_sprint_display_info, get_current_sprint, has_user_voted_in_sprint, get_current_datetime, load_testing_config

def show():
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
            watched = st.checkbox(f"Have you watched this?", key=f"vote_{movie.get('movie_name','')}")
            st.markdown("---")
            votes_data.append((movie.get('movie_name',''), watched))

        if st.button("Submit Votes"):
            try:
                from utils.sheets import get_sheet_connection
                ws = get_sheet_connection().worksheet("Voting")
                current_timestamp = get_current_datetime()
                for movie_name, watched in votes_data:
                    ws.append_row([movie_name, voter_name, watched, str(current_timestamp)])
                st.success("✅ Votes submitted!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.warning(f"Failed to submit votes: {e}")
