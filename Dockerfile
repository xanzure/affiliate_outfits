# Railway worker image.
# Built on the official Playwright Python image so Chromium + all its system
# libraries are present for the HTML/CSS collage renderer. Tag matches the
# playwright version pinned in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Browser binary matching the installed playwright (system deps come from the base image).
RUN playwright install chromium

COPY . .

# worker.py adds the repo root to sys.path itself, so no editable install needed.
CMD ["python", "scripts/worker.py", "--loop"]
