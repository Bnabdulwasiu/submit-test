import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse, unquote

import sys

# Ensure main is importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import main

def start_test_client(data_dir: str):
    main.DATA_DIR = Path(data_dir)
    main.UPLOAD_DIR = main.DATA_DIR / "uploads"
    main.DB_FILE = main.DATA_DIR / "submissions.json"
    main.ensure_storage()
    return TestClient(main.app)

def test_homepage_loads_and_shows_form():
    with TemporaryDirectory() as temp_dir:
        client = start_test_client(temp_dir)
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Assignment Submission Platform" in html
        assert "Upload assignment" in html

def test_valid_submission_is_saved():
    with TemporaryDirectory() as temp_dir:
        client = start_test_client(temp_dir)
        
        response = client.post(
            "/submit",
            data={"student_name": "Alice", "title": "Math Homework"},
            files={"file": ("homework.jpg", b"fake-image-bytes", "image/jpeg")},
            follow_redirects=False # We want to check the redirect location
        )

        assert response.status_code == 303
        location = unquote(response.headers["location"])
        assert "message=Assignment uploaded successfully" in location
        
        # Verify DB
        db = json.loads((Path(temp_dir) / "submissions.json").read_text())
        assert len(db) == 1
        assert db[0]["student_name"] == "Alice"
        assert db[0]["title"] == "Math Homework"
        uploaded = Path(temp_dir) / "uploads" / db[0]["stored_name"]
        assert uploaded.exists()
        assert uploaded.read_bytes() == b"fake-image-bytes"

def test_rejects_disallowed_file_type():
    with TemporaryDirectory() as temp_dir:
        client = start_test_client(temp_dir)
        
        response = client.post(
            "/submit",
            data={"student_name": "Alice", "title": "Essay"},
            files={"file": ("essay.txt", b"text", "text/plain")},
            follow_redirects=False
        )

        assert response.status_code == 303
        location = unquote(response.headers["location"])
        assert "error=" in location
        assert "Only PDF" in location

        db = json.loads((Path(temp_dir) / "submissions.json").read_text())
        assert len(db) == 0

def test_missing_form_values_sets_friendly_error_message():
    with TemporaryDirectory() as temp_dir:
        client = start_test_client(temp_dir)
        
        # Sending empty student name
        response = client.post(
            "/submit",
            data={"student_name": "", "title": "Essay"},
            files={"file": ("essay.jpg", b"image", "image/jpeg")},
            follow_redirects=False
        )

        assert response.status_code == 303
        location = unquote(response.headers["location"])
        assert "error=Please fill all fields" in location

