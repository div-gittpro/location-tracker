# lt.py
# 📍 Streamlit Deployable Location Tracker
# Works globally via HTTPS (Streamlit Cloud) or locally for testing.

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
# Read query parameters
# ───────────────────────────────
params = st.query_params.to_dict()
token = params.get("token", "")
lat = params.get("lat", "")
lon = params.get("lon", "")
acc = params.get("acc", "")

# ───────────────────────────────
# Save incoming GPS data
# ───────────────────────────────
if token and lat and lon:
    save_report(token, float(lat), float(lon), float(acc) if acc else None)
    st.success("✅ Location sent successfully!")
    st.stop()

# ───────────────────────────────
# Shareable tracking page (visitor)
# ───────────────────────────────
if token and not (lat and lon):
    st.set_page_config(page_title="📍 Share Location", layout="centered")
    st.title("📍 Share Location")
    st.write("Please allow location permission when prompted. Your GPS coordinates will be sent automatically.")

    js = f"""
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
          const target = window.location.origin + window.location.pathname +
              "?token={token}&lat=" + lat + "&lon=" + lon + "&acc=" + acc;
          fetch(target).then(() => {{
              document.body.innerHTML = "<h3>✅ Location sent successfully!</h3><p>You can close this tab.</p>";
          }});
        }}, function(err) {{
          document.body.innerHTML = "<h3>❌ Error: " + err.message + "</h3>";
        }});
      }}
      sendLocation();
    </script>
    """
    st.components.v1.html(js, height=0)
    st.stop()

# ───────────────────────────────
# Dashboard (default admin view)
# ───────────────────────────────
st.set_page_config(page_title="📍 Location Tracker Dashboard", layout="wide")
st.title("📍 Location Tracker Dashboard")

st.markdown("""
Generate a **shareable tracking link**.  
When someone opens it and allows GPS access, their location will appear below.
""")

# ────────────── Generate shareable link ──────────────
if st.button("🔗 Generate New Link"):
    new_token = uuid.uuid4().hex[:10]

    # Detect Streamlit Cloud public URL dynamically
    base_url = st.experimental_get_query_params().get("base", [""])[0]
    if not base_url:
        try:
            ctx = st.context if hasattr(st, "context") else None
            if ctx and hasattr(ctx, "browser"):
                base_url = ctx.browser.server_url
        except Exception:
            pass

    # Fallback: default to your Streamlit Cloud domain (replace below)
    if not base_url or "localhost" in base_url:
        base_url = "https://location-tracker-yourusername.streamlit.app"  # 🔹 change this to your app name

    link = f"{base_url}/?token={new_token}"

    st.success("✅ Share this public tracking link:")
    st.code(link, language="url")

st.divider()

# ────────────── Display received reports ──────────────
st.subheader("📊 Received Location Reports")

df = get_reports()
if df.empty:
    st.info("No location data yet. Generate a link and share it to start tracking.")
else:
    st.dataframe(df, use_container_width=True)
    st.map(df[["latitude", "longitude"]])

