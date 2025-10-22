# voting_session.py - Track voting session state
import streamlit as st
from sheets_utils import load_sheet
from sprint_management import get_current_sprint

def get_user_voting_session(user_name, sprint_id):
    """Get user's current voting session state"""
    try:
        suggestions = load_sheet("Suggestions")
        votes = load_sheet("Voting")
        
        # Get current sprint movies
        sprint_movies = [s for s in suggestions if s.get('sprint') == sprint_id]
        user_own_movie = next((s['movie_name'] for s in sprint_movies if s['user_name'] == user_name), None)
        
        # Movies user should vote on (excluding their own)
        movies_to_vote = [s for s in sprint_movies if s['movie_name'] != user_own_movie]
        
        # Get user's existing votes
        user_votes = {v['movie_name']: v for v in votes if v['user_name'] == user_name}
        
        # Separate voted and pending movies
        voted_movies = []
        pending_movies = []
        
        for movie in movies_to_vote:
            movie_name = movie['movie_name']
            if movie_name in user_votes:
                # User has voted for this movie
                voted_movies.append({
                    **movie,
                    'user_vote': user_votes[movie_name].get('watched'),
                    'vote_timestamp': user_votes[movie_name].get('timestamp')
                })
            else:
                # User hasn't voted for this movie yet
                pending_movies.append(movie)
        
        return {
            'voted_movies': voted_movies,
            'pending_movies': pending_movies,
            'all_movies_voted': len(pending_movies) == 0
        }
        
    except Exception as e:
        st.warning(f"Error getting voting session: {e}")
        return {'voted_movies': [], 'pending_movies': [], 'all_movies_voted': False}
