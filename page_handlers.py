import streamlit as st
import pandas as pd
import cloudinary.uploader
import json
import time
import datetime
from sheets_utils import load_sheet, connect_google_sheets
from sprint_management import get_current_sprint, get_previous_sprint, get_sprint_display_info, get_current_datetime, get_current_date, get_previous_sprint_quiz_data
from user_activity import has_user_suggested_in_sprint, has_user_voted_in_sprint, has_user_rated_sprint_movies
from voting_utils import get_voting_results, has_everyone_voted, is_movie_finalized, update_voting_phase

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


    # CACHE DASHBOARD DATA to prevent repeated API calls
    if 'dashboard_data_loaded' not in st.session_state:
        st.session_state.quiz_data, st.session_state.previous_sprint = get_previous_sprint_quiz_data()
        st.session_state.dashboard_data_loaded = True
    
    # Use cached data
    quiz_data = st.session_state.quiz_data
    previous_sprint = st.session_state.previous_sprint
    
    # QUIZ MODAL CHECK
    if st.session_state.get('show_quiz'):
        if quiz_data and previous_sprint:
            render_quiz_interface(quiz_data, previous_sprint)
            st.stop()
        else:
            # If no quiz data, remove the quiz state
            if 'show_show_quiz' in st.session_state:
                del st.session_state['show_quiz']
            st.error("Quiz data not available. Please try again later.")
            st.rerun()
            

    st.markdown("---")

    # Leaderboard Section
    st.subheader("🏆 Points Table")

    if not df_users.empty:
        # Create leaderboard from Users sheet points with proper error handling
        leaderboard_data = []
        for _, user in df_users.iterrows():
            # Skip admin users
            if user.get('role', '').lower() == 'admin':
                continue

            points = user.get('points', 0)
            try:
                points_float = float(points) if points != '' and points is not None else 0.0
            except (ValueError, TypeError):
                points_float = 0.0

            leaderboard_data.append({
                "Rank": len(leaderboard_data) + 1,
                "User": user['user_name'],
                "Total Points": points_float
            })

        # Sort by points descending with safe comparison
        leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)

        # Update ranks after sorting
        for i, item in enumerate(leaderboard_data):
            item['Rank'] = i + 1

        df_leaderboard = pd.DataFrame(leaderboard_data)
        st.dataframe(df_leaderboard, use_container_width=True, hide_index=True)
    else:
        st.info("No user data available.")

    st.markdown("---")

    st.subheader("📊 Last Sprint Highlights")

    # Get previous sprint quiz data
    quiz_data, previous_sprint = get_previous_sprint_quiz_data()
    previous_sprint_suggestions = []
    if previous_sprint:
        previous_sprint_suggestions = get_movie_suggestions_for_sprint(previous_sprint['sprint_id'])
    else:
        st.write("🔍 No previous sprint found")
    
    if quiz_data and previous_sprint_suggestions:
       if 'movies_quiz_data' in quiz_data:
        quiz_movies = {movie['movie_name']: movie for movie in quiz_data.get('movies_quiz_data', [])}
        suggestion_movies = {s['movie_name']: s for s in previous_sprint_suggestions}
        matching_movies = set(quiz_movies.keys()) & set(suggestion_movies.keys())
        
        # Display each movie
        for movie_name, suggestion in suggestion_movies.items():
            # Add a divider at the top of each card
            st.markdown("---")
            
            # Create columns for the entire card content
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Movie poster
                if suggestion.get('image_url') and pd.notna(suggestion['image_url']) and suggestion['image_url'].strip():
                    st.image(suggestion['image_url'], width=100, output_format="PNG")
                else:
                    st.image("https://via.placeholder.com/100x150/333333/FFFFFF?text=No+Poster", width=100, output_format="PNG")
            
            with col2:
                # Movie title and suggested by (compact)
                st.markdown(f"**{movie_name}**")
                st.caption(f"Suggested by: {suggestion.get('user_name', 'Unknown')}")
                
                # Quiz data in same column (right side)
                if movie_name in quiz_movies:
                    quiz_info = quiz_movies[movie_name]
                    
                    # Best quote (compact)
                    quote = quiz_info.get('best_quote', 'No quote available')
                    if quote and quote != 'No quote available':
                        st.markdown("**💬 Best Quote**")
                        st.caption(f'"{quote}"')
                    
                    # Fun trivia (compact)
                    trivia = quiz_info.get('fun_trivia', 'No trivia available')
                    if trivia and trivia != 'No trivia available':
                        st.markdown("**🎯 Fun Trivia**")
                        st.caption(trivia)
                else:
                    st.caption("⚠️ No quiz data for this movie")
    elif previous_sprint and not quiz_data:
        st.info(f"Quiz data for {previous_sprint['sprint_id']} is being generated. Check back soon!")
    elif quiz_data and not previous_sprint_suggestions:
        st.info("No movie suggestions found for the previous sprint.")
    else:
        st.info("No previous sprint data available yet.")


    st.markdown("---")
    st.subheader("🎯 Sprint Quiz")
    
    quiz_data, previous_sprint = get_previous_sprint_quiz_data()
    
    if quiz_data and previous_sprint:
        # Check if user already attempted the quiz
        quiz_attempted = check_quiz_attempt(previous_sprint['sprint_id'])
        
        if quiz_attempted:
            st.warning("✅ You have already attempted this sprint's quiz!")
            # Show previous score
            previous_score = get_previous_quiz_score(previous_sprint['sprint_id'])
            if previous_score is not None:
                total_questions = sum(len(movie.get('multiple_choice_questions', [])) 
                                    for movie in quiz_data.get('movies_quiz_data', []))
                st.write(f"Your score: **{previous_score}/{total_questions}**")
        else:
            st.write("Test your knowledge about the movies from the last sprint!")
            st.write(f"**{previous_sprint['sprint_id']}** - {previous_sprint.get('description', '')}")
            
            # Count total questions
            total_questions = sum(len(movie.get('multiple_choice_questions', [])) 
                                for movie in quiz_data.get('movies_quiz_data', []))
            st.write(f"**{total_questions} questions** • **20 seconds per question** • **No retries**")
            
            if st.button("🚀 Take Quiz Now", type="primary"):
                st.session_state.show_quiz = True
                st.rerun()
    else:
        st.info("No quiz available for previous sprint yet.")
    
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

# Add configuration for edit functionality at the top
EDIT_CONFIG = {
    'enable_spring_first_day_edit': True,  # Set to False to disable spring first day restriction
    'min_votes_ratio': 0.5,               # Minimum ratio of votes needed to allow editing
    'total_members': 10                    # Total members in the club (adjust based on your users)
}

def can_edit_movie_suggestion(movie_name, user_name, sprint_id):
    """
    Check if a movie suggestion can be edited based on the rules:
    1. Only allowed on first day of spring (configurable)
    2. OR if more than half of people voted it as seen already
    """
    today = datetime.datetime.now().date()
    #TODO Add Rules
    
    return True

def get_user_movie_suggestion(user_name, sprint_id):
    """Get the movie suggestion made by a user in a specific sprint"""
    try:
        suggestions = load_sheet("Suggestions")
        if suggestions:
            df_suggestions = pd.DataFrame(suggestions)
            user_suggestion = df_suggestions[
                (df_suggestions['user_name'] == user_name) & 
                (df_suggestions['sprint'] == sprint_id)
            ]
            if not user_suggestion.empty:
                return user_suggestion.iloc[0].to_dict()
    except Exception as e:
        st.warning(f"Error loading user suggestion: {e}")
    return None

# ---------------------------------------
# PAGE: SUGGEST MOVIE (Updated with Edit functionality)
# ---------------------------------------
def render_suggest_movie():
    """Render the suggest movie page with new voting flow"""
    if not st.session_state.enable_suggestion and st.session_state.role != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        return

    # Display sprint information
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()

    if sprint_info and current_sprint:
        st.header(f"🎥 Suggest a Movie - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | {sprint_info['days_remaining']} days remaining")
    else:
        st.header("🎥 Suggest a Movie")
        st.warning("No active sprint found.")
        return

    user_name = st.session_state.username
    sprint_id = current_sprint['sprint_id'] if current_sprint else ""
    current_phase = st.session_state.get('voting_phase', 'suggestion')

    # Check if user has existing suggestion
    existing_suggestion = None
    if current_sprint:
        existing_suggestion = get_user_movie_suggestion(user_name, sprint_id)

    # Get voting results if in voting phase
    movie_votes = {}
    total_voters = 0
    if current_phase in ['voting', 'results'] and existing_suggestion:
        movie_votes, total_voters, _ = get_voting_results(sprint_id)

    # PHASE 1: Suggestion Phase - User can suggest or see their suggestion
    if current_phase == 'suggestion':
        if existing_suggestion:
            show_existing_suggestion(existing_suggestion, show_edit=False)
        else:
            render_suggestion_form()
    
    # PHASE 2: Voting Phase - User sees their suggestion with voting status
    elif current_phase == 'voting':
        if existing_suggestion:
            show_existing_suggestion(existing_suggestion, show_edit=False)
            
            # Show voting status for user's movie
            movie_name = existing_suggestion['movie_name']
            if movie_name in movie_votes:
                stats = movie_votes[movie_name]
                st.subheader("📊 Voting Status for Your Movie")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Watched", stats['watched_count'])
                with col2:
                    st.metric("Not Watched", stats['not_watched_count'])
                with col3:
                    st.metric("Total Votes", stats['total_votes'])
                
                # Check if movie needs to be changed
                watched_ratio = stats['watched_count'] / stats['total_votes'] if stats['total_votes'] > 0 else 0
                
                if watched_ratio >= 0.5:
                    st.error("🚫 More than half of voters have watched this movie. Please suggest a different movie.")
                    if st.button("✏️ Edit and Suggest New Movie"):
                        st.session_state.editing_suggestion = True
                elif stats['not_watched_count'] == 0:
                    st.warning("⚠️ Everyone has watched this movie. You can keep it or suggest a new one.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Keep This Movie"):
                            st.success("Movie kept for the sprint!")
                    with col2:
                        if st.button("✏️ Suggest New Movie"):
                            st.session_state.editing_suggestion = True
                else:
                    st.success("✅ Your movie is accepted! At least one person hasn't watched it.")
            
            if st.session_state.get('editing_suggestion'):
                render_edit_suggestion(existing_suggestion, sprint_id)
        else:
            st.error("No movie suggestion found for this sprint. Please contact admin.")
    
    # PHASE 3: Results Phase - Finalized movies
    elif current_phase == 'results':
        if existing_suggestion:
            show_existing_suggestion(existing_suggestion, show_edit=False)
            
            # Show final voting results
            movie_name = existing_suggestion['movie_name']
            if movie_name in movie_votes:
                stats = movie_votes[movie_name]
                st.subheader("🎯 Final Voting Results")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Watched", stats['watched_count'])
                    st.metric("Not Watched", stats['not_watched_count'])
                with col2:
                    st.metric("Total Votes", stats['total_votes'])
                    
                    # Show final status
                    if is_movie_finalized(movie_name, movie_votes, total_voters):
                        st.success("✅ FINALIZED - Movie accepted for watching")
                    else:
                        st.error("❌ REJECTED - Movie not accepted")


def show_existing_suggestion(suggestion, show_edit=False):
    """Show existing movie suggestion with details"""
    st.success("✅ You have already suggested a movie for this sprint!")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if suggestion.get('image_url') and pd.notna(suggestion['image_url']) and suggestion['image_url'].strip():
            st.image(suggestion['image_url'], width=150)
        else:
            st.image("https://via.placeholder.com/150x225/333333/FFFFFF?text=No+Poster", width=150)
    
    with col2:
        st.write(f"**{suggestion.get('movie_name', 'Unknown Movie')}**")
        st.write(f"**Genre:** {suggestion.get('genre', 'Not specified')}")
        st.write(f"**Where to watch:** {suggestion.get('description', 'Not specified')}")
        st.write(f"**Suggested on:** {suggestion.get('timestamp', 'Unknown date')}")
    
    if show_edit and st.session_state.role == "admin":
        if st.button("Edit Suggestion"):
            st.session_state.editing_suggestion = True

def render_suggestion_form():
    """Render the movie suggestion form"""
    st.subheader("🎬 Suggest a New Movie")
    
    movie_name = st.text_input("Movie Name *")
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
                current_timestamp = get_current_datetime()
                
                current_sprint = get_current_sprint()
                sprint_id = current_sprint['sprint_id'] if current_sprint else ""

                ws.append_row([
                    sprint_id,
                    st.session_state.username,
                    movie_name,
                    genre,
                    description,
                    image_url,
                    str(current_timestamp)
                ])
                st.success("✅ Movie suggestion submitted!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.warning(f"Failed to write suggestion: {e}")

def render_edit_suggestion(existing_suggestion, sprint_id):
    """Render the edit suggestion form - UPDATED for new flow"""
    st.subheader("✏️ Edit Your Movie Suggestion")
    st.warning("You are editing your movie suggestion. This will replace your previous suggestion.")
    
    # Show current suggestion
    st.write("**Current Suggestion:**")
    col1, col2 = st.columns([1, 2])
    with col1:
        if existing_suggestion.get('image_url') and pd.notna(existing_suggestion['image_url']) and existing_suggestion['image_url'].strip():
            st.image(existing_suggestion['image_url'], width=120)
        else:
            st.image("https://via.placeholder.com/120x180/333333/FFFFFF?text=No+Poster", width=120)
    with col2:
        st.write(f"**{existing_suggestion.get('movie_name', 'Unknown Movie')}**")
        st.write(f"Genre: {existing_suggestion.get('genre', '')}")
        st.write(f"Where to watch: {existing_suggestion.get('description', '')}")
    
    st.markdown("---")
    
    # Edit form
    movie_name = st.text_input("New Movie Name", value=existing_suggestion.get('movie_name', ''))
    genre = st.text_input("Genre", value=existing_suggestion.get('genre', ''))
    description = st.text_area("Where to watch it?", value=existing_suggestion.get('description', ''))
    image = st.file_uploader("Upload New Poster (optional)", type=["png", "jpg", "jpeg"])
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save Changes", type="primary"):
            if not movie_name:
                st.error("Please provide a movie name!")
            else:
                update_movie_suggestion(existing_suggestion, movie_name, genre, description, image, sprint_id)
    
    with col2:
        if st.button("❌ Cancel Edit"):
            st.session_state.editing_suggestion = False
            st.rerun()

def update_movie_suggestion(existing_suggestion, new_movie_name, new_genre, new_description, new_image, sprint_id):
    """Update movie suggestion in Google Sheets"""
    # Use existing image URL unless new image is uploaded
    image_url = existing_suggestion.get('image_url', '')
    if new_image:
        try:
            result = cloudinary.uploader.upload(new_image)
            image_url = result.get('secure_url', '')
        except Exception as e:
            st.warning(f"Cloudinary upload failed: {e}")
    
    try:
        sheet = connect_google_sheets()
        ws = sheet.worksheet("Suggestions")
        
        # Get all suggestions to find the row to update
        suggestions = ws.get_all_records()
        
        # Find the row index of the user's suggestion for this sprint
        for idx, suggestion in enumerate(suggestions, start=2):  # start=2 because of header row
            if (suggestion.get('user_name') == st.session_state.username and 
                suggestion.get('sprint') == sprint_id):
                
                # Update the row
                ws.update(f'A{idx}:G{idx}', [[
                    sprint_id,
                    st.session_state.username,
                    new_movie_name,
                    new_genre,
                    new_description,
                    image_url,
                    str(get_current_datetime())  # Update timestamp
                ]])
                
                st.success("✅ Movie suggestion updated successfully!")
                st.session_state.editing_suggestion = False
                st.cache_data.clear()
                st.rerun()
                break
        
    except Exception as e:
        st.warning(f"Failed to update suggestion: {e}")

# ---------------------------------------
# PAGE: VOTING
# ---------------------------------------
def render_voting():
    """Render the voting page with admin controls"""
    current_phase = st.session_state.get('voting_phase', 'suggestion')
    
    # Only show voting in voting phase
    if current_phase != 'voting' and st.session_state.role != 'admin':
        st.warning("Voting is not currently active.")
        return

    if not st.session_state.enable_voting and st.session_state.role != "admin":
        st.warning("Voting page is currently disabled by admin.")
        return

    # Display sprint information
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()

    if sprint_info and current_sprint:
        st.header(f"🗳️ Voting - {sprint_info['sprint_id']}")
    else:
        st.header("🗳️ Voting")
        st.warning("No active sprint found for voting.")
        return

    voter_name = st.session_state.username
    sprint_id = current_sprint['sprint_id']

    # ADMIN VIEW - With controls and statistics
    if st.session_state.role == "admin":
        render_admin_voting_view(sprint_id)
    # USER VIEW - Normal voting interface
    else:
        render_user_voting_view(voter_name, sprint_id)

def render_admin_voting_view(sprint_id):
    """Render voting page for admin with controls"""
    st.info("👑 Admin Voting View - You can see results but cannot vote")
    
    # Load data
    suggestions = load_sheet("Suggestions")
    votes = load_sheet("Voting")
    users = load_sheet("Users")
    
    sprint_suggestions = [s for s in suggestions if s.get('sprint') == sprint_id]
    normal_users = [u for u in users if u.get('role', 'normal').lower() == 'normal']
    
    # Admin controls
    st.subheader("🛠️ Admin Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Send for Voting button
        if st.button("🚀 Send for Voting", type="primary"):
            if update_voting_phase("voting"):
                st.session_state.enable_voting = True
                st.success("Voting phase started! Users can now vote.")
                st.rerun()
    
    with col2:
        # Check if everyone has voted
        everyone_voted = has_everyone_voted(sprint_id)
        if everyone_voted:
            st.success("✅ All users have voted!")
            if st.button("📢 Publish Voting Results"):
                if update_voting_phase("results"):
                    st.session_state.enable_voting = False
                    st.success("Voting results published!")
                    st.rerun()
        else:
            st.warning("⏳ Waiting for all users to vote")
    
    with col3:
        if st.button("↩️ Back to Suggestion Phase"):
            if update_voting_phase("suggestion"):
                st.session_state.enable_voting = False
                st.success("Back to suggestion phase!")
                st.rerun()
    
    # Voting statistics
    st.subheader("📊 Voting Statistics")
    
    movie_votes, total_voters, total_votes = get_voting_results(sprint_id)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Movies Suggested", len(sprint_suggestions))
    with col2:
        st.metric("Total Voters", len(normal_users))
    with col3:
        st.metric("Votes Cast", total_votes)
    with col4:
        voted_users = len(set(v['user_name'] for v in votes if any(
            s['movie_name'] == v['movie_name'] for s in sprint_suggestions
        )))
        st.metric("Users Voted", f"{voted_users}/{len(normal_users)}")
    
    # Detailed voting results
    st.subheader("🎬 Movie Voting Results")
    
    for movie in sprint_suggestions:
        movie_name = movie['movie_name']
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if movie.get('image_url') and pd.notna(movie['image_url']) and movie['image_url'].strip():
                st.image(movie['image_url'], width=120)
            else:
                st.image("https://via.placeholder.com/120x180/333333/FFFFFF?text=No+Poster", width=120)
        
        with col2:
            st.write(f"**{movie_name}**")
            st.write(f"*Suggested by: {movie['user_name']}*")
            
            if movie_name in movie_votes:
                stats = movie_votes[movie_name]
                
                col2a, col2b, col2c, col2d = st.columns(4)
                with col2a:
                    st.metric("Watched", stats['watched_count'])
                with col2b:
                    st.metric("Not Watched", stats['not_watched_count'])
                with col2c:
                    st.metric("Total", stats['total_votes'])
                with col2d:
                    watched_ratio = stats['watched_count'] / stats['total_votes'] if stats['total_votes'] > 0 else 0
                    if watched_ratio >= 0.5:
                        st.error("REJECT")
                    elif stats['not_watched_count'] > 0:
                        st.success("ACCEPT")
                    else:
                        st.warning("ALL WATCHED")
        
        st.markdown("---")

def render_user_voting_view(voter_name, sprint_id):
    """Render voting page for normal users"""
    # Check if user has already voted
    if has_user_voted_in_sprint(voter_name, sprint_id):
        st.success("✅ You have already voted for this sprint!")
        
        # Show voting results if available
        movie_votes, total_voters, _ = get_voting_results(sprint_id)
        if movie_votes:
            st.subheader("📊 Current Voting Results")
            
            suggestions = load_sheet("Suggestions")
            sprint_suggestions = [s for s in suggestions if s.get('sprint') == sprint_id]
            
            for movie in sprint_suggestions:
                movie_name = movie['movie_name']
                if movie_name in movie_votes:
                    stats = movie_votes[movie_name]
                    
                    # Show green check for finalized movies
                    status_icon = "✅" if is_movie_finalized(movie_name, movie_votes, total_voters) else "⏳"
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{status_icon} **{movie_name}**")
                    with col2:
                        st.write(f"👁️ {stats['watched_count']} | 🙈 {stats['not_watched_count']}")
        
        return

    st.info("🗳️ Vote Yes if you have watched the movie, No if you haven't")

    movies = load_sheet("Suggestions")
    
    if sprint_id and movies:
        # Exclude user's own movies and get other users' movies
        movies = [movie for movie in movies
                  if (movie.get('sprint') == sprint_id
                      and movie.get('user_name') != voter_name)]

    if not movies:
        st.info("No movie suggestions from other members found for current sprint.")
        return

    st.info(f"Found {len(movies)} movies suggested by other members to vote on")
    votes_data = []
    
    for movie in movies:
        st.subheader(movie.get("movie_name", "Unknown"))
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if movie.get("image_url"):
                st.image(movie["image_url"], width=150)
            else:
                st.image("https://via.placeholder.com/150x225/333333/FFFFFF?text=No+Poster", width=150)
        
        with col2:
            st.write(f"**Genre:** {movie.get('genre','')}")
            st.write(f"**Where to watch:** {movie.get('description','')}")
            
            watched = st.radio(
                f"Have you watched {movie.get('movie_name', 'this movie')}?",
                options=["Yes", "No"],
                key=f"vote_{movie.get('movie_name','')}_{voter_name}"
            )
            watched_bool = watched == "Yes"
            votes_data.append((movie.get('movie_name',''), watched_bool))

        st.markdown("---")

    if st.button("Submit Votes", type="primary"):
        if len(votes_data) != len(movies):
            st.error("❌ Please vote Yes or No for all movies before submitting!")
            return

        try:
            sheet = connect_google_sheets()
            ws = sheet.worksheet("Voting")
            current_timestamp = get_current_datetime()
            
            for movie_name, watched in votes_data:
                ws.append_row([movie_name, voter_name, watched, str(current_timestamp)])
            
            st.cache_data.clear()
            st.success("✅ Votes submitted successfully!")
            st.balloons()
            st.rerun()

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

def get_movie_suggestions_for_sprint(sprint_id):
    """Get movie suggestions with user info for a specific sprint"""
    try:
        suggestions = load_sheet("Suggestions")
        return [s for s in suggestions if s.get('sprint') == sprint_id]
    except:
        return []


# def render_quiz_interface(quiz_data, previous_sprint):
#     """Render the quiz interface in a modal/popup style"""
#     # Store quiz data in session state to avoid reloading
#     if 'cached_quiz_data' not in st.session_state:
#         st.session_state.cached_quiz_data = quiz_data
#         st.session_state.cached_previous_sprint = previous_sprint
#     else:
#         # Use cached data instead of reloading
#         quiz_data = st.session_state.cached_quiz_data
#         previous_sprint = st.session_state.cached_previous_sprint
    
#     # Initialize ALL quiz state variables
#     if 'quiz_started' not in st.session_state:
#         st.session_state.quiz_started = True
#         st.session_state.current_question = 0
#         st.session_state.user_answers = []
#         st.session_state.quiz_score = 0
#         st.session_state.time_remaining = 20
#         st.session_state.quiz_completed = False
#         st.session_state.question_start_time = time.time()
    
#     # Get all questions from all movies (from cached data)
#     all_questions = []
#     for movie in quiz_data.get('movies_quiz_data', []):
#         for question in movie.get('multiple_choice_questions', []):
#             all_questions.append(question)
    
#     total_questions = len(all_questions)
    
#     # Quiz header
#     st.header(f"🎯 Movie Quiz - {previous_sprint['sprint_id']}")
#     st.write(f"**{total_questions} questions • 20 seconds per question • No retries**")
#     st.markdown("---")
    
#     # Progress bar
#     progress = (st.session_state.current_question) / total_questions
#     st.progress(progress)
#     st.write(f"Question {st.session_state.current_question + 1} of {total_questions}")
    
#     # Calculate time remaining
#     current_time = time.time()
#     elapsed_time = current_time - st.session_state.question_start_time
#     time_remaining = max(0, 20 - int(elapsed_time))
    
#     # Timer display
#     if time_remaining > 0:
#         st.warning(f"⏰ Time remaining: {time_remaining} seconds")
#     else:
#         st.error("⏰ Time's up!")
    
#     # If quiz completed, show results
#     if st.session_state.quiz_completed:
#         show_quiz_results(all_questions, previous_sprint)
#         return
    
#     # Current question
#     current_q = all_questions[st.session_state.current_question]
    
#     # Display question
#     st.subheader(f"Q{st.session_state.current_question + 1}: {current_q['question']}")
    
#     # Display options
#     selected_option = st.radio(
#         "Select your answer:",
#         options=current_q['options'],
#         key=f"question_{st.session_state.current_question}"
#     )
    
#     # Handle submissions WITHOUT auto-refresh
#     if time_remaining <= 0:
#         st.info(f"**Correct answer:** {current_q['correct_answer']}")
#         if st.button("Next Question →", key="timeout_next"):
#             handle_answer_submission(None, current_q, all_questions, previous_sprint)
#             st.rerun()
#     else:
#         if selected_option and st.button("Submit Answer", type="primary"):
#             handle_answer_submission(selected_option, current_q, all_questions, previous_sprint)
#             st.rerun()

def render_quiz_interface(quiz_data, previous_sprint):
    """Render the quiz interface with ALL questions on one page"""
    # CACHE THE QUIZ DATA
    if 'cached_quiz_data' not in st.session_state:
        st.session_state.cached_quiz_data = quiz_data
        st.session_state.cached_previous_sprint = previous_sprint
        st.session_state.cached_all_questions = []
        for movie in quiz_data.get('movies_quiz_data', []):
            for question in movie.get('multiple_choice_questions', []):
                st.session_state.cached_all_questions.append(question)
    
    # Use cached data
    quiz_data = st.session_state.cached_quiz_data
    previous_sprint = st.session_state.cached_previous_sprint
    all_questions = st.session_state.cached_all_questions
    
    # Initialize quiz state
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = True
        st.session_state.user_answers = [None] * len(all_questions)
        st.session_state.quiz_score = 0
        st.session_state.quiz_completed = False
        st.session_state.quiz_start_time = time.time()
        st.session_state.total_quiz_time = len(all_questions) * 20
    
    total_questions = len(all_questions)
    current_time = time.time()
    elapsed_time = current_time - st.session_state.quiz_start_time
    time_remaining = max(0, st.session_state.total_quiz_time - int(elapsed_time))
    
    # Quiz header
    st.header(f"🎯 Movie Quiz - {previous_sprint['sprint_id']}")
    st.write(f"**{total_questions} questions • {time_remaining//60}:{time_remaining%60:02d} total time • One-time submission**")
    st.markdown("---")
    
    # Progress and timer
    col1, col2 = st.columns(2)
    with col1:
        answered = sum(1 for answer in st.session_state.user_answers if answer is not None)
        progress = answered / total_questions
        st.progress(progress)
        st.write(f"Progress: {answered}/{total_questions} answered")
    
    with col2:
        if time_remaining > 0:
            mins, secs = divmod(time_remaining, 60)
            st.warning(f"⏰ Total time remaining: {mins:02d}:{secs:02d}")
        else:
            st.error("⏰ Time's up! Submit your answers now.")
    
    # If quiz completed, show results
    if st.session_state.quiz_completed:
        show_quiz_results(all_questions, previous_sprint)
        return
    
    # Display all questions in expanders
    st.subheader("📝 Questions")
    
    for i, question_data in enumerate(all_questions):
        with st.expander(f"Question {i+1}: {question_data['question'][:50]}...", expanded=False):
            st.write(f"**{question_data['question']}**")
            
            # Get current selection or None
            current_selection = st.session_state.user_answers[i]
            
            # Display options
            selected_option = st.radio(
                f"Select your answer for Q{i+1}:",
                options=question_data['options'],
                key=f"question_{i}",
                index=question_data['options'].index(current_selection) if current_selection in question_data['options'] else None
            )
            
            # Store the answer
            if selected_option and selected_option != current_selection:
                st.session_state.user_answers[i] = selected_option
                st.success("✓ Answer saved")
            elif current_selection:
                st.info(f"Current selection: {current_selection}")
            else:
                st.warning("⏳ Not answered yet")
    
    st.markdown("---")
    
    # Submit button logic
    answered_count = sum(1 for answer in st.session_state.user_answers if answer is not None)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if answered_count == total_questions:
            st.success(f"✅ All {total_questions} questions answered! Ready to submit.")
        else:
            st.warning(f"📝 {answered_count}/{total_questions} questions answered")
    
    with col2:
        if st.button("🔄 Update Timer", key="refresh_timer"):
            st.rerun()
    
    with col3:
        # Enable submit when ALL questions are answered OR time is up
        submit_disabled = (answered_count < total_questions) and (time_remaining > 0)
        
        if st.button("🚀 Submit Quiz", type="primary", disabled=submit_disabled):
            calculate_and_show_results(all_questions, previous_sprint)
            st.rerun()
    
    # Auto-submit when time runs out
    if time_remaining <= 0 and not st.session_state.quiz_completed and answered_count > 0:
        st.error("⏰ Time's up! Auto-submitting your quiz...")
        calculate_and_show_results(all_questions, previous_sprint)
        st.rerun()
    
    # AUTO-REFRESH FOR TIMER (Safe - only if time remaining)
    if time_remaining > 0 and not st.session_state.quiz_completed:
        time.sleep(1)
        st.rerun()

def calculate_and_show_results(all_questions, previous_sprint):
    """Calculate scores and show results - FIXED VERSION"""
    score = 0
    results = []
    
    for i, question_data in enumerate(all_questions):
        user_answer = st.session_state.user_answers[i] if i < len(st.session_state.user_answers) else None
        correct_answer = question_data['correct_answer']
        is_correct = (user_answer == correct_answer)
        
        if is_correct:
            score += 1
        
        results.append({
            'question': question_data['question'],
            'user_answer': user_answer or "No answer",
            'correct_answer': correct_answer,
            'is_correct': is_correct
        })
    
    # Update session state
    st.session_state.quiz_score = score
    st.session_state.user_answers_details = results  # Store in new format
    st.session_state.quiz_completed = True
    
    # Save result to Google Sheets
    save_quiz_result(previous_sprint)

def handle_answer_submission(selected_option, current_question, all_questions, previous_sprint):
    """Handle answer submission and scoring"""
    # Calculate score
    is_correct = False
    if selected_option:
        is_correct = (selected_option == current_question['correct_answer'])
    
    # Store user answer
    st.session_state.user_answers.append({
        'question': current_question['question'],
        'user_answer': selected_option or "No answer (timeout)",
        'correct_answer': current_question['correct_answer'],
        'is_correct': is_correct
    })
    
    # Update score
    if is_correct:
        st.session_state.quiz_score += 1
    
    # Move to next question or complete quiz
    st.session_state.current_question += 1
    st.session_state.time_remaining = 20  # Reset timer for next question
    
    if st.session_state.current_question >= len(all_questions):
        st.session_state.quiz_completed = True
        save_quiz_result(previous_sprint)

def show_quiz_results(all_questions, previous_sprint):
    """Display quiz results - FIXED VERSION"""
    st.success("🎉 Quiz Completed!")
    st.subheader(f"Your Score: {st.session_state.quiz_score}/{len(all_questions)}")
    
    # Calculate percentage
    percentage = (st.session_state.quiz_score / len(all_questions)) * 100
    st.metric("Score Percentage", f"{percentage:.1f}%")
    
    # Score breakdown
    st.markdown("---")
    st.subheader("📊 Detailed Results")
    
    # Check if we have user_answers_details (from new format) or user_answers (from old format)
    if hasattr(st.session_state, 'user_answers_details'):
        results = st.session_state.user_answers_details
    else:
        # Fallback: create results from old format
        results = []
        for i, question_data in enumerate(all_questions):
            user_answer = st.session_state.user_answers[i] if i < len(st.session_state.user_answers) else "No answer"
            correct_answer = question_data['correct_answer']
            is_correct = (user_answer == correct_answer)
            
            results.append({
                'question': question_data['question'],
                'user_answer': user_answer or "No answer",
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
    
    # Display results
    for i, result in enumerate(results):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Q{i+1}:** {result['question']}")
            st.write(f"**Your answer:** {result['user_answer']}")
            st.write(f"**Correct answer:** {result['correct_answer']}")
        with col2:
            if result['is_correct']:
                st.success("✅ Correct")
            else:
                st.error("❌ Incorrect")
        st.markdown("---")
    
    # Restart/Close buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Take Quiz Again"):
            clear_quiz_cache()
            st.rerun()
    with col2:
        if st.button("🏠 Back to Dashboard"):
            clear_quiz_cache()
            st.rerun()

def save_quiz_result(previous_sprint):
    """Save quiz result to Google Sheets"""
    try:
        sheet = connect_google_sheets()
        
        # Try to get existing QuizResult sheet, create if it doesn't exist
        try:
            result_ws = sheet.worksheet("QuizResult")
        except:
            result_ws = sheet.add_worksheet(title="QuizResult", rows="1000", cols="4")
            # Add headers
            result_ws.append_row(["sprint_id", "username", "points", "timestamp"])
        
        # Save the result
        result_ws.append_row([
            previous_sprint['sprint_id'],
            st.session_state.username,
            st.session_state.quiz_score,
            str(get_current_datetime())
        ])
        
        st.success("✅ Quiz result saved!")
        
    except Exception as e:
        st.warning(f"Could not save quiz result: {e}")

def clear_quiz_cache():
    """Clear quiz-related cache but keep the main data"""
    cache_keys = ['quiz_started', 'current_question', 'user_answers', 'quiz_score', 
                  'time_remaining', 'quiz_completed', 'question_start_time', 'show_quiz']
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]

def check_quiz_attempt(sprint_id):
    """Check if user has already attempted the quiz for this sprint"""
    try:
        quiz_results = load_sheet("QuizResult")
        username = st.session_state.username
        
        for result in quiz_results:
            if (result.get('sprint_id') == sprint_id and 
                result.get('username') == username):
                return True
        return False
    except:
        return False

def get_previous_quiz_score(sprint_id):
    """Get user's previous quiz score for this sprint"""
    try:
        quiz_results = load_sheet("QuizResult")
        username = st.session_state.username
        
        for result in quiz_results:
            if (result.get('sprint_id') == sprint_id and 
                result.get('username') == username):
                return int(result.get('points', 0))
        return None
    except:
        return None
