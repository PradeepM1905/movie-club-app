import streamlit as st
from datetime import datetime, date
from sheets_utils import load_sheet
import json

# ---------------------------------------
# SPRINT MANAGEMENT
# ---------------------------------------
@st.cache_data(ttl=120)
def get_current_sprint():
    """Get the current active sprint based on date"""
    try:
        sprints_data = load_sheet("Sprints")
        current_date = get_current_date()

        for sprint in sprints_data:
            start_date = datetime.strptime(sprint['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()

            if start_date <= current_date <= end_date:
                return sprint

        # If no active sprint found, return the most recent past sprint or None
        if sprints_data:
            # Sort sprints by end_date descending to get the most recent one
            sorted_sprints = sorted(sprints_data,
                                    key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'),
                                    reverse=True)
            return sorted_sprints[0]

        return None
    except Exception as e:
        st.warning(f"Error loading sprints: {e}")
        return None

def get_previous_sprint():
    """Get the previous sprint for rating purposes"""
    try:
        sprints_data = load_sheet("Sprints")
        current_date = get_current_date()

        # Sort sprints by end_date descending
        sorted_sprints = sorted(sprints_data,
                                key=lambda x: datetime.strptime(x['end_date'], '%Y-%m-%d'),
                                reverse=True)

        # Find the sprint that ended just before today
        for sprint in sorted_sprints:
            end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()
            if end_date < current_date:
                return sprint

        return None
    except Exception as e:
        st.warning(f"Error loading previous sprint: {e}")
        return None

def is_rating_allowed_for_sprint(sprint_data):
    """Check if rating is allowed for a sprint (between start date and end date + 1 day)"""
    if not sprint_data:
        return False
    
    try:
        current_date = get_current_date()
        start_date = datetime.strptime(sprint_data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(sprint_data['end_date'], '%Y-%m-%d').date()
        
        # Rating allowed from start date to end date + 1 day
        rating_end_date = end_date + timedelta(days=1)
        
        return start_date <= current_date <= rating_end_date
    except Exception as e:
        st.warning(f"Error checking rating period: {e}")
        return False

def get_sprint_display_info():
    """Get sprint information for display"""
    current_sprint = get_current_sprint()
    if current_sprint:
        current_date = get_current_date()
        sprint_end = datetime.strptime(current_sprint['end_date'], '%Y-%m-%d').date()
        days_remaining = (sprint_end - current_date).days

        return {
            'sprint_id': current_sprint['sprint_id'],
            'description': current_sprint.get('description', ''),
            'start_date': current_sprint['start_date'],
            'end_date': current_sprint['end_date'],
            'days_remaining': max(0, days_remaining),
            'total_days': (sprint_end - datetime.strptime(current_sprint['start_date'], '%Y-%m-%d').date()).days + 1
        }
    return None

# ---------------------------------------
# TESTING MODE FROM GOOGLE SHEETS
# ---------------------------------------
@st.cache_data(ttl=60)
def load_testing_config():
    """Load testing configuration from Google Sheets"""
    try:
        testing_data = load_sheet("Testing")
        # Add null check here
        if not testing_data or len(testing_data) == 0:
            return False, date.today()

        if testing_data and len(testing_data) > 0:
            # Get the first row which should contain the test date
            test_config = testing_data[0]
            # Add null check for test_config
            if not test_config:
                return False, date.today()

            test_date_str = test_config.get('date', '').strip()

            # Add check for empty string
            if not test_date_str:
                return False, date.today()

            try:
                # Parse date from string (assuming YYYY-MM-DD format)
                test_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
                return True, test_date
            except ValueError:
                # Try other common date formats
                try:
                    test_date = datetime.strptime(test_date_str, '%d/%m/%Y').date()
                    return True, test_date
                except ValueError:
                    st.warning(f"⚠️ Invalid date format in Testing sheet: {test_date_str}. Use YYYY-MM-DD or DD/MM/YYYY")
                    return False, date.today()
        return False, date.today()
    except Exception as e:
        # If Testing sheet doesn't exist or has errors, return normal mode
        return False, date.today()

def get_previous_sprint_quiz_data():
    """Get quiz data for the previous sprint"""
    try: 
        # Load quiz data
        quiz_data = load_sheet("QuizInfo")
        
        if not quiz_data:
            return None, None
        
        # Load sprints to find previous sprint
        sprints_data = load_sheet("Sprints")
        if not sprints_data:
            return None, None
        
        current_date = get_current_date()
        
        # Find previous sprint
        previous_sprint = None
        
        for sprint in sorted(sprints_data, key=lambda x: x['end_date'], reverse=True):
            end_date = end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()
            
            if end_date < current_date:
                previous_sprint = sprint
                break
        
        if not previous_sprint:
            return None, None
        
        for quiz in quiz_data:
            if quiz.get('sprint_id') == previous_sprint['sprint_id']:
                try:
                    quiz_json_str = quiz.get('quiz_json', '{}')
                    quiz_json = json.loads(quiz_json_str)
                    return quiz_json, previous_sprint
                except json.JSONDecodeError as e:
                    continue
                except Exception as e:
                    continue
        
        return None, None
        
    except Exception as e:
        import traceback
        return None, None

def get_current_date():
    """Get current date - either real or from testing configuration"""
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return test_date
    else:
        return date.today()

def get_current_datetime():
    """Get current datetime - either real or from testing configuration"""
    testing_enabled, test_date = load_testing_config()
    if testing_enabled:
        return datetime.combine(test_date, datetime.min.time())
    else:
        return datetime.now()
