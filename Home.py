import streamlit as st
import os

# --- LOGIN CONFIG ---
# Simple hardcoded login
PASSWORD = st.secrets["STREAMLIT_PASSWORD"]
VALID_USERS = {
    "mike": PASSWORD,
    "adam": PASSWORD
}

# Set wide layout and page title
st.set_page_config(page_title="Searchabull Keyword Engine", layout="wide")

# --- AUTHENTICATION CHECK ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Login Required")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

        if login_btn:
            if username in VALID_USERS and VALID_USERS[username] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()

# --- AUTHENTICATED AREA BELOW ---

st.title("🚀 Welcome to the Searchabull Keyword Engine")

with st.sidebar:
    st.markdown("## 👤 Profile")
    st.text_input("User", value=st.session_state.user, key="user_display", disabled=True)


col1, col2 = st.columns(2)

with col1:
    st.subheader("🔑 Monthly Access Tool")
    st.write("""Get either historical volumes or keyword ideas using Google Ads API\n
- Returns only the last 12 months of search volumes for the keywords\n
- For Historical Volumes it can batch up to 10,000 keywords at a time (per API request)\n
- For Keyword Ideas it can batch up to 20 keywords at a time (per API request)\n
- The API access is free
             """)
    if st.button("Go to Monthly Access Tool"):
        st.switch_page("pages/Google_Ads_API.py")

with col2:
    st.subheader("🔍 DataForSEO API Tool")
    st.write("""Get either historical volumes or keyword ideas using DataForSEO API
- Returns the full 48 months of search volumes for the keywords\n
- For Historical Volumes it can batch up to 1000 keywords at a time (per API request)\n
- For Keyword Ideas it can batch up to 20 keywords at a time (per API request)\n
- The API access costs 7.5 cents per request!
             """)
    if st.button("Go to DataForSEO API Tool"):
        st.switch_page("pages/Data_For_SEO_API.py")

st.markdown("---")
