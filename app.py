import streamlit as st
import cloudinary
import cloudinary.uploader
import os

# Import functions from main app
from app import (load_sheet, get_sprint_display_info, get_current_sprint, 
                has_user_suggested_in_sprint, get_current_datetime, load_testing_config,
                get_sheet_connection, CLOUD_NAME, API_KEY, API_SECRET)

st.set_page_config(page_title="Suggest Movie", page_icon="🎥")

def main():
    if not st.session_state.get('enable_suggestion', True) and st.session_state.get('role') != "admin":
        st.warning("Suggestion page is currently disabled by admin.")
        return

    # Display sprint information in header
    sprint_info = get_sprint_display_info()
    current_sprint = get_current_sprint()
    
    if sprint_info and current_sprint:
        st.header(f"🎥 Suggest a Movie - {sprint_info['sprint_id']}")
        st.write(f"**{sprint_info['description']}** | {sprint_info['days_remaining']} days remaining")
    else:
        st.header("🎥 Suggest a Movie")
        st.warning("No active sprint found. Movie suggestions will not be associated with any sprint.")
    
    # Show testing mode indicator
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        st.info(f"🧪 Testing Mode: Using date {test_date}")
    
    user_name = st.session_state.username
    
    # Check if user has already suggested in this sprint
    if current_sprint and has_user_suggested_in_sprint(user_name, current_sprint['sprint_id']):
        st.success("✅ You have already suggested a movie for this sprint!")
        st.info("You can only suggest one movie per sprint.")
        return
    
    movie_name = st.text_input("Movie Name")
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
                    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
                    result = cloudinary.uploader.upload(image)
                    image_url = result.get('secure_url', '')
                except Exception as e:
                    st.warning(f"Cloudinary upload failed: {e}")

            try:
                ws = get_sheet_connection().worksheet("Suggestions")
                current_timestamp = get_current_datetime()
                sprint_id = current_sprint['sprint_id'] if current_sprint else ""
                
                ws.append_row([
                    sprint_id,
                    user_name,
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

if __name__ == "__main__":
    main()
