FROM python:3.12-slim

# Install D2 diagram renderer (supports ARM64/Pi5 via official install script)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates make && \
    curl -fsSL https://d2lang.com/install.sh | sh -s -- && \
    apt-get purge -y curl make && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Skip Playwright auto-install — we only use SVG output from D2
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake all files of backend into backend container
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
