import streamlit as st
import pandas as pd
from utils.sheets import load_sheet, get_sprint_display_info, get_current_sprint, load_testing_config, get_current_date

def show():
    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    if sprint_info:
        st.header(f"🎬 Movie Club Dashboard - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | {sprint_info['start_date']} to {sprint_info['end_date']} | {sprint_info['days_remaining']} days remaining")
    else:
        st.header("🎬 Movie Club Dashboard")
        st.warning("No active sprint found. Please check Sprints configuration.")
    
    # Show testing mode indicator
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Members", len(df_users))
    with col2:
        st.metric("Movies Suggested", len(df_suggestions) if not df_suggestions.empty else 0)
    with col3:
        if sprint_info:
            st.metric("Days Remaining", sprint_info['days_remaining'])
        else:
            st.metric("Sprint Status", "No Active Sprint")
    
    st.markdown("---")
    
    # Leaderboard Section
    st.subheader("🏆 Leaderboard")
    
    if not df_users.empty:
        leaderboard_data = []
        for _, user in df_users.iterrows():
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
        
        leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)
        
        for i, item in enumerate(leaderboard_data):
            item['Rank'] = i + 1
        
        df_leaderboard = pd.DataFrame(leaderboard_data)
        st.dataframe(df_leaderboard, use_container_width=True)
    else:
        st.info("No user data available.")
    
    st.markdown("---")
    
    # Current Sprint Movies Section
    st.subheader("🎬 Current Sprint Movies & Ratings")
    
    if not df_suggestions.empty and not df_ratings.empty:
        try:
            df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
            
            if 'did_not_watch' in df_ratings.columns:
                df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(str).str.lower().isin(['true', 'yes', '1', 'y', 't'])
                df_valid_ratings = df_ratings[~df_ratings['did_not_watch']]
            else:
                df_valid_ratings = df_ratings
            
            if not df_valid_ratings.empty:
                movie_ratings = df_valid_ratings.groupby('movie_name')['rating'].agg(['mean', 'count']).round(2)
                movie_ratings = movie_ratings.rename(columns={'mean': 'Average Rating', 'count': 'Number of Ratings'})
                movie_ratings = movie_ratings.sort_values('Average Rating', ascending=False)
                
                for movie, ratings in movie_ratings.iterrows():
                    avg_rating = ratings['Average Rating']
                    num_ratings = int(ratings['Number of Ratings'])
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{movie}**")
                    with col2:
                        st.write(f"⭐ {avg_rating}/10 ({num_ratings} ratings)")
                    
                    progress_value = float(avg_rating) / 10.0
                    st.progress(min(1.0, max(0.0, progress_value)))
            else:
                st.info("No valid ratings available for current movies.")
                
        except Exception as e:
            st.error(f"Error processing ratings: {e}")
            st.info("Showing suggested movies without ratings:")
            for _, movie in df_suggestions.iterrows():
                st.write(f"• **{movie['movie_name']}** - {movie.get('genre', '')}")
                
    elif not df_suggestions.empty:
        st.info("Movies suggested but no ratings yet.")
        for _, movie in df_suggestions.iterrows():
            st.write(f"• **{movie['movie_name']}** - {movie.get('genre', '')}")
    else:
        st.info("No movies suggested for current sprint.")
    
    st.markdown("---")
    
    # Sprint Countdown Section
    st.subheader("⏰ Sprint Progress")
    
    if sprint_info:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Days until sprint end", sprint_info['days_remaining'])
        with col2:
            if sprint_info['days_remaining'] > 0:
                st.write(f"Sprint ends in **{sprint_info['days_remaining']} days**")
            else:
                st.success("🎉 Sprint completed! Ready for finalization!")
        
        progress = 100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100)
        st.progress(min(100, max(0, progress)) / 100)
        st.caption(f"Current sprint progress: {progress:.1f}% ({sprint_info['total_days'] - sprint_info['days_remaining']} of {sprint_info['total_days']} days)")
    else:
        st.info("No active sprint found. Please check Sprints configuration.")
