import streamlit as st
import hashlib

# ---------------------------------------
# PASSWORD HASHING
# ---------------------------------------
def hash_password(password):
    """Simple password hashing for basic security"""
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------------------------------
# LOGIN SYSTEM
# ---------------------------------------
def initialize_session_state():
    """Initialize session state variables for login"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "role" not in st.session_state:
        st.session_state.role = "normal"

def login(username, password, users_roles, users_passwords, ADMIN_PASS):
    """Handle user login logic"""
    if username not in users_roles:
        st.error("Invalid username")
        return False

    role = users_roles[username]
    stored_password = users_passwords.get(username, "")

    if role == "admin":
        # Admin uses the secret password
        if password != ADMIN_PASS:
            st.error("Incorrect admin password")
            return False
    else:
        # Normal user uses password from Google Sheets
        if not stored_password or stored_password == "":
            st.error("No password set for this user. Please contact admin.")
            return False

        if hash_password(password) != stored_password:
            st.error("Incorrect password")
            return False

    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.role = role
    st.success(f"✅ Logged in as {username} ({role})")
    return True

def render_login_page(users_list, users_roles, users_passwords, ADMIN_PASS):
    """Render the login page and handle authentication"""
    st.title("🎬 Movie Club Login")
    username = st.selectbox("Select Username", users_list)

    # Always show password field for all users
    password = st.text_input("Password", type="password")

    # Show password hint based on user type
    if username and users_roles.get(username) == "admin":
        st.info("🔐 Admin login - enter admin password")
    elif username:
        st.info("🔐 User login - enter your personal password")

    if st.button("Login"):
        if not password:
            st.error("Please enter your password")
        else:
            if login(username, password, users_roles, users_passwords, ADMIN_PASS):
                st.rerun()

    return False  # Return False if not logged in