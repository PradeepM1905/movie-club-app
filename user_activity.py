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
    """Check if user has already voted in the current sprint"""
    try:
        votes = load_sheet("Voting")
        # Get movies from current sprint that are NOT user's own movies
        suggestions = load_sheet("Suggestions")
        sprint_movies = [s['movie_name'] for s in suggestions
                         if (s.get('sprint') == sprint_id
                             and s.get('user_name') != user_name)]  # Exclude own movies

        # Check if user has voted for any movie in this sprint
        user_votes = [v for v in votes if v.get('user_name') == user_name and v.get('movie_name') in sprint_movies]
        return len(user_votes) > 0
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