# voting_utils.py - New file for voting logic
import streamlit as st
import pandas as pd
from sheets_utils import load_sheet, connect_google_sheets
from sprint_management import get_current_sprint

def get_voting_results(sprint_id):
    """Get voting results for a sprint with counts"""
    try:
        suggestions = load_sheet("Suggestions")
        votes = load_sheet("Voting")
        users = load_sheet("Users")
        
        # Filter normal users (exclude admin)
        normal_users = [user for user in users if user.get('role', 'normal').lower() == 'normal']
        total_voters = len(normal_users)
        
        sprint_suggestions = [s for s in suggestions if s.get('sprint') == sprint_id]
        sprint_votes = [v for v in votes if any(s['movie_name'] == v['movie_name'] for s in sprint_suggestions)]
        
        # Calculate votes for each movie
        movie_votes = {}
        for movie in sprint_suggestions:
            movie_name = movie['movie_name']
            movie_votes[movie_name] = {
                'suggester': movie['user_name'],
                'watched_count': 0,
                'not_watched_count': 0,
                'total_votes': 0,
                'watched_percentage': 0
            }
        
        for vote in sprint_votes:
            movie_name = vote['movie_name']
            if movie_name in movie_votes:
                if vote.get('watched') in [True, 'True', 'true', 'Yes', 'yes']:
                    movie_votes[movie_name]['watched_count'] += 1
                else:
                    movie_votes[movie_name]['not_watched_count'] += 1
                movie_votes[movie_name]['total_votes'] += 1
        
        # Calculate percentages
        for movie_name, stats in movie_votes.items():
            if stats['total_votes'] > 0:
                stats['watched_percentage'] = (stats['watched_count'] / stats['total_votes']) * 100
        
        return movie_votes, total_voters, len(sprint_votes)
    
    except Exception as e:
        st.warning(f"Error calculating voting results: {e}")
        return {}, 0, 0

def has_everyone_voted(sprint_id):
    """Check if all users have voted for all movies in the sprint"""
    try:
        suggestions = load_sheet("Suggestions")
        votes = load_sheet("Voting")
        users = load_sheet("Users")
        
        # Filter normal users
        normal_users = [user['user_name'] for user in users if user.get('role', 'normal').lower() == 'normal']
        sprint_movies = [s['movie_name'] for s in suggestions if s.get('sprint') == sprint_id]
        
        # Remove user's own movies from voting requirement
        user_movie_mapping = {}
        for suggestion in suggestions:
            if suggestion.get('sprint') == sprint_id:
                user_movie_mapping[suggestion['user_name']] = suggestion['movie_name']
        
        # Check if each user has voted for all movies except their own
        for user in normal_users:
            user_votes = [v for v in votes if v['user_name'] == user]
            user_movies_voted = [v['movie_name'] for v in user_votes]
            
            # Movies user should vote on (all sprint movies except their own)
            user_own_movie = user_movie_mapping.get(user)
            movies_to_vote_on = [m for m in sprint_movies if m != user_own_movie]
            
            if len(user_votes) < len(movies_to_vote_on):
                return False
        
        return True
    
    except Exception as e:
        st.warning(f"Error checking voting completion: {e}")
        return False

def is_movie_finalized(movie_name, movie_votes, total_voters):
    """Check if a movie is finalized (not watched by majority)"""
    if movie_name not in movie_votes:
        return False
    
    stats = movie_votes[movie_name]
    # Movie is finalized if less than 50% have watched it AND at least one person hasn't watched it
    if stats['total_votes'] > 0:
        watched_ratio = stats['watched_count'] / stats['total_votes']
        has_not_watched = stats['not_watched_count'] > 0
        return watched_ratio < 0.5 and has_not_watched
    return False

def update_voting_phase(new_phase):
    """Update the voting phase in Config sheet"""
    try:
        sheet = connect_google_sheets()
        ws = sheet.worksheet("Config")
        
        # Get current config
        config_data = ws.get_all_records()
        
        # Update or add voting_phase
        phase_updated = False
        for i, row in enumerate(config_data):
            if row['key'] == 'voting_phase':
                ws.update_cell(i + 2, 2, new_phase)  # Update value column
                phase_updated = True
                break
        
        if not phase_updated:
            ws.append_row(['voting_phase', new_phase])
        
        st.session_state.voting_phase = new_phase
        st.cache_data.clear()
        return True
    except Exception as e:
        st.warning(f"Failed to update voting phase: {e}")
        return False
