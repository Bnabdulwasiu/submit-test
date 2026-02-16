import io
import json
import threading
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import server
from http.server import ThreadingHTTPServer


def start_test_server(data_dir: str):
    server.DATA_DIR = Path(data_dir)
    server.UPLOAD_DIR = server.DATA_DIR / "uploads"
    server.DB_FILE = server.DATA_DIR / "submissions.json"
    server.ensure_storage()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AssignmentHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def encode_multipart(fields, files, boundary="----testboundary"):
    body = io.BytesIO()
    for name, value in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(str(value).encode())
        body.write(b"\r\n")

    for name, file_meta in files.items():
        filename, content, content_type = file_meta
        body.write(f"--{boundary}\r\n".encode())
        body.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        body.write(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.write(content)
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def test_homepage_loads_and_shows_form():
    with TemporaryDirectory() as temp_dir:
        httpd = start_test_server(temp_dir)
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1])
        conn.request("GET", "/")
        response = conn.getresponse()
        html = response.read().decode()
        assert response.status == 200
        assert "Assignment Submission Platform" in html
        assert "Upload assignment" in html
        httpd.shutdown()


def test_valid_submission_is_saved():
    with TemporaryDirectory() as temp_dir:
        httpd = start_test_server(temp_dir)
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1])

        body, content_type = encode_multipart(
            {"student_name": "Alice", "title": "Math Homework"},
            {"file": ("homework.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        conn.request("POST", "/submit", body=body, headers={"Content-Type": content_type})
        response = conn.getresponse()
        response.read()

        assert response.status == 303
        location = response.getheader("Location")
        assert location.startswith("/?message=")
        params = parse_qs(urlparse(location).query)
        assert params["message"][0] == "Assignment uploaded successfully."

        db = json.loads((Path(temp_dir) / "submissions.json").read_text())
        assert len(db) == 1
        assert db[0]["student_name"] == "Alice"
        assert db[0]["title"] == "Math Homework"
        uploaded = Path(temp_dir) / "uploads" / db[0]["stored_name"]
        assert uploaded.exists()
        assert uploaded.read_bytes() == b"fake-image-bytes"

        httpd.shutdown()


def test_rejects_disallowed_file_type():
    with TemporaryDirectory() as temp_dir:
        httpd = start_test_server(temp_dir)
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1])

        body, content_type = encode_multipart(
            {"student_name": "Alice", "title": "Essay"},
            {"file": ("essay.txt", b"text", "text/plain")},
        )
        conn.request("POST", "/submit", body=body, headers={"Content-Type": content_type})
        response = conn.getresponse()
        response.read()

        assert response.status == 303
        location = response.getheader("Location")
        assert "error=" in location
        params = parse_qs(urlparse(location).query)
        assert params["error"][0] == "Only PDF, PNG, JPG, and JPEG files are allowed."
        db = json.loads((Path(temp_dir) / "submissions.json").read_text())
        assert db == []

        httpd.shutdown()


def test_missing_form_values_sets_friendly_error_message():
    with TemporaryDirectory() as temp_dir:
        httpd = start_test_server(temp_dir)
        conn = HTTPConnection("127.0.0.1", httpd.server_address[1])

        body, content_type = encode_multipart(
            {"student_name": "", "title": "Essay"},
            {"file": ("essay.jpg", b"image", "image/jpeg")},
        )
        conn.request("POST", "/submit", body=body, headers={"Content-Type": content_type})
        response = conn.getresponse()
        response.read()

        assert response.status == 303
        params = parse_qs(urlparse(response.getheader("Location")).query)
        assert params["error"][0] == "Please fill all fields and upload a file."

        httpd.shutdown()
