import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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


app = FastAPI()
templates = Jinja2Templates(directory="templates")

ensure_storage()

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, message: str = "", error: str = ""):
    submissions = load_submissions()
    # Pre-process for display
    display_submissions = []
    for s in reversed(submissions):
        s_copy = s.copy()
        s_copy["submitted_at_human"] = human_time(s["submitted_at"])
        display_submissions.append(s_copy)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "submissions": display_submissions,
            "message": message,
            "error": error,
        },
    )


@app.post("/submit", response_class=RedirectResponse)
async def submit_assignment(
    student_name: Annotated[str, Form()],
    title: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    if not student_name.strip() or not title.strip():
         return RedirectResponse(
            url="/?error=Please fill all fields and upload a file.", status_code=303
        )

    if not file.filename:
         return RedirectResponse(
            url="/?error=Please fill all fields and upload a file.", status_code=303
        )

    original_name = Path(file.filename).name
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return RedirectResponse(
            url="/?error=Only PDF, PNG, JPG, and JPEG files are allowed.", status_code=303
        )

    # Read file content to check size (could be memory intensive for large files, but consistent with original logic)
    # FastAPI UploadFile is a spool file, so we can verify size better if needed.
    # For now, read it all.
    file_data = await file.read()
    
    if len(file_data) > MAX_FILE_SIZE:
        return RedirectResponse(
            url="/?error=File too large. Maximum size is 15MB.", status_code=303
        )

    stored_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}{ext}"
    (UPLOAD_DIR / stored_name).write_bytes(file_data)

    entry = {
        "student_name": student_name.strip(),
        "title": title.strip(),
        "original_name": original_name,
        "stored_name": stored_name,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    save_submission(entry)

    return RedirectResponse(
        url="/?message=Assignment uploaded successfully.", status_code=303
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
