#!/usr/bin/env python3
"""Minimal assignment submission platform using Python's stdlib HTTP server."""

from __future__ import annotations

import cgi
import html
import json
import os
import secrets
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("ASSIGNMENT_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_FILE = DATA_DIR / "submissions.json"
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        DB_FILE.write_text("[]", encoding="utf-8")


def load_submissions() -> list[dict]:
    ensure_storage()
    return json.loads(DB_FILE.read_text(encoding="utf-8"))


def save_submission(entry: dict) -> None:
    submissions = load_submissions()
    submissions.append(entry)
    DB_FILE.write_text(json.dumps(submissions, indent=2), encoding="utf-8")


def human_time(iso_timestamp: str) -> str:
    parsed = datetime.fromisoformat(iso_timestamp)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def render_page(submissions: list[dict], message: str = "", error: str = "") -> str:
    rows = []
    for item in reversed(submissions):
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['student_name'])}</td>"
            f"<td>{html.escape(item['title'])}</td>"
            f"<td><a href='/uploads/{html.escape(item['stored_name'])}'>{html.escape(item['original_name'])}</a></td>"
            f"<td>{html.escape(human_time(item['submitted_at']))}</td>"
            "</tr>"
        )

    table_content = "\n".join(rows) if rows else "<tr><td colspan='4'>No submissions yet.</td></tr>"

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Assignment Submission Platform</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; }}
    h1 {{ margin-bottom: 0.5rem; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 1rem; margin-bottom: 1.5rem; }}
    .message {{ color: #0a7d1f; }}
    .error {{ color: #b00020; }}
    label {{ display: block; margin-top: 0.75rem; font-weight: 600; }}
    input, button {{ margin-top: 0.3rem; font-size: 1rem; }}
    input[type='text'] {{ width: min(500px, 100%); padding: 0.4rem; }}
    button {{ padding: 0.5rem 0.8rem; border-radius: 6px; border: 1px solid #888; cursor: pointer; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.6rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>Assignment Submission Platform</h1>
  <p>Upload handwritten assignment scans/photos (PDF, PNG, JPG, JPEG). Max size: 15MB.</p>
  {f"<p class='message'>{html.escape(message)}</p>" if message else ""}
  {f"<p class='error'>{html.escape(error)}</p>" if error else ""}

  <section class='card'>
    <h2>Submit assignment</h2>
    <form action='/submit' method='post' enctype='multipart/form-data'>
      <label for='student_name'>Student name</label>
      <input type='text' id='student_name' name='student_name' required>

      <label for='title'>Assignment title</label>
      <input type='text' id='title' name='title' required>

      <label for='file'>Handwritten assignment file</label>
      <input type='file' id='file' name='file' accept='.pdf,.png,.jpg,.jpeg' required>

      <div style='margin-top: 1rem;'>
        <button type='submit'>Upload assignment</button>
      </div>
    </form>
  </section>

  <section class='card'>
    <h2>Recent submissions</h2>
    <table>
      <thead>
        <tr><th>Student</th><th>Title</th><th>File</th><th>Submitted at</th></tr>
      </thead>
      <tbody>
        {table_content}
      </tbody>
    </table>
  </section>
</body>
</html>
"""


class AssignmentHandler(BaseHTTPRequestHandler):
    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect_home(self, message: str = "", error: str = "") -> None:
        params = {}
        if message:
            params["message"] = message
        if error:
            params["error"] = error
        suffix = f"?{urlencode(params)}" if params else ""
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", f"/{suffix}")
        self.end_headers()

    def do_GET(self) -> None:
        ensure_storage()
        parsed = urlparse(self.path)
        if parsed.path == "/":
            params = parse_qs(parsed.query)
            message = params.get("message", [""])[0]
            error = params.get("error", [""])[0]
            body = render_page(load_submissions(), message=message, error=error)
            self._send_html(body)
            return

        if parsed.path.startswith("/uploads/"):
            filename = Path(parsed.path).name
            target = UPLOAD_DIR / filename
            if not target.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            data = target.read_bytes()
            ext = target.suffix.lower()
            content_type = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
            }.get(ext, "application/octet-stream")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/submit":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self._redirect_home(error="Invalid form submission.")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )

        student_name = (form.getfirst("student_name") or "").strip()
        title = (form.getfirst("title") or "").strip()
        upload_field = form["file"] if "file" in form else None

        if not student_name or not title or upload_field is None or not getattr(upload_field, "filename", ""):
            self._redirect_home(error="Please fill all fields and upload a file.")
            return

        original_name = Path(upload_field.filename).name
        ext = Path(original_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            self._redirect_home(error="Only PDF, PNG, JPG, and JPEG files are allowed.")
            return

        file_data = upload_field.file.read()
        if len(file_data) > MAX_FILE_SIZE:
            self._redirect_home(error="File too large. Maximum size is 15MB.")
            return

        ensure_storage()
        stored_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}{ext}"
        (UPLOAD_DIR / stored_name).write_bytes(file_data)

        entry = {
            "student_name": student_name,
            "title": title,
            "original_name": original_name,
            "stored_name": stored_name,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        save_submission(entry)
        self._redirect_home(message="Assignment uploaded successfully.")


def run() -> None:
    ensure_storage()
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AssignmentHandler)
    print(f"Assignment platform running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
