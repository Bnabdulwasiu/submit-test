# Minimal Assignment Submission Platform

A tiny web app for collecting handwritten assignment uploads.

## Features

- Upload handwritten assignments as **PDF / PNG / JPG / JPEG**.
- Captures student name and assignment title.
- Stores file and submission metadata locally.
- Lists recent submissions with downloadable file links.

## Run locally

```bash
python server.py
```

Open http://localhost:8000

### Optional environment variables

- `PORT` (default: `8000`)
- `ASSIGNMENT_DATA_DIR` (default: `./data`)

## Testing

```bash
pytest
```
