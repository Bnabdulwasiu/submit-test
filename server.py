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


def render_status_alert(message: str = "", error: str = "") -> str:
    if message:
        return (
            "<div class='mb-6 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700'>"
            f"{html.escape(message)}"
            "</div>"
        )
    if error:
        return (
            "<div class='mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700'>"
            f"{html.escape(error)}"
            "</div>"
        )
    return ""


def render_submission_rows(submissions: list[dict]) -> str:
    if not submissions:
        return (
            "<tr>"
            "<td class='px-4 py-6 text-center text-slate-500' colspan='4'>No submissions yet.</td>"
            "</tr>"
        )

    rows = []
    for item in reversed(submissions):
        rows.append(
            "<tr class='border-t border-slate-100 hover:bg-slate-50'>"
            f"<td class='px-4 py-3 text-slate-700'>{html.escape(item['student_name'])}</td>"
            f"<td class='px-4 py-3 text-slate-700'>{html.escape(item['title'])}</td>"
            "<td class='px-4 py-3'>"
            f"<a class='font-medium text-indigo-600 hover:text-indigo-500 hover:underline' href='/uploads/{html.escape(item['stored_name'])}'>"
            f"{html.escape(item['original_name'])}"
            "</a>"
            "</td>"
            f"<td class='px-4 py-3 text-slate-500'>{html.escape(human_time(item['submitted_at']))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_page(submissions: list[dict], message: str = "", error: str = "") -> str:
    alert = render_status_alert(message=message, error=error)
    table_content = render_submission_rows(submissions)

    return f"""<!doctype html>
<html lang='en' class='h-full bg-slate-50'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Assignment Submission Platform</title>
  <script src='https://cdn.tailwindcss.com'></script>
</head>
<body class='min-h-full text-slate-900'>
  <main class='mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8'>
    <section class='mb-8'>
      <h1 class='text-3xl font-bold tracking-tight text-slate-900'>Assignment Submission Platform</h1>
      <p class='mt-2 text-slate-600'>Upload handwritten assignment scans/photos (PDF, PNG, JPG, JPEG). Max size: 15MB.</p>
    </section>

    {alert}

    <div class='grid gap-6 lg:grid-cols-5'>
      <section class='rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2'>
        <h2 class='text-lg font-semibold text-slate-900'>Submit assignment</h2>
        <form class='mt-4 space-y-4' action='/submit' method='post' enctype='multipart/form-data'>
          <div>
            <label class='block text-sm font-medium text-slate-700' for='student_name'>Student name</label>
            <input class='mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20' type='text' id='student_name' name='student_name' required>
          </div>

          <div>
            <label class='block text-sm font-medium text-slate-700' for='title'>Assignment title</label>
            <input class='mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20' type='text' id='title' name='title' required>
          </div>

          <div>
            <label class='block text-sm font-medium text-slate-700' for='file'>Handwritten assignment file</label>
            <input class='mt-1 block w-full cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200' type='file' id='file' name='file' accept='.pdf,.png,.jpg,.jpeg' required>
          </div>

          <button class='inline-flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2' type='submit'>
            Upload assignment
          </button>
        </form>
      </section>

      <section class='rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-3'>
        <h2 class='text-lg font-semibold text-slate-900'>Recent submissions</h2>
        <div class='mt-4 overflow-x-auto'>
          <table class='min-w-full divide-y divide-slate-200 text-sm'>
            <thead class='bg-slate-50'>
              <tr>
                <th class='px-4 py-3 text-left font-semibold text-slate-600'>Student</th>
                <th class='px-4 py-3 text-left font-semibold text-slate-600'>Title</th>
                <th class='px-4 py-3 text-left font-semibold text-slate-600'>File</th>
                <th class='px-4 py-3 text-left font-semibold text-slate-600'>Submitted at</th>
              </tr>
            </thead>
            <tbody class='divide-y divide-slate-100 bg-white'>
              {table_content}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </main>
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
