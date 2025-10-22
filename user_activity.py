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
    """Check if user has voted on all required movies"""
    from voting_session import get_user_voting_session
    session = get_user_voting_session(user_name, sprint_id)
    return session['all_movies_voted']

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
