# location_tracker_streamlit_only.py
#
# 📍 Location Tracker (Streamlit-only version — works on Streamlit Cloud)
#
# Usage:
#   pip install streamlit pandas
#   streamlit run location_tracker_streamlit_only.py
#
# Features:
#   - Works on HTTPS (e.g., Streamlit Cloud)
#   - Two modes:
#       1. Dashboard (default): generate links & view reports
#       2. Tracker: collects and reports geolocation
#
#   Example URLs:
#   Dashboard → https://yourapp.streamlit.app/
#   Tracker   → https://yourapp.streamlit.app/?mode=track&token=abc123
#

import streamlit as st
import pandas as pd
import time
import uuid
from datetime import datetime

# ────────────────────────────────────────────────────────────────
# Initialize in-memory store
# ────────────────────────────────────────────────────────────────
if "reports" not in st.session_state:
    st.session_state.reports = {}  # {token: [entries]}
if "meta" not in st.session_state:
    st.session_state.meta = {}     # {token: {label, created_at}}

# ────────────────────────────────────────────────────────────────
# Get query params (mode, token, lat, lon)
# ────────────────────────────────────────────────────────────────
params = st.query_params.to_dict()
mode = params.get("mode", "dashboard")
token = params.get("token", [""])[0] if isinstance(params.get("token"), list) else params.get("token", "")
lat = params.get("lat", [""])[0] if isinstance(params.get("lat"), list) else params.get("lat", "")
lon = params.get("lon", [""])[0] if isinstance(params.get("lon"), list) else params.get("lon", "")
acc = params.get("acc", [""])[0] if isinstance(params.get("acc"), list) else params.get("acc", "")

# ────────────────────────────────────────────────────────────────
# MODE 1: TRACKER PAGE (for link visitors)
# ────────────────────────────────────────────────────────────────
if mode == "track" and token:
    st.set_page_config(page_title="📍 Share Location", layout="centered")
    st.title("📍 Share your location")
    st.write("Please allow location permission when prompted.")

    # Inject JS that gets user location and reloads with lat/lon in query
    js_code = f"""
    <script>
    function sendLocation() {{
        if (!navigator.geolocation) {{
            document.body.innerHTML = "<h3>❌ Geolocation not supported.</h3>";
            return;
        }}
        navigator.geolocation.getCurrentPosition(function(pos) {{
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const acc = pos.coords.accuracy;
            const newUrl = window.location.origin + window.location.pathname + 
                "?mode=track&token={token}&lat=" + lat + "&lon=" + lon + "&acc=" + acc;
            window.location.href = newUrl;
        }}, function(err) {{
            document.body.innerHTML = "<h3>❌ Permission denied: " + err.message + "</h3>";
        }});
    }}
    sendLocation();
    </script>
    """
    st.components.v1.html(js_code, height=0)

    # If location is already in URL, record it
    if lat and lon:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "latitude": float(lat),
            "longitude": float(lon),
            "accuracy": float(acc) if acc else None
        }
        if token not in st.session_state.reports:
            st.session_state.reports[token] = []
        st.session_state.reports[token].append(entry)

        st.success("✅ Location sent successfully!")
        st.json(entry)
        st.markdown("You can close this page now.")
    st.stop()

# ────────────────────────────────────────────────────────────────
# MODE 2: DASHBOARD (default)
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="📍 Location Tracker Dashboard", layout="wide")
st.title("📍 Streamlit Location Tracker")

st.markdown("""
This app generates unique tracking links.  
When someone opens a link and allows location access, their coordinates will appear below.
""")

# Generate link
st.subheader("Generate Tracking Link")
label = st.text_input("Label for this link (optional):")
if st.button("Generate link"):
    token = uuid.uuid4().hex[:12]
    st.session_state.meta[token] = {"label": label, "created_at": datetime.utcnow().isoformat() + "Z"}
    link = f"{st.request.url}?mode=track&token={token}"
    st.success("✅ Link generated:")
    st.code(link, language="url")

st.divider()

# View reports
st.subheader("Received Reports")
tokens = list(st.session_state.meta.keys())
if not tokens:
    st.info("No links generated yet.")
else:
    selected = st.selectbox("Select tracking token", tokens)
    reports = st.session_state.reports.get(selected, [])

    st.write(f"**Total {len(reports)} reports** for `{selected}`")
    if reports:
        df = pd.DataFrame(reports)
        st.dataframe(df)
        st.map(df[["latitude", "longitude"]].dropna())
    else:
        st.warning("No reports received yet for this token.")

st.divider()
with st.expander("Raw JSON data"):
    st.json(st.session_state.reports)

