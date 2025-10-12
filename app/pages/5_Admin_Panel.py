import streamlit as st
import pandas as pd
from datetime import date, timedelta
from utils.sheets import load_sheet, get_sprint_display_info, load_testing_config, get_current_date, get_sheet_connection
from utils.auth import hash_password

def show():
    if st.session_state.role != "admin":
        st.warning("Admin access only.")
        return

    st.header("⚙️ Admin Panel")

    # Show testing mode status
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.warning(f"🧪 **TESTING MODE ACTIVE** - Current simulated date: {test_date}")
    else:
        st.info(f"📅 **PRODUCTION MODE** - Current date: {get_current_date()}")

    # Show current sprint information
    sprint_info = get_sprint_display_info()
    if sprint_info:
        st.subheader("🏃‍♂️ Current Sprint Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sprint ID", sprint_info['sprint_id'])
        with col2:
            st.metric("Days Remaining", sprint_info['days_remaining'])
        with col3:
            st.metric("Progress", f"{100 - (sprint_info['days_remaining'] / sprint_info['total_days'] * 100):.1f}%")
        
        st.write(f"**Description:** {sprint_info['description']}")
        st.write(f"**Period:** {sprint_info['start_date']} to {sprint_info['end_date']}")

    st.subheader("Testing Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("Configure testing mode using the Testing sheet")
        st.info("""
        **To enable testing mode:**
        1. Create a 'Testing' worksheet in your Google Sheet
        2. Add headers: `date` (first row)
        3. Set your test date in format YYYY-MM-DD or DD/MM/YYYY
        
        **To disable testing mode:**
        - Clear the date cell or delete the Testing worksheet
        """)
    
    with col2:
        # Quick actions for testing
        st.write("**Quick Actions**")
        if testing_enabled:
            if st.button("🔄 Disable Testing Mode"):
                try:
                    ws = get_sheet_connection().worksheet("Testing")
                    ws.clear()
                    st.success("✅ Testing mode disabled!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to disable testing: {e}")
        else:
            if st.button("🧪 Enable Testing Mode"):
                try:
                    # Create Testing sheet if it doesn't exist
                    try:
                        ws = get_sheet_connection().worksheet("Testing")
                    except:
                        ws = get_sheet_connection().add_worksheet(title="Testing", rows="100", cols="2")
                        ws.append_row(["date"])  # Add header
                    
                    # Set today as test date
                    ws.update_cell(2, 1, date.today().strftime('%Y-%m-%d'))
                    st.success("✅ Testing mode enabled with today's date!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to enable testing: {e}")

    # Current testing configuration
    if testing_enabled:
        st.write("**Current Testing Configuration**")
        st.code(f"""
        Testing Sheet Status: ACTIVE
        Simulated Date: {test_date}
        """)
        
        # Quick date updates
        st.write("**Quick Date Updates**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Set to Today"):
                try:
                    ws = get_sheet_connection().worksheet("Testing")
                    ws.update_cell(2, 1, date.today().strftime('%Y-%m-%d'))
                    st.success("✅ Date set to today!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        with col2:
            if st.button("+1 Day"):
                try:
                    ws = get_sheet_connection().worksheet("Testing")
                    new_date = test_date + timedelta(days=1)
                    ws.update_cell(2, 1, new_date.strftime('%Y-%m-%d'))
                    st.success(f"✅ Date set to {new_date}!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        with col3:
            if st.button("-1 Day"):
                try:
                    ws = get_sheet_connection().worksheet("Testing")
                    new_date = test_date - timedelta(days=1)
                    ws.update_cell(2, 1, new_date.strftime('%Y-%m-%d'))
                    st.success(f"✅ Date set to {new_date}!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update date: {e}")
        
        # Manual date input
        new_test_date = st.date_input(
            "Set Custom Test Date",
            value=test_date,
            key="test_date_picker"
        )
        
        if new_test_date != test_date:
            try:
                ws = get_sheet_connection().worksheet("Testing")
                ws.update_cell(2, 1, new_test_date.strftime('%Y-%m-%d'))
                st.success(f"✅ Date set to {new_test_date}!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update date: {e}")

    st.subheader("Page Control")
    # Use callbacks to save changes immediately
    def update_page_config():
        try:
            ws = get_sheet_connection().worksheet("Config")
            # Clear existing config
            ws.clear()
            # Add headers
            ws.append_row(["key", "value"])
            # Add new config
            config_data = [
                ["enable_suggestion", str(st.session_state.enable_suggestion)],
                ["enable_voting", str(st.session_state.enable_voting)], 
                ["enable_rating", str(st.session_state.enable_rating)]
            ]
            for config in config_data:
                ws.append_row(config)
            st.cache_data.clear()
            st.success("✅ Page settings saved!")
        except Exception as e:
            st.warning(f"Failed to save config: {e}")

    col1, col2, col3 = st.columns(3)
    with col1:
        suggestion_enabled = st.checkbox("Enable Suggestion Page", 
                      value=st.session_state.enable_suggestion,
                      key="admin_suggestion")
    
    with col2:
        voting_enabled = st.checkbox("Enable Voting Page", 
                      value=st.session_state.enable_voting,
                      key="admin_voting")
    
    with col3:
        rating_enabled = st.checkbox("Enable Rating Page",
                      value=st.session_state.enable_rating,
                      key="admin_rating")

    if st.button("Save Page Settings"):
        st.session_state.enable_suggestion = suggestion_enabled
        st.session_state.enable_voting = voting_enabled
        st.session_state.enable_rating = rating_enabled
        update_page_config()

    st.subheader("User Management")
    
    tab1, tab2 = st.tabs(["Add New User", "Reset User Password"])
    
    with tab1:
        st.write("Add a new user to the system")
        new_user = st.text_input("New User Name")
        role = st.selectbox("Role", ["normal", "admin"])
        user_password = st.text_input("Set Password", type="password", key="new_user_password")
        
        if st.button("Add User"):
            if new_user and user_password:
                try:
                    ws = get_sheet_connection().worksheet("Users")
                    # Hash the password before storing
                    hashed_password = hash_password(user_password)
                    ws.append_row([new_user, role, 0, hashed_password])  # Start with 0 points
                    st.success(f"✅ Added {new_user} as {role}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.warning(f"Failed to add user: {e}")
            else:
                st.error("Please enter both username and password")
    
    with tab2:
        st.write("Reset password for existing user")
        users_data = load_sheet("Users")
        user_names = [user['user_name'] for user in users_data if user['user_name'] != st.session_state.username]
        
        if user_names:
            selected_user = st.selectbox("Select User", user_names)
            new_password = st.text_input("New Password", type="password", key="reset_password")
            
            if st.button("Reset Password"):
                if new_password:
                    try:
                        ws = get_sheet_connection().worksheet("Users")
                        users_records = ws.get_all_records()
                        
                        # Find the user and update their password
                        for i, user_record in enumerate(users_records):
                            if user_record['user_name'] == selected_user:
                                hashed_password = hash_password(new_password)
                                # Update password in column 4 (D)
                                ws.update_cell(i + 2, 4, hashed_password)
                                st.success(f"✅ Password reset for {selected_user}")
                                st.cache_data.clear()
                                break
                    except Exception as e:
                        st.warning(f"Failed to reset password: {e}")
                else:
                    st.error("Please enter a new password")
        else:
            st.info("No other users found")
