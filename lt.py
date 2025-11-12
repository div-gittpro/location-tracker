# location_tracker_app.py
#
# Streamlit + Flask location tracker app
# Usage:
#   pip install streamlit flask flask_cors
#   streamlit run location_tracker_app.py
#
# Works locally (http://localhost) or with HTTPS on a public server.
# Browser will ask the visitor for location permission.

import streamlit as st
from streamlit.components.v1 import html
import threading
import time
import uuid
from datetime import datetime, timedelta   # ✅ FIXED: added timedelta import
import json
from flask import Flask, request, Response
from flask_cors import CORS
import socket

# ---------- CONFIG ----------
FLASK_PORT = 5001
# If you deploy publicly, set PUBLIC_HOST = "yourdomain.com"
PUBLIC_HOST = ""
# ----------------------------

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

# Shared in-memory storage
reports = {}
reports_lock = threading.Lock()

# ---------- Flask server ----------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/track/<token>", methods=["GET"])
def track_page(token):
    html_page = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>Location Share</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <h3 style="font-family:sans-serif">📍 Share location</h3>
    <p id="status">Requesting location permission…</p>
    <script>
      const statusEl = document.getElementById('status');
      function show(msg) {{ statusEl.innerText = msg; }}

      function sendReport(data) {{
        fetch('/report/{token}', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json'
          }},
          body: JSON.stringify(data)
        }}).then(r => {{
          if (r.ok) {{
            show('✅ Location sent. You may close this page.');
          }} else {{
            show('❌ Failed to send location. Server returned ' + r.status);
          }}
        }}).catch(err => {{
          show('⚠️ Failed to send location: ' + err);
        }});
      }}

      if (!navigator.geolocation) {{
        show('Geolocation not supported by your browser.');
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
          show('Got location. Sending to server...');
          sendReport(payload);
        }}, function(err) {{
          show('Permission denied or error: ' + err.message);
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
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return {"error": "invalid json", "details": str(e)}, 400

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

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Simple Location Tracker", layout="wide")
st.title("📍 Simple Location Tracker (Streamlit + Flask)")

st.markdown(
    """
This app generates a unique tracking link.  
When someone opens that link **and allows location access**,  
their browser sends location data back to this dashboard.

⚠️ **Geolocation works only on HTTPS or localhost.**
"""
)

if "flask_started" not in st.session_state:
    start_flask_in_thread()
    st.session_state.flask_started = True

col1, col2 = st.columns([2, 1])

with col1:
    st.header("Generate tracking link")
    name = st.text_input("Label for this link (optional)", value="")
    ttl_minutes = st.number_input("Link expiry (minutes, 0 = never expire)", min_value=0, value=60, step=10)
    if st.button("Generate link"):
        token = uuid.uuid4().hex[:12]
        expires_at = None
        if ttl_minutes > 0:
            expires_at = (datetime.utcnow() + timedelta(minutes=int(ttl_minutes))).isoformat() + "Z"
        with reports_lock:
            reports.setdefault(token, [])
   link = f"http://localhost:{FLASK_PORT}/track/{token}"
        st.success("Link generated!")
        st.code(link, language="url")
        st.session_state[f"meta_{token}"] = {"label": name, "expires_at": expires_at, "token": token}

with col2:
    st.header("Notes")
    st.markdown(
        f"""
- Flask endpoint: `http://{HOST}:{FLASK_PORT}/track/<token>`  
- Ask the person to **open and allow location**  
- For public use, host behind **HTTPS**
"""
    )

st.markdown("---")
st.header("Received reports")

tokens = []
for key in list(st.session_state.keys()):
    if key.startswith("meta_"):
        tokens.append(st.session_state[key]["token"])

if not tokens:
    st.info("No links generated yet.")
else:
    sel = st.selectbox("Select tracking token", options=tokens)
    with reports_lock:
        token_reports = reports.get(sel, []).copy()
    st.write(f"Showing {len(token_reports)} report(s) for token `{sel}`.")
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
                "userAgent": (p.get("userAgent") or "")[:120]
            })
        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df)

        # Optional: show map
        try:
            st.map(df[["latitude", "longitude"]].dropna())
        except Exception:
            pass

st.markdown("### Raw reports (debug)")
with st.expander("Show raw JSON storage"):
    with reports_lock:
        st.json(reports)


