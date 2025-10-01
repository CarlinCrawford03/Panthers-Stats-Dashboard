import shlex
import subprocess
from pathlib import Path
import os
import modal

# -------------------------------
# --- Define paths ---
# -------------------------------
streamlit_script_local_path = Path(__file__).parent / "app.py"
streamlit_script_remote_path = "/root/app.py"

# -------------------------------
# --- Define Modal image ---
# -------------------------------
image = (
    modal.Image.debian_slim(python_version="3.9")
    .pip_install("streamlit", "supabase", "pandas", "plotly")
    .env({"FORCE_REBUILD": "true"})
    .add_local_file(streamlit_script_local_path, streamlit_script_remote_path)
)

# -------------------------------
# --- Define Modal app ---
# -------------------------------
app = modal.App(name="panthers-dashboard", image=image)

# -------------------------------
# --- Validate local Streamlit script ---
# -------------------------------
if not streamlit_script_local_path.exists():
    raise RuntimeError("Missing app.py — make sure it's in the same folder.")

# -------------------------------
# --- Define web server function ---
# -------------------------------
@app.function(
    allow_concurrent_inputs=100,
    secrets=[modal.Secret.from_name("panthers-secret")]  # 👈 attach your secret here
)
@modal.web_server(8000)
def run():
    target = shlex.quote(streamlit_script_remote_path)
    cmd = f"streamlit run {target} --server.port 8000 --server.enableCORS=false --server.enableXsrfProtection=false"

    # All secrets are injected into os.environ automatically
    subprocess.Popen(cmd, shell=True, env=os.environ.copy())
