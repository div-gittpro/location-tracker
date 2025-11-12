# location_tracker_app.py
#
# Streamlit + Flask Location Tracker
# Usage:
#   pip install -r requirements.txt
#   streamlit run location_tracker_app.py
#
# Notes:
# - Works perfectly on localhost (browser will allow location).
# - For sharing publicly, deploy using HTTPS (e.g. Streamlit Cloud).

import streamlit as st
from streamlit.components.v1 import html
import threading
import time
import uuid
from datetime import datetime, timedelta
import json
from flask import Flask, request, Response
from flask_cors import CORS
import socket
import pandas as pd

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
FLASK_PORT = 5001
PUBLIC_HOST = ""  # If deploying publicly, put your domain name here (e.g. "myapp.streamlit.app")

# ────────────────────────────────────────────────────────────────
# Helper: Detect local IP (for LAN testing)
# ────────────────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

HOST = PUBLIC_HOST.strip() or get_local_ip()

# ────────────────────────────────────────────────────────────────
# Shared memory for reports
# ────────────────────────────────────────────────────────────────
reports = {}
reports_lock = threading.Lock()

# ────────────────────────────────────────────────────────────────
# Flask setup
# ────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/track/<token>", methods=["GET"])
def track_page(token):
    """Serve HTML page to collect user's location"""
    html_page = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Share Location</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body style="font-family:sans-serif; text-align:center; margin-top:50px;">
    <h2>📍 Share your location</h2>
    <p id="status">Requesting permission…</p>
    <script>
      const statusEl = document.getElementById('status');
      function show(msg) {{ statusEl.innerText = msg; }}

      function sendReport(data) {{
        fetch('/report/{token}', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(data)
        }}).then(r => {{
          if (r.ok) show('✅ Location sent! You may close this tab.');
          else show('❌ Failed to send location.');
        }}).catch(err => show('⚠️ Network error: ' + err));
      }}

      if (!navigator.geolocation) {{
        show('❌ Geolocation not supported by your browser.');
      }} else {{
        navigator.geolocation.getCurrentPosition(function(pos) {{
          const payload = {{
            token: '{token}',
            timestamp: new Date().toISOString(),
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
            heading: pos.coords.heading,
            speed: pos.coords.speed,
            userAgent: navigator.userAgent
          }};
          show('Got location, sending...');
          sendReport(payload);
        }}, function(err) {{
          show('❌ Permission denied or error: ' + err.message);
        }}, {{
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        }});
      }}
    </script>
  </body>
</html>
"""
    return Response(html_page, mimetype="text/html")

@app.route("/report/<token>", methods=["POST"])
def receive_report(token):
    """Receive and store location data"""
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return {"error": "Invalid JSON", "details": str(e)}, 400

    entry = {
        "received_at": datetime.utcnow().isoformat() + "Z",
        "remote_addr": request.remote_addr,
        "payload": data
    }

    with reports_lock:
        reports.setdefault(token, []).append(entry)

    return {"status": "ok"}, 200

def run_flask():
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)

def start_flask_in_thread():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    time.sleep(0.7)

# ────────────────────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="📍 Location Tracker", layout="wide")
st.title("📍 Simple Location Tracker (Streamlit + Flask)")

st.markdown("""
This app generates a **unique tracking link**.

When someone opens the link and **allows location access**,  
their latitude and longitude will be sent back and displayed below.

> ⚠️ **Important:**  
> Works only on `http://localhost` or secure `https://` origins.
""")

# Start Flask only once
if "flask_started" not in st.session_state:
    start_flask_in_thread()
    st.session_state.flask_started = True

# ────────────────────────────────────────────────────────────────
# Generate tracking link
# ────────────────────────────────────────────────────────────────
st.subheader("Generate Tracking Link")

name = st.text_input("Label for this link (optional):", value="")
ttl_minutes = st.number_input("Expiry time (minutes, 0 = never):", min_value=0, value=60, step=10)

if st.button("Generate link"):
    token = uuid.uuid4().hex[:12]
    expires_at = None
    if ttl_minutes > 0:
        expires_at = (datetime.utcnow() + timedelta(minutes=int(ttl_minutes))).isoformat() + "Z"

    with reports_lock:
        reports.setdefault(token, [])

    # Always use localhost for safer testing
    link = f"http://localhost:{FLASK_PORT}/track/{token}"

    st.success("✅ Link generated!")
    st.code(link, language="url")

    st.session_state[f"meta_{token}"] = {
        "label": name,
        "expires_at": expires_at,
        "token": token
    }

st.divider()

# ────────────────────────────────────────────────────────────────
# Display received reports
# ────────────────────────────────────────────────────────────────
st.subheader("Received Reports")

tokens = [st.session_state[key]["token"] for key in st.session_state if key.startswith("meta_")]

if not tokens:
    st.info("No links generated yet.")
else:
    sel = st.selectbox("Select tracking token:", tokens)
    with reports_lock:
        token_reports = reports.get(sel, []).copy()

    st.write(f"Total {len(token_reports)} report(s) for token `{sel}`")

    if token_reports:
        rows = []
        for r in token_reports:
            p = r["payload"]
            rows.append({
                "received_at": r["received_at"],
                "remote_addr": r.get("remote_addr"),
                "timestamp_from_client": p.get("timestamp"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "accuracy(m)": p.get("accuracy"),
                "userAgent": (p.get("userAgent") or "")[:100]
            })
        df = pd.DataFrame(rows)
        st.dataframe(df)

        # Map preview
        try:
            st.map(df[["latitude", "longitude"]].dropna())
        except Exception:
            st.warning("Map preview not available.")

# Raw JSON (debug)
with st.expander("Show raw JSON data"):
    with reports_lock:
        st.json(reports)

