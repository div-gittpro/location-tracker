# lt.py
# 📍 Simple Location Tracker (Dashboard + Shareable Tracking Page)

import streamlit as st
import pandas as pd
import uuid
import sqlite3
from datetime import datetime

DB_PATH = "locations.db"

# ───────────────────────────────
# Database setup
# ───────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            token TEXT,
            timestamp TEXT,
            latitude REAL,
            longitude REAL,
            accuracy REAL
        )
    """)
    conn.commit()
    conn.close()

def save_report(token, lat, lon, acc):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reports (token, timestamp, latitude, longitude, accuracy) VALUES (?, ?, ?, ?, ?)",
        (token, datetime.utcnow().isoformat() + "Z", lat, lon, acc),
    )
    conn.commit()
    conn.close()

def get_reports():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM reports ORDER BY timestamp DESC", conn)
    conn.close()
    return df

init_db()

# ───────────────────────────────
# Read query params
# ───────────────────────────────
params = st.query_params.to_dict()
token = params.get("token", "")
lat = params.get("lat", "")
lon = params.get("lon", "")
acc = params.get("acc", "")

# ───────────────────────────────
# Save incoming location if provided
# ───────────────────────────────
if token and lat and lon:
    save_report(token, float(lat), float(lon), float(acc) if acc else None)
    st.success("✅ Location sent successfully!")
    st.stop()

# ───────────────────────────────
# If token exists (shareable link opened)
# ───────────────────────────────
if token and not (lat and lon):
    st.set_page_config(page_title="📍 Share Location", layout="centered")
    st.title("📍 Share Location")
    st.write("Please allow location permission when prompted. Your location will be sent automatically.")

    js = f"""
    <script>
      function sendLocation() {{
        if (!navigator.geolocation) {{
          document.body.innerHTML = "<h3>❌ Geolocation not supported.</h3>";
          return;
        }}
        navigator.geolocation.getCurrentPosition(function(p) {{
          const lat = p.coords.latitude;
          const lon = p.coords.longitude;
          const acc = p.coords.accuracy;
          const url = window.location.origin + window.location.pathname +
              "?token={token}&lat=" + lat + "&lon=" + lon + "&acc=" + acc;
          window.location.href = url;
        }}, err => {{
          document.body.innerHTML = "<h3>❌ Error: " + err.message + "</h3>";
        }});
      }}
      sendLocation();
    </script>
    """
    st.components.v1.html(js, height=0)
    st.stop()

# ───────────────────────────────
# Otherwise → Dashboard view
# ───────────────────────────────
st.set_page_config(page_title="📍 Location Tracker Dashboard", layout="wide")
st.title("📍 Location Tracker Dashboard")

st.markdown("""
Generate a shareable link.  
When someone opens it and allows location access, their coordinates appear below.
""")

# Generate link
if st.button("🔗 Generate New Link"):
    new_token = uuid.uuid4().hex[:10]
    host = st.get_option("browser.serverAddress")
    if "localhost" in host or "127.0.0.1" in host:
        link = f"http://localhost:8501/?token={new_token}"
    else:
        link = f"https://{host}/?token={new_token}"
    st.success("✅ Share this link:")
    st.code(link, language="url")

st.divider()

# Display reports
st.subheader("📊 Received Reports")

df = get_reports()
if df.empty:
    st.info("No location data yet. Generate a link and open it on a phone to start tracking.")
else:
    st.dataframe(df, use_container_width=True)
    st.map(df[["latitude", "longitude"]])

