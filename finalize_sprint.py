import streamlit as st
import pandas as pd
from sheets_utils import load_sheet, connect_google_sheets
from sprint_management import get_sprint_display_info, get_current_sprint, get_current_date, load_testing_config

def render_finalize_sprint(hash_password):
    """Render the finalize sprint page"""
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        return

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()

    if sprint_info and current_sprint:
        st.header(f"🏁 Finalize Sprint - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | Ending on {sprint_info['end_date']}")
    else:
        st.header("🏁 Finalize Sprint")
        st.warning("No active sprint found to finalize.")
        return

    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")

    st.markdown("---")

    # Load current data - filter for current sprint
    all_suggestions = load_sheet("Suggestions")
    all_ratings = load_sheet("Ratings")
    all_votes = load_sheet("Voting")  # ADDED: Load voting data for bonus calculation
    users_data = load_sheet("Users")

    # Filter data for current sprint
    suggestions = [s for s in all_suggestions if s.get('sprint') == current_sprint['sprint_id']]
    ratings = [r for r in all_ratings if r.get('sprint') == current_sprint['sprint_id']]
    votes = [v for v in all_votes]  # We'll filter by movie name later

    if not suggestions:
        st.warning("No movie suggestions found for this sprint.")
        return

    if not ratings:
        st.warning("No ratings found for this sprint.")
        return

    # Calculate statistics
    st.subheader("📊 Sprint Statistics")

    # Convert to DataFrames for easier analysis
    df_suggestions = pd.DataFrame(suggestions)
    df_ratings = pd.DataFrame(ratings)
    df_users = pd.DataFrame(users_data)

    # Data cleaning
    df_ratings['rating'] = pd.to_numeric(df_ratings['rating'], errors='coerce')
    df_ratings['did_not_watch'] = df_ratings['did_not_watch'].astype(str).str.lower().isin(['true', 'yes', '1', 'y', 't'])

    # Display basic stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Movies Suggested", len(df_suggestions))
    with col2:
        total_ratings = len(df_ratings)
        st.metric("Total Ratings", total_ratings)
    with col3:
        watched_ratings = len(df_ratings[~df_ratings['did_not_watch']])
        st.metric("Watched Movies Rated", watched_ratings)
    with col4:
        st.metric("Active Users", len(df_users))

    # Calculate button
    st.markdown("---")
    st.subheader("💰 Calculate Points")
    
    # Check if points already calculated for this sprint
    points_already_calculated = False
    try:
        points_data = load_sheet("Points")
        # Check if any points entry exists for current sprint
        for point_entry in points_data:
            if point_entry.get('sprint') == current_sprint['sprint_id']:
                points_already_calculated = True
                break
    except:
        pass
    
    if points_already_calculated:
        st.error(f"❌ Points for {current_sprint['sprint_id']} have already been calculated!")
        st.info("To recalculate, please delete the existing entries from the Points sheet first.")
    else:
        if st.button("🚀 Calculate & Save Sprint Points", type="primary"):
            # Points Calculation Logic
            user_points = {}
            user_breakdown = {}
            point_info_data = []
    
            # Points rules
            bonus_per_new_movie = 0.5
            deduction_per_missed_movie = 0.25
    
            # Create a mapping from movie name to suggester
            movie_to_suggester = {}
            for _, row in df_suggestions.iterrows():
                movie_to_suggester[row['movie_name']] = row['user_name']
    
            # FIXED: Calculate bonus eligibility from VOTING data, not ratings
            movie_bonus_eligible = {}
            for movie_name in movie_to_suggester.keys():
                # Get all votes for this movie
                movie_votes = [v for v in votes if v.get('movie_name') == movie_name]
                
                if movie_votes:
                    # Count how many people have watched this movie
                    watched_count = 0
                    for vote in movie_votes:
                        watched_value = vote.get('watched')
                        # Handle different boolean representations
                        if isinstance(watched_value, bool):
                            if watched_value:
                                watched_count += 1
                        elif isinstance(watched_value, str):
                            if watched_value.lower() in ['true', 'yes', '1', 't', 'y']:
                                watched_count += 1
                        elif watched_value:  # Handle other truthy values
                            watched_count += 1
                    
                    # Movie gets bonus if NO ONE has watched it (watched_count == 0)
                    movie_bonus_eligible[movie_name] = (watched_count == 0)
                else:
                    # If no votes, no bonus (need votes to determine)
                    movie_bonus_eligible[movie_name] = False
    
            # Calculate points for each user
            for user in df_users['user_name'].tolist():
                # Get movies suggested by this user
                user_suggested_movies = df_suggestions[df_suggestions['user_name'] == user]['movie_name'].tolist()
    
                # Calculate total deductions for this user
                user_not_watched = df_ratings[(df_ratings['user_name'] == user) & (df_ratings['did_not_watch'] == True)]
                total_deductions = len(user_not_watched) * deduction_per_missed_movie
    
                # Calculate bonus for movies suggested that no one watched
                bonus = 0
                unwatched_suggestions = []
                for movie in user_suggested_movies:
                    if movie_bonus_eligible.get(movie, False):
                        bonus += bonus_per_new_movie
                        unwatched_suggestions.append(movie)
    
                # For each movie suggested by the user, calculate points
                user_total_points = 0
    
                # If user suggested multiple movies, distribute deductions evenly
                deduction_per_movie = total_deductions / len(user_suggested_movies) if user_suggested_movies else 0
    
                for movie in user_suggested_movies:
                    # Get all ratings for this movie where people actually watched it
                    movie_ratings = df_ratings[(df_ratings['movie_name'] == movie) & (~df_ratings['did_not_watch'])]
    
                    total_point = 0
                    average_point = 0
    
                    if not movie_ratings.empty:
                        total_point = movie_ratings['rating'].sum()
                        average_point = movie_ratings['rating'].mean()
    
                    # Calculate deduction for this specific movie (distributed evenly)
                    movie_deduction = -deduction_per_movie  # Negative because it's a deduction
    
                    # Calculate bonus for this specific movie - FIXED: Use voting-based bonus
                    movie_bonus = bonus_per_new_movie if movie_bonus_eligible.get(movie, False) else 0
    
                    # Final total for this movie
                    final_total = average_point + movie_deduction + movie_bonus
    
                    # Add to user's total points
                    user_total_points += final_total
    
                    # Add to point info table
                    point_info_data.append({
                        "Movie": movie,
                        "User": user,
                        "Total Point": round(total_point, 3),
                        "Average Point": round(average_point, 3),
                        "Deduction": round(movie_deduction, 3),
                        "Bonus": round(movie_bonus, 3),
                        "Final Total": round(final_total, 3)
                    })
    
                # Store user breakdown
                user_breakdown[user] = {
                    "total_points": user_total_points,
                    "total_deductions": total_deductions,
                    "bonus_new_movies": bonus,
                    "movies_suggested": len(user_suggested_movies)
                }
                user_points[user] = user_total_points
    
            # Save to Points sheet
            sheet = connect_google_sheets()
            try:
                ws_points = sheet.worksheet("Points")
            except:
                ws_points = sheet.add_worksheet(title="Points", rows="1000", cols="10")
                ws_points.append_row(["sprint", "user_name", "total_points", "deductions", "bonus", "movies_suggested", "finalized_date"])
    
            # Save individual sprint results
            for user, points in user_points.items():
                breakdown = user_breakdown[user]
                ws_points.append_row([
                    current_sprint['sprint_id'],
                    user,
                    round(points, 3),
                    round(breakdown['total_deductions'], 3),
                    round(breakdown['bonus_new_movies'], 3),
                    breakdown['movies_suggested'],
                    str(get_current_date())
                ])
    
            # Update Users sheet with accumulated points
            ws_users = sheet.worksheet("Users")
            users_records = ws_users.get_all_records()
            
            # Check if sprint_id column exists, if not add it
            headers = ws_users.row_values(1)
            if 'sprint_id' not in headers:
                headers.append('sprint_id')
                ws_users.update('A1', [headers])
            
            # Create a mapping of current points for each user
            current_user_points = {}
            for user_record in users_records:
                user_name = user_record['user_name']
                points_value = user_record.get('points', '0')
                try:
                    current_user_points[user_name] = float(points_value) if points_value not in ['', None] else 0.0
                except (ValueError, TypeError):
                    current_user_points[user_name] = 0.0
            
            # Update points in Users sheet with sprint_id
            for i, user_record in enumerate(users_records, start=2):
                user_name = user_record['user_name']
                if user_name in user_points:
                    # Update points and sprint_id
                    ws_users.update_cell(i, 3, round(user_points[user_name], 3))
                    ws_users.update_cell(i, 5, current_sprint['sprint_id'])
    
            st.success("✅ Sprint points calculated and saved successfully!")
    
            # Display Point Info Table
            st.markdown("---")
            st.subheader("📋 Point Info")
    
            df_point_info = pd.DataFrame(point_info_data)
            st.dataframe(df_point_info, use_container_width=True)
    
            # Show bonus summary
            st.subheader("🎁 Bonus Summary")
            bonus_movies = [movie for movie, eligible in movie_bonus_eligible.items() if eligible]
            if bonus_movies:
                st.success(f"Movies eligible for +0.5 bonus: {', '.join(bonus_movies)}")
            else:
                st.info("No movies eligible for bonus this sprint")
    
            # WhatsApp Messages Section
            st.markdown("---")
            st.subheader("📱 WhatsApp Messages")
    
            # Message 1: Current Sprint Average Points (per user)
            message1 = f"""🎥 {current_sprint['sprint_id']} Rating 🎥
    ━━━━━━━━━━━━━━
    """
            # Calculate average points per user (sum of Final Total for their movies)
            user_avg_points = {}
            for row in point_info_data:
                user = row['User']
                final_total = row['Final Total']
                if user not in user_avg_points:
                    user_avg_points[user] = 0
                user_avg_points[user] += final_total
    
            # Sort users by average points (highest first)
            sorted_by_avg = sorted(user_avg_points.items(), key=lambda x: x[1], reverse=True)
            for user, avg_points in sorted_by_avg:
                if avg_points > 0:  # Only include users with positive points
                    message1 += f"🍿 {user}: {avg_points:.3f}\n"
    
            message1 += "━━━━━━━━━━━━━━"
    
            # Message 2: Total Points after this sprint
            message2 = f"🏆 *Points after {current_sprint['sprint_id']} Sprint* 🏆\n━━━━━━━━━━━━━━\n"
    
            # Get updated total points from current_user_points (after adding this sprint's points)
            updated_totals = {}
            for user in current_user_points:
                if user in user_points:
                    updated_totals[user] = current_user_points[user] + user_points[user]
                else:
                    updated_totals[user] = current_user_points[user]
    
            # Sort by total points (highest first)
            sorted_by_total = sorted(updated_totals.items(), key=lambda x: x[1], reverse=True)
    
            for user, total in sorted_by_total:
                if total > 0:  # Only include users with points
                    # Format with consistent spacing
                    message2 += f"👤 {user.ljust(12)}:{total:.3f}\n"
    
            message2 += "━━━━━━━━━━━━━━"
    
            # Display messages in two columns
            col1, col2 = st.columns(2)
    
            with col1:
                st.write("**Current Sprint Ratings**")
                st.code(message1, language=None)
                if st.button("📋 Copy Rating Message", key="copy_rating"):
                    st.session_state.copied_text = message1
                    st.success("✅ Rating message copied to clipboard!")
    
            with col2:
                st.write("**Total Points Leaderboard**")
                st.code(message2, language=None)
                if st.button("📋 Copy Points Message", key="copy_points"):
                    st.session_state.copied_text = message2
                    st.success("✅ Points message copied to clipboard!")
    
            # JavaScript for clipboard copy
            if 'copied_text' in st.session_state:
                st.markdown(f"""
                <script>
                navigator.clipboard.writeText(`{st.session_state.copied_text}`);
                </script>
                """, unsafe_allow_html=True)
                # Clear after use
                del st.session_state.copied_text
