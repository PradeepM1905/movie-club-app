import streamlit as st
from sheets_utils import load_sheet

# ---------------------------------------
# CHECK USER ACTIVITY STATUS
# ---------------------------------------
def has_user_suggested_in_sprint(user_name, sprint_id):
    """Check if user has already suggested a movie in the current sprint"""
    try:
        suggestions = load_sheet("Suggestions")
        for suggestion in suggestions:
            if (suggestion.get('user_name') == user_name and
                    suggestion.get('sprint') == sprint_id):
                return True
        return False
    except Exception as e:
        st.warning(f"Error checking user suggestions: {e}")
        return False

def has_user_voted_in_sprint(user_name, sprint_id):
    """Check if user has already voted for all required movies in the current sprint"""
    try:
        suggestions = load_sheet("Suggestions")
        votes = load_sheet("Voting")
        
        # Get all movies from current sprint except user's own movie
        sprint_movies = [s for s in suggestions if s.get('sprint') == sprint_id]
        user_own_movie = next((s['movie_name'] for s in sprint_movies if s['user_name'] == user_name), None)
        
        # Movies user should vote on (all sprint movies except their own)
        movies_to_vote_on = [s['movie_name'] for s in sprint_movies if s['movie_name'] != user_own_movie]
        
        # Get user's votes for this sprint
        user_votes = [v for v in votes if v['user_name'] == user_name and v['movie_name'] in movies_to_vote_on]
        
        # User has voted if they've voted for all required movies
        return len(user_votes) >= len(movies_to_vote_on)
        
    except Exception as e:
        st.warning(f"Error checking user votes: {e}")
        return False

def has_user_rated_sprint_movies(user_name, sprint_id):
    """Check if user has already rated movies from a specific sprint"""
    try:
        ratings = load_sheet("Ratings")
        for rating in ratings:
            if (rating.get('user_name') == user_name and
                    rating.get('sprint') == sprint_id):
                return True
        return False
    except Exception as e:
        st.warning(f"Error checking user ratings: {e}")
        return False
