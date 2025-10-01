import shlex
import subprocess
from pathlib import Path
import os
from dotenv import load_dotenv
import modal

# -------------------------------
# --- Load environment variables ---
# -------------------------------
load_dotenv()

endpoint = os.getenv("OPENAI_ENDPOINT")
api_key = os.getenv("OPENAI_API_KEY")
deployment_name = os.getenv("OPENAI_DEPLOYMENT")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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
    .pip_install("streamlit", "supabase", "pandas", "plotly", "python-dotenv")
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
@app.function(allow_concurrent_inputs=100)
@modal.web_server(8000)
def run():
    target = shlex.quote(streamlit_script_remote_path)
    cmd = f"streamlit run {target} --server.port 8000 --server.enableCORS=false --server.enableXsrfProtection=false"

    # Build environment variables
    env_vars = {}
    if SUPABASE_KEY:
        env_vars["SUPABASE_KEY"] = SUPABASE_KEY
    if SUPABASE_URL:
        env_vars["SUPABASE_URL"] = SUPABASE_URL
    if endpoint:
        env_vars["OPENAI_ENDPOINT"] = endpoint
    if api_key:
        env_vars["OPENAI_API_KEY"] = api_key
    if deployment_name:
        env_vars["OPENAI_DEPLOYMENT"] = deployment_name

    env_vars.update(os.environ)
    subprocess.Popen(cmd, shell=True, env=env_vars)