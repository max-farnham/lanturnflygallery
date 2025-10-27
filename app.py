from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import os, re, logging

# --- Config ---
CONTAINER_NAME = os.getenv("IMAGES_CONTAINER", "lanternfly-images")

# Use connection string (local dev) or account URL (deployment)
if "AZURE_STORAGE_CONNECTION_STRING" in os.environ:
    bsc = BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])
else:
    account_url = os.environ.get("STORAGE_ACCOUNT_URL")
    if not account_url:
        raise ValueError("Missing STORAGE_ACCOUNT_URL or AZURE_STORAGE_CONNECTION_STRING")
    bsc = BlobServiceClient(account_url=account_url)

cc = bsc.get_container_client(CONTAINER_NAME)

# --- Flask App ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

@app.route("/api/v1/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify(ok=False, error="No file uploaded"), 400

        f = request.files["file"]

        # Validate file type
        if not f.mimetype.startswith("image/"):
            return jsonify(ok=False, error="Only image files allowed"), 400

        # Limit file size to 10MB
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > 10 * 1024 * 1024:
            return jsonify(ok=False, error="File too large (max 10MB)"), 400

        # Create timestamped filename
        safe_name = sanitize_filename(f.filename)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        blob_name = f"{ts}-{safe_name}"

        # Upload to Azure Blob Storage
        blob_client = cc.get_blob_client(blob_name)
        blob_client.upload_blob(f, overwrite=True)

        app.logger.info(f"Uploaded: {blob_name}")
        return jsonify(ok=True, url=f"{cc.url}/{blob_name}")
    except Exception as e:
        app.logger.error(f"Upload error: {e}")
        return jsonify(ok=False, error=str(e)), 500


@app.route("/api/v1/gallery", methods=["GET"])
def gallery():
    try:
        blobs = cc.list_blobs()
        urls = [f"{cc.url}/{b.name}" for b in blobs]
        return jsonify(ok=True, gallery=urls)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@app.route("/health")
def health():
    return jsonify(ok=True)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
