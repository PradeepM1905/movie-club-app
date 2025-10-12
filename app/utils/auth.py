import streamlit as st
import hashlib
import os

def hash_password(password):
    """Simple password hashing for basic security"""
    return hashlib.sha256(password.encode()).hexdigest()

def login_system(username, password, users_roles, users_passwords):
    """Handle user login"""
    ADMIN_PASS = st.secrets.get("adminPass", os.getenv("adminPass"))
    
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
